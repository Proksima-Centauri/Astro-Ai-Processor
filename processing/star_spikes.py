"""Natural-looking diffraction spikes for bright stars in astro images."""

from __future__ import annotations

import cv2
import numpy as np
from collections import defaultdict


def _to_unit(image: np.ndarray) -> tuple[np.ndarray, float]:
    source = np.asarray(image)
    if np.issubdtype(source.dtype, np.integer):
        scale = float(np.iinfo(source.dtype).max)
    else:
        finite = source[np.isfinite(source)]
        scale = max(1.0, float(finite.max())) if finite.size else 1.0
    return np.clip(source.astype(np.float32) / scale, 0.0, 1.0), scale


def _luminance(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)


def detect_bright_stars(
    image: np.ndarray,
    *,
    brightness_percent: float = 10.0,
    max_stars: int = 500,
    aperture_radius: int = 5,
    linear_input: bool = True,
) -> list[dict[str, float]]:
    """Return the brightest point sources ranked by background-subtracted flux.

    Flat saturated cores are grouped into one regional maximum. Flux is measured
    in a small aperture after subtracting a local smooth background, so a clipped
    peak still ranks highly without generating one candidate per plateau pixel.
    """
    source = np.asarray(image)
    if source.ndim not in (2, 3) or source.size == 0:
        raise ValueError("Expected a non-empty grayscale or color image")
    if source.ndim == 3 and source.shape[2] not in (3, 4):
        raise ValueError("Expected an image with 3 or 4 channels")
    unit, _ = _to_unit(source)
    if not linear_input:
        unit = np.where(unit <= 0.04045, unit / 12.92, ((unit + 0.055) / 1.055) ** 2.4).astype(np.float32)
    gray = _luminance(unit)
    h, w = gray.shape
    if h < 3 or w < 3:
        return []

    sigma = float(np.clip(min(h, w) / 1200.0, 2.0, 6.0))
    background = cv2.GaussianBlur(gray, (0, 0), sigma)
    residual = np.maximum(gray - background, 0.0)
    positive = residual[residual > 0]
    if positive.size == 0:
        return []
    med = float(np.median(positive))
    noise = float(np.median(np.abs(positive - med))) * 1.4826
    threshold = max(
        med + noise * 5.0,
        float(np.percentile(positive, 99.7)),
        float(positive.max()) * 0.008,
        1e-7,
    )
    dilated = cv2.dilate(residual, np.ones((5, 5), np.uint8))
    tolerance = max(float(residual.max()) * 1e-7, 1e-8)
    peak_mask = (residual >= dilated - tolerance) & (residual >= threshold)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        peak_mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return []

    radius = max(2, int(aperture_radius))
    yy, xx = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    aperture = xx * xx + yy * yy <= radius * radius
    candidates: list[dict[str, float]] = []
    for label in range(1, count):
        x, y = centroids[label]
        if stats[label, cv2.CC_STAT_AREA] <= 0:
            continue
        cx, cy = int(round(x)), int(round(y))
        x0, x1 = max(0, cx - radius), min(w, cx + radius + 1)
        y0, y1 = max(0, cy - radius), min(h, cy + radius + 1)
        ax0, ay0 = radius - (cx - x0), radius - (cy - y0)
        patch = residual[y0:y1, x0:x1]
        local_aperture = aperture[ay0:ay0 + patch.shape[0], ax0:ax0 + patch.shape[1]]
        flux = float(patch[local_aperture].sum(dtype=np.float64))
        bx, by, bw, bh = stats[label, :4]
        peak_region = residual[by:by + bh, bx:bx + bw]
        peak_labels = labels[by:by + bh, bx:bx + bw]
        peak = float(peak_region[peak_labels == label].max())
        if flux > 0:
            candidates.append({"x": float(x), "y": float(y), "flux": flux, "peak": peak})
    if not candidates:
        return []

    candidates.sort(key=lambda item: item["flux"], reverse=True)
    # Merge duplicate maxima at the same unresolved source while retaining close
    # but distinct stars. Processing is limited to the flux-ranked list.
    unique: list[dict[str, float]] = []
    min_distance_sq = 5.5 * 5.5
    cell_size = 4
    cells: dict[tuple[int, int], list[dict[str, float]]] = defaultdict(list)
    for candidate in candidates:
        cell = (int(candidate["x"] // cell_size), int(candidate["y"] // cell_size))
        nearby = (
            item
            for cy in range(cell[1] - 1, cell[1] + 2)
            for cx in range(cell[0] - 1, cell[0] + 2)
            for item in cells.get((cx, cy), ())
        )
        duplicate = next(
            (item for item in nearby if
             (candidate["x"] - item["x"]) ** 2 + (candidate["y"] - item["y"]) ** 2 < min_distance_sq),
            None,
        )
        if duplicate is None:
            unique.append(candidate)
            cells[cell].append(candidate)
        else:
            total = max(duplicate["peak"], 1e-12) + max(candidate["peak"], 1e-12)
            duplicate["x"] = (duplicate["x"] * duplicate["peak"] + candidate["x"] * candidate["peak"]) / total
            duplicate["y"] = (duplicate["y"] * duplicate["peak"] + candidate["y"] * candidate["peak"]) / total
            duplicate["flux"] = max(duplicate["flux"], candidate["flux"])
            duplicate["peak"] = max(duplicate["peak"], candidate["peak"])
            cells[cell].append(duplicate)
    selected_count = max(1, int(np.ceil(len(unique) * np.clip(brightness_percent, 0.1, 100.0) / 100.0)))
    return unique[:min(selected_count, max(1, int(max_stars)))]


def scale_spike_length(
    flux: float,
    flux_reference: float,
    base_length: float,
    scaling: float = 0.5,
    max_length: float | None = None,
) -> float:
    """Scale a base ray length by integrated stellar flux using a power law."""
    reference = max(float(flux_reference), 1e-12)
    ratio = max(float(flux), 1e-12) / reference
    length = max(0.0, float(base_length)) * float(np.clip(ratio ** float(scaling), 0.35, 3.0))
    return min(length, float(max_length)) if max_length is not None else length


def spike_profile(
    distance: np.ndarray | float,
    length: float,
    amplitude: float = 1.0,
    *,
    falloff: float = 2.0,
    core_radius: float = 4.0,
) -> np.ndarray:
    """Monotonically fading radial ray profile with a soft zero-valued tip."""
    distance = np.maximum(np.asarray(distance, dtype=np.float32), 0.0)
    length = max(float(length), 1e-6)
    radius = max(float(core_radius), 1e-3)
    power = max(float(falloff), 0.0)
    radial = float(amplitude) * np.power(1.0 + distance / radius, -power)
    fade = np.clip(1.0 - distance / length, 0.0, 1.0)
    return (radial * fade * fade).astype(np.float32)


def add_star_spikes(
    image: np.ndarray,
    *,
    brightness_percent: float = 10.0,
    base_length: float = 90.0,
    length_scaling: float = 0.5,
    intensity: float = 0.7,
    width: float = 2.5,
    angle_degrees: float = 0.0,
    rays: int = 4,
    halo: bool = True,
    max_stars: int = 500,
    linear_input: bool = True,
) -> tuple[np.ndarray, int]:
    """Add tapered, colored, antialiased spikes locally around selected stars.

    ``linear_input=False`` converts sRGB-like display values to linear light for
    blending. The return value includes the number of affected stars.
    """
    source = np.asarray(image)
    if source.ndim not in (2, 3) or source.size == 0:
        raise ValueError("Expected a non-empty grayscale or color image")
    if source.ndim == 3 and source.shape[2] not in (3, 4):
        raise ValueError("Expected an image with 3 or 4 channels")
    unit, value_scale = _to_unit(source)
    if not linear_input:
        unit = np.where(unit <= 0.04045, unit / 12.92, ((unit + 0.055) / 1.055) ** 2.4).astype(np.float32)
    stars = detect_bright_stars(
        source, brightness_percent=brightness_percent, max_stars=max_stars,
        linear_input=linear_input,
    )
    if not stars or float(intensity) <= 0:
        return source.copy(), 0

    h, w = unit.shape[:2]
    min_dimension = min(h, w)
    ref_flux = float(stars[len(stars) // 2]["flux"])
    base_length = float(np.clip(base_length, 4.0, max(4.0, min_dimension * 0.2)))
    strength = float(np.clip(intensity, 0.0, 2.0))
    width = float(np.clip(width, 0.4, 20.0))
    ray_count = int(np.clip(rays, 2, 8))
    if ray_count not in (2, 4, 6):
        ray_count = min((2, 4, 6), key=lambda value: abs(value - ray_count))
    angles = np.deg2rad(float(angle_degrees)) + np.arange(ray_count) * (2.0 * np.pi / ray_count)
    overlay = np.zeros((h, w, 3), dtype=np.float32) if unit.ndim == 3 else np.zeros((h, w), dtype=np.float32)
    count_added = 0

    for star in stars:
        x, y = star["x"], star["y"]
        length = scale_spike_length(
            star["flux"], ref_flux, base_length, length_scaling,
            max_length=min(min_dimension * 0.22, base_length * 3.0),
        )
        if length < 2:
            continue
        peak = float(star["peak"])
        amplitude = min(1.0, peak * strength * 1.8)
        if unit.ndim == 3:
            core_radius = max(1, int(round(width)))
            cx, cy = int(round(x)), int(round(y))
            color_patch = unit[max(0, cy-core_radius):min(h, cy+core_radius+1),
                               max(0, cx-core_radius):min(w, cx+core_radius+1), :3]
            star_color = np.mean(color_patch, axis=(0, 1)) if color_patch.size else np.ones(3, np.float32) * peak
            star_color = 0.8 * star_color + 0.2 * float(np.max(star_color))
        for angle in angles:
            dx_unit, dy_unit = float(np.cos(angle)), float(np.sin(angle))
            extent_x = int(np.ceil(abs(dx_unit) * length + width * 4.0 + 2.0))
            extent_y = int(np.ceil(abs(dy_unit) * length + width * 4.0 + 2.0))
            x0, x1 = max(0, int(np.floor(x)) - extent_x), min(w, int(np.ceil(x)) + extent_x + 1)
            y0, y1 = max(0, int(np.floor(y)) - extent_y), min(h, int(np.ceil(y)) + extent_y + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            py, px = np.mgrid[y0:y1, x0:x1]
            dx = px.astype(np.float32) - x
            dy = py.astype(np.float32) - y
            along = dx * dx_unit + dy * dy_unit
            across = -dx * dy_unit + dy * dx_unit
            valid = (along >= 0) & (along < length)
            profile = spike_profile(along, length, amplitude, core_radius=max(3.0, width * 2.0))
            taper = np.maximum(0.12, 1.0 - along / max(length, 1e-6)) ** 0.8
            local_width = np.maximum(0.35, width * taper)
            transverse = np.exp(-0.5 * (across / local_width) ** 2)
            local = np.where(valid, profile * transverse, 0.0)
            if unit.ndim == 3:
                overlay[y0:y1, x0:x1] += local[:, :, None] * star_color[None, None, :]
            else:
                overlay[y0:y1, x0:x1] += local

        if halo:
            halo_sigma = max(1.5, width * 2.5)
            halo_extent = int(np.ceil(halo_sigma * 4.0))
            x0, x1 = max(0, int(np.floor(x)) - halo_extent), min(w, int(np.ceil(x)) + halo_extent + 1)
            y0, y1 = max(0, int(np.floor(y)) - halo_extent), min(h, int(np.ceil(y)) + halo_extent + 1)
            py, px = np.mgrid[y0:y1, x0:x1]
            radius_sq = (px.astype(np.float32) - x) ** 2 + (py.astype(np.float32) - y) ** 2
            halo_gain = amplitude * 0.16 * np.exp(-0.5 * radius_sq / (halo_sigma * halo_sigma))
            if unit.ndim == 3:
                overlay[y0:y1, x0:x1] += halo_gain[:, :, None] * star_color[None, None, :]
            else:
                overlay[y0:y1, x0:x1] += halo_gain
        count_added += 1

    if count_added == 0:
        return source.copy(), 0
    overlay = np.clip(overlay, 0.0, 1.0)
    if unit.ndim == 3:
        blended = 1.0 - (1.0 - unit[:, :, :3]) * (1.0 - overlay)
        result_unit = unit.copy()
        result_unit[:, :, :3] = blended
    else:
        result_unit = 1.0 - (1.0 - unit) * (1.0 - overlay)
    if not linear_input:
        result_unit = np.where(result_unit <= 0.0031308, result_unit * 12.92,
                               1.055 * np.power(result_unit, 1.0 / 2.4) - 0.055)
    result = np.clip(result_unit, 0.0, 1.0) * value_scale
    if np.issubdtype(source.dtype, np.integer):
        result = np.rint(result).astype(source.dtype)
    else:
        result = result.astype(source.dtype, copy=False)
    changed = np.any(overlay > 0, axis=2) if overlay.ndim == 3 else overlay > 0
    result = source.copy()
    if source.ndim == 2:
        gray_values = np.clip(result_unit[changed] * value_scale, 0.0, value_scale)
        if np.issubdtype(source.dtype, np.integer):
            gray_values = np.rint(gray_values)
        result[changed] = gray_values.astype(source.dtype)
    else:
        blended_values = np.clip(result_unit[changed] * value_scale, 0.0, value_scale)
        if np.issubdtype(source.dtype, np.integer):
            blended_values = np.rint(blended_values).astype(source.dtype)
        else:
            blended_values = blended_values.astype(source.dtype, copy=False)
        result[changed, :3] = blended_values[:, :3]
    return result, count_added
