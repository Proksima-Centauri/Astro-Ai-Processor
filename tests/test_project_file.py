import json
import zipfile

import numpy as np
import pytest

from processing.project_file import (
    PROJECT_FORMAT,
    ProjectFileError,
    load_project,
    save_project,
)


def test_project_round_trip_preserves_float32_arrays(tmp_path):
    state = {
        "original_img": np.linspace(-2, 4, 60, dtype=np.float32).reshape(4, 5, 3),
        "magic_img": np.random.default_rng(12).normal(size=(5, 6)).astype(np.float32),
        "layer_images": {"stars": np.ones((4, 5), dtype=np.float32)},
        "layer_masks": {"stars": np.arange(20, dtype=np.float32).reshape(4, 5)},
        "processing_history": [{"id": 1, "name": "Stretch", "img": np.full((2, 3), 0.125, np.float32)}],
        "latest_plate_solve_result": {"ra": 12.5, "solution": [1, 2]},
        "layer_titles": {"stars": "Stars"},
    }
    path = tmp_path / "sample.astroproj"
    save_project(path, state)
    loaded = load_project(path)
    for key in ("original_img", "magic_img"):
        np.testing.assert_array_equal(loaded[key], state[key])
    np.testing.assert_array_equal(loaded["layer_images"]["stars"], state["layer_images"]["stars"])
    np.testing.assert_array_equal(loaded["layer_masks"]["stars"], state["layer_masks"]["stars"])
    np.testing.assert_array_equal(loaded["processing_history"][0]["img"], state["processing_history"][0]["img"])
    assert loaded["latest_plate_solve_result"] == state["latest_plate_solve_result"]
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert {"project.json", "base.fits", "current.fits", "layers/stars.npy", "masks/stars.npy", "thumbnail.png"} <= set(names)
        metadata = json.loads(archive.read("project.json"))
    assert metadata["format"] == PROJECT_FORMAT
    assert metadata["format_version"] == 1
    assert metadata["layers"][0]["name"] == "stars"


def _write_metadata(path, metadata, extra=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(metadata))
        for name, data in (extra or {}).items():
            archive.writestr(name, data)


def test_corrupt_zip_raises_clear_error(tmp_path):
    path = tmp_path / "broken.astroproj"
    path.write_bytes(b"not a zip")
    with pytest.raises(ProjectFileError, match="ZIP"):
        load_project(path)


def test_unknown_format_rejected(tmp_path):
    path = tmp_path / "unknown.astroproj"
    _write_metadata(path, {"format": "other", "format_version": 1})
    with pytest.raises(ProjectFileError, match="not an Astro"):
        load_project(path)


def test_newer_version_rejected(tmp_path):
    path = tmp_path / "future.astroproj"
    _write_metadata(path, {"format": PROJECT_FORMAT, "format_version": 999})
    with pytest.raises(ProjectFileError, match="newer format"):
        load_project(path)


@pytest.mark.parametrize("member", ["../escape.npy", "/absolute.npy", "arrays/../../escape.npy", "C:/escape.npy"])
def test_zip_slip_rejected(tmp_path, member):
    path = tmp_path / "unsafe.astroproj"
    _write_metadata(path, {"format": PROJECT_FORMAT, "format_version": 1, "state": {}}, {member: b"x"})
    with pytest.raises(ProjectFileError, match="unsafe ZIP path"):
        load_project(path)
