import numpy as np

from processing.color_processor import ColorProcessor
from processing.preview import PreviewCache
from processing.tonal_adjustments import apply_curves_lut, apply_levels


def test_curve_edit_reuses_upstream_results_and_matches_exact_pipeline():
    image = np.random.default_rng(8).random((80, 100, 3), dtype=np.float32)
    cache = PreviewCache()
    basic = {"exposure": .2}
    levels = dict(black=8, midtones=.3, white=240, channels=["r", "g", "b"])
    curves = dict(points=[(90, 120)], channels=["r", "g", "b"], curve_mode="linear")
    first, _ = cache.process(image, 1, basic, {}, {}, levels, curves)
    upstream = {name: cache._stages[name][1] for name in ("color", "ghs", "levels")}
    curves["points"] = [(90, 160)]
    second, _ = cache.process(image, 1, basic, {}, {}, levels, curves)
    assert not np.array_equal(first, second)
    assert all(cache._stages[name][1] is value for name, value in upstream.items())
    reference = ColorProcessor.apply_camera_raw_and_hsl(image, basic, {}, {})
    reference = apply_levels(reference, 8, .3, 240, levels["channels"])
    reference = apply_curves_lut(reference, curves["points"], curves["channels"])
    # A one-code input difference can span two codes on a steep display curve.
    np.testing.assert_allclose(second.astype(float), reference.astype(float), atol=2, rtol=0)


def test_document_invalidation_rebuilds_sources_and_downstream():
    cache = PreviewCache()
    image = np.full((5, 6, 3), .2, dtype=np.float32)
    levels = dict(black=0, midtones=.5, white=255, channels=None)
    before, _ = cache.process(image, cache.generation, {}, {}, {}, levels, None)
    image.fill(.7)
    cache.clear()
    after, _ = cache.process(image, cache.generation, {}, {}, {}, levels, None)
    np.testing.assert_array_equal(before, np.full_like(image, .2))
    np.testing.assert_array_equal(after, image)


def test_preview_ghs_lut_error_is_bounded_and_does_not_mutate_source():
    image = np.random.default_rng(9).random((60, 80, 3), dtype=np.float32)
    original = image.copy()
    cache = PreviewCache()
    for model in ("independent_channel_values", "luminance_only"):
        params = dict(stretch_factor=2, symmetry_point=.4,
                      highlight_protection_point=.95, shadow_protection_point=.05,
                      colour_stretch_model=model)
        actual = cache.apply_ghs(image, params)
        expected = ColorProcessor._apply_ghs(image, params)
        np.testing.assert_allclose(actual, expected, atol=.0002, rtol=0)
    np.testing.assert_array_equal(image, original)


def test_preview_luts_handle_nonfinite_pixels_without_invalid_indices():
    image = np.array([[[np.nan, np.inf, -np.inf], [.5, .7, .9]]], dtype=np.float32)
    cache = PreviewCache()
    for model in ("luminance_only", "independent_channel_values"):
        params = dict(stretch_factor=2, colour_stretch_model=model)
        result = cache.apply_ghs(image, params)
        assert np.isfinite(result).all()
    levels = dict(black=8, midtones=.3, white=240, channels=["r", "g", "b"])
    assert np.isfinite(cache.apply_levels(image, levels)).all()
