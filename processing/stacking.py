"""Memory-bounded frame integration helpers inspired by Siril's stacker."""

from __future__ import annotations

import numpy as np


STACK_NORMALIZATION_MODES = {
    "none",
    "additive",
    "multiplicative",
    "additive_scaling",
    "multiplicative_scaling",
}


def _channel_stats(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return robust per-channel location and noise estimates."""
    channels = frame[..., None] if frame.ndim == 2 else frame
    locations = []
    scales = []
    for channel in range(channels.shape[2]):
        values = channels[..., channel].reshape(-1)
        values = values[np.isfinite(values) & (values != 0)]
        if values.size == 0:
            locations.append(0.0)
            scales.append(1.0)
            continue
        location = float(np.median(values))
        mad = float(np.median(np.abs(values - location)))
        scale = 1.4826 * mad
        if not np.isfinite(scale) or scale <= 1e-8:
            scale = float(np.std(values))
        locations.append(location)
        scales.append(scale if np.isfinite(scale) and scale > 1e-8 else 1.0)
    return np.asarray(locations, np.float32), np.asarray(scales, np.float32)


def normalize_stack_frames(frames, mode: str = "none") -> list[np.ndarray]:
    """Normalize each frame against the first, per channel.

    Additive/multiplicative modes follow Siril's reference-frame convention;
    ``*_scaling`` modes also match robust frame noise scales.
    """
    normalized_mode = str(mode or "none").strip().lower()
    if normalized_mode not in STACK_NORMALIZATION_MODES:
        raise ValueError(f"Unsupported stacking normalization: {mode}")
    if not frames:
        return []
    arrays = [np.asarray(frame, dtype=np.float32) for frame in frames]
    reference_shape = arrays[0].shape
    if any(frame.shape != reference_shape for frame in arrays):
        raise ValueError("All stacking frames must have matching shapes.")
    if arrays[0].ndim not in (2, 3) or (arrays[0].ndim == 3 and arrays[0].shape[2] not in (1, 3, 4)):
        raise ValueError(f"Unsupported stacking frame shape: {reference_shape}")
    arrays = [np.nan_to_num(frame, nan=0.0, posinf=0.0, neginf=0.0) for frame in arrays]
    if normalized_mode == "none":
        return arrays

    stats = [_channel_stats(frame) for frame in arrays]
    reference_location, reference_scale = stats[0]
    normalized = [arrays[0].copy()]
    for frame, (location, scale) in zip(arrays[1:], stats[1:]):
        factor = np.ones_like(reference_scale)
        if normalized_mode.endswith("_scaling"):
            factor = reference_scale / np.maximum(scale, 1e-8)

        if normalized_mode.startswith("additive"):
            offset = location * factor - reference_location
            corrected = frame * factor - offset
        else:
            multiplier = np.ones_like(reference_location)
            safe_location = np.abs(location) > 1e-8
            multiplier[safe_location] = reference_location[safe_location] / location[safe_location]
            corrected = frame * factor * multiplier
        normalized.append(np.asarray(corrected, dtype=np.float32))
    return normalized


def _sigma_clipped_mean(cube: np.ndarray, sigma_low: float, sigma_high: float) -> np.ndarray:
    """Iterative asymmetric MAD rejection followed by a mean of survivors."""
    valid = np.isfinite(cube)
    remaining = valid.sum(axis=0)
    if cube.shape[0] <= 4:
        return np.divide(
            np.where(valid, cube, 0.0).sum(axis=0),
            remaining,
            out=np.zeros(cube.shape[1:], dtype=np.float32),
            where=remaining > 0,
        )

    for _ in range(cube.shape[0]):
        sample = np.where(valid, cube, np.nan)
        with np.errstate(invalid="ignore"):
            center = np.nanmedian(sample, axis=0)
            deviations = np.abs(sample - center)
            mad = np.nanmedian(deviations, axis=0)
        # Siril uses the unscaled median absolute deviation in its MAD mode.
        low_limit = center - float(sigma_low) * mad
        high_limit = center + float(sigma_high) * mad
        reject = valid & (remaining[None, ...] > 4) & ((cube < low_limit) | (cube > high_limit))
        if not np.any(reject):
            break
        valid &= ~reject
        remaining = valid.sum(axis=0)

    return np.divide(
        np.where(valid, cube, 0.0).sum(axis=0),
        remaining,
        out=np.zeros(cube.shape[1:], dtype=np.float32),
        where=remaining > 0,
    )


def integrate_stack_frames(
    frames,
    method: str = "median",
    *,
    sigma_low: float = 4.0,
    sigma_high: float = 3.0,
    target_chunk_bytes: int = 16 * 1024 * 1024,
) -> np.ndarray:
    """Integrate image frames in row chunks to cap temporary stack memory."""
    arrays = [np.asarray(frame, dtype=np.float32) for frame in frames]
    if not arrays:
        raise ValueError("At least one frame is required for stacking.")
    shape = arrays[0].shape
    if len(shape) not in (2, 3) or any(frame.shape != shape for frame in arrays):
        raise ValueError("Stacking frames must have the same 2D/3D shape.")
    normalized_method = str(method or "median").strip().lower()
    if normalized_method not in {"median", "average", "mad_clip"}:
        raise ValueError(f"Unsupported stacking method: {method}")
    if not np.isfinite(sigma_low) or not np.isfinite(sigma_high) or sigma_low < 0 or sigma_high < 0:
        raise ValueError("Sigma thresholds must be finite, non-negative values.")

    height, width = shape[:2]
    channels = shape[2] if len(shape) == 3 else 1
    bytes_per_row = max(1, len(arrays) * width * channels * np.dtype(np.float32).itemsize)
    rows_per_chunk = max(1, min(height, int(target_chunk_bytes) // bytes_per_row))
    result = np.empty(shape, dtype=np.float32)
    for row_start in range(0, height, rows_per_chunk):
        row_end = min(height, row_start + rows_per_chunk)
        cube = np.stack([frame[row_start:row_end] for frame in arrays], axis=0)
        if normalized_method == "median":
            combined = np.median(cube, axis=0)
        elif normalized_method == "mad_clip":
            combined = _sigma_clipped_mean(cube, sigma_low, sigma_high)
        else:
            combined = np.mean(cube, axis=0, dtype=np.float32)
        result[row_start:row_end] = combined
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
