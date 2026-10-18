"""Shared exact full-resolution processing for synchronous and worker jobs."""
from __future__ import annotations

import numpy as np

from processing.color_processor import ColorProcessor
from processing.stretch import stretch_image
from processing.tonal_adjustments import apply_curves_lut, apply_levels


def process_image(image, basic_params, hsl_params, ghs_params, levels, curves=None, curves_visible=True):
    result = ColorProcessor.apply_camera_raw_and_hsl(image, basic_params, hsl_params, ghs_params)
    result = apply_levels(result, levels["black"], levels["gamma"], levels["white"], levels["channels"])
    if curves and curves_visible:
        result = apply_curves_lut(result, curves["points"], curves["channels"], curves["curve_mode"])
    if levels.get("autostretch", False):
        result = stretch_image(result, "autostretch")
    if image.dtype == np.uint8:
        result = np.clip(np.rint(result * 255.0), 0, 255).astype(np.uint8)
    return result
