"""First-use installation of the pinned Skyshot Full index into user data."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time


_INDEX_INSTALL_LOCK = threading.Lock()
_SKYSHOT_RELEASE_ID = "skyshot-data-2026.10.17.2"
_SKYSHOT_ENGINE_VERSION = "0.1.0"


def skyshot_data_home() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "astro-ai-processor" / "skyshot"


def _installer_resources():
    frozen_root = getattr(sys, "_MEIPASS", "")
    if frozen_root:
        root = Path(frozen_root) / "skyshot_runtime"
    else:
        root = Path(__file__).resolve().parents[1] / "third_party" / "skyshot"
    tools = root / "tools"
    release = root / "provenance" / "data-releases" / "2026.10.17.2" / "release.json"
    if not tools.is_dir() or not release.is_file():
        raise RuntimeError("Skyshot index installer resources are missing from the application.")
    return tools, release


def _load_fetcher(tools: Path):
    location = str(tools)
    if location not in sys.path:
        sys.path.insert(0, location)
    return importlib.import_module("fetch_data")


def _find_installed_full(destination_root: Path):
    for destination in sorted(destination_root.glob(f"{_SKYSHOT_RELEASE_ID}-full*")):
        installation_path = destination / "INSTALLATION.json"
        index_path = destination / "index"
        try:
            installation = json.loads(installation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            installation.get("release_id") == _SKYSHOT_RELEASE_ID
            and installation.get("engine_version") == _SKYSHOT_ENGINE_VERSION
            and installation.get("preset") == "full"
            and (index_path / "manifest.json").is_file()
        ):
            return index_path
    return None


def ensure_default_skyshot_index(progress=None, *, fetcher=None, data_home=None, release_path=None) -> str:
    """Return a verified local Full index, fetching the pinned public bundle if absent.

    The archive is downloaded over HTTPS and verified by Skyshot's upstream
    installer against the bundled release catalogue (size, SHA256 and file
    manifests). The data remain under user-data, never in the application repo.
    The upstream preview index carries its own non-commercial data-use terms.
    """
    if fetcher is None or release_path is None:
        tools, bundled_release = _installer_resources()
    else:
        tools, bundled_release = None, Path(release_path)
    release_file = Path(release_path) if release_path is not None else bundled_release
    installer = fetcher if fetcher is not None else _load_fetcher(tools)
    release = json.loads(release_file.read_text(encoding="utf-8"))
    release_id = str(release.get("release_id") or "")
    if release_id != _SKYSHOT_RELEASE_ID:
        raise RuntimeError("Bundled Skyshot data catalogue has an unexpected release ID.")

    home = Path(data_home) if data_home is not None else skyshot_data_home()
    destination_root = home / "indexes"
    cache = home / "download-cache" / release_id
    with _INDEX_INSTALL_LOCK:
        installed = _find_installed_full(destination_root)
        if installed is not None:
            return str(installed)
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / f"{release_id}-full"
        if destination.exists():
            destination = destination_root / f"{release_id}-full-retry-{time.time_ns()}"

        if progress:
            progress(
                "Downloading Skyshot Full index (about 0.84 GB). Non-commercial data-use terms apply: skyshot.app/downloads",
                5,
                0,
            )

        def report(name, received, total):
            if progress:
                percent = int(max(0, min(100, received * 100 / max(1, total))))
                progress(f"Skyshot index: {name} ({percent}%)", 10 + percent * 75 // 100, percent)

        try:
            installer.fetch_and_install(
                release_file,
                cache,
                destination,
                "full",
                _SKYSHOT_ENGINE_VERSION,
                progress=report,
            )
        except Exception as exc:
            raise RuntimeError(f"Automatic Skyshot index installation failed: {exc}") from None

        installed = _find_installed_full(destination_root)
        if installed is None:
            raise RuntimeError("Skyshot index download finished without a verified installation receipt.")
        if progress:
            progress("Skyshot Full index installed and verified.", 90, 100)
        return str(installed)
