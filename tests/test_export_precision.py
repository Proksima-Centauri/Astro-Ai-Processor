import numpy as np
import pytest

from processing.export import normalized_to_uint16


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.uint32, np.float32, np.float64])
def test_chunked_export_is_bit_identical_to_full_float64_reference(dtype):
    image = np.random.default_rng(17).random((23, 37, 3))
    if np.issubdtype(dtype, np.integer):
        image *= np.iinfo(dtype).max
    image = image.astype(dtype)
    scale = 65535.0 / np.iinfo(dtype).max if np.issubdtype(dtype, np.integer) else 65535.0
    expected = np.clip(np.rint(image.astype(np.float64) * scale), 0, 65535).astype(np.uint16)
    actual = normalized_to_uint16(image, chunk_pixels=113)
    np.testing.assert_array_equal(actual, expected)


def test_export_half_steps_and_noncontiguous_channels():
    image = ((np.arange(1000) + .5) / 65535).reshape(10, 100).astype(np.float32)
    image = image[:, ::-1]
    expected = np.clip(np.rint(image.astype(np.float64) * 65535), 0, 65535).astype(np.uint16)
    np.testing.assert_array_equal(normalized_to_uint16(image, 110), expected)
