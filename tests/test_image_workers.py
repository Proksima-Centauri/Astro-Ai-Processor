import importlib.util
import sys
from pathlib import Path

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
