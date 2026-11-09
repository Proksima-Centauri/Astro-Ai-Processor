import os
from pathlib import Path
import subprocess
import sys


def test_p0_ui_regressions():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import os
import sys
import tempfile

import numpy as np

spec = importlib.util.spec_from_file_location("astro_app_p0_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()
fly_dialog = module.Fly3DDialog(np.zeros((24, 32, 3), dtype=np.uint8))
assert fly_dialog.stage_stack.count() == len(module.Fly3DStage)
assert fly_dialog.stage_nav.currentRow() == module.Fly3DStage.STAR_REMOVAL
assert "(opcjonalnie)" in fly_dialog.stage_nav.item(module.Fly3DStage.STAR_REMOVAL).text()
assert "etapu 2" in fly_dialog.stage1_guidance.text()
assert "Przeciagnij" in fly_dialog.motion_interaction_legend.text()
assert fly_dialog.stage_progress_bar.format() == "Etap %v z %m"
assert fly_dialog.stage_progress_bar.value() == 1
assert not fly_dialog.stage_back_button.isEnabled()
assert fly_dialog.stage_next_button.isEnabled()
fly_dialog.stage_next_button.click()
assert fly_dialog.stage_nav.currentRow() == module.Fly3DStage.ZONE_SELECTION
assert not fly_dialog.stage_next_button.isEnabled()
fly_dialog.stage_back_button.click()
assert fly_dialog.stage_nav.currentRow() == module.Fly3DStage.STAR_REMOVAL
fly_dialog._update_cut_sections_visibility(module.Fly3DStage.ZONE_SELECTION)
assert not fly_dialog.cuts_label.isHidden()
fly_dialog._update_run_button_visibility(module.Fly3DStage.AUDIO)
assert not fly_dialog.btn_run.isHidden()
fly_dialog.close()
assert window.star_halo_reduction_strength == 0.35
assert not hasattr(window.dashboard_altair_chat, "token_usage_bar")
assert not hasattr(window.photoshop_menu_dialog.panel, "blend_combo")
assert not hasattr(window.photoshop_menu_dialog.panel, "opacity_spin")
window._set_dashboard_tab(0)
assert not window.dashboard_search.isHidden()
for tab_index in (2, 3, 4):
    window._set_dashboard_tab(tab_index)
    assert window.dashboard_search.isHidden()

crop_dialog = module.CropDialog()
assert all(
    isinstance(spin, module.QSpinBox)
    for spin in (crop_dialog.spin_x, crop_dialog.spin_y, crop_dialog.spin_w, crop_dialog.spin_h)
)
assert [crop_dialog.combo_grid.itemData(i) for i in range(crop_dialog.combo_grid.count())] == [
    "none", "thirds", "golden", "cross", "diagonals"
]
crop_dialog.set_image(np.zeros((40, 60, 3), dtype=np.uint8))
crop_dialog.spin_x.setValue(58)
assert crop_dialog.spin_w.maximum() == 2
crop_dialog.spin_w.setValue(2)
assert crop_dialog.get_rect() == (58, 0, 2, 40)
observed_grid_modes = []
crop_dialog.gridChanged.connect(observed_grid_modes.append)
crop_dialog.combo_grid.setCurrentIndex(1)
assert observed_grid_modes == ["thirds"]

shrink_dialog = module.StarShrinkDialog()
shrink_dialog.reset_defaults()
assert shrink_dialog.get_values() == (0.6, 0.5)

correction_dialog = module.StarCorrectionDialog(lambda *args: None, lambda: None, lambda: None)
assert correction_dialog.get_values() == (0.0, 0.0, 0.35)
correction_dialog._reset()
assert correction_dialog.get_values() == (0.0, 0.0, 0.35)

window._start_deepsnr_progress_dialog()
assert window.progress_dialog.progress_overall.minimum() == 0
assert window.progress_dialog.progress_overall.maximum() == 0
assert window.progress_dialog.progress_current.minimum() == 0
assert window.progress_dialog.progress_current.maximum() == 0
window._stop_deepsnr_progress_dialog()

source = np.arange(12 * 10 * 3, dtype=np.uint8).reshape((10, 12, 3))
window.original_img = source.copy()
window.magic_img = source.copy()
window.processed_img = source.copy()
window._full_processing_dirty = False
window.channel_visibility = {"r": False, "g": True, "b": True}
visible = window.apply_channel_visibility(window.processed_img)
assert not np.array_equal(visible, source)
with tempfile.TemporaryDirectory() as output_dir:
    output_path = os.path.join(output_dir, "channels.png")
    window.save_image_to_path(output_path)
    np.testing.assert_array_equal(module.safe_imread(output_path), source)

window.processing_history = [
    {"id": 1, "parent_id": None, "name": "History test", "img": source.copy(), "magic_img": source.copy()}
]
window._update_thumbnails_view()
window.selected_thumbnail_index = -1
window.current_history_node_id = None
window.magic_img = np.zeros_like(source)
window.thumbnails_layout.itemAt(0).widget().thumbnail_clicked.emit(0)
np.testing.assert_array_equal(window.magic_img, source)
assert window.current_history_node_id == 1

failure_dialog = module.MagicProgressDialog(window)
failure_dialog.set_close_locked(True)
window.progress_dialog = failure_dialog
window._starnet_progress_dialog = failure_dialog
window.on_starnet_finished(None, "StarNet test failure", failure_dialog)
assert not failure_dialog._close_locked
failure_dialog.close()

window.close()
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
        timeout=60,
    )
