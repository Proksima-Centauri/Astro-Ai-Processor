from __future__ import annotations

import cv2
import numpy as np


def _to_uint8_lut_source(img: np.ndarray) -> np.ndarray:
    arr = np.asarray(img)
    if arr.dtype == np.uint8:
        return arr

    if np.issubdtype(arr.dtype, np.floating):
        work = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=1.0, neginf=0.0)
        max_value = float(np.max(work)) if work.size else 0.0
        if max_value <= 1.0 + 1e-6:
            work = work * 255.0
        return np.clip(work, 0.0, 255.0).astype(np.uint8)

    if np.issubdtype(arr.dtype, np.integer):
        info = np.iinfo(arr.dtype)
        if info.max <= 255:
            return np.clip(arr, 0, 255).astype(np.uint8)
        scale = 255.0 / float(info.max)
        return np.clip(arr.astype(np.float32) * scale, 0.0, 255.0).astype(np.uint8)

    return np.clip(arr, 0, 255).astype(np.uint8)


def apply_levels(img: np.ndarray, black: int, gamma: float, white: int, channels=None) -> np.ndarray:
    if img is None:
        return None

    if channels is not None and len(channels) == 0:
        return img.copy()

    is_integer = np.issubdtype(img.dtype, np.integer)
    value_range = float(np.iinfo(img.dtype).max) if is_integer else 1.0

    def apply_to_channel(channel_img):
        img_f = np.nan_to_num(channel_img.astype(np.float32) / value_range, nan=0.0, posinf=1.0, neginf=0.0)

        img_f = (img_f - black / 255.0) / max(1e-6, (white - black) / 255.0)
        img_f = np.clip(img_f, 0, 1)
        img_f = img_f ** (1.0 / max(0.01, gamma))

        if is_integer:
            return np.clip(np.rint(img_f * value_range), 0, value_range).astype(img.dtype)
        return img_f.astype(img.dtype, copy=False)

    if channels is None or img.ndim == 2:
        return apply_to_channel(img)

    out = img.copy()
    channel_map = {"b": 0, "g": 1, "r": 2}
    for channel_name in channels:
        idx = channel_map.get(channel_name.lower())
        if idx is not None and idx < out.shape[2]:
            out[:, :, idx] = apply_to_channel(out[:, :, idx])

    return out


def build_curve_lut(points, curve_mode="linear") -> np.ndarray:
    control_points = [(0, 0)] + list(points or []) + [(255, 255)]
    sorted_points = sorted((int(x), int(y)) for x, y in control_points)
    compact_points = []
    for x, y in sorted_points:
        x = int(np.clip(x, 0, 255))
        y = int(np.clip(y, 0, 255))
        if compact_points and compact_points[-1][0] == x:
            compact_points[-1] = (x, y)
        else:
            compact_points.append((x, y))

    if len(compact_points) < 2:
        return np.arange(256, dtype=np.uint8)

    sorted_points = compact_points
    xs = np.array([p[0] for p in sorted_points], dtype=np.float32)
    ys = np.array([p[1] for p in sorted_points], dtype=np.float32)

    if curve_mode == "cubic" and len(xs) >= 3:
        lut = natural_cubic_spline(xs, ys, np.arange(256, dtype=np.float32))
    else:
        lut = np.interp(np.arange(256, dtype=np.float32), xs, ys)

    return np.clip(lut, 0, 255).astype(np.uint8)


def natural_cubic_spline(xs: np.ndarray, ys: np.ndarray, query_xs: np.ndarray) -> np.ndarray:
    n = len(xs)
    h = np.diff(xs)
    if np.any(h <= 0):
        return np.interp(query_xs, xs, ys)

    alpha = np.zeros(n, dtype=np.float32)
    for i in range(1, n - 1):
        alpha[i] = (3.0 / h[i]) * (ys[i + 1] - ys[i]) - (3.0 / h[i - 1]) * (ys[i] - ys[i - 1])

    l = np.ones(n, dtype=np.float32)
    mu = np.zeros(n, dtype=np.float32)
    z = np.zeros(n, dtype=np.float32)

    for i in range(1, n - 1):
        l[i] = 2.0 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1]
        if abs(l[i]) < 1e-6:
            return np.interp(query_xs, xs, ys)
        mu[i] = h[i] / l[i]
        z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]

    b = np.zeros(n - 1, dtype=np.float32)
    c = np.zeros(n, dtype=np.float32)
    d = np.zeros(n - 1, dtype=np.float32)

    for j in range(n - 2, -1, -1):
        c[j] = z[j] - mu[j] * c[j + 1]
        b[j] = ((ys[j + 1] - ys[j]) / h[j]) - (h[j] * (c[j + 1] + 2.0 * c[j]) / 3.0)
        d[j] = (c[j + 1] - c[j]) / (3.0 * h[j])

    indices = np.searchsorted(xs, query_xs, side="right") - 1
    indices = np.clip(indices, 0, n - 2)
    dx = query_xs - xs[indices]
    return ys[indices] + b[indices] * dx + c[indices] * dx ** 2 + d[indices] * dx ** 3


def apply_curves_lut(img: np.ndarray, points, channels=None, curve_mode="linear") -> np.ndarray:
    if img is None:
        return None

    if not points or (channels is not None and len(channels) == 0):
        return img.copy()

    source = _to_uint8_lut_source(img)
    lut = build_curve_lut(points, curve_mode)
    if source.ndim == 2:
        return cv2.LUT(source, lut)

    out = source.copy()
    channel_map = {"b": 0, "g": 1, "r": 2}
    selected_channels = channels if channels is not None else ("b", "g", "r")
    for channel_name in selected_channels:
        idx = channel_map.get(channel_name.lower())
        if idx is not None and idx < out.shape[2]:
            out[:, :, idx] = cv2.LUT(out[:, :, idx], lut)

    return out
