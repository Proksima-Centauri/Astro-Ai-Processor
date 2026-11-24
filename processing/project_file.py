"""Portable, non-pickle Astro AI Processor project container."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

PROJECT_EXTENSION = ".aap"
PROJECT_FORMAT = "astro-ai-processor-project"
PROJECT_FORMAT_VERSION = 1
MAX_PROJECT_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_PROJECT_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
MAX_PROJECT_ENTRIES = 10000


class ProjectFileError(ValueError):
    """Invalid or unsupported project container."""


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_member_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not name
        or ".." in path.parts
        or "\\" in name
        or name.startswith("/")
        or re.match(r"^[A-Za-z]:", name)
    ):
        raise ProjectFileError("Project contains an unsafe ZIP path.")
    return str(path)


def _image_png(array):
    arr = np.asarray(array)
    if arr.size == 0:
        return None
    if arr.ndim == 2:
        lo, hi = np.nanpercentile(arr.astype(np.float32), (1, 99.5))
        shown = np.zeros(arr.shape, np.uint8) if hi <= lo else np.clip((arr - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
        shown = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    else:
        shown = arr[..., :3].astype(np.float32)
        lo, hi = np.nanpercentile(shown, (1, 99.5))
        shown = np.zeros_like(shown, np.uint8) if hi <= lo else np.clip((shown - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
    h, w = shown.shape[:2]
    scale = min(256 / max(1, w), 256 / max(1, h), 1.0)
    if scale < 1:
        shown = cv2.resize(shown, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".png", shown)
    return encoded.tobytes() if ok else None


def save_project(path, state):
    """Atomically write a state dictionary as a compressed .aap ZIP."""
    target = Path(path).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    now = _timestamp()
    state = dict(state or {})
    arrays = {}
    counter = 0

    def encode(value, key_path=""):
        nonlocal counter
        if isinstance(value, np.ndarray):
            counter += 1
            leaf = key_path.split(".")[-1]
            safe_leaf = re.sub(r"[^A-Za-z0-9_.-]+", "_", leaf).strip("._") or f"layer_{counter}"
            if key_path == "original_img":
                name, kind = "base.fits", "fits"
            elif key_path == "magic_img":
                name, kind = "current.fits", "fits"
            elif ".layer_images." in f".{key_path}." or key_path.startswith("layer_images."):
                name, kind = f"layers/{safe_leaf}.npy", "npy"
            elif ".layer_masks." in f".{key_path}." or key_path.startswith("layer_masks."):
                name, kind = f"masks/{safe_leaf}.npy", "npy"
            else:
                name, kind = f"arrays/array_{counter:06d}.npy", "npy"
            if kind == "fits" and value.dtype == np.float32:
                try:
                    import io
                    from astropy.io import fits
                    buffer = io.BytesIO()
                    fits.PrimaryHDU(data=np.ascontiguousarray(value)).writeto(buffer)
                    arrays[name] = buffer.getvalue()
                    return {"__fits__": name}
                except Exception:
                    pass
            # Preserve non-float32 source formats losslessly as NPY.
            if kind == "fits":
                name = f"arrays/array_{counter:06d}.npy"
            arrays[name] = value
            return {"__array__": name}
        if isinstance(value, dict):
            return {str(k): encode(v, f"{key_path}.{k}" if key_path else str(k)) for k, v in value.items() if not str(k).startswith("__")}
        if isinstance(value, (list, tuple)):
            return [encode(v, key_path) for v in value]
        if isinstance(value, np.generic):
            return encode(value.item(), key_path)
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, (str, int, bool)) or value is None:
            return value
        # Qt and other runtime objects are not portable; known pixmaps are skipped.
        return None

    image = state.get("magic_img")
    encoded_state = encode(state)
    metadata = {
        "format": PROJECT_FORMAT,
        "format_version": PROJECT_FORMAT_VERSION,
        "app_version": str(state.pop("app_version", "")),
        "created": str(state.pop("created", None) or now),
        "modified": now,
        "image_size": list(image.shape[:2][::-1]) if isinstance(image, np.ndarray) else None,
        "settings": {
            key: encoded_state.get(key)
            for key in ("display_stretch_mode", "display_stretch_linked", "channel_visibility", "layer_visibility")
            if key in encoded_state
        },
        "layers": [
            {
                "name": name,
                "title": (state.get("layer_titles") or {}).get(name, name),
                "type": (state.get("layer_types") or {}).get(name),
                "visible": (state.get("layer_visibility") or {}).get(name, True),
                "has_image": name in (state.get("layer_images") or {}),
                "has_mask": name in (state.get("layer_masks") or {}),
            }
            for name in dict.fromkeys([
                *(state.get("layer_order") or []),
                *(state.get("layer_images") or {}).keys(),
                *(state.get("layer_masks") or {}).keys(),
            ])
        ],
        "processing_history": encoded_state.get("processing_history", []),
        "plate_solve_result": encoded_state.get("latest_plate_solve_result"),
        "state": encoded_state,
    }
    thumbnail = _image_png(image) if isinstance(image, np.ndarray) else None
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("project.json", json.dumps(metadata, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            for name, array in arrays.items():
                if isinstance(array, bytes):
                    archive.writestr(name, array)
                else:
                    import io
                    buffer = io.BytesIO()
                    np.save(buffer, array, allow_pickle=False)
                    archive.writestr(name, buffer.getvalue())
            if thumbnail:
                archive.writestr("thumbnail.png", thumbnail)
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return str(target)


def load_project(path):
    """Read and validate a project, returning its state dictionary."""
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectFileError(f"Could not read project ZIP: {exc}") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_PROJECT_ENTRIES:
            raise ProjectFileError("Project contains too many files.")
        total = 0
        info_by_name = {}
        for info in infos:
            name = _safe_member_name(info.filename)
            total += info.file_size
            if info.file_size > MAX_PROJECT_FILE_BYTES or total > MAX_PROJECT_TOTAL_BYTES:
                raise ProjectFileError("Project exceeds the allowed uncompressed size.")
            info_by_name[name] = info
        if "project.json" not in info_by_name:
            raise ProjectFileError("Project is missing project.json.")
        try:
            metadata = json.loads(archive.read(info_by_name["project.json"]).decode("utf-8"))
        except Exception as exc:
            raise ProjectFileError("Project metadata is invalid.") from exc
        if metadata.get("format") != PROJECT_FORMAT:
            raise ProjectFileError("This file is not an Astro AI Processor project.")
        version = metadata.get("format_version")
        if not isinstance(version, int) or version > PROJECT_FORMAT_VERSION:
            raise ProjectFileError(f"This project uses a newer format version ({version}). Update Astro AI Processor.")
        if version < 1:
            raise ProjectFileError(f"Unsupported project format version ({version}).")
        # Migration dispatch point for future older versions.
        raw_state = metadata.get("state", {})

        def decode(value):
            if isinstance(value, dict):
                if set(value) == {"__array__"}:
                    name = _safe_member_name(value["__array__"])
                    info = info_by_name.get(name)
                    if info is None:
                        raise ProjectFileError("Project references a missing array.")
                    try:
                        import io
                        return np.load(io.BytesIO(archive.read(info)), allow_pickle=False)
                    except Exception as exc:
                        raise ProjectFileError("Project contains an invalid array.") from exc
                if set(value) == {"__fits__"}:
                    name = _safe_member_name(value["__fits__"])
                    info = info_by_name.get(name)
                    if info is None:
                        raise ProjectFileError("Project references a missing image.")
                    try:
                        import io
                        from astropy.io import fits
                        with fits.open(io.BytesIO(archive.read(info)), memmap=False) as hdus:
                            return np.array(hdus[0].data, copy=True)
                    except Exception as exc:
                        raise ProjectFileError("Project contains an invalid FITS image.") from exc
                return {key: decode(item) for key, item in value.items()}
            if isinstance(value, list):
                return [decode(item) for item in value]
            return value

        state = decode(raw_state)
        state["project_created"] = metadata.get("created")
        state["project_modified"] = metadata.get("modified")
        state["project_thumbnail"] = archive.read("thumbnail.png") if "thumbnail.png" in info_by_name else None
        return state
