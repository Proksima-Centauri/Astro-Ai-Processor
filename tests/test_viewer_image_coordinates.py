import os
from pathlib import Path
import subprocess
import sys


def test_viewer_maps_clicks_to_full_resolution_image_coordinates():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import sys

from PyQt5.QtTest import QTest

spec = importlib.util.spec_from_file_location("astro_app_viewer_coordinates_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
view = module.SingleViewer()
view.resize(640, 480)
view.set_pixmap(module.QPixmap(1200, 800))
view.set_image_size_provider(lambda: (3000, 2000))
view.show()
app.processEvents()

expected_fit = min(
    view.viewport().width() / 1200,
    view.viewport().height() / 800,
)
assert abs(view.scale_factor - expected_fit) < 1e-9

view.set_pick_mode(True)
selected = []
view.imageClicked.connect(lambda x, y: selected.append((x, y)))

def verify_click(pos):
    scene_pos = view.mapToScene(pos)
    pixmap_pos = view._pixmap_item.pos()
    display_x = scene_pos.x() - pixmap_pos.x()
    display_y = scene_pos.y() - pixmap_pos.y()
    expected = (
        round(display_x * 2999 / 1199),
        round(display_y * 1999 / 799),
    )
    QTest.mouseClick(view.viewport(), module.Qt.LeftButton, pos=pos)
    assert selected[-1] == expected, (selected[-1], expected)

verify_click(view.viewport().rect().center())
view.resize(800, 600)
app.processEvents()
resized_fit = min(
    view.viewport().width() / 1200,
    view.viewport().height() / 800,
)
assert abs(view.scale_factor - resized_fit) < 1e-9

view.zoom_in()
view.zoom_in()
view.pan_by(37, -19)
app.processEvents()
verify_click(view.viewport().rect().center())
view.close()
'''
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_loading_image_uses_siril_linear_display_mode():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import os
import sys
import tempfile

home = tempfile.TemporaryDirectory()
os.environ["HOME"] = home.name
os.environ["XDG_CONFIG_HOME"] = os.path.join(home.name, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(home.name, "data")

spec = importlib.util.spec_from_file_location("astro_app_viewer_mode_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()
window.run_plate_solve = lambda automatic=False: False
image_path = os.path.join("tests", "fixtures", "color16_5x5.tiff")

assert window.load_image_from_path(image_path)
assert window.display_stretch_mode == "linear"
assert window.combo_stretch_bottom.currentData() == "linear"

window.apply_stretch("autostretch", commit=False)
assert window.display_stretch_mode == "autostretch"
assert window.load_image_from_path(image_path)
assert window.display_stretch_mode == "linear"
assert window.combo_stretch_bottom.currentData() == "linear"
assert module.GLOBAL_DISPLAY_STRETCH_MODE == "linear"

window.close()
home.cleanup()
'''
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
