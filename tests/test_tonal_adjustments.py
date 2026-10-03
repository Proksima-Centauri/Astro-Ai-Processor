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

    out = apply_levels(image, black=10, gamma=1.0, white=255, channels=["b"])

    assert out.shape == image.shape
    assert np.all(out[:, :, 0] < original[:, :, 0])
    assert np.array_equal(out[:, :, 1:], original[:, :, 1:])


def test_neutral_levels_preserve_float_precision():
    image = np.array([[[0.00123, 0.12567, 0.98765]]], dtype=np.float32)

    out = apply_levels(image, black=0, gamma=1.0, white=255, channels=["b", "g", "r"])

    assert out.dtype == np.float32
    assert np.array_equal(out, image)


def test_curves_change_only_selected_channel():
    image = np.full((2, 2, 3), 100, dtype=np.uint8)

    out = apply_curves_lut(image, [(128, 220)], channels=["r"])

    assert out.shape == image.shape
    assert np.all(out[:, :, 2] > image[:, :, 2])
    assert np.array_equal(out[:, :, :2], image[:, :, :2])
