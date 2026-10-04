"""Photometry-conscious, non-generative image enlargement for astro data."""

from __future__ import annotations

import math
import os
import re
import sys
from typing import Iterable

import cv2
import numpy as np


class AstroUpscaleError(ValueError):
    """Raised when an upscale request is invalid or exceeds safety limits."""


class AstroUpscaler:
    """Resample existing image data without stretching or generating detail."""

    METHODS = {
        "lanczos": cv2.INTER_LANCZOS4,
        "bicubic": cv2.INTER_CUBIC,
    }
    SCALES = (2, 4)
    MAX_OUTPUT_DIMENSION = 32_768
    MAX_OUTPUT_PIXELS = 160_000_000

    @classmethod
    def output_shape(cls, image: np.ndarray, scale: float) -> tuple[int, int]:
        arr = np.asarray(image)
        if arr.ndim not in (2, 3) or arr.size == 0:
            raise AstroUpscaleError("Astro Upscale expects a non-empty 2D or 3D image array.")
        try:
            factor = float(scale)
        except (TypeError, ValueError) as exc:
            raise AstroUpscaleError("Scale must be 2× or 4×.") from exc
        if factor not in cls.SCALES:
            raise AstroUpscaleError("Only 2× and 4× Astro Upscale are supported.")

        height, width = arr.shape[:2]
        out_width = int(round(width * factor))
        out_height = int(round(height * factor))
        if out_width > cls.MAX_OUTPUT_DIMENSION or out_height > cls.MAX_OUTPUT_DIMENSION:
            raise AstroUpscaleError(
                f"Upscaled dimensions {out_width} × {out_height} exceed the safe limit "
                f"of {cls.MAX_OUTPUT_DIMENSION} pixels per side."
            )
        if out_width * out_height > cls.MAX_OUTPUT_PIXELS:
            raise AstroUpscaleError(
                f"Output size {out_width} × {out_height} ({out_width * out_height:,} pixels) "
                f"exceeds the safe limit of {cls.MAX_OUTPUT_PIXELS:,} pixels."
            )
        return out_width, out_height

    @classmethod
    def upscale(
        cls,
        image: np.ndarray,
        scale: float,
        method: str = "lanczos",
        *,
        sharpen: bool = False,
        anti_ringing: bool = True,
    ) -> np.ndarray:
        """Enlarge an image while keeping its dtype, channels, and linear values.

        Interpolated output is constrained to a smoothly resized 3×3 source
        neighborhood range. This suppresses overshoot around bright point
        sources without adding sharpening or changing the global data range.
        """
        arr = np.asarray(image)
        out_width, out_height = cls.output_shape(arr, scale)
        if arr.ndim == 3 and not 1 <= arr.shape[2] <= 4:
            raise AstroUpscaleError("Images must have between one and four channels.")
        if arr.dtype not in (np.dtype(np.uint8), np.dtype(np.uint16), np.dtype(np.float32), np.dtype(np.float64)):
            raise AstroUpscaleError(
                f"Unsupported image type {arr.dtype}; use uint8, uint16, float32, or float64 data."
            )

        method_key = str(method or "lanczos").strip().lower()
        if method_key not in cls.METHODS:
            raise AstroUpscaleError(f"Unsupported interpolation method: {method}.")
        interpolation = cls.METHODS[method_key]

        single_channel = arr.ndim == 3 and arr.shape[2] == 1
        source = arr[:, :, 0] if single_channel else arr
        result = cv2.resize(source, (out_width, out_height), interpolation=interpolation)
        if anti_ringing:
            kernel = np.ones((3, 3), dtype=np.uint8)
            local_min = cv2.erode(source, kernel, borderType=cv2.BORDER_REPLICATE)
            local_max = cv2.dilate(source, kernel, borderType=cv2.BORDER_REPLICATE)
            lower = cv2.resize(local_min, (out_width, out_height), interpolation=cv2.INTER_LINEAR)
            upper = cv2.resize(local_max, (out_width, out_height), interpolation=cv2.INTER_LINEAR)
            np.maximum(result, lower, out=result)
            np.minimum(result, upper, out=result)

        if sharpen:
            # Very mild unsharp mask, opt-in only. Keep the result within the
            # source data range so this cannot create new extreme highlights.
            work = result.astype(np.float64 if result.dtype == np.float64 else np.float32)
            blurred = cv2.GaussianBlur(work, (0, 0), 0.55)
            np.subtract(work, blurred, out=blurred)
            blurred *= 0.08
            np.add(work, blurred, out=work)
            source_min = float(np.nanmin(arr))
            source_max = float(np.nanmax(arr))
            np.clip(work, source_min, source_max, out=work)
            if np.issubdtype(arr.dtype, np.integer):
                info = np.iinfo(arr.dtype)
                np.clip(np.rint(work), info.min, info.max, out=work)
            result = work.astype(arr.dtype, copy=False)

        return result[:, :, np.newaxis] if single_channel else result

    @classmethod
    def upscale_mask(cls, mask: np.ndarray, scale: float) -> np.ndarray:
        """Resize layer masks without Lanczos ringing or changing their range."""
        arr = np.asarray(mask)
        out_width, out_height = cls.output_shape(arr, scale)
        single_channel = arr.ndim == 3 and arr.shape[2] == 1
        source = arr[:, :, 0] if single_channel else arr
        if arr.dtype == np.bool_:
            result = cv2.resize(
                source.astype(np.float32),
                (out_width, out_height),
                interpolation=cv2.INTER_LINEAR,
            )
            result = result >= 0.5
            return result[:, :, np.newaxis] if single_channel else result
        result = cv2.resize(source, (out_width, out_height), interpolation=cv2.INTER_LINEAR)
        lower = float(np.nanmin(source))
        upper = float(np.nanmax(source))
        np.clip(result, lower, upper, out=result)
        return result[:, :, np.newaxis] if single_channel else result

    @classmethod
    def estimate_working_set_bytes(
        cls,
        images: Iterable[np.ndarray],
        scale: float,
        *,
        sharpen: bool = False,
    ) -> int:
        """Estimate source, result, interpolation-bound, and display buffers."""
        source_bytes = 0
        output_bytes = 0
        seen = set()
        for image in images:
            if not isinstance(image, np.ndarray) or id(image) in seen:
                continue
            seen.add(id(image))
            out_width, out_height = cls.output_shape(image, scale)
            source_bytes += int(image.nbytes)
            output_bytes += int(out_width * out_height * (image.dtype.itemsize * (1 if image.ndim == 2 else image.shape[2])))
        # Includes accumulated output arrays and temporary Lanczos bounds.
        return int(source_bytes * 3 + output_bytes * (5 if sharpen else 4))


