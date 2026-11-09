import os
from pathlib import Path
import subprocess
import sys


def test_toolbar_limits_favorites_and_overflows_for_narrow_windows():
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
spec = importlib.util.spec_from_file_location("astro_app_toolbar_overflow_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()
window.screen_stack.setCurrentWidget(window.editor_page)
window.resize(1600, 900)
window.show()
app.processEvents()

buttons = [
    getattr(window, name)
    for name in window.default_topbar_button_order
]
visible_count = sum(button.isVisible() for button in buttons)
assert visible_count == 10, visible_count
assert window.topbar_overflow_menu.actions()
assert len(window.topbar_overflow_menu.actions()) == len(buttons) - visible_count

window.top_actions_bar.setFixedWidth(390)
app.processEvents()
visible_count = sum(button.isVisible() for button in buttons)
assert 0 < visible_count < 10, visible_count
overflow_names = [action.text() for action in window.topbar_overflow_menu.actions()]
hidden_names = [
    button.accessibleName()
    for button in buttons
    if not button.isVisible()
]
assert overflow_names == hidden_names, (overflow_names, hidden_names)

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
        timeout=60,
    )
