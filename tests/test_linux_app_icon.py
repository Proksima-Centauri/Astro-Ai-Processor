import importlib.util
import sys
from pathlib import Path


INSTALLER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "linux" / "gui_installer.py"
INSTALLER_SPEC = importlib.util.spec_from_file_location("astro_linux_gui_installer_icon_test", INSTALLER_PATH)
INSTALLER_MODULE = importlib.util.module_from_spec(INSTALLER_SPEC)
sys.modules[INSTALLER_SPEC.name] = INSTALLER_MODULE
INSTALLER_SPEC.loader.exec_module(INSTALLER_MODULE)


def test_linux_bundle_icon_resolves_png_from_pyinstaller_internal_dir(tmp_path):
    internal_dir = tmp_path / "_internal"
    internal_dir.mkdir()
    icon_path = internal_dir / "favicon-32.png"
    icon_path.write_bytes(b"png")

    assert INSTALLER_MODULE.resolve_icon(tmp_path) == icon_path


def test_linux_bundle_icon_resolves_png_in_flat_legacy_layout(tmp_path):
    icon_path = tmp_path / "favicon-32.png"
    icon_path.write_bytes(b"png")

    assert INSTALLER_MODULE.resolve_icon(tmp_path) == icon_path
