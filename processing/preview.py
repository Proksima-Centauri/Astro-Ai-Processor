"""Bounded, document-local intermediate cache for interactive image previews."""
from __future__ import annotations

import cv2
import numpy as np

from processing.color_processor import ColorProcessor
from processing.tonal_adjustments import _to_uint8_lut_source, apply_curves_lut, apply_levels


def parameter_key(value):
    if isinstance(value, dict):
        return tuple(sorted((key, parameter_key(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(parameter_key(item) for item in value)
    return value


class PreviewCache:
    """One cached value per stage; retain sources to avoid recycled identity keys.

    Parameter edits invalidate downstream stages through their keys. Document
    edits must clear the cache, including edits performed in place.
    """

    def __init__(self):
        self._stages = {}
        self.sources = ()
        self.generation = 0

    def clear(self):
        self._stages.clear()
        self.sources = ()
        self.generation += 1

    def stage(self, name, key, build):
        cached = self._stages.get(name)
        if cached is None or cached[0] != key:
            result = build()
            self._stages[name] = (key, result)
            return result
        return cached[1]

    def process(self, image, source_key, basic, hsl, ghs, levels, curves):
        color_key = (source_key, parameter_key(basic), parameter_key(hsl))
        color = self.stage("color", color_key, lambda: ColorProcessor.apply_camera_raw_and_hsl(image, basic, hsl))
        ghs_key = (color_key, parameter_key(ghs))
        stretched = self.stage("ghs", ghs_key, lambda: self.apply_ghs(color, ghs))
        levels_key = (ghs_key, parameter_key(levels))
        leveled = self.stage("levels", levels_key, lambda: self.apply_levels(stretched, levels))
        curve_key = (levels_key, parameter_key(curves))
        curve_source = self.stage("curve_source", levels_key, lambda: _to_uint8_lut_source(leveled)) if curves and curves["points"] else leveled
        result = self.stage("curves", curve_key, lambda: apply_curves_lut(
            curve_source, curves["points"], curves["channels"], curves["curve_mode"]) if curves else leveled)
        return result, curve_key

    def apply_levels(self, image, params):
        if params["black"] == 0 and params["gamma"] == 1.0 and params["white"] == 255:
            return image
        lut = self.stage("levels_lut", parameter_key(params), lambda: apply_levels(
            np.linspace(0, 1, 65536, dtype=np.float32).reshape(1, -1),
            params["black"], params["gamma"], params["white"]))
        out = image.copy()
        for name in params["channels"] if params["channels"] is not None else ("b", "g", "r"):
            index = {"b": 0, "g": 1, "r": 2}.get(name.lower())
            if index is not None:
                values = np.nan_to_num(out[:, :, index], nan=0, posinf=1, neginf=0)
                indices = np.clip(np.rint(values * 65535), 0, 65535).astype(np.int32)
                out[:, :, index] = lut[0, indices]
        return out

    def apply_ghs(self, image, params):
        if not params or float(params.get("stretch_factor", 0.0)) <= 1e-6:
            return image
        key = parameter_key(params)
        lut = self.stage("ghs_lut", key, lambda: ColorProcessor._ghs_curve_values(
            np.linspace(0.0, 1.0, 65536, dtype=np.float32),
            params.get("stretch_factor", 0.0), params.get("symmetry_point", .5),
            params.get("highlight_protection_point", .95), params.get("shadow_protection_point", .05)))
        if params.get("colour_stretch_model") == "luminance_only":
            image = np.nan_to_num(image, nan=0, posinf=1, neginf=0)
            gray = image[:, :, 0] * .114 + image[:, :, 1] * .587 + image[:, :, 2] * .299
            mapped = lut[np.clip(np.rint(gray * 65535), 0, 65535).astype(np.int32)]
            return np.clip(image * (mapped / np.maximum(gray, 1e-5))[:, :, None], 0, 1)
        values = np.nan_to_num(image, nan=0, posinf=1, neginf=0)
        return lut[np.clip(np.rint(values * 65535), 0, 65535).astype(np.int32)]

    @staticmethod
    def resize(image, max_side=1200):
        height, width = image.shape[:2]
        scale = min(1.0, max_side / float(max(height, width)))
        if scale == 1.0:
            return image.copy()
        return cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
