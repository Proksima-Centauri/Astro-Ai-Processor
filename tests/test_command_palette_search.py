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
