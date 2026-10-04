import numpy as np
import pytest

from processing.astro_upscale import AstroUpscaleError, AstroUpscaler, rescale_fits_header


def test_astro_upscale_2x_doubles_1000px_image():
    image = np.arange(1_000_000, dtype=np.uint8).reshape(1000, 1000)

    result = AstroUpscaler.upscale(image, 2, "lanczos")

    assert result.shape == (2000, 2000)
    assert result.dtype == image.dtype


def test_astro_upscale_4x_doubles_each_axis_to_4000px():
    image = np.zeros((1000, 1000), dtype=np.uint16)

    result = AstroUpscaler.upscale(image, 4, "bicubic")

    assert result.shape == (4000, 4000)
    assert result.dtype == np.uint16


def test_float32_data_remains_float32_without_8bit_conversion():
    image = np.linspace(0.0, 1.0, 64 * 64, dtype=np.float32).reshape(64, 64)

    result = AstroUpscaler.upscale(image, 2)

    assert result.dtype == np.float32
    assert result.shape == (128, 128)
    assert float(result.min()) >= float(image.min())
    assert float(result.max()) <= float(image.max())


def test_uint16_rgba_channels_and_alpha_are_preserved():
    image = np.full((5, 7, 4), 8192, dtype=np.uint16)
    image[:, :, 3] = 32768

    result = AstroUpscaler.upscale(image, 2)

    assert result.shape == (10, 14, 4)
    assert result.dtype == np.uint16
    assert np.all(result[:, :, :3] == 8192)
    assert np.all(result[:, :, 3] == 32768)


def test_singleton_channel_axis_is_preserved():
    image = np.ones((9, 11, 1), dtype=np.float32)

    result = AstroUpscaler.upscale(image, 2)

    assert result.shape == (18, 22, 1)
    assert result.dtype == np.float32


def test_boolean_layer_masks_resize_and_keep_boolean_dtype():
    mask = np.zeros((12, 12), dtype=bool)
    mask[3:9, 3:9] = True

    result = AstroUpscaler.upscale_mask(mask, 2)

    assert result.shape == (24, 24)
    assert result.dtype == np.bool_
    assert result[8:16, 8:16].all()


def test_extreme_output_size_is_rejected_before_allocation():
    image = np.empty((4000, 4000), dtype=np.uint8)

    with pytest.raises(AstroUpscaleError, match="safe limit"):
        AstroUpscaler.output_shape(image, 4)


def test_bright_point_source_does_not_gain_ringing_or_shift_position():
    image = np.zeros((33, 33), dtype=np.float32)
    image[16, 16] = 1.0

    result = AstroUpscaler.upscale(image, 2, "lanczos")
    peak_y, peak_x = np.unravel_index(int(np.argmax(result)), result.shape)

    assert float(result.min()) >= 0.0
    assert float(result.max()) <= 1.0
    assert abs(peak_x - 32.5) <= 1.0
    assert abs(peak_y - 32.5) <= 1.0


def test_fits_header_wcs_and_non_wcs_metadata_survive_upscale(tmp_path):
    fits = pytest.importorskip("astropy.io.fits")
    image = np.zeros((16, 16), dtype=np.float32)
    header = fits.Header()
    header["OBJECT"] = "M42"
    header["CRPIX1"] = 8.5
    header["CRPIX2"] = 7.5
    header["CDELT1"] = -0.001
    header["CDELT2"] = 0.001
    header["A_2_0"] = 0.0002

    result = AstroUpscaler.upscale(image, 2)
    updated_header = rescale_fits_header(header, 2, result.shape[1], result.shape[0])
    output_path = tmp_path / "upscaled.fits"
    fits.PrimaryHDU(data=result, header=updated_header).writeto(output_path)

    with fits.open(output_path) as hdul:
        output_header = hdul[0].header
        assert hdul[0].data.shape == (32, 32)
        assert output_header["OBJECT"] == "M42"
        assert output_header["CRPIX1"] == pytest.approx(16.5)
        assert output_header["CRPIX2"] == pytest.approx(14.5)
        assert output_header["CDELT1"] == pytest.approx(-0.0005)
        assert output_header["A_2_0"] == pytest.approx(0.0001)
