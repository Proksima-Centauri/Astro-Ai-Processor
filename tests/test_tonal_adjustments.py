import numpy as np

from processing.tonal_adjustments import apply_curves_lut, apply_levels, build_curve_lut


def test_curve_lut_passes_through_control_point():
    lut = build_curve_lut([(128, 200)])

    assert lut.dtype == np.uint8
    assert lut.shape == (256,)
    assert int(lut[128]) == 200


def test_levels_change_only_selected_channel():
    image = np.full((2, 2, 3), 100, dtype=np.uint8)
    original = image.copy()

    out = apply_levels(image, black=10, midtones=0.5, white=255, channels=["b"])

    assert out.shape == image.shape
    assert np.all(out[:, :, 0] < original[:, :, 0])
    assert np.array_equal(out[:, :, 1:], original[:, :, 1:])


def test_neutral_levels_preserve_float_precision():
    image = np.array([[[0.00123, 0.12567, 0.98765]]], dtype=np.float32)

    out = apply_levels(image, black=0, midtones=0.5, white=255, channels=["b", "g", "r"])

    assert out.dtype == np.float32
    assert np.array_equal(out, image)


def test_levels_midtones_use_siril_mtf_balance():
    image = np.array([[0.0, 0.25, 0.5, 0.75, 1.0]], dtype=np.float32)
    brighter = apply_levels(image, black=0, midtones=0.25, white=255)
    darker = apply_levels(image, black=0, midtones=0.75, white=255)

    assert brighter[0, 2] == np.float32(0.75)
    assert darker[0, 2] == np.float32(0.25)
    assert brighter[0, 0] == darker[0, 0] == 0.0
    assert brighter[0, -1] == darker[0, -1] == 1.0


def test_levels_black_and_white_are_mtf_shadows_and_highlights():
    image = np.array([[0.0, 0.2, 0.5, 0.8, 1.0]], dtype=np.float32)
    result = apply_levels(image, black=51, midtones=0.5, white=204)

    np.testing.assert_allclose(result, [[0.0, 0.0, 0.5, 1.0, 1.0]], atol=2e-7, rtol=0)


def test_curves_change_only_selected_channel():
    image = np.full((2, 2, 3), 100, dtype=np.uint8)

    out = apply_curves_lut(image, [(128, 220)], channels=["r"])

    assert out.shape == image.shape
    assert np.all(out[:, :, 2] > image[:, :, 2])
    assert np.array_equal(out[:, :, :2], image[:, :, :2])
