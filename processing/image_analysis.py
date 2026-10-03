from __future__ import annotations

import math
from datetime import datetime, timezone

import cv2
import numpy as np


SEP_AVAILABLE = False
ASTROPY_STATS_AVAILABLE = False
PHOTUTILS_AVAILABLE = False
sep = None
sigma_clipped_stats = None
Background2D = None
MedianBackground = None
detect_sources = None
SourceCatalog = None
_BACKENDS_LOADED = False


def _load_analysis_backends() -> None:
    """Load optional astronomy libraries on first analysis request."""
    global SEP_AVAILABLE, ASTROPY_STATS_AVAILABLE, PHOTUTILS_AVAILABLE
    global sep, sigma_clipped_stats, Background2D, MedianBackground
    global detect_sources, SourceCatalog, _BACKENDS_LOADED

    if _BACKENDS_LOADED:
        return

    try:
        import sep as sep_module

        sep = sep_module
        SEP_AVAILABLE = True
    except ImportError:
        sep = None
        SEP_AVAILABLE = False

    try:
        from astropy.stats import sigma_clipped_stats as stats_function

        sigma_clipped_stats = stats_function
        ASTROPY_STATS_AVAILABLE = True
    except ImportError:
        sigma_clipped_stats = None
        ASTROPY_STATS_AVAILABLE = False

    try:
        from photutils.background import Background2D as background_class
        from photutils.background import MedianBackground as median_background_class
        from photutils.segmentation import SourceCatalog as source_catalog_class
        from photutils.segmentation import detect_sources as detect_sources_function

        Background2D = background_class
        MedianBackground = median_background_class
        SourceCatalog = source_catalog_class
        detect_sources = detect_sources_function
        PHOTUTILS_AVAILABLE = True
    except ImportError:
        Background2D = None
        MedianBackground = None
        SourceCatalog = None
        detect_sources = None
        PHOTUTILS_AVAILABLE = False

    _BACKENDS_LOADED = True


def _safe_median_absolute_deviation(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float32)
    if arr.size == 0:
        return 0.0
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    return mad


def _estimate_background_and_noise(gray_f32: np.ndarray) -> tuple[float, float, str]:
    if ASTROPY_STATS_AVAILABLE and sigma_clipped_stats is not None:
        try:
            _mean, median, std = sigma_clipped_stats(gray_f32, sigma=3.0, maxiters=5)
            noise_sigma = max(1e-6, float(std))
            return float(median), noise_sigma, "astropy_sigma_clip"
        except Exception:
            pass

    median = float(np.median(gray_f32))
    noise_sigma = max(1e-6, 1.4826 * _safe_median_absolute_deviation(gray_f32))
    return median, noise_sigma, "mad"


def _build_empty_stars_payload(method: str) -> dict:
    return {
        "count": 0,
        "fwhm_px_median": None,
        "fwhm_px_mean": None,
        "fwhm_px_min": None,
        "fwhm_px_max": None,
        "snr_median": None,
        "snr_mean": None,
        "sample_size": 0,
        "top_stars": [],
        "method": method,
    }


def _build_stars_payload_from_samples(stars: list, method: str) -> dict:
    if not stars:
        return _build_empty_stars_payload(method)

    fwhm_vals = np.array([item["fwhm_px"] for item in stars], dtype=np.float32)
    snr_vals = np.array([item["snr"] for item in stars], dtype=np.float32)
    return {
        "count": int(len(stars)),
        "fwhm_px_median": float(np.median(fwhm_vals)),
        "fwhm_px_mean": float(np.mean(fwhm_vals)),
        "fwhm_px_min": float(np.min(fwhm_vals)),
        "fwhm_px_max": float(np.max(fwhm_vals)),
        "snr_median": float(np.median(snr_vals)),
        "snr_mean": float(np.mean(snr_vals)),
        "sample_size": int(len(stars)),
        "top_stars": stars[:10],
        "method": method,
    }


