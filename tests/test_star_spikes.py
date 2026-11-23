import numpy as np

from processing.star_spikes import (
    add_star_spikes,
    detect_bright_stars,
    scale_spike_length,
    spike_profile,
)


def _star_field():
    y, x = np.mgrid[:160, :200]
    image = np.full((160, 200), 0.015, dtype=np.float32)
    for cx, cy, peak, sigma in ((45, 55, 0.95, 2.0), (110, 75, 0.55, 2.2), (155, 120, 0.2, 2.5)):
        image += peak * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma**2))
    return np.clip(image, 0.0, 1.0)


def test_star_selection_ranks_integrated_flux_and_keeps_saturated_core_single():
    image = _star_field()
    image[53:58, 43:48] = 1.0
    stars = detect_bright_stars(image, brightness_percent=20)

    assert len(stars) == 1
    assert abs(stars[0]["x"] - 45) <= 1
    assert abs(stars[0]["y"] - 55) <= 1
    assert stars[0]["flux"] > 0


def test_spike_length_scales_as_power_of_measured_flux():
    short = scale_spike_length(25, 100, 60, scaling=0.5)
    long = scale_spike_length(400, 100, 60, scaling=0.5)

    assert short == 30
    assert long == 120
    assert long > short


def test_spike_profile_fades_monotonically_to_zero():
    distances = np.linspace(0, 120, 241)
    profile = spike_profile(distances, 100, amplitude=0.8, falloff=2.0)

    assert np.all(np.diff(profile) <= 1e-7)
    assert profile[0] == 0.8
    assert profile[distances >= 100].max() == 0.0


def test_spikes_leave_pixels_outside_their_local_extent_unchanged():
    image = _star_field()
    result, count = add_star_spikes(
        image,
        brightness_percent=10,
        base_length=24,
        intensity=0.8,
        width=1.5,
        halo=False,
        linear_input=True,
    )
    changed = np.abs(result - image) > 1e-6
    yy, xx = np.where(changed)

    assert count == 1
    assert len(xx) > 0
    radius = int(np.ceil(24 + 1.5 * 5 + 3))
    assert xx.min() >= 45 - radius and xx.max() <= 45 + radius
    assert yy.min() >= 55 - radius and yy.max() <= 55 + radius
    assert result[10, 10] == image[10, 10]


def test_progress_callback_reports_rendering_and_completion():
    events = []
    _result, count = add_star_spikes(
        _star_field(),
        brightness_percent=10,
        base_length=20,
        halo=False,
        progress_callback=lambda percent, stage, current, total: events.append(
            (percent, stage, current, total)
        ) or True,
    )

    assert count > 0
    assert any(stage == "render" for _, stage, _, _ in events)
    assert events[-1][0] == 100 and events[-1][1] == "done"
    assert [percent for percent, *_ in events] == sorted(percent for percent, *_ in events)


def test_progress_callback_can_cancel_without_returning_partial_image():
    def cancel_at_render(_percent, stage, _current, _total):
        return stage != "render"

    try:
        add_star_spikes(_star_field(), progress_callback=cancel_at_render)
    except InterruptedError:
        pass
    else:
        raise AssertionError("The renderer should stop when its progress callback cancels")
