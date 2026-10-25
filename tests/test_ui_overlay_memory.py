import os
from pathlib import Path
import subprocess
import sys


def test_large_plate_solve_overlay_is_bounded_and_kept_above_image():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("astro_app_overlay_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])

class CanvasFactory:
    _overlay_render_size = staticmethod(module.AstroApp._overlay_render_size)
    _new_overlay_canvas = module.AstroApp._new_overlay_canvas

size = CanvasFactory._overlay_render_size(20000, 12000)
assert max(size) == 4096
assert abs(size[0] / size[1] - 20000 / 12000) < 0.001
canvas, painter = CanvasFactory()._new_overlay_canvas(20000, 12000)
assert (canvas.width(), canvas.height()) == size
painter.end()

viewer = module.BlendViewer()
viewer.set_before(module.QPixmap(1000, 800))
viewer.set_overlay_pixmap(module.QPixmap(100, 80))
item = viewer.view._overlay_item
assert item is not None
assert abs(item.transform().m11() - 10.0) < 1e-9
assert abs(item.transform().m22() - 10.0) < 1e-9
assert item.zValue() > viewer.view._pixmap_item.zValue()
assert item.acceptedMouseButtons() == module.Qt.NoButton
viewer.clear_overlay()
assert viewer.view._overlay_item is None

temporary_home = tempfile.TemporaryDirectory()
os.environ["HOME"] = temporary_home.name
os.environ["XDG_CONFIG_HOME"] = temporary_home.name + "/config"
os.environ["XDG_DATA_HOME"] = temporary_home.name + "/data"
window = module.AstroApp()
assert not window.btn_grid_overlay_bottom.isEnabled()
window.latest_plate_solve_result = {"solution": {}}
window._sync_plate_overlay_controls()
assert window.btn_grid_overlay_bottom.isEnabled()
window.btn_grid_overlay_bottom.click()
assert window.layer_visibility["grid_overlay"]
window.btn_object_overlay_bottom.click()
assert window.layer_visibility["object_labels"]
assert window.layer_visibility["plate_solve_overlay"]
assert window.plate_solving_dialog.chk_grid_overlay.isChecked()
assert window.plate_solving_dialog.chk_annotate_overlay.isChecked()
window.close()
temporary_home.cleanup()
'''
    env = os.environ.copy()
    env["XDG_SESSION_TYPE"] = ""
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
