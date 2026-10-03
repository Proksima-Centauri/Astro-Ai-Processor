from __future__ import annotations

import numpy as np


_AUTOSTRETCH_SHADOW_CLIPPING = -2.80
_AUTOSTRETCH_TARGET_BACKGROUND = 0.25
_AUTOSTRETCH_MAD_FALLBACK = 0.001
_HISTOGRAM_BINS_FLOAT = 65536
_MAX_FLOAT_STATS_SAMPLES = 1_000_000
_MAX_TRANSFORM_PIXELS = 1_000_000


def _mtf(values: np.ndarray, midtone: float, shadows: float = 0.0, highlights: float = 1.0) -> np.ndarray:
    """Siril's MTF implementation (histogram.c: MTF)."""
    x = np.asarray(values, dtype=np.float32)
    lo = float(shadows)
    hi = float(highlights)
    m = float(np.clip(midtone, 1e-6, 1.0 - 1e-6))
    if not np.isfinite(hi - lo) or hi <= lo:
        return np.zeros_like(x)

    xp = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    denominator = ((2.0 * m - 1.0) * xp) - m
    epsilon = np.finfo(np.float32).eps
    denominator = np.where(np.abs(denominator) < epsilon, -epsilon, denominator)
    mapped = ((m - 1.0) * xp) / denominator
    mapped = np.where(x <= lo, 0.0, mapped)
    mapped = np.where(x >= hi, 1.0, mapped)
    return np.clip(np.nan_to_num(mapped, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    total = int(np.sum(weights, dtype=np.int64))
    if total <= 0:
        return 0.0
    cumulative = np.cumsum(weights, dtype=np.int64)
    lower_index = (total - 1) // 2
    upper_index = total // 2
    lower = int(np.searchsorted(cumulative, lower_index + 1, side="left"))
    upper = int(np.searchsorted(cumulative, upper_index + 1, side="left"))
    return float((values[lower] + values[upper]) * 0.5)


def _channel_sample(channel: np.ndarray) -> tuple[np.ndarray, float]:
    """Return representative normalized values and the channel's data scale."""
    if np.issubdtype(channel.dtype, np.integer):
        value_range = float(np.iinfo(channel.dtype).max)
    else:
        value_range = 1.0

    height, width = channel.shape[:2]
    pixel_count = height * width
    stride = max(1, int(np.ceil(pixel_count / float(_MAX_FLOAT_STATS_SAMPLES))))
    flat_indices = np.arange(0, pixel_count, stride, dtype=np.int64)
    sample = channel[flat_indices // width, flat_indices % width].astype(np.float32)
    sample /= value_range
    np.nan_to_num(sample, copy=False, nan=0.0, posinf=1.0, neginf=0.0)
    np.clip(sample, 0.0, 1.0, out=sample)
    return sample, value_range


def _integer_histogram(channel: np.ndarray, bin_count: int) -> np.ndarray:
    histogram = np.zeros(bin_count, dtype=np.int64)
    height, width = channel.shape[:2]
    rows_per_chunk = max(1, _MAX_TRANSFORM_PIXELS // max(1, width))
    for y0 in range(0, height, rows_per_chunk):
        y1 = min(height, y0 + rows_per_chunk)
        values = channel[y0:y1].reshape(-1)
        histogram += np.bincount(values, minlength=bin_count)
    return histogram


def _channel_statistics(channel: np.ndarray) -> dict:
    """Compute median and Siril-normalized MAD for one image channel."""
    if channel.size == 0:
        return {"median": 0.0, "noise": _AUTOSTRETCH_MAD_FALLBACK, "sample": np.empty(0, np.float32)}

    if np.issubdtype(channel.dtype, np.unsignedinteger):
        value_range = float(np.iinfo(channel.dtype).max)
        hist = _integer_histogram(channel, int(value_range) + 1)
        levels = np.arange(hist.size, dtype=np.float64) / value_range
        median = _weighted_median(levels, hist)
        deviations = np.abs(levels - median)
        order = np.argsort(deviations, kind="stable")
        mad = _weighted_median(deviations[order], hist[order])
        # Quantized image values still provide the exact Siril-style median/MAD
        # without allocating a full-size float copy of a large channel.
        sample, _ = _channel_sample(channel)
    else:
        sample, _ = _channel_sample(channel)
        median = float(np.median(sample))
        mad = float(np.median(np.abs(sample - median)))

    noise = float(mad * 1.4826)
    if not np.isfinite(noise) or noise == 0.0:
        noise = _AUTOSTRETCH_MAD_FALLBACK
    return {"median": float(median), "noise": noise, "sample": sample}


def _get_image_channels(image: np.ndarray) -> tuple[list[np.ndarray], int | None]:
    if image.ndim == 2:
        return [image], None
    if image.shape[2] == 1:
        return [image[:, :, 0]], 0
    # Alpha is carried through unchanged, just as Siril renders image planes.
    return [image[:, :, channel] for channel in range(3)], 3 if image.shape[2] == 4 else None


def _float_histogram(channel: np.ndarray) -> np.ndarray:
    histogram = np.zeros(_HISTOGRAM_BINS_FLOAT, dtype=np.int64)
    height, width = channel.shape[:2]
    rows_per_chunk = max(1, _MAX_TRANSFORM_PIXELS // max(1, width))
    for y0 in range(0, height, rows_per_chunk):
        y1 = min(height, y0 + rows_per_chunk)
        values = np.nan_to_num(
            channel[y0:y1].astype(np.float32).reshape(-1),
            nan=0.0,
            posinf=1.0,
            neginf=0.0,
        )
        siril_histogram_range = 1.0 + 1.0 / float(_HISTOGRAM_BINS_FLOAT - 1)
        indices = np.clip(
            np.floor(np.clip(values, 0.0, 1.0) / siril_histogram_range * _HISTOGRAM_BINS_FLOAT).astype(np.int64),
            0,
            _HISTOGRAM_BINS_FLOAT - 1,
        )
        histogram += np.bincount(indices, minlength=_HISTOGRAM_BINS_FLOAT)
    return histogram


def _siril_autostretch_parameters(stats: list[dict]) -> dict:
    """Port of findMidtonesBalance() from Siril's gui/histogram.c."""
    medians = np.asarray([item["median"] for item in stats], dtype=np.float64)
    noises = np.asarray([item["noise"] for item in stats], dtype=np.float64)
    channel_count = len(stats)
    inverted_channels = int(np.count_nonzero(medians > 0.5))
    mean_median = float(np.mean(medians))

    if inverted_channels < channel_count:
        shadows = max(0.0, float(np.mean(medians + _AUTOSTRETCH_SHADOW_CLIPPING * noises)))
        distance = float(np.clip(mean_median - shadows, 0.0, 1.0))
        midtone = float(_mtf(np.asarray([distance], dtype=np.float32), _AUTOSTRETCH_TARGET_BACKGROUND)[0])
        highlights = 1.0
        inverted = False
    else:
        shadows = 0.0
        highlights = min(1.0, float(np.mean(medians - _AUTOSTRETCH_SHADOW_CLIPPING * noises)))
        distance = float(np.clip(highlights - mean_median, 0.0, 1.0))
        midtone = 1.0 - float(_mtf(np.asarray([distance], dtype=np.float32), _AUTOSTRETCH_TARGET_BACKGROUND)[0])
        inverted = True

    midtone = float(np.clip(midtone, 1e-6, 1.0 - 1e-6))
    return {
        "shadows": shadows,
        "midtone": midtone,
        "highlights": highlights,
        "background": mean_median,
        "noise": float(np.mean(noises)),
        "inverted": inverted,
    }


def _build_histogram_lut(channels: list[np.ndarray], dtype: np.dtype, linked: bool) -> tuple[list[np.ndarray], dict]:
    if np.issubdtype(dtype, np.unsignedinteger):
        value_range = int(np.iinfo(dtype).max)
        bin_count = value_range + 1
        histograms = [_integer_histogram(channel, bin_count) for channel in channels]
    else:
        value_range = _HISTOGRAM_BINS_FLOAT - 1
        histograms = [_float_histogram(channel) for channel in channels]
        bin_count = _HISTOGRAM_BINS_FLOAT

    if linked and len(histograms) > 1:
        pooled = np.sum(np.stack(histograms, axis=0), axis=0, dtype=np.int64)
        histograms = [pooled.copy() for _ in histograms]

    luts = []
    clip_low = []
    clip_high = []
    for hist in histograms:
        count = int(np.sum(hist, dtype=np.int64))
        if count == 0:
            luts.append(np.linspace(0.0, 1.0, bin_count, dtype=np.float32))
            clip_low.append(0.0)
            clip_high.append(0.0)
            continue

        cdf = np.cumsum(hist, dtype=np.float64) / float(count)
        # Siril sets bin zero to black, then maps each following bin to its
        # inclusive cumulative histogram count.
        cdf[0] = 0.0
        luts.append(np.clip(cdf, 0.0, 1.0).astype(np.float32))
        clip_low.append(float(hist[0] / count))
        clip_high.append(float(hist[-1] / count))

    return luts, {
        "background": None,
        "noise": None,
        "black_point": 0.0,
        "white_point": 1.0,
        "normalized_background": None,
        "midtone": None,
        "target": None,
        "clipping_low": float(np.mean(clip_low)) if clip_low else 0.0,
        "clipping_high": float(np.mean(clip_high)) if clip_high else 0.0,
        "model": "siril_histogram_cdf",
        "linked_channels": bool(linked),
        "degenerate": False,
    }


def _apply_histogram(image: np.ndarray, channels: list[np.ndarray], linked: bool) -> tuple[np.ndarray, dict]:
    luts, diagnostics = _build_histogram_lut(channels, image.dtype, linked)
    result = image.copy()
    height, width = image.shape[:2]
    rows_per_chunk = max(1, _MAX_TRANSFORM_PIXELS // max(1, width))
    if np.issubdtype(image.dtype, np.unsignedinteger):
        value_range = int(np.iinfo(image.dtype).max)
        for channel_index, channel in enumerate(channels):
            lut = np.rint(luts[channel_index] * value_range).astype(image.dtype)
            for y0 in range(0, height, rows_per_chunk):
                y1 = min(height, y0 + rows_per_chunk)
                if image.ndim == 2:
                    result[y0:y1] = lut[channel[y0:y1]]
                else:
                    result[y0:y1, :, channel_index] = lut[channel[y0:y1]]
    else:
        if np.issubdtype(image.dtype, np.integer):
            value_range = float(np.iinfo(image.dtype).max)
        else:
            value_range = 1.0
        bins = _HISTOGRAM_BINS_FLOAT - 1
        for channel_index, channel in enumerate(channels):
            lut = luts[channel_index]
            for y0 in range(0, height, rows_per_chunk):
                y1 = min(height, y0 + rows_per_chunk)
                tile = np.nan_to_num(channel[y0:y1].astype(np.float32), nan=0.0, posinf=1.0, neginf=0.0)
                normalized = np.clip(tile / value_range, 0.0, 1.0)
                indices = np.clip(np.rint(normalized * bins).astype(np.int64), 0, bins)
                mapped = lut[indices]
                if np.issubdtype(image.dtype, np.integer):
                    mapped = np.rint(mapped * value_range).astype(image.dtype)
                if image.ndim == 2:
                    result[y0:y1] = mapped.astype(image.dtype, copy=False)
                else:
                    result[y0:y1, :, channel_index] = mapped.astype(image.dtype, copy=False)
    return result, diagnostics


def stretch_image(
    image: np.ndarray,
    mode: str = "autostretch",
    *,
    linked_channels: bool = True,
    return_diagnostics: bool = False,
) -> np.ndarray | tuple[np.ndarray, dict]:
    """Render Linear, Siril AutoStretch (STF), or Siril Histogram view mode.

    The transform is non-destructive. AutoStretch ports Siril's -2.8 sigma,
    0.25 background and MTF calculations. Histogram ports Siril's per-channel
    cumulative histogram remapping. Channel linking selects common parameters
    / histogram versus independent transforms for each color channel.
    """
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.ndim not in (2, 3):
        raise ValueError("image must be mono or have color channels")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise ValueError("image must have 1, 3, or 4 channels")
    if not (np.issubdtype(image.dtype, np.integer) or np.issubdtype(image.dtype, np.floating)):
        raise TypeError("image must contain real numeric pixel values")

    selected_mode = str(mode or "autostretch").strip().lower()
    if selected_mode not in {"linear", "autostretch", "histogram"}:
        raise ValueError("mode must be linear, autostretch, or histogram")
    linked = bool(linked_channels)
    channels, _ = _get_image_channels(image)

    if selected_mode == "linear":
        output = image.copy()
        diagnostics = {
            "background": None,
            "noise": None,
            "black_point": 0.0,
            "white_point": 1.0,
            "normalized_background": None,
            "midtone": 0.5,
            "target": None,
            "clipping_low": 0.0,
            "clipping_high": 0.0,
            "model": "linear",
            "linked_channels": linked,
            "degenerate": False,
        }
        return (output, diagnostics) if return_diagnostics else output

    if selected_mode == "histogram":
        output, diagnostics = _apply_histogram(image, channels, linked)
        return (output, diagnostics) if return_diagnostics else output

    stats = [_channel_statistics(channel) for channel in channels]
    if linked:
        common = _siril_autostretch_parameters(stats)
        channel_params = [common] * len(channels)
        diagnostic_params = common
    else:
        channel_params = [_siril_autostretch_parameters([channel_stats]) for channel_stats in stats]
        diagnostic_params = {
            "shadows": float(np.mean([item["shadows"] for item in channel_params])),
            "midtone": float(np.mean([item["midtone"] for item in channel_params])),
            "highlights": float(np.mean([item["highlights"] for item in channel_params])),
            "background": float(np.mean([item["background"] for item in channel_params])),
            "noise": float(np.mean([item["noise"] for item in channel_params])),
            "inverted": all(item["inverted"] for item in channel_params),
        }

    diagnostics = {
        "background": diagnostic_params["background"],
        "noise": diagnostic_params["noise"],
        "black_point": diagnostic_params["shadows"],
        "white_point": diagnostic_params["highlights"],
        "normalized_background": None,
        "midtone": diagnostic_params["midtone"],
        "target": _AUTOSTRETCH_TARGET_BACKGROUND,
        "clipping_low": float(np.mean([np.mean(item["sample"] <= channel_params[i]["shadows"]) for i, item in enumerate(stats)])),
        "clipping_high": float(np.mean([np.mean(item["sample"] >= channel_params[i]["highlights"]) for i, item in enumerate(stats)])),
        "model": "siril_autostretch_mtf",
        "linked_channels": linked,
        "inverted": diagnostic_params["inverted"],
        "channels": channel_params,
        "degenerate": False,
    }
    spans = [params["highlights"] - params["shadows"] for params in channel_params]
    if spans:
        diagnostics["normalized_background"] = float(np.mean([
            np.clip((item["median"] - channel_params[i]["shadows"]) / max(spans[i], 1e-7), 0.0, 1.0)
            for i, item in enumerate(stats)
        ]))

    result = image.copy()
    height, width = image.shape[:2]
    rows_per_chunk = max(1, _MAX_TRANSFORM_PIXELS // max(1, width))
    if np.issubdtype(image.dtype, np.integer):
        value_range = float(np.iinfo(image.dtype).max)
        dtype_info = np.iinfo(image.dtype)
    else:
        value_range = 1.0
        dtype_info = None

    for channel_index, channel in enumerate(channels):
        params = channel_params[channel_index]
        for y0 in range(0, height, rows_per_chunk):
            y1 = min(height, y0 + rows_per_chunk)
            tile = channel[y0:y1].astype(np.float32)
            tile /= value_range
            np.nan_to_num(tile, copy=False, nan=0.0, posinf=1.0, neginf=0.0)
            np.clip(tile, 0.0, 1.0, out=tile)
            mapped = _mtf(tile, params["midtone"], params["shadows"], params["highlights"])
            if np.issubdtype(image.dtype, np.integer):
                mapped = np.clip(np.rint(mapped * value_range), dtype_info.min, dtype_info.max).astype(image.dtype)
            else:
                mapped = mapped.astype(image.dtype, copy=False)
            if image.ndim == 2:
                result[y0:y1] = mapped
            else:
                result[y0:y1, :, channel_index] = mapped

    # An RGBA input's alpha plane was intentionally not included in channel
    # calculations and remains exactly as it was in the copied output.
    return (result, diagnostics) if return_diagnostics else result
