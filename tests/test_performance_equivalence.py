import numpy as np
import pytest

from performance_reference import curves_reference, ghs_reference, levels_reference
from processing.color_processor import ColorProcessor
from processing.tonal_adjustments import apply_curves_lut, apply_levels
from processing.pipeline import process_image
from processing.stretch import stretch_image


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.float32, np.float64])
@pytest.mark.parametrize("channels", [None, [], ["b"], ["r", "g", "b"], ["b", "b"], ["invalid"]])
@pytest.mark.parametrize("params", [(0, 1.0, 255), (8, 1.7, 240), (200, 0.1, 201)])
def test_levels_matches_frozen_reference(dtype, channels, params):
    image = np.random.default_rng(7).random((19, 23, 3)).astype(dtype)
    if np.issubdtype(dtype, np.integer):
        image = (np.random.default_rng(8).random(image.shape) * np.iinfo(dtype).max).astype(dtype)
    else:
        image[0, :3] = [[np.nan, np.inf, -np.inf], [-0.0, -1, 2], [0.5, 1, 0]]
    source = image.copy()
    actual = apply_levels(image, *params, channels)
    expected = levels_reference(image, *params, channels)
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(image, source)
    assert not np.shares_memory(actual, image)


@pytest.mark.parametrize("params", [(0, .5, .95, .05), (2, .5, .95, .05), (20, .2, .1, .9)])
def test_exact_ghs_matches_frozen_reference(params):
    image = np.linspace(-.1, 1.1, 10001, dtype=np.float32)
    np.testing.assert_array_equal(ColorProcessor._ghs_curve_values(image, *params),
                                  ghs_reference(image, *params))


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.float32, np.float64])
@pytest.mark.parametrize("channels", [None, [], ["b"], ["r", "g", "b"], ["b", "b"]])
def test_curves_matches_frozen_reference(dtype, channels):
    image = np.random.default_rng(10).random((19, 23, 3))
    if np.issubdtype(dtype, np.integer):
        image *= np.iinfo(dtype).max
    image = image.astype(dtype)
    if np.issubdtype(dtype, np.floating):
        image[0, 0] = [np.nan, np.inf, -np.inf]
    for mode in ("linear", "cubic"):
        np.testing.assert_array_equal(apply_curves_lut(image, [(40, 70), (150, 210)], channels, mode),
                                      curves_reference(image, [(40, 70), (150, 210)], channels, mode))


def test_owned_color_buffers_match_allocating_pipeline(monkeypatch):
    image = np.random.default_rng(11).random((40, 50, 3), dtype=np.float32)
    original = image.copy()
    configs = [{}, {"exposure": .7, "temperature": 8, "texture": .1, "clarity": .2},
               {"saturation": .1, "dehaze": .2}]
    for basic in configs:
        actual = ColorProcessor.apply_camera_raw_and_hsl(image, basic, {}, {"stretch_factor": 2})
        # Frozen allocator semantics: perform each clip into a fresh buffer.
        old_clip = np.clip
        def allocating_clip(array, lower, upper, out=None, **kwargs):
            result = old_clip(array, lower, upper, **kwargs)
            if out is not None:
                out[...] = result
                return out
            return result
        with monkeypatch.context() as patch:
            patch.setattr(np, "clip", allocating_clip)
            expected = ColorProcessor.apply_camera_raw_and_hsl(image, basic, {}, {"stretch_factor": 2})
        np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(image, original)


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.float32])
@pytest.mark.parametrize("autostretch", [False, True])
def test_shared_full_pipeline_matches_old_stage_order(dtype, autostretch):
    image = np.random.default_rng(12).random((40, 50, 3))
    if np.issubdtype(dtype, np.integer):
        image *= np.iinfo(dtype).max
    image = image.astype(dtype)
    levels = dict(black=8, gamma=1.7, white=240, channels=["r", "g", "b"], autostretch=autostretch)
    curves = dict(points=[(40, 70), (150, 210)], channels=["r", "g", "b"], curve_mode="linear")
    expected = ColorProcessor.apply_camera_raw_and_hsl(image, {"exposure": .2}, {}, {"stretch_factor": .5})
    expected = levels_reference(expected, 8, 1.7, 240, levels["channels"])
    expected = curves_reference(expected, curves["points"], curves["channels"])
    if autostretch:
        expected = stretch_image(expected, "autostretch")
    if dtype == np.uint8:
        expected = np.clip(np.rint(expected * 255.0), 0, 255).astype(np.uint8)
    actual = process_image(image, {"exposure": .2}, {}, {"stretch_factor": .5}, levels, curves)
    np.testing.assert_array_equal(actual, expected)
