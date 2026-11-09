import os
from pathlib import Path
import subprocess
import sys


def test_command_palette_fuzzy_matching_ranks_best_match_first():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("astro_app_command_palette_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
entries = [
    {"title_en": "Astro Upscale", "category_en": "AI"},
    {"title_en": "Upscale", "category_en": "AI"},
    {"title_en": "Open image", "category_en": "File", "pinned": True},
]
palette = module.CommandPaletteDialog(entries, lambda _prompt: None, lambda: None, language="en")
palette.search_edit.setText("upscle")
results = [
    palette.tools_list.item(index).text()
    for index in range(palette.tools_list.count())
]
assert results == ["Upscale", "Astro Upscale", "Open image"], results
palette.close()
app.quit()
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


def test_application_command_palette_contains_requested_commands():
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

spec = importlib.util.spec_from_file_location("astro_app_palette_coverage_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
window = module.AstroApp()

entries = {entry["title_en"]: entry for entry in window.command_palette_entries}
expected_actions = {
    "Histogram": "action_histogram",
    "Console": "action_console",
    "GHS Stretch": "action_ghs",
    "Correction": "action_correction",
    "SVG Brush": "action_svg_brush",
    "Time-lapse Movie": "action_timelapse",
    "Planetary Stack": "action_solar_stack",
    "Theme": "action_preferences",
    "Language": "action_preferences",
}
for title, action_name in expected_actions.items():
    assert title in entries, title
    assert entries[title]["action"] is getattr(window, action_name), title

window.command_palette_dialog.set_language("pl")
window.command_palette_dialog.search_edit.setText("planetary")
assert any(
    window.command_palette_dialog.tools_list.item(index).text() == "Stack planetarny"
    for index in range(window.command_palette_dialog.tools_list.count())
)
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
