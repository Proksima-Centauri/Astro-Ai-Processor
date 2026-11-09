import os
from pathlib import Path
import subprocess
import sys


def test_menu_navigation_and_shortcuts():
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
spec = importlib.util.spec_from_file_location("astro_app_menu_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()
window.language = "en"
window._update_ui_language()
window.show()
app.processEvents()
assert not window.menuBar().isVisible()
assert window.btn_more_top.text() == "More"
assert window.action_reset_topbar.text() == "Restore Default Toolbar Order"
assert window.tr("top_drag_hint", "Drag to reorder") in window.btn_open.toolTip(), (
    window.btn_open.toolTip(),
    window.tr("top_drag_hint", "Drag to reorder"),
)
assert list(window.top_menus) == [
    "file", "edit", "layers", "image", "filters", "ai", "astro", "view", "tools", "help"
]
assert len(window._top_button_icon_files.values()) == len(set(window._top_button_icon_files.values()))
default_toolbar_order = list(window.default_topbar_button_order)
window.topbar_button_order = list(reversed(default_toolbar_order))
window._apply_saved_topbar_button_order()
assert window._current_topbar_button_order() == list(reversed(default_toolbar_order))
window._save_topbar_button_order = lambda: None
window.action_reset_topbar.trigger()
assert window._current_topbar_button_order() == default_toolbar_order
for action, shortcut in (
    (window.action_open, "Ctrl+O"),
    (window.action_save, "Ctrl+S"),
    (window.action_save_as, "Ctrl+Shift+S"),
    (window.action_paste_layer, "Ctrl+V"),
    (window.action_exit, "Ctrl+Q"),
):
    assert action.shortcut().toString() == shortcut

window.language = "pl"
window._update_ui_language()
assert window.top_menus["file"].title() == "&Plik"
assert window.top_menus["layers"].title() == "&Warstwy"
assert window.top_menus["help"].title() == "Pomo&c"
assert window.action_reset_topbar.text() == "Przywróć domyślną kolejność paska"
assert window.btn_more_top.text() == "Więcej"
assert "Przeciągnij, aby zmienić kolejność" in window.btn_open.toolTip()
assert window.action_adjustment_levels.text() == "Warstwa korekcyjna: Poziomy"
assert window.action_levels.text() == "Poziomy"
window.language = "en"
window._update_ui_language()
assert window.top_menus["file"].title() == "&File"
assert window.top_menus["help"].title() == "&Help"
assert window.action_adjustment_levels.text() == "Levels Adjustment Layer"

window.screen_stack.setCurrentWidget(window.editor_page)
window.action_dashboard.trigger()
assert window.screen_stack.currentWidget() is window.dashboard_page

opened = []
original_exec = module.QDialog.exec_
module.QDialog.exec_ = lambda self: opened.append(self.windowTitle()) or module.QDialog.Accepted
window.show_3d_fly_help()
module.QDialog.exec_ = original_exec
assert opened == ["3D FLY Guide"]

messages = []
module.QMessageBox.information = lambda *args: messages.append(args[-1])
window.show_keyboard_shortcuts()
assert "Ctrl+O" in messages[-1]
module.QMessageBox.about = lambda *args: messages.append(args[-1])
window.show_about_dialog()
assert module.APP_VERSION in messages[-1]
window.close()
home.cleanup()
'''
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_SESSION_TYPE"] = ""
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
