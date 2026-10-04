import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PyQt5.QtCore import QCoreApplication


APP_PATH = Path(__file__).resolve().parents[1] / "Astro Ai Processor.py"
APP_MODULE_NAME = "astro_ai_processor_worker_tests"
APP_SPEC = importlib.util.spec_from_file_location(APP_MODULE_NAME, APP_PATH)
APP_MODULE = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_MODULE_NAME] = APP_MODULE
APP_SPEC.loader.exec_module(APP_MODULE)

QT_APPLICATION = QCoreApplication.instance() or QCoreApplication([])


def test_image_processing_worker_runs_pipeline_off_the_caller_thread():
    image = np.array(
        [
            [[12, 40, 90], [80, 100, 120]],
            [[200, 160, 80], [25, 75, 125]],
        ],
        dtype=np.uint8,
    )
    worker = APP_MODULE.ImageProcessingWorker(
        {
            "revision": 1,
            "image": image,
            "basic_params": {"exposure": 1.0},
            "hsl_params": None,
            "ghs_params": None,
            "levels": {"black": 0, "gamma": 1.0, "white": 255, "channels": None},
            "curves": None,
            "curves_visible": True,
        }
    )

    worker.start()
    assert worker.wait(10_000)

    assert worker.error == ""
    assert worker.result.shape == image.shape
    assert worker.result.dtype == np.uint8
    assert not np.array_equal(worker.result, image)


def test_image_processing_worker_commits_autostretch_into_its_result():
    image = np.array(
        [
            [[3, 7, 12], [15, 20, 28], [40, 50, 60]],
            [[75, 90, 105], [120, 135, 150], [180, 195, 210]],
            [[220, 230, 240], [30, 45, 55], [8, 12, 20]],
        ],
        dtype=np.uint8,
    )
    job = {
        "revision": 1,
        "image": image,
        "basic_params": {"exposure": 1.0},
        "hsl_params": None,
        "ghs_params": None,
        "levels": {"black": 0, "gamma": 1.0, "white": 255, "channels": None},
        "curves": None,
        "curves_visible": True,
    }
    plain_worker = APP_MODULE.ImageProcessingWorker(job)
    plain_worker.start()
    assert plain_worker.wait(10_000)
    assert plain_worker.error == ""

    stretched_job = dict(job)
    stretched_job["levels"] = dict(job["levels"], autostretch=True)
    stretched_worker = APP_MODULE.ImageProcessingWorker(stretched_job)
    stretched_worker.start()
    assert stretched_worker.wait(10_000)

    expected = APP_MODULE.stretch_image(plain_worker.result, "autostretch")
    assert stretched_worker.error == ""
    assert np.array_equal(stretched_worker.result, expected)
    assert not np.array_equal(stretched_worker.result, plain_worker.result)


def test_image_analysis_worker_computes_metrics_on_its_thread():
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    source_image = image.copy()
    worker = APP_MODULE.ImageAnalysisWorker(
        image,
        source_image,
        request_id=7,
        processing_revision=3,
    )

    worker.start()
    assert worker.wait(10_000)

    assert worker.error == ""
    assert worker.result["image_shape"] == {"width": 32, "height": 32}
    assert worker.result["luminance"]["mean"] == 0.0


def test_astro_upscale_worker_keeps_float32_and_returns_scaled_data():
    image = np.linspace(0.0, 1.0, 32 * 32, dtype=np.float32).reshape(32, 32)
    worker = APP_MODULE.AstroUpscaleWorker([(image, False)], 2, "lanczos")

    worker.start()
    assert worker.wait(10_000)

    assert worker.error == ""
    assert worker.result[0].shape == (64, 64)
    assert worker.result[0].dtype == np.float32


def test_astro_upscale_document_state_round_trips_through_existing_undo_redo():
    original = np.zeros((8, 8), dtype=np.float32)
    enlarged = np.zeros((16, 16), dtype=np.float32)
    pre_upscale = {"_astro_upscale_state": True, "magic_img": original}
    app = SimpleNamespace(
        undo_stack=[pre_upscale],
        redo_stack=[],
        magic_img=enlarged,
        log=lambda *_args, **_kwargs: None,
    )
    app._capture_astro_upscale_state = lambda: {
        "_astro_upscale_state": True,
        "magic_img": app.magic_img,
    }
    app._restore_magic_state = lambda state: setattr(app, "magic_img", state["magic_img"])

    APP_MODULE.AstroApp.undo(app)
    assert app.magic_img is original
    assert app.redo_stack[-1]["magic_img"] is enlarged

    APP_MODULE.AstroApp.redo(app)
    assert app.magic_img is enlarged
    assert app.undo_stack[-1]["magic_img"] is original


def test_astro_upscale_snapshot_restores_layers_and_fits_metadata():
    image = np.zeros((10, 12, 3), dtype=np.float32)
    layer = np.ones_like(image)
    mask = np.ones((10, 12), dtype=np.float32)
    app = SimpleNamespace(
        magic_img=image,
        original_img=image.copy(),
        processed_img=image.copy(),
        _native_loaded_image=image.copy(),
        preview_override_img=None,
        layer_images={"stars": layer},
        layer_masks={"stars": mask},
        layer_visibility={"background": True, "stars": False},
        layer_order=["background", "stars"],
        selected_layer_key="stars",
        overlay_layer_pixmaps={"grid": object()},
        constellation_lines=[(1, 2)],
        current_fits_header={"OBJECT": "M42", "CRPIX1": 6.5},
        latest_image_analysis={"source": "before"},
        analysis_dirty=False,
        latest_plate_solve_result={"solved": True},
        plate_solve_object_info={"name": "M42"},
        _bge_save_image=image.copy(),
        _bge_save_magic_snapshot=image.copy(),
        _bge_save_processing_revision=7,
    )

    snapshot = APP_MODULE.AstroApp._capture_astro_upscale_state(app)
    app.magic_img = np.zeros((20, 24, 3), dtype=np.float32)
    app.layer_images = {}
    app.layer_masks = {}
    app.current_fits_header = {"CRPIX1": 13.0}

    APP_MODULE.AstroApp._restore_astro_upscale_state(app, snapshot)

    assert app.magic_img.shape == (10, 12, 3)
    assert app.layer_images["stars"] is layer
    assert app.layer_masks["stars"] is mask
    assert app.layer_visibility["stars"] is False
    assert app.selected_layer_key == "stars"
    assert app.current_fits_header == {"OBJECT": "M42", "CRPIX1": 6.5}
    assert app.latest_plate_solve_result == {"solved": True}


def test_astro_upscale_history_entry_can_keep_large_arrays_without_copying():
    image = np.zeros((64, 64, 3), dtype=np.float32)
    app = SimpleNamespace(
        processing_history=[],
        max_thumbnails=15,
        selected_thumbnail_index=-1,
        current_history_node_id=None,
        thumbnail_next_id=1,
        magic_img=image,
        processed_img=image,
        _update_thumbnails_view=lambda: None,
    )

    APP_MODULE.AstroApp.add_thumbnail(app, "Astro Upscale 2×", image, copy_images=False)

    assert app.processing_history[0]["img"] is image
    assert app.processing_history[0]["magic_img"] is image
