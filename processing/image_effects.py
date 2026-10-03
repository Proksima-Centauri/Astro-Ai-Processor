from __future__ import annotations

import numpy as np
import cv2


def neutralize_background(image: np.ndarray, roi: tuple) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must have shape (H, W, 3)")
    if image.dtype != np.float32:
        raise ValueError("image must be float32")
    if not isinstance(roi, tuple) or len(roi) != 4:
        raise TypeError("roi must be a tuple: (y1, y2, x1, x2)")

    try:
        y1, y2, x1, x2 = (int(v) for v in roi)
    except Exception as exc:
        raise ValueError("roi values must be integers") from exc

    h, w, _ = image.shape
    if not (0 <= y1 < y2 <= h and 0 <= x1 < x2 <= w):
        raise ValueError(f"roi {roi} is out of image bounds (H={h}, W={w})")

    roi_data = image[y1:y2, x1:x2, :]
    if roi_data.size == 0 or roi_data.shape[0] == 0 or roi_data.shape[1] == 0:
        raise ValueError("roi is empty")

    if not np.isfinite(roi_data).all():
        raise ValueError("roi contains non-finite values (NaN/Inf)")
    if np.any(roi_data < 0.0):
        raise ValueError("roi contains negative values")

    channel_means = roi_data.mean(axis=(0, 1), dtype=np.float64).astype(np.float32)
    if channel_means.size != 3:
        raise ValueError("failed to compute channel means for ROI")

    eps = np.float32(1e-6)
    target = np.float32(channel_means.mean(dtype=np.float64))
    gains = target / (channel_means + eps)
    balanced = image * gains.reshape(1, 1, 3)
    return np.clip(balanced, 0.0, 1.0).astype(np.float32, copy=False)


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    width = max(1e-6, float(edge1) - float(edge0))
    t = np.clip((x - float(edge0)) / width, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _normalize_mask01(mask: np.ndarray | None, shape_hw: tuple[int, int], dtype: np.dtype) -> np.ndarray | None:
    if mask is None:
        return None
    arr = np.asarray(mask)
    if arr.size == 0:
        return None
    if arr.ndim == 3:
        arr = arr[:, :, 0]

    arr_f = arr.astype(np.float32, copy=False)
    if np.issubdtype(arr.dtype, np.integer):
        info = np.iinfo(arr.dtype)
        max_val = float(max(1, info.max))
        arr_f = arr_f / max_val

    arr_f = np.clip(arr_f, 0.0, 1.0)
    h, w = shape_hw
    if arr_f.shape[:2] != (h, w):
        arr_f = cv2.resize(arr_f, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(arr_f, 0.0, 1.0).astype(dtype, copy=False)


def local_contrast_enhancement(
    image: np.ndarray,
    radius_px: float = 35.0,
    strength: float = 0.4,
    protect_background: bool = True,
    protect_stars: bool = True,
    star_mask: np.ndarray | None = None,
    low_threshold: float = 0.03,
    high_threshold: float = 0.15,
) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.ndim not in (2, 3):
        raise ValueError("image must be mono (H,W) or RGB/BGR (H,W,C)")
    if image.dtype not in (np.float32, np.float64):
        raise ValueError("image must be float32 or float64")

    src = np.clip(image, 0.0, 1.0).astype(image.dtype, copy=False)
    sigma = float(np.clip(radius_px, 0.1, 300.0))
    gain = float(np.clip(strength, 0.0, 2.0))

    blur = cv2.GaussianBlur(src, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REPLICATE)
    detail = src - blur
    enhanced = src + detail * gain

    if bool(protect_background):
        if src.ndim == 3 and src.shape[2] >= 3:
            luminance = (
                src[:, :, 0] * 0.114
                + src[:, :, 1] * 0.587
                + src[:, :, 2] * 0.299
            )
        elif src.ndim == 3:
            luminance = np.mean(src, axis=2)
        else:
            luminance = src
        signal_mask = _smoothstep(float(low_threshold), float(high_threshold), luminance).astype(src.dtype, copy=False)
        if src.ndim == 3:
            signal_mask = signal_mask[:, :, np.newaxis]
        enhanced = src + signal_mask * (enhanced - src)

    if bool(protect_stars):
        stars = _normalize_mask01(star_mask, src.shape[:2], src.dtype)
        if stars is not None:
            inv_stars = 1.0 - stars
            if src.ndim == 3:
                inv_stars = inv_stars[:, :, np.newaxis]
            enhanced = src + inv_stars * (enhanced - src)

    return np.clip(enhanced, 0.0, 1.0).astype(image.dtype, copy=False)
