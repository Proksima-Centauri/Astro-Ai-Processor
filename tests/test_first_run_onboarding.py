import os
from pathlib import Path
import subprocess
import sys


def test_first_run_setup_and_tour_persist_completion():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import json
import os
import sys
import tempfile
from unittest.mock import patch

home = tempfile.TemporaryDirectory()
os.environ["HOME"] = home.name
os.environ["XDG_CONFIG_HOME"] = os.path.join(home.name, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(home.name, "data")

spec = importlib.util.spec_from_file_location("astro_app_onboarding_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
assert module.load_config()["onboarding_completed"] is False

config_path = module.get_config_path()
os.makedirs(os.path.dirname(config_path), exist_ok=True)
with open(config_path, "w", encoding="utf-8") as config_file:
    json.dump({"language": "pl"}, config_file)
assert module.load_config()["onboarding_completed"] is True
os.remove(config_path)

window = module.AstroApp()
window.resize(1100, 700)
window.show()
app.processEvents()

def accept_setup(dialog):
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    dialog.theme_combo.setCurrentText("Graphite")
    return module.QDialog.Accepted

with patch.object(module.FirstRunSetupDialog, "exec_", accept_setup):
    window._start_first_run_onboarding()
app.processEvents()
assert window.language == "en"
assert window.theme_name == "Graphite"
tour = window._first_run_tour
assert tour.isVisible()
assert tour.card_title.text() == "Welcome to Astro AI Processor"
assert tour._highlight_rect.isValid()
assert tour._accent == module.get_accent_colors(window.accent_name)
editor_step = next(
    index for index, step in enumerate(tour.steps) if step.get("editor_screen")
)
assert tour.steps[editor_step]["target"] is window.menuBar()
tour.show_step(editor_step)
app.processEvents()
assert window.screen_stack.currentWidget() is window.editor_page
assert tour._highlight_rect == module.QRect(
    window.menuBar().mapTo(window, module.QPoint(0, 0)),
    window.menuBar().size(),
).adjusted(-10, -8, 10, 8)

for _ in range(editor_step, len(tour.steps)):
    tour.next_step()
    app.processEvents()

assert window.onboarding_completed
assert window.screen_stack.currentWidget() is window.editor_page
with open(config_path, encoding="utf-8") as config_file:
    saved_config = json.load(config_file)
assert saved_config["onboarding_completed"] is True
assert saved_config["language"] == "en"
assert saved_config["theme_name"] == "Graphite"

window.denoise_model_path = "/tmp/custom-denoise.onnx"
window.apply_preferences(
    theme_name="Midnight",
    language="pl",
    openrouter_api_key="test-key",
)
with patch.object(
    module.QMessageBox,
    "question",
    return_value=module.QMessageBox.No,
):
    window._clear_application_config()
assert window.theme_name == "Midnight"
assert window.openrouter_api_key == "test-key"

with patch.object(
    module.QMessageBox,
    "question",
    return_value=module.QMessageBox.Yes,
):
    window._clear_application_config()
assert window.theme_name == "Fusion Dark"
assert window.language == "pl"
assert window.denoise_model_path is None
assert window.openrouter_api_key == ""
assert window.onboarding_completed is False
with open(config_path, encoding="utf-8") as config_file:
    reset_config = json.load(config_file)
assert reset_config["theme_name"] == "Fusion Dark"
assert reset_config["accent_name"] == "Ultra Blue"
assert reset_config["language"] == "pl"
assert reset_config["denoise_model_path"] is None
assert reset_config["openrouter_api_key"] == ""
assert reset_config["recent_images"] == []
assert reset_config["onboarding_completed"] is False
restarted_window = module.AstroApp()
assert restarted_window.onboarding_completed is False
restarted_window.close()
window.close()
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
        timeout=90,
    )