def _compute_star_metrics_sep(gray_u8: np.ndarray, max_stars: int = 120) -> dict:
    if not SEP_AVAILABLE or sep is None:
        return _build_empty_stars_payload("sep_unavailable")

    data = gray_u8.astype(np.float32)
    bkg = sep.Background(data)
    data_sub = data - bkg.back()
    threshold = max(4.0 * float(bkg.globalrms), 6.0)

    objects = sep.extract(
        data_sub,
        threshold,
        err=bkg.globalrms,
        minarea=5,
        deblend_cont=0.005,
        clean=True,
    )

    if objects is None or len(objects) == 0:
        return _build_empty_stars_payload("sep")

    fwhm_factor = 2.354820045
    stars = []
    for obj in objects:
        a = float(obj["a"])
        b = float(obj["b"])
        if not np.isfinite(a) or not np.isfinite(b) or a <= 0.0 or b <= 0.0:
            continue

        sigma_eq = math.sqrt(max(1e-6, 0.5 * (a * a + b * b)))
        fwhm = float(fwhm_factor * sigma_eq)
        if not (0.7 <= fwhm <= 20.0):
            continue

        flux = float(obj["flux"])
        peak = float(obj["peak"])
        npix = float(obj["npix"]) if "npix" in obj.dtype.names else max(1.0, math.pi * a * b)
        noise_term = max(1e-6, math.sqrt(max(0.0, flux) + npix * (float(bkg.globalrms) ** 2)))
        snr = float(flux / noise_term)
        if not np.isfinite(snr) or snr <= 0.0:
            continue

        stars.append({
            "fwhm_px": fwhm,
            "snr": snr,
            "peak": peak,
            "x": int(round(float(obj["x"]))),
            "y": int(round(float(obj["y"]))),
            "area": int(round(npix)),
            "ellipticity": float(max(a, b) / max(1e-6, min(a, b))),
        })

    if not stars:
        return _build_empty_stars_payload("sep")

    stars.sort(key=lambda item: item.get("snr", 0.0), reverse=True)
    stars = stars[:max(1, int(max_stars))]
    return _build_stars_payload_from_samples(stars, "sep")


