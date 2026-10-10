import importlib.util
import sys
from pathlib import Path

import pytest


APP_PATH = Path(__file__).resolve().parents[1] / "Astro Ai Processor.py"
APP_MODULE_NAME = "astro_ai_processor_file_search_tests"
APP_SPEC = importlib.util.spec_from_file_location(APP_MODULE_NAME, APP_PATH)
APP_MODULE = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_MODULE_NAME] = APP_MODULE
APP_SPEC.loader.exec_module(APP_MODULE)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("otwóż mi obraz m42_stacked.tif", "m42_stacked.tif"),
        ('Otwórz plik "M42 stack.tif"', "M42 stack.tif"),
        ("wczytaj obraz /home/astro/M42.fit", "/home/astro/M42.fit"),
        ("open image nebula.fits", "nebula.fits"),
        ("otwórz obraz NGC2929", "NGC2929"),
        ("otwórz obraz NGC 2929", "NGC 2929"),
        ("otwórz mi ngc2929", "ngc2929"),
        ("czy ten plik m42.tif jest dobry?", ""),
        ("otwórz dokument notes.txt", ""),
    ],
)
def test_extract_image_open_request(message, expected):
    assert APP_MODULE.extract_image_open_request(message) == expected


def test_find_image_paths_by_exact_name_is_case_insensitive_and_recursive(tmp_path):
    image_dir = tmp_path / "Pictures" / "Nebulae"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "M42_Stacked.TIF"
    image_path.write_bytes(b"test image")

    matches = APP_MODULE.find_image_paths_by_name("m42_stacked.tif", [str(tmp_path)])

    assert matches == [str(image_path)]


def test_find_image_paths_does_not_match_different_names_or_non_images(tmp_path):
    (tmp_path / "m42_stacked.tif.backup").write_bytes(b"not an image")
    (tmp_path / "m42_stacked.txt").write_text("not an image", encoding="utf-8")

    assert APP_MODULE.find_image_paths_by_name("m42_stacked.tif", [str(tmp_path)]) == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("otwóż mi klatkę o numerze 87", "87"),
        ("wczytaj frame number 12", "12"),
        ("otwórz obraz NGC 2929", ""),
    ],
)
def test_extract_frame_number_open_request(message, expected):
    assert APP_MODULE.extract_frame_number_open_request(message) == expected


def test_find_image_paths_can_search_by_exact_stem_or_frame_number(tmp_path):
    (tmp_path / "NGC2929.fit").write_bytes(b"fits")
    (tmp_path / "Light_Ngc223_87.fit").write_bytes(b"frame")
    (tmp_path / "Light_Ngc223_187.fit").write_bytes(b"other frame")

    assert APP_MODULE.find_image_paths_by_name("ngc2929", [str(tmp_path)]) == [str(tmp_path / "NGC2929.fit")]
    assert APP_MODULE.find_image_paths_by_name("87", [str(tmp_path)], match_mode="frame") == [
        str(tmp_path / "Light_Ngc223_87.fit")
    ]


def test_find_image_paths_returns_case_variants_from_separate_catalogs(tmp_path):
    first = tmp_path / "catalog-a" / "ngc2929.tif"
    second = tmp_path / "catalog-b" / "NGC2929.TIF"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    assert APP_MODULE.find_image_paths_by_name("ngc2929", [str(tmp_path)]) == sorted(
        [str(first), str(second)], key=str.casefold
    )
