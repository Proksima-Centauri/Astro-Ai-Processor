import numpy as np
import pytest

from processing.stretch import stretch_image


def _mtf_reference(values, midtone, shadows=0.0, highlights=1.0):
    values = np.asarray(values, dtype=np.float64)
    normalized = np.clip((values - shadows) / (highlights - shadows), 0.0, 1.0)
    result = ((midtone - 1.0) * normalized) / (((2.0 * midtone - 1.0) * normalized) - midtone)
    result = np.where(values <= shadows, 0.0, result)
    return np.where(values >= highlights, 1.0, np.clip(result, 0.0, 1.0))


def _autostretch_parameters_reference(image, channel_indices):
    stats = []
    for channel_index in channel_indices:
        plane = image if channel_index is None else image[:, :, channel_index]
        values = plane.astype(np.float64) / 255.0
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        sigma = 1.4826 * mad if mad else 0.001
        stats.append((median, sigma))

    inverted = sum(median > 0.5 for median, _ in stats) == len(stats)
    median = float(np.mean([item[0] for item in stats]))
    if not inverted:
        shadows = max(0.0, float(np.mean([value - 2.8 * sigma for value, sigma in stats])))
        midtone = float(_mtf_reference(np.asarray([median - shadows]), 0.25)[0])
        highlights = 1.0
    else:
        shadows = 0.0
        highlights = min(1.0, float(np.mean([value + 2.8 * sigma for value, sigma in stats])))
        midtone = 1.0 - float(_mtf_reference(np.asarray([highlights - median]), 0.25)[0])
    return shadows, midtone, highlights


def _autostretch_reference(image, linked=True):
    if image.ndim == 2:
        channel_indices = [None]
    else:
        channel_indices = list(range(3 if image.shape[2] >= 3 else image.shape[2]))

    shared = _autostretch_parameters_reference(image, channel_indices)
    result = image.copy()
    if linked:
        for channel_index in channel_indices:
            plane = image if channel_index is None else image[:, :, channel_index]
            shadows, midtone, highlights = shared
            mapped = _mtf_reference(plane.astype(np.float64) / 255.0, midtone, shadows, highlights)
            output = np.rint(mapped * 255.0).astype(np.uint8)
            if channel_index is None:
                result[:] = output
            else:
                result[:, :, channel_index] = output
    else:
        for channel_index in channel_indices:
            plane = image if channel_index is None else image[:, :, channel_index]
            params = _autostretch_parameters_reference(image, [channel_index])
            shadows, midtone, highlights = params
            mapped = _mtf_reference(plane.astype(np.float64) / 255.0, midtone, shadows, highlights)
            output = np.rint(mapped * 255.0).astype(np.uint8)
            if channel_index is None:
                result[:] = output
            else:
                result[:, :, channel_index] = output
    return result


def _histogram_reference(image, linked):
    channels = [image] if image.ndim == 2 else [image[:, :, i] for i in range(min(3, image.shape[2]))]
    histograms = [np.bincount(channel.reshape(-1), minlength=256) for channel in channels]
    if linked and len(channels) > 1:
        pooled = np.sum(histograms, axis=0)
        histograms = [pooled] * len(channels)
    output = image.copy()
    for index, (channel, histogram) in enumerate(zip(channels, histograms)):
        cdf = np.cumsum(histogram, dtype=np.float64) / histogram.sum()
        cdf[0] = 0.0
        lut = np.rint(cdf * 255.0).astype(np.uint8)
        mapped = lut[channel]
        if image.ndim == 2:
            output[:] = mapped
        else:
            output[:, :, index] = mapped
    return output


def _sample_rgb(seed=8):
    rng = np.random.default_rng(seed)
    image = np.empty((48, 64, 3), dtype=np.uint8)
    image[:, :, 0] = np.clip(rng.normal(25, 5, image.shape[:2]), 0, 255).astype(np.uint8)
    image[:, :, 1] = np.clip(rng.normal(34, 7, image.shape[:2]), 0, 255).astype(np.uint8)
    image[:, :, 2] = np.clip(rng.normal(21, 4, image.shape[:2]), 0, 255).astype(np.uint8)
    image[12:20, 12:20] += np.uint8(45)
    image[28:30, 40:42] = (230, 200, 245)
    return image


def test_autostretch_matches_siril_find_midtones_balance_and_mtf():
    image = _sample_rgb()

    actual, diagnostics = stretch_image(image, "autostretch", return_diagnostics=True)
    expected = _autostretch_reference(image, linked=True)

    assert np.array_equal(actual, expected)
    assert diagnostics["model"] == "siril_autostretch_mtf"
    assert diagnostics["target"] == 0.25
    assert diagnostics["linked_channels"]


def test_unlinked_autostretch_uses_siril_mtf_per_channel():
    image = _sample_rgb(seed=12)

    actual = stretch_image(image, "autostretch", linked_channels=False)

    assert np.array_equal(actual, _autostretch_reference(image, linked=False))
    assert not np.array_equal(actual, stretch_image(image, "autostretch", linked_channels=True))


def test_histogram_mode_matches_siril_cumulative_histogram_mapping():
    image = _sample_rgb(seed=17)

    actual = stretch_image(image, "histogram", linked_channels=False)

    assert np.array_equal(actual, _histogram_reference(image, linked=False))


def test_linked_histogram_uses_one_pooled_rgb_cdf():
    image = _sample_rgb(seed=21)

    actual, diagnostics = stretch_image(image, "histogram", linked_channels=True, return_diagnostics=True)

    assert np.array_equal(actual, _histogram_reference(image, linked=True))
    assert diagnostics["model"] == "siril_histogram_cdf"
    assert diagnostics["linked_channels"]


def test_linked_and_unlinked_modes_keep_alpha_unchanged():
    rgb = _sample_rgb(seed=25)
    alpha = np.full(rgb.shape[:2], 173, dtype=np.uint8)
    rgba = np.dstack((rgb, alpha))

    for mode in ("autostretch", "histogram"):
        for linked in (True, False):
            result = stretch_image(rgba, mode, linked_channels=linked)
            assert np.array_equal(result[:, :, 3], alpha)
            assert result.shape == rgba.shape
            assert result.dtype == rgba.dtype


def test_linear_is_non_mutating_and_auto_stretch_handles_inverted_data():
    image = _sample_rgb(seed=29)
    original = image.copy()
    linear = stretch_image(image, "linear")
    inverted = np.full((48, 64), 210, dtype=np.uint8)
    inverted[20:25, 20:25] = 170

    auto_output, diagnostics = stretch_image(inverted, "autostretch", return_diagnostics=True)

    assert np.array_equal(linear, original)
    assert linear is not image
    assert np.array_equal(image, original)
    assert diagnostics["inverted"]
    assert np.isfinite(auto_output).all()


def test_constant_float_and_nonfinite_input_are_safe():
    flat = np.full((16, 16), 0.25, dtype=np.float32)
    special = np.array([[0.0, np.nan], [np.inf, -np.inf]], dtype=np.float32)

    flat_output = stretch_image(flat, "autostretch")
    special_output = stretch_image(special, "histogram")

    assert np.isfinite(flat_output).all()
    assert not np.array_equal(flat_output, flat)
    assert np.isfinite(special_output).all()


def test_removed_profile_names_are_rejected():
    with pytest.raises(ValueError, match="linear, autostretch, or histogram"):
        stretch_image(np.ones((4, 4), dtype=np.float32), "medium")