def available_memory_bytes() -> int | None:
    """Return a best-effort estimate of currently available physical memory."""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys)
        except Exception:
            return None

    try:
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        if available_pages > 0 and page_size > 0:
            return available_pages * page_size
    except (AttributeError, OSError, ValueError):
        pass
    return None


def rescale_fits_header(header, scale: float, width: int, height: int):
    """Copy FITS metadata and update linear WCS for pixel-center resampling.

    CRPIX follows the half-pixel-center mapping used by cv2.resize. CD/CDELT
    and SIP coefficients are scaled analytically; unrelated header cards remain
    untouched. Non-standard WCS conventions are retained without guessing.
    """
    if header is None:
        return None
    try:
        result = header.copy()
    except Exception:
        result = dict(header)

    factor = float(scale)
    for raw_key in list(result.keys()):
        key = str(raw_key).strip().upper()
        match = re.match(r"^CRPIX([12])([A-Z]?)$", key)
        if match:
            try:
                result[raw_key] = (float(result[raw_key]) - 0.5) * factor + 0.5
            except (TypeError, ValueError):
                pass
            continue

        match = re.match(r"^CDELT([12])([A-Z]?)$", key)
        if match:
            try:
                result[raw_key] = float(result[raw_key]) / factor
            except (TypeError, ValueError):
                pass
            continue

        match = re.match(r"^CD(\d+)_(\d+)([A-Z]?)$", key)
        if match and int(match.group(2)) in (1, 2):
            try:
                result[raw_key] = float(result[raw_key]) / factor
            except (TypeError, ValueError):
                pass
            continue

        match = re.match(r"^(A|B|AP|BP)_(\d+)_(\d+)$", key)
        if match:
            degree = int(match.group(2)) + int(match.group(3))
            try:
                result[raw_key] = float(result[raw_key]) * math.pow(factor, 1 - degree)
            except (TypeError, ValueError, OverflowError):
                pass

    for key, value in (("NAXIS1", int(width)), ("NAXIS2", int(height))):
        if key in result:
            try:
                result[key] = value
            except Exception:
                pass
    return result
