import os
from pathlib import Path
import subprocess
import sys


def test_deepsnr_ui_signals_do_not_pass_checked_state_as_strength():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import os
import sys
import tempfile

home = tempfile.TemporaryDirectory()
os.environ["HOME"] = home.name
os.environ["XDG_CONFIG_HOME"] = home.name + "/config"
os.environ["XDG_DATA_HOME"] = home.name + "/data"
spec = importlib.util.spec_from_file_location("astro_app_deepsnr_signal_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
calls = []
module.AstroApp.run_deepsnr = lambda self, strength=None: calls.append(strength)
window = module.AstroApp()
preferences = module.PreferencesDialog(window)
window.dashboard_run_deepsnr_button.click()
window.action_deepsnr.trigger()
preferences.btn_run_deepsnr_pref.click()
assert calls == [None, None, None], calls
preferences.close()
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
    )
