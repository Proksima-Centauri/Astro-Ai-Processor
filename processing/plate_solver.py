"""GPLv3 application adapter for the separately installed Apache-2.0 Skyshot CLI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np


def resolve_skyshot(binary=""):
    requested = str(binary or os.environ.get("SKYSHOT_BINARY", "")).strip()
    if requested:
        path = shutil.which(requested) or os.path.expanduser(requested)
        if os.path.isfile(path):
            return os.path.abspath(path)
        raise RuntimeError("Nie znaleziono wskazanego pliku Skyshot Solver.")
    for name in ("skyshot", "skyshot.exe"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Wybierz plik Skyshot Solver w oknie Plate Solving lub dodaj skyshot do PATH.")


def skyshot_result(payload, header, image_shape):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("Nieobsługiwana odpowiedź Skyshot Solver (schema_version).")
    solution = payload.get("solution")
    if not isinstance(solution, dict) or solution.get("status") != "solved":
        status = solution.get("status", "unknown") if isinstance(solution, dict) else "unknown"
        raise RuntimeError(f"Skyshot nie znalazł jednoznacznego rozwiązania: {status}.")
    if not isinstance(solution.get("wcs"), dict):
        raise RuntimeError("Skyshot nie zwrócił WCS dla rozwiązania.")
    if not header or "CRVAL1" not in header or "CRVAL2" not in header:
        raise RuntimeError("Skyshot nie zapisał poprawnego nagłówka WCS.")
    ra, dec, scale, rotation = (float(solution[name]) for name in ("ra", "dec", "scale_arcsec", "rotation_deg"))
    if not all(math.isfinite(value) for value in (ra, dec, scale, rotation)) or scale <= 0:
        raise RuntimeError("Skyshot zwrócił niepoprawne parametry rozwiązania.")
    height, width = image_shape[:2]
    if solution.get("width") != width or solution.get("height") != height:
        raise RuntimeError("Rozmiar rozwiązania Skyshot nie odpowiada obrazowi.")
    points = []
    for match in solution.get("matches", []):
        if not isinstance(match, dict):
            continue
        x, y = match.get("x"), match.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and math.isfinite(x) and math.isfinite(y):
            points.append((int(round(x)), int(round(y))))
    return {
        "ra": ra, "dec": dec, "scale": scale, "rotation": rotation,
        "fov_x": width * scale / 3600.0, "fov_y": height * scale / 3600.0,
        "points": points, "wcs_header": header, "objects_in_field": [],
        "calibration_data": {"ra": ra, "dec": dec, "pixscale": scale, "orientation": rotation},
        "source": "skyshot", "skyshot_timings": payload.get("timings", {}),
        "skyshot_wcs": solution["wcs"],
    }


def solve_with_skyshot(image, binary="", index="", progress=None, runner=None):
    """Export native pixels as FITS and read Skyshot's JSON and FITS WCS header.

    Runs only locally. Index data is provided by the user under its own terms.
    """
    from astropy.io import fits

    executable = resolve_skyshot(binary)
    index_path = Path(os.path.expanduser(str(index or os.environ.get("SKYSHOT_INDEX", "")))).resolve()
    if not str(index or os.environ.get("SKYSHOT_INDEX", "")).strip() or not index_path.is_dir():
        raise RuntimeError("Wybierz poprawny katalog indeksu Skyshot w oknie Plate Solving.")
    source = np.asarray(image)
    if source.size == 0 or source.ndim not in (2, 3):
        raise RuntimeError("Niepoprawny obraz do plate solving.")
    if progress:
        progress("Skyshot: preparing native FITS image...", 5, 5)
    with tempfile.TemporaryDirectory(prefix="astro_skyshot_") as directory:
        input_path = Path(directory) / "input.fits"
        wcs_path = Path(directory) / "solution.wcs"
        data = source
        if source.ndim == 3:
            if source.shape[2] not in (3, 4):
                raise RuntimeError("Skyshot expects mono or RGB/BGR image data.")
            data = np.moveaxis(source[:, :, :3][:, :, ::-1], 2, 0)
        fits.PrimaryHDU(data=np.ascontiguousarray(data)).writeto(input_path)
        command = [executable, "solve", str(input_path), "--index", str(index_path),
                   "--wcs", str(wcs_path), "--matches", "--deadline-ms", "60000"]
        if progress:
            progress("Skyshot: solving locally...", 20, 20)
        try:
            completed = (runner or subprocess.run)(command, capture_output=True, text=True,
                                                   encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Skyshot Solver przekroczył limit czasu.") from None
        if completed.returncode not in (0, 1):
            raise RuntimeError(f"Skyshot Solver failed: {(completed.stderr or completed.stdout).strip()[:1000]}")
        try:
            payload = json.loads(completed.stdout)
        except (TypeError, json.JSONDecodeError):
            raise RuntimeError("Skyshot zwrócił niepoprawny JSON.") from None
        if completed.returncode == 1:
            status = (payload.get("solution") or {}).get("status", "unsolved")
            raise RuntimeError(f"Skyshot nie znalazł jednoznacznego rozwiązania: {status}.")
        if not wcs_path.is_file():
            raise RuntimeError("Skyshot nie zapisał pliku WCS.")
        try:
            header = dict(fits.Header.fromfile(wcs_path).items())
        except Exception as exc:
            raise RuntimeError(f"Nie można odczytać nagłówka WCS Skyshot: {exc}") from None
        result = skyshot_result(payload, header, source.shape)
        if progress:
            progress("Skyshot: solved.", 100, 100)
        return result
