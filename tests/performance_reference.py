"""Frozen pre-optimization tonal algorithms for output equivalence checks."""
import numpy as np
import cv2


def levels_reference(img, black, gamma, white, channels=None):
    if img is None:
        return None
    if channels is not None and len(channels) == 0:
        return img.copy()
    is_integer = np.issubdtype(img.dtype, np.integer)
    value_range = float(np.iinfo(img.dtype).max) if is_integer else 1.0

    def transform(channel):
        work = np.nan_to_num(channel.astype(np.float32) / value_range,
                             nan=0.0, posinf=1.0, neginf=0.0)
        work = (work - black / 255.0) / max(1e-6, (white - black) / 255.0)
        work = np.clip(work, 0, 1)
        work = work ** (1.0 / max(0.01, gamma))
        if is_integer:
            return np.clip(np.rint(work * value_range), 0, value_range).astype(img.dtype)
        return work.astype(img.dtype, copy=False)

    if channels is None or img.ndim == 2:
        return transform(img)
    out = img.copy()
    for name in channels:
        index = {"b": 0, "g": 1, "r": 2}.get(name.lower())
        if index is not None and index < out.shape[2]:
            out[:, :, index] = transform(out[:, :, index])
    return out


def ghs_reference(x, stretch_factor, symmetry_point, highlight_point, shadow_point):
    x = np.clip(np.asarray(x, dtype=np.float32), 0.0, 1.0)
    s = float(np.clip(stretch_factor, 0.0, 20.0))
    sp = float(np.clip(symmetry_point, 0.0, 1.0))
    hp = float(np.clip(highlight_point, 0.0, 1.0))
    sh = float(np.clip(shadow_point, 0.0, 1.0))
    if sh > hp:
        sh, hp = hp, sh
    if s <= 1e-6:
        base = x
    else:
        base = 1.0 / (1.0 + np.exp(-(1.0 + 8.0 * s) * (x - sp)))
        base = np.clip((base - 0.5) / 0.5, 0.0, 1.0)
    if sh > 0.0:
        t = np.clip(x / max(1e-6, sh), 0.0, 1.0)
        weight = t * t * (3.0 - 2.0 * t)
        base = x * (1.0 - weight) + base * weight
    if hp < 1.0:
        t = np.clip((x - hp) / max(1e-6, 1.0 - hp), 0.0, 1.0)
        weight = t * t * (3.0 - 2.0 * t)
        base = base * (1.0 - weight) + x * weight
    return np.clip(base, 0.0, 1.0).astype(np.float32)


def curves_reference(image, points, channels, mode="linear"):
    from processing.tonal_adjustments import build_curve_lut
    if not points or (channels is not None and not channels):
        return image.copy()
    if image.dtype == np.uint8:
        source = image
    elif np.issubdtype(image.dtype, np.floating):
        source = np.nan_to_num(image.astype(np.float32), nan=0, posinf=1, neginf=0)
        if source.max() <= 1.0 + 1e-6:
            source = source * 255.0
        source = np.clip(source, 0, 255).astype(np.uint8)
    else:
        source = np.clip(image.astype(np.float32) * (255.0 / np.iinfo(image.dtype).max), 0, 255).astype(np.uint8)
    lut = build_curve_lut(points, mode)
    if image.ndim == 2:
        return cv2.LUT(source, lut)
    out = source.copy()
    for name in channels if channels is not None else ("b", "g", "r"):
        index = {"b": 0, "g": 1, "r": 2}.get(name.lower())
        if index is not None and index < out.shape[2]:
            out[:, :, index] = cv2.LUT(out[:, :, index], lut)
    return out
