import numpy as np
import pytest

from processing.stacking import integrate_stack_frames, normalize_stack_frames


def test_sigma_clipped_average_rejects_transient_high_and_low_outliers():
    base = np.full((3, 4, 3), 20.0, dtype=np.float32)
    frames = [base.copy() for _ in range(7)]
    frames[0][1, 2] = 255.0
    frames[1][0, 0] = 0.0

    result = integrate_stack_frames(frames, "mad_clip", target_chunk_bytes=32)

    np.testing.assert_allclose(result[1, 2], 20.0)
    np.testing.assert_allclose(result[0, 0], 20.0)
    np.testing.assert_allclose(result[2, 3], 20.0)


def test_sigma_clipped_average_keeps_all_samples_for_four_or_fewer_frames():
    frames = [np.full((2, 2), value, dtype=np.float32) for value in (10, 10, 10, 100)]

    result = integrate_stack_frames(frames, "mad_clip")

    np.testing.assert_allclose(result, 32.5)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("additive", 10.0),
        ("multiplicative", 10.0),
        ("additive_scaling", 10.0),
        ("multiplicative_scaling", 10.0),
    ],
)
def test_reference_normalization_matches_constant_frame_levels(mode, expected):
    frames = [np.full((5, 5, 3), 10.0), np.full((5, 5, 3), 20.0)]

    normalized = normalize_stack_frames(frames, mode)

    np.testing.assert_allclose(normalized[0], 10.0)
    np.testing.assert_allclose(normalized[1], expected)


def test_additive_scaling_matches_reference_noise_scale():
    yy, xx = np.indices((24, 24), dtype=np.float32)
    reference = 30.0 + xx + yy
    second = 2.0 * reference + 15.0

    normalized = normalize_stack_frames([reference, second], "additive_scaling")

    np.testing.assert_allclose(normalized[1], reference, atol=1e-4)


def test_integrators_match_expected_median_and_average():
    frames = [np.full((2, 3), value, dtype=np.float32) for value in (2, 4, 100)]

    np.testing.assert_allclose(integrate_stack_frames(frames, "median"), 4.0)
    np.testing.assert_allclose(integrate_stack_frames(frames, "average"), 106.0 / 3.0)


def test_normalization_rejects_invalid_mode_and_incompatible_frames():
    with pytest.raises(ValueError, match="Unsupported stacking normalization"):
        normalize_stack_frames([np.zeros((2, 2))], "auto")
    with pytest.raises(ValueError, match="matching shapes"):
        normalize_stack_frames([np.zeros((2, 2)), np.zeros((3, 2))], "additive")