def _compute_star_metrics_photutils(gray_f32: np.ndarray, noise_sigma: float, max_stars: int = 120) -> dict:
    if not PHOTUTILS_AVAILABLE or detect_sources is None or SourceCatalog is None:
        return _build_empty_stars_payload("photutils_unavailable")

    try:
        box_size = (
            max(32, min(96, int(gray_f32.shape[0] // 8))),
            max(32, min(96, int(gray_f32.shape[1] // 8))),
        )
        bkg = Background2D(
            gray_f32,
            box_size=box_size,
            filter_size=(3, 3),
            bkg_estimator=MedianBackground(),
        )
        background = bkg.background
        rms = np.maximum(bkg.background_rms, 1e-6)
        rms_median = float(np.median(rms))
    except Exception:
        background = np.full_like(gray_f32, float(np.median(gray_f32)), dtype=np.float32)
        rms_median = max(1e-6, float(noise_sigma))
        rms = np.full_like(gray_f32, rms_median, dtype=np.float32)

    data_sub = gray_f32 - background
    threshold = max(4.0 * rms_median, 6.0)
    segmentation = detect_sources(data_sub, threshold, n_pixels=5)
    if segmentation is None:
        return _build_empty_stars_payload("photutils")

    catalog = SourceCatalog(data_sub, segmentation, error=rms)
    table = catalog.to_table(
        columns=(
            "x_centroid",
            "y_centroid",
            "area",
            "max_value",
            "segment_flux",
            "fwhm",
            "semimajor_axis",
            "semiminor_axis",
        )
    )
    if table is None or len(table) == 0:
        return _build_empty_stars_payload("photutils")

    stars = []
    fwhm_factor = 2.354820045
    for row in table:
        area = float(row["area"])
        flux = float(row["segment_flux"])
        peak = float(row["max_value"])
        x_val = float(row["x_centroid"])
        y_val = float(row["y_centroid"])
        fwhm = row["fwhm"]
        try:
            fwhm_candidate = float(fwhm)
        except Exception:
            fwhm_candidate = float("nan")

        if not np.isfinite(fwhm_candidate):
            major = float(row["semimajor_axis"])
            minor = float(row["semiminor_axis"])
            sigma_eq = math.sqrt(max(1e-6, 0.5 * (major * major + minor * minor)))
            fwhm_val = float(fwhm_factor * sigma_eq)
        else:
            fwhm_val = fwhm_candidate

        if not np.isfinite(fwhm_val) or not (0.7 <= fwhm_val <= 24.0):
            continue

        noise_term = max(1e-6, math.sqrt(max(0.0, flux) + max(1.0, area) * (rms_median ** 2)))
        snr = float(flux / noise_term)
        if not np.isfinite(snr) or snr <= 0.0:
            continue

        stars.append(
            {
                "fwhm_px": fwhm_val,
                "snr": snr,
                "peak": peak,
                "x": int(round(x_val)),
                "y": int(round(y_val)),
                "area": int(round(area)),
                "ellipticity": None,
            }
        )

    if not stars:
        return _build_empty_stars_payload("photutils")

    stars.sort(key=lambda item: item.get("snr", 0.0), reverse=True)
    stars = stars[:max(1, int(max_stars))]
    return _build_stars_payload_from_samples(stars, "photutils")


def _compute_star_metrics_localmax(gray_f32: np.ndarray, background_median: float, noise_sigma: float, max_stars: int = 120) -> dict:
    blurred = cv2.GaussianBlur(gray_f32, (0, 0), 1.0)
    height, width = blurred.shape[:2]
    star_threshold = background_median + max(8.0, noise_sigma * 4.0)

    dilated = cv2.dilate(blurred, np.ones((3, 3), dtype=np.uint8))
    local_max_mask = np.logical_and(blurred >= star_threshold, blurred >= (dilated - 1e-6))
    binary_candidates = local_max_mask.astype(np.uint8)
    num_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(binary_candidates, connectivity=8)

    stars = []
    patch_radius = 4
    fwhm_factor = 2.354820045

    for idx in range(1, num_labels):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area <= 0:
            continue

        cx, cy = centroids[idx]
        ix = int(round(float(cx)))
        iy = int(round(float(cy)))

        if ix < patch_radius or iy < patch_radius or ix >= (width - patch_radius) or iy >= (height - patch_radius):
            continue

        patch = blurred[iy - patch_radius:iy + patch_radius + 1, ix - patch_radius:ix + patch_radius + 1]
        if patch.shape != (2 * patch_radius + 1, 2 * patch_radius + 1):
            continue

        local_background = float(np.percentile(patch, 20))
        signal = np.clip(patch - local_background, 0.0, None)
        peak = float(signal[patch_radius, patch_radius])
        total_signal = float(signal.sum())
        if peak <= noise_sigma * 2.0 or total_signal <= 0.0:
            continue

        yy, xx = np.indices(signal.shape, dtype=np.float32)
        dx = xx - patch_radius
        dy = yy - patch_radius
        var_x = float((signal * (dx ** 2)).sum() / total_signal)
        var_y = float((signal * (dy ** 2)).sum() / total_signal)
        sigma = max(0.1, math.sqrt(max(0.0, 0.5 * (var_x + var_y))))

        stars.append({
            "fwhm_px": float(fwhm_factor * sigma),
            "snr": float(peak / max(noise_sigma, 1e-6)),
            "peak": peak,
            "x": ix,
            "y": iy,
            "area": area,
            "ellipticity": None,
        })

    if not stars:
        return _build_empty_stars_payload("localmax")

    stars.sort(key=lambda item: item.get("snr", 0.0), reverse=True)
    stars = stars[:max(1, int(max_stars))]
    return _build_stars_payload_from_samples(stars, "localmax")


def compute_image_analysis_metrics(image: np.ndarray, max_stars: int = 120) -> dict:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return {}

    if image.ndim == 3 and image.shape[2] >= 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif image.ndim == 2:
        gray = image
    else:
        return {}

    _load_analysis_backends()

    if gray.dtype != np.uint8:
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    gray_f32 = gray.astype(np.float32)
    height, width = gray_f32.shape[:2]

    background_median, noise_sigma, noise_method = _estimate_background_and_noise(gray_f32)

    stars_payload = _build_empty_stars_payload("none")
    if SEP_AVAILABLE:
        try:
            stars_payload = _compute_star_metrics_sep(gray, max_stars=max_stars)
        except Exception:
            stars_payload = _build_empty_stars_payload("sep_error")

    if int(stars_payload.get("count") or 0) == 0 and PHOTUTILS_AVAILABLE:
        try:
            stars_payload = _compute_star_metrics_photutils(
                gray_f32,
                noise_sigma=noise_sigma,
                max_stars=max_stars,
            )
        except Exception:
            stars_payload = _build_empty_stars_payload("photutils_error")

    if int(stars_payload.get("count") or 0) == 0:
        stars_payload = _compute_star_metrics_localmax(
            gray_f32,
            background_median=background_median,
            noise_sigma=noise_sigma,
            max_stars=max_stars,
        )

    p01 = float(np.percentile(gray_f32, 1.0))
    p99 = float(np.percentile(gray_f32, 99.0))
    clipped_black = float(np.mean(gray_f32 <= 1.0) * 100.0)
    clipped_white = float(np.mean(gray_f32 >= 254.0) * 100.0)

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "image_shape": {
            "width": int(width),
            "height": int(height),
        },
        "analysis_backend": {
            "stars_method": stars_payload.get("method"),
            "noise_method": noise_method,
            "sep_available": bool(SEP_AVAILABLE),
            "photutils_available": bool(PHOTUTILS_AVAILABLE),
            "astropy_stats_available": bool(ASTROPY_STATS_AVAILABLE),
        },
        "luminance": {
            "mean": float(np.mean(gray_f32)),
            "median": background_median,
            "std": float(np.std(gray_f32)),
            "background_sigma": float(noise_sigma),
            "p01": p01,
            "p99": p99,
            "dynamic_range_p99_p01": float(max(0.0, p99 - p01)),
            "black_clipping_pct": clipped_black,
            "white_clipping_pct": clipped_white,
        },
        "stars": stars_payload,
    }
