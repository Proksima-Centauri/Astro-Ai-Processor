import os
from pathlib import Path
import subprocess
import sys


def test_missing_skyshot_is_reported_once_for_automatic_solves():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("astro_app_plate_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()
window.original_img = object()
window._build_plate_solve_result_from_current_fits_header = lambda: None
def missing_solver(_path):
    raise RuntimeError("Skyshot missing")

module.resolve_skyshot = missing_solver
logs = []
window.log = lambda message, level="info": logs.append((message, level))

window.run_plate_solve(automatic=True)
window.run_plate_solve(automatic=True)
assert logs == [("Automatic Plate Solving unavailable: Skyshot missing", "info")]

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
        timeout=60,
    )
