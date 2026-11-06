"""Restricted Python API for Altair's image-processing commands."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


_API_FUNCTIONS = {"load", "bge", "denoise", "astroupscale", "save", "stretch", "undo", "redo"}
_MAX_SCRIPT_LENGTH = 20_000
_MAX_SCRIPT_CALLS = 32

_app = None
_find_image_paths: Callable | None = None
_get_image_search_roots: Callable | None = None


class AstroAPError(ValueError):
    """Raised when an AstroAP call or generated script is invalid."""


@dataclass(frozen=True)
class AstroAPCall:
    function: str
    args: tuple
    kwargs: dict


def configure(
    app,
    find_image_paths: Callable | None = None,
    get_image_search_roots: Callable | None = None,
) -> None:
    """Bind the active application and its existing image-search helper."""
    global _app, _find_image_paths, _get_image_search_roots
    _app = app
    _find_image_paths = find_image_paths
    _get_image_search_roots = get_image_search_roots


def _get_app():
    if _app is None:
        raise AstroAPError("AstroAP is not connected to an open application.")
    return _app


def _require_loaded_image(app, operation: str) -> None:
    image = getattr(app, "magic_img", None)
    if image is None or getattr(image, "size", 0) == 0:
        raise AstroAPError(f"Load an image before running {operation}.")


def _literal_argument(node: ast.AST):
    value = ast.literal_eval(node)
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise AstroAPError("AstroAP arguments must be scalar strings, numbers, booleans, or None.")
    return value


def validate_script(source: str) -> list[AstroAPCall]:
    """Parse only imports and calls to the small, explicitly supported API."""
    text = str(source or "")
    if not text.strip():
        raise AstroAPError("The Python script is empty.")
    if len(text) > _MAX_SCRIPT_LENGTH:
        raise AstroAPError(f"The Python script exceeds {_MAX_SCRIPT_LENGTH} characters.")

    try:
        module = ast.parse(text, mode="exec")
    except SyntaxError as exc:
        raise AstroAPError(f"Invalid Python syntax on line {exc.lineno}: {exc.msg}") from exc

    calls = []
    for statement in module.body:
        if isinstance(statement, ast.Import):
            if len(statement.names) != 1 or statement.names[0].name != "astroap" or statement.names[0].asname:
                raise AstroAPError("Only `import astroap` is allowed.")
            continue
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            raise AstroAPError("Scripts may contain only `import astroap` and direct AstroAP function calls.")

        call = statement.value
        if (
            not isinstance(call.func, ast.Attribute)
            or not isinstance(call.func.value, ast.Name)
            or call.func.value.id != "astroap"
            or call.func.attr not in _API_FUNCTIONS
        ):
            raise AstroAPError(
                "Only supported direct AstroAP calls are allowed: load, bge, denoise, "
                "astroupscale, save, stretch, undo, redo."
            )
        if any(isinstance(argument, ast.Starred) for argument in call.args):
            raise AstroAPError("Starred arguments are not allowed.")
        if any(keyword.arg is None for keyword in call.keywords):
            raise AstroAPError("Expanded keyword arguments are not allowed.")

        try:
            args = tuple(_literal_argument(argument) for argument in call.args)
            kwargs = {keyword.arg: _literal_argument(keyword.value) for keyword in call.keywords}
        except (ValueError, TypeError) as exc:
            raise AstroAPError("AstroAP arguments must be literal strings, numbers, or booleans.") from exc

        if len(kwargs) != len(call.keywords):
            raise AstroAPError("Duplicate keyword arguments are not allowed.")
        calls.append(AstroAPCall(call.func.attr, args, kwargs))
        if len(calls) > _MAX_SCRIPT_CALLS:
            raise AstroAPError(f"Scripts may contain at most {_MAX_SCRIPT_CALLS} AstroAP calls.")

    if not calls:
        raise AstroAPError("The script does not contain any AstroAP calls.")
    return calls


def execute_script(source: str) -> None:
    """Execute a validated script without evaluating arbitrary Python code."""
    calls = validate_script(source)
    functions = {name: globals()[name] for name in _API_FUNCTIONS}
    for call in calls:
        functions[call.function](*call.args, **call.kwargs)


def load(path_or_query: str) -> str:
    """Open an image by path or find its name in the active image folder."""
    app = _get_app()
    query = str(path_or_query or "").strip().strip("\"'")
    if not query:
        raise AstroAPError("load() requires a file path or image name.")

    candidate = Path(os.path.expanduser(query))
    if candidate.is_file():
        path = str(candidate.resolve())
    else:
        if candidate.is_dir():
            raise AstroAPError("Pass an image name as well as a folder path.")

        current_path = str(getattr(app, "current_image_path", "") or "").strip()
        home_folder = str(getattr(app, "home_folder", "") or "").strip()
        fallback_root = (
            os.path.dirname(os.path.abspath(current_path))
            if current_path
            else home_folder if home_folder and os.path.isdir(home_folder)
            else os.getcwd()
        )
        if _find_image_paths is None:
            raise AstroAPError("The application's image search is unavailable.")
        search_roots = [fallback_root]
        if _get_image_search_roots is not None:
            for root in _get_image_search_roots(app) or []:
                root_path = os.path.abspath(os.path.expanduser(str(root or "")))
                if root_path not in search_roots:
                    search_roots.append(root_path)
        matches = _find_image_paths(query, search_roots, max_matches=12)
        if not matches:
            raise FileNotFoundError(
                f"No matching image was found in the configured image locations: {query}"
            )
        path = str(matches[0])

    if app.load_image_from_path(path) is False:
        raise AstroAPError(f"The application could not open image: {path}")
    if str(getattr(app, "current_image_path", "") or "") != path:
        raise AstroAPError(f"The application could not open image: {path}")
    return path


def bge(
    type: str = "ai",
    *,
    correction: str = "subtraction",
    smoothing: float = 20,
    sample_size: int = 25,
    kernel: str = "thin_plate",
    spline_order: int = 3,
    background_sample_points: int = 15,
    show_dialog: bool = False,
) -> None:
    """Run AI or RBF background extraction on the active image."""
    app = _get_app()
    _require_loaded_image(app, "background extraction")
    method = str(type or "ai").strip().lower()
    if method not in {"ai", "rfb"}:
        raise AstroAPError("bge() type must be 'ai' or 'rfb'.")

    correction_value = str(correction or "subtraction").strip().lower()
    corrections = {
        "subtraction": "Subtraction",
        "substraction": "Subtraction",
        "division": "Division",
    }
    if correction_value not in corrections:
        raise AstroAPError("correction must be 'subtraction' or 'division'.")

    smoothing_value = float(smoothing)
    if not 0 <= smoothing_value <= 100:
        raise AstroAPError("smoothing must be between 0 and 100.")
    smoothing_value /= 100.0
    sample_size_value = int(sample_size)
    points_per_row = int(background_sample_points)
    order = int(spline_order)
    if not 5 <= sample_size_value <= 50:
        raise AstroAPError("sample_size must be between 5 and 50.")
    if not 2 <= points_per_row <= 40:
        raise AstroAPError("background_sample_points must be between 2 and 40.")
    if not 1 <= order <= 5:
        raise AstroAPError("spline_order must be between 1 and 5.")
    kernel_value = str(kernel).strip().lower()
    if kernel_value not in {"thin_plate", "quintic", "cubic", "linear"}:
        raise AstroAPError("kernel must be thin_plate, quintic, cubic, or linear.")

    points = None
    if method == "rfb":
        source = app._get_background_extraction_source_data()
        if source is None or getattr(source, "size", 0) == 0:
            raise AstroAPError("Load an image before running background extraction.")
        from processing.background_extraction import image_to_graxpert_rgb, select_background_grid

        points = select_background_grid(
            image_to_graxpert_rgb(source),
            points_per_row=points_per_row,
            sample_size=sample_size_value,
        )[:, :2]

    result = app.run_background_extraction(
        {
            "method": "AI" if method == "ai" else "RBF",
            "correction_type": corrections[correction_value],
            "smoothing": smoothing_value,
            "sample_size": sample_size_value,
            "rbf_kernel": kernel_value,
            "spline_order": order,
            "points_per_row": points_per_row,
            "background_points": points,
        },
        show_dialog=bool(show_dialog),
    )
    if result is False:
        raise AstroAPError("Background extraction was canceled or could not start.")


def denoise(model: int = 2) -> None:
    """Run deepSNR model 1 or 2 on the active image."""
    app = _get_app()
    _require_loaded_image(app, "denoising")
    if isinstance(model, bool) or model not in (1, 2):
        raise AstroAPError("denoise() model must be 1 or 2.")
    selected_model = int(model)
    if app.run_deepsnr(strength=selected_model) is False:
        raise AstroAPError("deepSNR was canceled or could not start.")


def astroupscale(amount: int = 2) -> None:
    """Upscale the active image by 2x or 4x."""
    app = _get_app()
    _require_loaded_image(app, "Astro Upscale")
    if isinstance(amount, bool) or amount not in (2, 4):
        raise AstroAPError("astroupscale() amount must be 2 or 4.")
    scale = int(amount)
    if app.run_astro_upscale(
        parameters={"scale": scale, "method": "lanczos", "sharpen": False}
    ) is False:
        raise AstroAPError("Astro Upscale was canceled or could not start.")


def save(path: str | None = None) -> str:
    """Save the current processed image, optionally to an explicit path."""
    app = _get_app()
    _require_loaded_image(app, "saving")
    target = str(path or getattr(app, "current_save_path", "") or "").strip()
    if not target:
        raise AstroAPError("save() needs a file path when the image has no save location.")
    target = os.path.abspath(os.path.expanduser(target))
    app.save_image_to_path(target)
    if not os.path.isfile(target):
        raise AstroAPError(f"The image was not saved to {target!r}.")
    return target


def stretch(mode: str = "autostretch") -> None:
    """Set the image display stretch to linear, autostretch, or histogram."""
    app = _get_app()
    _require_loaded_image(app, "stretch")
    selected_mode = str(mode or "").strip().lower()
    if selected_mode not in {"linear", "autostretch", "histogram"}:
        raise AstroAPError("stretch() mode must be linear, autostretch, or histogram.")
    app.apply_stretch(mode=selected_mode, commit=True)
    if str(getattr(app, "display_stretch_mode", "") or "").lower() != selected_mode:
        raise AstroAPError(f"The {selected_mode} stretch could not be applied.")


def undo() -> None:
    """Undo the last image operation."""
    app = _get_app()
    _require_loaded_image(app, "undo")
    if not getattr(app, "undo_stack", None):
        raise AstroAPError("There is no image operation to undo.")
    app.undo()


def redo() -> None:
    """Redo the last undone image operation."""
    app = _get_app()
    _require_loaded_image(app, "redo")
    if not getattr(app, "redo_stack", None):
        raise AstroAPError("There is no image operation to redo.")
    app.redo()
