import numpy as np
import pytest

from processing import background_extraction as bge


def test_graxpert_subtraction_correction_uses_mean_background(monkeypatch):
    source = np.full((2, 2, 3), 0.5, dtype=np.float32)
    estimated = np.array(
        [
            [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]],
            [[0.3, 0.4, 0.5], [0.4, 0.5, 0.6]],
        ],
        dtype=np.float32,
    )
    monkeypatch.setattr(bge, "_run_ai", lambda *_args, **_kwargs: estimated.copy())
    progress_updates = []

    corrected, background = bge.extract_background(
        source,
        np.empty((0, 2), dtype=int),
        interpolation_type="AI",
        correction_type="Subtraction",
        ai_model_path="fake.onnx",
        progress=lambda stage, overall, current: progress_updates.append((stage, overall, current)),
    )

    expected = np.clip(source - estimated + np.mean(estimated), 0.0, 1.0)
    np.testing.assert_allclose(background, estimated)
    np.testing.assert_allclose(corrected, expected)
    assert progress_updates[-1][1] == 100


def test_automatic_grid_returns_in_bounds_sample_points():
    y, x = np.mgrid[:128, :192]
    image = np.stack(
        [0.1 + x / 1000.0 + y / 2000.0, 0.2 + x / 1000.0 + y / 2000.0, 0.3 + x / 1000.0 + y / 2000.0],
        axis=-1,
    ).astype(np.float32)

    points = bge.select_background_grid(image, points_per_row=6, sample_size=5)

    assert points.ndim == 2 and points.shape[1] == 3
    assert len(points) > 0
    assert np.all((points[:, 0] >= 0) & (points[:, 0] < image.shape[1]))
    assert np.all((points[:, 1] >= 0) & (points[:, 1] < image.shape[0]))


def test_uint16_image_round_trip_keeps_native_precision_and_bgr_layout():
    source_bgr = np.arange(5 * 6 * 3, dtype=np.uint16).reshape(5, 6, 3) + 32000

    working_rgb = bge.image_to_graxpert_rgb(source_bgr)
    restored_bgr = bge.image_from_graxpert_rgb(working_rgb, source_bgr)

    assert working_rgb.dtype == np.float32
    assert restored_bgr.dtype == np.uint16
    np.testing.assert_array_equal(restored_bgr, source_bgr)


def test_uint16_background_correction_retains_16_bit_output(monkeypatch):
    source_bgr = np.full((3, 4, 3), 32768, dtype=np.uint16)
    working_rgb = bge.image_to_graxpert_rgb(source_bgr)
    estimated = np.linspace(0.1, 0.2, working_rgb.size, dtype=np.float32).reshape(working_rgb.shape)
    monkeypatch.setattr(bge, "_run_ai", lambda *_args, **_kwargs: estimated.copy())

    corrected_rgb, _background = bge.extract_background(
        working_rgb,
        np.empty((0, 2), dtype=int),
        interpolation_type="AI",
        correction_type="Subtraction",
        ai_model_path="fake.onnx",
    )
    corrected_bgr = bge.image_from_graxpert_rgb(corrected_rgb, source_bgr)

    assert corrected_bgr.dtype == np.uint16
    assert len(np.unique(corrected_bgr)) > 1
    assert np.max(corrected_bgr) > 255


def test_rbf_interpolation_reports_progress_and_returns_full_size_map():
    pytest.importorskip("scipy")
    y, x = np.mgrid[:32, :32]
    channel = (0.2 + x * 0.002 + y * 0.001).astype(np.float32)
    points = np.array([[5, 5], [25, 5], [5, 25], [25, 25]], dtype=int)
    updates = []

    background = bge._interpolate_channel(
        channel,
        points,
        "RBF",
        smoothing=0.0,
        downscale_factor=1,
        sample_size=3,
        rbf_kernel="thin_plate",
        spline_order=3,
        progress=lambda stage, value: updates.append((stage, value)),
    )

    assert background.shape == channel.shape
    assert np.isfinite(background).all()
    assert updates[-1] == ("Background map ready", 100)
    assert any(stage == "Interpolating background" for stage, _value in updates)
