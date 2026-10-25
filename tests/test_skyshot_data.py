import json
from pathlib import Path
from types import SimpleNamespace

from processing.skyshot_data import ensure_default_skyshot_index, _wait_for_download_lock


def test_default_index_is_fetched_once_and_reused(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    release = repo_root / "third_party/skyshot/provenance/data-releases/2026.10.17.2/release.json"
    data_home = tmp_path / "user-data"
    cache = data_home / "download-cache" / "skyshot-data-2026.10.17.2"
    cache.mkdir(parents=True)
    stale_lock = cache / ".download.lock"
    stale_lock.write_text("99999999\n", encoding="ascii")
    monkeypatch.setattr("processing.skyshot_data._pid_is_running", lambda _pid: False)
    progress_updates = []
    calls = []

    def fetcher(release_path, cache, destination, preset, engine_version, *, progress):
        calls.append((release_path, cache, destination, preset, engine_version))
        assert not (cache / ".download.lock").exists()
        destination.mkdir(parents=True)
        index = destination / "index"
        index.mkdir()
        (index / "manifest.json").write_text("{}", encoding="utf-8")
        (destination / "INSTALLATION.json").write_text(json.dumps({
            "release_id": "skyshot-data-2026.10.17.2",
            "engine_version": "0.1.0",
            "preset": "full",
        }), encoding="utf-8")
        progress("archive.tar.gz", 10, 10)

    installer = SimpleNamespace(fetch_and_install=fetcher)

    installed = ensure_default_skyshot_index(
        progress=lambda *update: progress_updates.append(update),
        fetcher=installer,
        data_home=data_home,
        release_path=release,
    )
    assert Path(installed).is_dir()
    assert len(calls) == 1
    assert calls[0][3:] == ("full", "0.1.0")
    assert progress_updates

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("a verified index should be reused")

    assert ensure_default_skyshot_index(
        fetcher=SimpleNamespace(fetch_and_install=unexpected_fetch),
        data_home=data_home,
        release_path=release,
    ) == installed


def test_live_download_lock_is_waited_out_without_removing_it(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    lock = cache / ".download.lock"
    lock.write_text("12345\n", encoding="ascii")
    progress_updates = []

    monkeypatch.setattr("processing.skyshot_data._pid_is_running", lambda _pid: True)

    def finish_other_download(_seconds):
        assert lock.exists()
        lock.unlink()

    monkeypatch.setattr("processing.skyshot_data.time.sleep", finish_other_download)
    _wait_for_download_lock(lock, lambda *update: progress_updates.append(update))

    assert not lock.exists()
    assert progress_updates[0][0].startswith("Waiting for another Skyshot")
