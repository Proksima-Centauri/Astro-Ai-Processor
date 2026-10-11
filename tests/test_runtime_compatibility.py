import ast
import importlib.util
import os
import subprocess
import sys
import typing
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "Astro Ai Processor.py"
APP_SPEC = importlib.util.spec_from_file_location("astro_runtime_compatibility_tests", APP_PATH)
APP_MODULE = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = APP_MODULE
APP_SPEC.loader.exec_module(APP_MODULE)


def test_image_layer_forward_reference_resolves_after_import():
    hints = typing.get_type_hints(APP_MODULE.Fly3DDialog._build_motion_preview_layers)

    assert hints["return"] == tuple[np.ndarray, list[APP_MODULE.ImageLayer], list[str]]
    assert typing.get_type_hints(APP_MODULE.style_rgb_channel_checkbox)["checkbox"] is APP_MODULE.QCheckBox


def test_classes_have_no_shadowed_method_definitions():
    source = ast.parse(APP_PATH.read_text(encoding="utf-8-sig"))
    duplicates = []
    for node in ast.walk(source):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = set()
        for member in node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if member.name in methods:
                duplicates.append(f"{node.name}.{member.name}")
            methods.add(member.name)

    assert not duplicates, duplicates


def test_qt_logging_without_a_console(monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "__stderr__", None)

    APP_MODULE._qt_message_handler(None, None, "Qt runtime diagnostic")


def test_unicode_image_io_preserves_16bit_rgba(tmp_path):
    path = tmp_path / "Zdjęcie Łódź ąę.png"
    image = np.arange(6 * 8 * 4, dtype=np.uint16).reshape(6, 8, 4) * 257

    assert APP_MODULE.safe_imwrite(str(path), image)
    restored = APP_MODULE.safe_imread(str(path), APP_MODULE.cv2.IMREAD_UNCHANGED)

    np.testing.assert_array_equal(restored, image)


def test_failed_save_keeps_the_previous_document_path(tmp_path):
    from types import SimpleNamespace

    app = SimpleNamespace(
        processed_img=np.zeros((6, 8, 3), dtype=np.uint8),
        current_save_path="previous.png",
        log=lambda *_args, **_kwargs: None,
    )

    APP_MODULE.AstroApp.save_image_to_path(app, str(tmp_path / "missing-folder" / "output.png"))

    assert app.current_save_path == "previous.png"


GUI_SMOKE_SCRIPT = r'''
import importlib.abc
import importlib.util
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np


class DisableOptionalAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "llama_cpp" or fullname.startswith("llama_cpp."):
            raise ImportError("llama.cpp is optional in the startup test")


if sys.argv[1] == "without-ai":
    sys.meta_path.insert(0, DisableOptionalAI())

root = Path.cwd()
spec = importlib.util.spec_from_file_location("astro_gui_smoke", root / "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
errors = []
sys.excepthook = lambda *error: errors.append("".join(traceback.format_exception(*error)))
app = module.QApplication([])
module.load_config = lambda: {}
module.save_config = lambda *args, **kwargs: None
window = module.AstroApp()
try:
    window.show()
    app.processEvents()
    assert window.ai_assistant_panel.input_text.isEnabled()
    assert not window.ai_assistant_panel.input_text.isReadOnly()
    with tempfile.TemporaryDirectory() as directory:
        for fixture in sorted((root / "tests/fixtures").glob("*")):
            if fixture.suffix.lower() not in {".png", ".jpg", ".tiff", ".fit"}:
                continue
            target = Path(directory) / ("Zdjęcie Łódź " + fixture.name)
            shutil.copyfile(fixture, target)
            window.load_image_from_path(str(target))
            assert window.processed_img is not None, fixture.name
            assert window.current_image_path == str(target), fixture.name
            app.processEvents()

        image_path = Path(directory) / "Łódź source.png"
        source = np.arange(64 * 64 * 3, dtype=np.uint8).reshape(64, 64, 3)
        assert module.safe_imwrite(str(image_path), source)
        window.load_image_from_path(str(image_path))
        window.viewer.set_compare_enabled(True)
        view = window.viewer.view
        view.fit_to_window()
        for _ in range(4):
            view.zoom_in()
        view.pan_by(73, -41)
        app.processEvents()
        original_scale = view.transform().m11()
        original_center = view.mapToScene(view.viewport().rect().center())
        original_viewport_size = view.viewport().size()
        for mode in ("autostretch", "histogram", "linear"):
            window.apply_stretch(mode=mode, commit=False)
            app.processEvents()
            current_center = view.mapToScene(view.viewport().rect().center())
            assert abs(current_center.x() - original_center.x()) < 1.1, mode
            assert abs(current_center.y() - original_center.y()) < 1.1, mode
            assert abs(view.transform().m11() - original_scale) < 1e-9, mode
            assert view.viewport().size() == original_viewport_size, mode

        window.create_new_layer()
        window.select_layer(window.layer_order[-1])
        window.delete_selected_layer()
        for factory in (
            "_get_blur_dialog", "_get_background_extraction_dialog", "_get_deconvolution_dialog",
            "_get_local_contrast_dialog", "_get_crop_dialog", "_get_color_calibration_dialog",
            "_get_star_correction_dialog", "_get_plate_solve_dialog", "_get_starnet_dialog",
            "_get_deepsnr_dialog", "_get_mosaic_dialog", "_get_stack_dialog",
            "_get_solar_stack_dialog", "_get_timelapse_dialog", "_get_fly3d_dialog",
            "_get_star_shrink_dialog",
        ):
            dialog = getattr(window, factory)()
            assert dialog is not None, factory
            dialog.show()
            app.processEvents()
            dialog.hide()

        fly = window.fly3d_dialog
        zone_map = fly.zone_widget.zone_map
        zone_map.fill(-1)
        zone_map[16:32, 16:32] = 0
        fly._refresh_motion_layers(keep_selection=False)
        background, layers, warnings = fly._build_motion_preview_layers()
        assert background.shape == source.shape
        assert layers and all(isinstance(layer, module.ImageLayer) for layer in layers)
        assert not warnings, warnings

        output_path = Path(directory) / "Wynik Łódź.png"
        window.save_image_to_path(str(output_path))
        assert output_path.is_file()
        assert window.current_save_path == str(output_path)
finally:
    window.close()
    app.processEvents()
    for widget in app.topLevelWidgets():
        widget.close()
    app.processEvents()

assert not errors, "\n".join(errors)
print("Source application startup, dialogs, image I/O and shutdown OK")
'''


@pytest.mark.parametrize("mode", ["normal", "without-ai"])
def test_source_application_starts_loads_images_and_opens_tools(mode):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_SESSION_TYPE"] = "x11"
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", GUI_SMOKE_SCRIPT, mode],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Source application startup" in result.stdout
