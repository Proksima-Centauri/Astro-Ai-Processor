from pathlib import Path

import pytest

import astroap


def test_validate_script_allows_only_literal_astroap_calls():
    calls = astroap.validate_script(
        'import astroap\nastroap.load("ngc281")\nastroap.denoise(model=2)'
        '\nastroap.stretch(mode="autostretch")\nastroap.undo()\nastroap.redo()\nastroap.save()'
    )

    assert [(call.function, call.args, call.kwargs) for call in calls] == [
        ("load", ("ngc281",), {}),
        ("denoise", (), {"model": 2}),
        ("stretch", (), {"mode": "autostretch"}),
        ("undo", (), {}),
        ("redo", (), {}),
        ("save", (), {}),
    ]


@pytest.mark.parametrize(
    "source",
    [
        "import os\nastroap.load('image.tif')",
        "astroap.load(__import__('os').getcwd())",
        "astroap.__dict__['load']('image.tif')",
        "image = 'image.tif'\nastroap.load(image)",
        "astroap.load(**{'path_or_query': 'image.tif'})",
    ],
)
def test_validate_script_rejects_non_api_python(source):
    with pytest.raises(astroap.AstroAPError):
        astroap.validate_script(source)


def test_execute_script_dispatches_only_validated_api_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(astroap, "load", lambda value: calls.append(("load", value)))
    monkeypatch.setattr(astroap, "denoise", lambda **kwargs: calls.append(("denoise", kwargs)))

    astroap.execute_script(
        'import astroap\nastroap.load("ngc281")\nastroap.denoise(model=1)'
    )

    assert calls == [("load", "ngc281"), ("denoise", {"model": 1})]


def test_load_searches_configured_image_locations(monkeypatch, tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    shared_images = tmp_path / "shared-images"
    shared_images.mkdir()
    image_path = str(shared_images / "M27.tif")
    searched = []

    class App:
        current_image_path = str(folder / "current.tif")
        home_folder = str(tmp_path / "other")
        current_image_path_after_load = ""

        def load_image_from_path(self, path):
            self.current_image_path = path

    app = App()

    def find_paths(query, roots, max_matches):
        searched.append((query, roots, max_matches))
        return [image_path]

    monkeypatch.setattr(astroap, "_app", app)
    monkeypatch.setattr(astroap, "_find_image_paths", find_paths)
    monkeypatch.setattr(
        astroap,
        "_get_image_search_roots",
        lambda active_app: [str(folder), str(shared_images)],
    )

    assert astroap.load("M27") == image_path
    assert searched == [("M27", [str(folder), str(shared_images)], 12)]
    assert app.current_image_path == image_path


def test_processing_api_calls_application_with_normalized_parameters(monkeypatch):
    class App:
        magic_img = type("Image", (), {"size": 1})()

        def __init__(self):
            self.calls = []

        def run_background_extraction(self, parameters, show_dialog=True):
            self.calls.append(("bge", parameters, show_dialog))

        def run_deepsnr(self, strength=None):
            self.calls.append(("denoise", strength))

        def run_astro_upscale(self, parameters=None):
            self.calls.append(("upscale", parameters))

    app = App()
    monkeypatch.setattr(astroap, "_app", app)

    astroap.bge(type="ai", smoothing=20, correction="substraction")
    astroap.denoise(model=1)
    astroap.astroupscale(amount=4)

    assert app.calls == [
        (
            "bge",
            {
                "method": "AI",
                "correction_type": "Subtraction",
                "smoothing": 0.2,
                "sample_size": 25,
                "rbf_kernel": "thin_plate",
                "spline_order": 3,
                "points_per_row": 15,
                "background_points": None,
            },
            False,
        ),
        ("denoise", 1),
        ("upscale", {"scale": 4, "method": "lanczos", "sharpen": False}),
    ]


def test_save_stretch_undo_redo_api_calls_existing_app_operations(monkeypatch, tmp_path):
    class App:
        magic_img = type("Image", (), {"size": 1})()
        undo_stack = [object()]
        redo_stack = [object()]
        current_save_path = ""
        display_stretch_mode = ""

        def __init__(self):
            self.calls = []

        def save_image_to_path(self, path):
            self.calls.append(("save", path))
            Path(path).write_bytes(b"image")

        def apply_stretch(self, mode, commit):
            self.calls.append(("stretch", mode, commit))
            self.display_stretch_mode = mode

        def undo(self):
            self.calls.append(("undo",))

        def redo(self):
            self.calls.append(("redo",))

    app = App()
    monkeypatch.setattr(astroap, "_app", app)
    target_path = tmp_path / "output.tif"

    assert astroap.save(str(target_path)) == str(target_path)
    astroap.stretch("autostretch")
    astroap.undo()
    astroap.redo()
    assert app.calls == [
        ("save", str(target_path)),
        ("stretch", "autostretch", True),
        ("undo",),
        ("redo",),
    ]


def test_save_without_explicit_path_requires_existing_save_target(monkeypatch, tmp_path):
    class App:
        magic_img = type("Image", (), {"size": 1})()
        current_save_path = ""

    monkeypatch.setattr(astroap, "_app", App())
    with pytest.raises(astroap.AstroAPError, match="needs a file path"):
        astroap.save()


def test_stretch_rejects_unknown_mode(monkeypatch):
    class App:
        magic_img = type("Image", (), {"size": 1})()

    monkeypatch.setattr(astroap, "_app", App())
    with pytest.raises(astroap.AstroAPError, match="mode must be"):
        astroap.stretch("solarize")
