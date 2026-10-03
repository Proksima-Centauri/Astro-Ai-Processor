import numpy as np

from processing.image_effects import local_contrast_enhancement, neutralize_background


def test_neutralize_background_balances_roi_channel_means():
    image = np.empty((4, 4, 3), dtype=np.float32)
    image[:, :, 0] = 0.2
    image[:, :, 1] = 0.4
    image[:, :, 2] = 0.6

    out = neutralize_background(image, (0, 4, 0, 4))

    means = out.mean(axis=(0, 1))
    assert out.dtype == np.float32
    assert np.allclose(means, means.mean(), atol=1e-5)


def test_local_contrast_enhancement_boosts_point_detail_and_keeps_range():
    image = np.full((15, 15), 0.1, dtype=np.float32)
    image[7, 7] = 0.9

    out = local_contrast_enhancement(
        image,
        radius_px=1.0,
        strength=1.0,
        protect_background=False,
        protect_stars=False,
    )

    assert out.shape == image.shape
    assert out.dtype == np.float32
    assert out[7, 7] > image[7, 7]
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
