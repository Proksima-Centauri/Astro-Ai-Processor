import numpy as np

from processing.color_processor import ColorProcessor


def test_to_float01_accepts_16bit_mono_and_expands_to_three_channels():
    mono = np.arange(25, dtype=np.uint16).reshape(5, 5) * 1024

    out = ColorProcessor._to_float01(mono)

    assert out.shape == (5, 5, 3)
    assert out.dtype == np.float32
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
    assert np.allclose(out[:, :, 0], out[:, :, 1])
    assert np.allclose(out[:, :, 1], out[:, :, 2])


def test_apply_camera_raw_and_hsl_identity_when_params_are_empty():
    image = np.array(
        [
            [[0, 64, 255], [32, 32, 32]],
            [[255, 128, 0], [16, 200, 16]],
        ],
        dtype=np.uint8,
    )

    out = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params=None,
        hsl_params=None,
        ghs_params=None,
    )

    expected = image.astype(np.float32) / 255.0
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert np.allclose(out, expected, atol=5 / 255)


def test_neutral_saturation_and_hsl_leave_float_image_unchanged():
    image = np.array(
        [
            [[0.1234, 0.4567, 0.8912], [0.3141, 0.2718, 0.1618]],
            [[0.7071, 0.5772, 0.2236], [0.9876, 0.5432, 0.1098]],
        ],
        dtype=np.float32,
    )

    out = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params={"saturation": 0.0, "vibrance": 0.0},
        hsl_params={
            "Hue": {"Reds": 0.0},
            "Saturation": {"Reds": 0.0},
            "Luminance": {"Reds": 0.0},
        },
    )

    assert np.array_equal(out, image)


def test_nonzero_saturation_changes_image():
    image = np.array([[[0.3, 0.4, 0.5]]], dtype=np.float32)

    out = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params={"saturation": 0.5},
        hsl_params=None,
    )

    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert not np.allclose(out, image, atol=1e-3)


def test_hsl_hue_adjustment_changes_target_band_without_changing_blue_band():
    image = np.array([[[0.0, 0.0, 0.6], [0.6, 0.0, 0.0]]], dtype=np.float32)

    out = ColorProcessor._apply_hsl(image, {"Hue": {"Reds": 40.0}})

    assert not np.allclose(out[0, 0], image[0, 0], atol=1 / 255)
    assert np.allclose(out[0, 1], image[0, 1], atol=1 / 255)


def test_apply_camera_raw_and_hsl_changes_image_with_exposure_and_hsl():
    image = np.full((5, 5, 3), 64, dtype=np.uint8)
    basic_params = {
        "exposure": 1.0,
        "contrast": 0.2,
        "saturation": 0.3,
        "vibrance": 0.2,
        "texture": 0.0,
        "clarity": 0.0,
        "dehaze": 0.0,
        "noise_reduction": 0.0,
    }
    hsl_params = {
        "Hue": {"Blues": 15.0},
        "Saturation": {"Blues": 20.0},
        "Luminance": {"Blues": 5.0},
    }

    out = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params=basic_params,
        hsl_params=hsl_params,
        ghs_params={"stretch_factor": 0.0},
    )

    src = image.astype(np.float32) / 255.0
    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert float(out.mean()) > float(src.mean())
    assert not np.allclose(out, src)


def test_star_halo_reduction_reduces_halo_ring_intensity():
    size = 128
    yy, xx = np.indices((size, size), dtype=np.float32)
    cy = cx = (size - 1) / 2.0
    rr2 = (xx - cx) ** 2 + (yy - cy) ** 2

    core = np.exp(-rr2 / (2.0 * (1.8 ** 2)))
    halo = np.exp(-rr2 / (2.0 * (6.0 ** 2)))
    mono = np.clip(0.08 + 0.72 * core + 0.22 * halo, 0.0, 1.0)
    image = np.stack([
        mono * 0.92,
        mono,
        mono * 1.08,
    ], axis=2).astype(np.float32)

    baseline = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params={"star_aberration": 0.0, "star_shape": 0.0},
        hsl_params=None,
        ghs_params=None,
    )
    corrected = ColorProcessor.apply_camera_raw_and_hsl(
        image=image,
        basic_params={"star_aberration": 0.0, "star_shape": 0.0, "star_halo_reduction": 1.0},
        hsl_params=None,
        ghs_params=None,
    )

    rr = np.sqrt(rr2)
    ring_mask = (rr >= 6.0) & (rr <= 12.0)

    baseline_ring = float(np.mean(baseline[:, :, 1][ring_mask]))
    corrected_ring = float(np.mean(corrected[:, :, 1][ring_mask]))

    assert corrected_ring < baseline_ring
