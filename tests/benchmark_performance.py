"""Run with PYTHONPATH=.:tests .venv/bin/python tests/benchmark_performance.py.

Standalone benchmarks are kept out of normal pytest runs. No extra plugin.
"""
import json
import time

import numpy as np

from performance_reference import levels_reference
from processing.color_processor import ColorProcessor
from processing.preview import PreviewCache
from processing.tonal_adjustments import apply_levels


def measure(function, repeats=5):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = function()
        samples.append((time.perf_counter() - start) * 1000)
        del result
    return dict(median_ms=float(np.median(samples)), p95_ms=float(np.percentile(samples, 95)), samples_ms=samples)


if __name__ == "__main__":
    image = np.random.default_rng(7).random((4000, 6000, 3), dtype=np.float32)
    output = {}
    for name, params in (("neutral", (0, 1.0, 255)), ("active", (8, 1.7, 240))):
        old = lambda: levels_reference(image, *params, ["r", "g", "b"])
        new = lambda: apply_levels(image, *params, ["r", "g", "b"])
        output["levels_" + name] = {"reference": measure(old, 3), "optimized": measure(new, 3)}
    small = PreviewCache.resize(image)
    levels = dict(black=8, gamma=1.7, white=240, channels=["r", "g", "b"])
    curves = dict(points=[(90, 120)], channels=["r", "g", "b"], curve_mode="linear")
    cache = PreviewCache()
    cache.process(small, 1, {}, {}, {}, levels, curves)
    def drag_curve():
        curves["points"] = [(90, 120 if curves["points"][0][1] != 120 else 125)]
        return cache.process(small, 1, {}, {}, {}, levels, curves)
    def drag_levels():
        levels["gamma"] = 1.5 if levels["gamma"] != 1.5 else 1.7
        return cache.process(small, 1, {}, {}, {}, levels, curves)
    ghs = {}
    def drag_ghs():
        ghs["stretch_factor"] = 2 if ghs.get("stretch_factor") != 2 else 2.1
        return cache.process(small, 1, {}, {}, ghs, levels, curves)
    output["curve_drag_compute"] = measure(drag_curve, 20)
    output["levels_drag_compute"] = measure(drag_levels, 20)
    output["ghs_drag_compute"] = measure(drag_ghs, 20)
    print(json.dumps(output, indent=2))
