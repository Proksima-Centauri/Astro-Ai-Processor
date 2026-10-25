"""GPLv3 application adapter for the separately installed Apache-2.0 Skyshot CLI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np


def resolve_skyshot(binary=""):
    candidates = []
    for requested in (os.environ.get("SKYSHOT_BINARY", ""), binary):
        requested = str(requested or "").strip()
        if requested:
            candidates.append(shutil.which(requested) or os.path.expanduser(requested))

    bundle_root = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "_MEIPASS", "") else None
    if bundle_root is not None:
        candidates.append(bundle_root / ("skyshot.exe" if os.name == "nt" else "skyshot"))
    app_root = Path(__file__).resolve().parents[1]
    vendored_name = "skyshot.exe" if os.name == "nt" else "skyshot"
    candidates.append(app_root / "third_party" / "skyshot" / "target" / "release" / vendored_name)
    for name in ("skyshot", "skyshot.exe"):
        located = shutil.which(name)
        if located:
            candidates.append(located)

    skyshot_repo = app_root.parent / "skyshot-solver-main"
    candidates.extend((
        Path.home() / ".cargo" / "bin" / "skyshot",
        skyshot_repo / "target" / "release" / "skyshot",
        skyshot_repo / "target" / "debug" / "skyshot",
    ))
    for candidate in candidates:
        path = os.path.abspath(os.fspath(candidate))
        if os.path.isfile(path) and (os.name == "nt" or os.access(path, os.X_OK)):
            return path
    raise RuntimeError("Nie wykryto Skyshot Solver w PATH ani w repozytorium Skyshot obok aplikacji.")


def resolve_skyshot_index(index=""):
    candidates = []
    for requested in (os.environ.get("SKYSHOT_INDEX", ""), index):
        requested = str(requested or "").strip()
        if requested:
            candidates.append(Path(os.path.expanduser(requested)))

    home = Path.home()
    app_root = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        app_data = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif sys.platform == "darwin":
        app_data = home / "Library" / "Application Support"
    else:
        app_data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    data_roots = (
        app_data / "astro-ai-processor" / "skyshot" / "indexes",
        home / ".local" / "share" / "skyshot",
        home / "Documents" / "skyshot",
        home / "Documents" / "skyshot-solver-main" / "data",
        home / "Downloads" / "skyshot",
        home / "Downloads",
        Path.cwd() / "data",
        app_root / "data",
        app_root.parent / "skyshot-solver-main" / "data",
    )
    for root in data_roots:
        candidates.extend((root, root / "index"))
        if root.is_dir():
            try:
                candidates.extend(path.parent for path in root.glob("*/index/manifest.json"))
                candidates.extend(path.parent for path in root.glob("*/manifest.json"))
            except OSError:
                pass

    for candidate in candidates:
        path = candidate.resolve()
        if path.is_dir() and (path / "manifest.json").is_file():
            return str(path)
    raise RuntimeError("Nie wykryto katalogu indeksu Skyshot. Pobierz indeks Full ze strony Skyshot i umieść go w katalogu danych Skyshot.")


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
    try:
        index_path = Path(resolve_skyshot_index(index))
    except RuntimeError:
        from processing.skyshot_data import ensure_default_skyshot_index

        index_path = Path(ensure_default_skyshot_index(progress))
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
        result["skyshot_index"] = str(index_path)
        if progress:
            progress("Skyshot: solved.", 100, 100)
        return result
