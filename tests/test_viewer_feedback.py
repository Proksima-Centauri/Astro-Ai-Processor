import os
from pathlib import Path
import subprocess
import sys


def test_compare_viewer_pan_scrubbing_and_status_feedback():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import os
import sys
import tempfile

from PyQt5.QtTest import QTest
from PyQt5.QtGui import QMouseEvent

home = tempfile.TemporaryDirectory()
os.environ["HOME"] = home.name
os.environ["XDG_CONFIG_HOME"] = os.path.join(home.name, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(home.name, "data")

spec = importlib.util.spec_from_file_location("astro_viewer_feedback_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])

viewer = module.BlendViewer()
viewer.resize(900, 650)
viewer.set_before(module.QPixmap(1600, 1200))
viewer.set_after(module.QPixmap(1600, 1200))
viewer.set_compare_enabled(True)
viewer.show()
app.processEvents()

assert viewer.compare_controls.isVisible()
assert viewer.compare_before_label.text() == "Przed"
assert viewer.compare_after_label.text() == "Po"
assert viewer.compare_position_label.text() == "50%"
viewer.set_language("en")
assert viewer.compare_before_label.text() == "Before"
assert viewer.compare_after_label.text() == "After"
viewer.set_language("pl")

viewport = viewer.view.viewport()
center_y = viewport.rect().center().y()
initial_slider_value = viewer.slider.value()
QTest.mouseClick(viewport, module.Qt.LeftButton, pos=module.QPoint(5, center_y))
assert viewer.slider.value() == initial_slider_value

handle_x = viewer._compare_handle_x()
QTest.mousePress(viewport, module.Qt.LeftButton, pos=module.QPoint(handle_x, center_y))
QTest.mouseMove(viewport, module.QPoint(handle_x + 60, center_y), 20)
QTest.mouseRelease(viewport, module.Qt.LeftButton, pos=module.QPoint(handle_x + 60, center_y))
app.processEvents()
assert viewer.slider.value() > initial_slider_value
assert viewer.compare_position_label.text() == f"{viewer.slider.value()}%"

hbar = viewer.view.horizontalScrollBar()
hbar.setValue((hbar.minimum() + hbar.maximum()) // 2)
old_scroll = hbar.value()
pan_start = viewport.rect().center()
QTest.mousePress(viewport, module.Qt.MiddleButton, pos=pan_start)
assert viewer._pan_active
pan_end = pan_start + module.QPoint(-35, 0)
move_event = QMouseEvent(
    module.QEvent.MouseMove,
    module.QPointF(pan_end),
    module.Qt.NoButton,
    module.Qt.MiddleButton,
    module.Qt.NoModifier,
)
assert viewer.eventFilter(viewport, move_event)
scroll_after_move = hbar.value()
QTest.mouseRelease(viewport, module.Qt.MiddleButton, pos=pan_end)
app.processEvents()
assert scroll_after_move != old_scroll
scroll_before_space_pan = hbar.value()
QTest.keyPress(viewer.view, module.Qt.Key_Space)
QTest.mousePress(viewport, module.Qt.LeftButton, pos=pan_start)
assert viewer._pan_active
space_pan_end = pan_start + module.QPoint(25, 0)
space_move_event = QMouseEvent(
    module.QEvent.MouseMove,
    module.QPointF(space_pan_end),
    module.Qt.NoButton,
    module.Qt.LeftButton,
    module.Qt.NoModifier,
)
assert viewer.eventFilter(viewport, space_move_event)
assert hbar.value() != scroll_before_space_pan
QTest.mouseRelease(viewport, module.Qt.LeftButton, pos=space_pan_end)
QTest.keyRelease(viewer.view, module.Qt.Key_Space)
assert not viewer._space_pan_active
viewer.close()

window = module.AstroApp()
image = module.np.array([[[1, 2, 3], [10, 20, 30]], [[4, 5, 6], [7, 8, 9]]], dtype=module.np.uint16)
window.magic_img = image
window.original_img = image
window._native_loaded_image = image
window.viewer.view.set_pixmap(module.QPixmap(2, 2))
window._update_viewer_status((1, 0))
assert window.status_coordinates_label.text() == "X: 1  Y: 0"
assert window.status_pixel_label.text() == "RGB: 30, 20, 10"
assert window.status_size_label.text() == "2 × 2"
window.log("Processing test")
assert window.status_operation_label.text() == "Processing test"
window.viewer.view.zoom_in()
assert window.status_zoom_label.text() != "Zoom: 100%"
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
