import json
from pathlib import Path
from types import SimpleNamespace

from processing.skyshot_data import ensure_default_skyshot_index


def test_default_index_is_fetched_once_and_reused(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    release = repo_root / "third_party/skyshot/provenance/data-releases/2026.10.17.2/release.json"
    data_home = tmp_path / "user-data"
    progress_updates = []
    calls = []

    def fetcher(release_path, cache, destination, preset, engine_version, *, progress):
        calls.append((release_path, cache, destination, preset, engine_version))
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
