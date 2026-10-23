import json
from types import SimpleNamespace

import numpy as np
import pytest
from astropy.io import fits

from processing.plate_solver import skyshot_result, solve_with_skyshot


def solution():
    return {"schema_version": 1, "solution": {
        "status": "solved", "width": 8, "height": 6,
        "ra": 83.8, "dec": -5.4, "scale_arcsec": 2.0, "rotation_deg": 12.0,
        "wcs": {"ra": 83.8, "dec": -5.4}, "matches": [{"x": 2.5, "y": 3.2}],
    }, "timings": {"total_ms": 8}}


def test_skyshot_cli_preserves_native_image_and_wcs(tmp_path):
    binary = tmp_path / "skyshot"
    binary.write_text("fake")
    index = tmp_path / "index"
    index.mkdir()
    source = np.random.default_rng(4).random((6, 8, 3), dtype=np.float32)
    def runner(command, **kwargs):
        assert command[1] == "solve"
        np.testing.assert_array_equal(fits.getdata(command[2]), np.moveaxis(source[:, :, ::-1], 2, 0))
        header = fits.Header({"CRVAL1": 83.8, "CRVAL2": -5.4, "CRPIX1": 4.5,
                              "CRPIX2": 3.5, "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
                              "CD1_1": -2/3600, "CD2_2": 2/3600})
        header.tofile(command[command.index("--wcs") + 1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(solution()), stderr="")
    result = solve_with_skyshot(source, str(binary), str(index), runner=runner)
    assert result["source"] == "skyshot"
    assert result["ra"] == 83.8
    assert result["scale"] == 2
    assert result["wcs_header"]["CRPIX1"] == 4.5


def test_skyshot_failed_exit_never_accepts_wcs(tmp_path):
    binary = tmp_path / "skyshot"
    binary.write_text("fake")
    def runner(command, **kwargs):
        payload = solution()
        payload["solution"]["status"] = "ambiguous"
        return SimpleNamespace(returncode=1, stdout=json.dumps(payload), stderr="")
    with pytest.raises(RuntimeError, match="ambiguous"):
        solve_with_skyshot(np.zeros((6, 8)), str(binary), str(tmp_path), runner=runner)


@pytest.mark.parametrize("status", ["unsolved", "ambiguous", "timeout"])
def test_skyshot_rejects_non_solutions(status):
    payload = solution()
    payload["solution"]["status"] = status
    with pytest.raises(RuntimeError, match=status):
        skyshot_result(payload, {"CRVAL1": 83.8, "CRVAL2": -5.4}, (6, 8, 3))


def test_skyshot_requires_index_and_binary(tmp_path):
    with pytest.raises(RuntimeError, match="pliku Skyshot"):
        solve_with_skyshot(np.zeros((6, 8)), str(tmp_path / "missing"), str(tmp_path))


def test_license_and_notice_preserve_upstream_attribution():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    notice = (root / "docs/NOTICE-Skyshot.txt").read_text()
    assert "Copyright 2026 Adam Jesionkiewicz" in notice
    assert "Apache License 2.0" in notice
    assert "Apache License" in (root / "docs/LICENSE-Skyshot-Apache-2.0.txt").read_text()


def test_skyshot_preserves_sip_and_fits_pixel_origin():
    payload = solution()
    header = {"CRVAL1": 83.8, "CRVAL2": -5.4, "CRPIX1": 4.5, "CRPIX2": 3.5,
              "CTYPE1": "RA---TAN-SIP", "CTYPE2": "DEC--TAN-SIP", "A_ORDER": 2,
              "A_2_0": 1e-7}
    result = skyshot_result(payload, header, (6, 8, 3))
    assert result["wcs_header"] == header
    assert result["points"] == [(2, 3)]
