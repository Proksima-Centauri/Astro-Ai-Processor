"""First-use installation of the pinned Skyshot Full index into user data."""
from __future__ import annotations

import errno
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
_EMPTY_LOCK_GRACE_SECONDS = 30
_DOWNLOAD_LOCK_WAIT_SECONDS = 60 * 60


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


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER means no such PID.
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno != errno.ESRCH
    return True


def _read_lock_owner(lock_path: Path):
    try:
        value = lock_path.read_text(encoding="ascii").strip()
        return int(value) if value else None
    except (OSError, ValueError):
        return None


def _remove_stale_download_lock(lock_path: Path) -> bool:
    """Remove only abandoned lock files; leave locks owned by live processes alone."""
    try:
        if lock_path.is_symlink():
            raise RuntimeError("Skyshot download lock must not be a symlink.")
        original_stat = lock_path.stat()
        original_contents = lock_path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return True
    except UnicodeError:
        return False
    except OSError:
        return False

    try:
        owner = int(original_contents) if original_contents else None
    except ValueError:
        owner = None

    if owner is not None:
        if _pid_is_running(owner):
            return False
    elif time.time() - original_stat.st_mtime < _EMPTY_LOCK_GRACE_SECONDS:
        # The installer creates the lock before writing its PID.
        return False

    try:
        current_stat = lock_path.stat()
        current_contents = lock_path.read_text(encoding="ascii").strip()
        if (
            current_stat.st_ino != original_stat.st_ino
            or current_stat.st_mtime_ns != original_stat.st_mtime_ns
            or current_contents != original_contents
        ):
            return False
        lock_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    return True


def _wait_for_download_lock(lock_path: Path, progress=None) -> None:
    deadline = time.monotonic() + _DOWNLOAD_LOCK_WAIT_SECONDS
    waiting_reported = False
    while not _remove_stale_download_lock(lock_path):
        if time.monotonic() >= deadline:
            raise RuntimeError("Another Skyshot index download still holds the lock after one hour.")
        if progress and not waiting_reported:
            progress("Waiting for another Skyshot index download to finish...", 5, 0)
            waiting_reported = True
        time.sleep(1)


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
            lock_path = cache / ".download.lock"
            cache.mkdir(parents=True, exist_ok=True)
            while True:
                _wait_for_download_lock(lock_path, progress)
                try:
                    installer.fetch_and_install(
                        release_file,
                        cache,
                        destination,
                        "full",
                        _SKYSHOT_ENGINE_VERSION,
                        progress=report,
                    )
                    break
                except FileExistsError:
                    # Another process can win between our check and the
                    # upstream installer's exclusive lock-file creation.
                    if not lock_path.exists() or _read_lock_owner(lock_path) == os.getpid():
                        raise
        except Exception as exc:
            raise RuntimeError(f"Automatic Skyshot index installation failed: {exc}") from None

        installed = _find_installed_full(destination_root)
        if installed is None:
            raise RuntimeError("Skyshot index download finished without a verified installation receipt.")
        if progress:
            progress("Skyshot Full index installed and verified.", 90, 100)
        return str(installed)
