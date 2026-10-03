"""GraXpert-compatible background estimation and gradient correction."""

from __future__ import annotations

import math

import cv2
import numpy as np


def gaussian_kernel(sigma: float = 1.0, truncate: float = 4.0) -> tuple[int, int]:
    # Same kernel sizing as skimage.filters.gaussian used by GraXpert.
    size = round(sigma * truncate)
    size = size - 1 if size % 2 == 0 else size
    return size, size


def image_to_graxpert_rgb(image: np.ndarray) -> np.ndarray:
    """Convert native app pixels to GraXpert's float32 RGB [0, 1] working space."""
    source = np.asarray(image)
    if source.ndim == 2:
        source = source[:, :, np.newaxis]
    elif source.ndim == 3 and source.shape[2] == 4:
        source = source[:, :, :3]
    if source.ndim != 3 or source.shape[2] not in (1, 3):
        raise ValueError("Background extraction expects a mono or RGB/BGR image.")

    if np.issubdtype(source.dtype, np.unsignedinteger):
        working = source.astype(np.float32) / float(np.iinfo(source.dtype).max)
    elif np.issubdtype(source.dtype, np.signedinteger):
        info = np.iinfo(source.dtype)
        working = source.astype(np.float32) / float(-info.min)
    else:
        working = np.asarray(source, dtype=np.float32)
        if not np.isfinite(working).all():
            working = np.nan_to_num(working, nan=0.0, posinf=1.0, neginf=0.0)
    if float(np.min(working)) < 0.0 or float(np.max(working)) > 1.0:
        minimum = float(np.min(working))
        maximum = float(np.max(working))
        if maximum > minimum:
            working = (working - minimum) / (maximum - minimum)
        else:
            working = np.zeros_like(working, dtype=np.float32)

    if working.shape[2] == 3:
        working = working[:, :, ::-1]
    return np.ascontiguousarray(working, dtype=np.float32)


def image_from_graxpert_rgb(image: np.ndarray, source_image: np.ndarray) -> np.ndarray:
    """Restore GraXpert float RGB pixels to the source image's dtype and app layout."""
    source = np.asarray(source_image)
    result = np.asarray(image, dtype=np.float32)
    if result.ndim == 2:
        result = result[:, :, np.newaxis]
    if source.ndim == 3 and source.shape[2] >= 3:
        result = result[:, :, ::-1]

    dtype = source.dtype
    if np.issubdtype(dtype, np.integer):
        max_value = np.iinfo(dtype).max
        result_native = np.rint(np.clip(result, 0.0, 1.0) * max_value).astype(dtype)
    elif np.issubdtype(dtype, np.bool_):
        result_native = result >= 0.5
    elif np.issubdtype(dtype, np.floating):
        result_native = result.astype(dtype, copy=False)
    else:
        raise ValueError(f"Unsupported source image dtype for precision-preserving extraction: {dtype}")

    if source.ndim == 2 or (source.ndim == 3 and source.shape[2] == 1):
        gray = result_native[:, :, 0]
        return np.repeat(gray[:, :, np.newaxis], 3, axis=2)
    return np.ascontiguousarray(result_native)


def _find_darkest_quadrant(x: int, y: int, data_padded: np.ndarray, sample_size: int):
    coordinates = (
        (x, y),
        (x + sample_size, y + sample_size),
        (x - sample_size, y + sample_size),
        (x + sample_size, y - sample_size),
        (x - sample_size, y - sample_size),
    )
    medians = []
    for px, py in coordinates:
        if px < 0 or px > data_padded.shape[1] - 2 * sample_size or py < 0 or py > data_padded.shape[0] - 2 * sample_size:
            medians.append(2.0)
        else:
            medians.append(float(np.median(data_padded[py:py + 2 * sample_size, px:px + 2 * sample_size])))
    best = int(np.argmin(medians))
    return coordinates[best], medians[best]


def select_background_grid(data: np.ndarray, points_per_row: int = 15, tolerance: float = 1.0, sample_size: int = 25) -> np.ndarray:
    """Port of GraXpert's automatic grid selector."""
    mono = np.asarray(data, dtype=np.float32)
    if mono.ndim == 3 and mono.shape[-1] == 3:
        mono = mono[:, :, 0] * 0.2125 + mono[:, :, 1] * 0.7154 + mono[:, :, 2] * 0.0721
    elif mono.ndim == 3:
        mono = mono[:, :, 0]
    if mono.ndim != 2 or mono.size == 0:
        return np.empty((0, 3), dtype=int)

    global_median = float(np.median(mono))
    distance = mono.shape[1] / max(1, int(points_per_row))
    points = []
    x_start = int(0.5 * distance)
    y_start = int(0.5 * (mono.shape[0] % distance))
    y = y_start
    while y < mono.shape[0]:
        x = x_start
        while x < mono.shape[1]:
            points.append([x, y, 1])
            x = int(x + distance)
        y = int(y + distance)

    halfsize = max(1, int(sample_size))
    padded = np.pad(mono, ((halfsize, halfsize), (halfsize, halfsize)), mode="reflect")
    local_medians = np.zeros(len(points), dtype=np.float64)
    for i, point in enumerate(points):
        selected, median = _find_darkest_quadrant(point[0], point[1], padded, halfsize)
        point[0], point[1] = selected
        local_medians[i] = median
    mad = float(np.median(np.abs(local_medians - global_median)))
    return np.asarray([p for p, value in zip(points, local_medians) if value < global_median + tolerance * mad], dtype=int).reshape(-1, 3)


class _RadialBasisInterpolation:
    """GraXpert's augmented RBF interpolation formulation."""

    def __init__(self, points, values, kernel: str, smooth: float):
        from scipy import linalg
        from scipy.spatial.distance import cdist

        self.points = np.atleast_2d(points).astype(np.float64)
        self.kernel = str(kernel)
        self.smooth = max(float(smooth), 1e-10)
        kernel_matrix = self._kernel(cdist(self.points, self.points))
        kernel_matrix += np.eye(len(self.points)) * self.smooth * np.mean(kernel_matrix)
        polynomial = self._vandermonde(self.points)
        zero = np.zeros((polynomial.shape[1], polynomial.shape[1]))
        system = np.block([[kernel_matrix, polynomial], [polynomial.T, zero]])
        rhs = np.concatenate([np.asarray(values, dtype=np.float64), np.zeros(polynomial.shape[1])])
        coefficients = linalg.solve(system, rhs)
        self.rbf_coefficients = coefficients[:len(self.points)]
        self.polynomial_coefficients = coefficients[len(self.points):]

    @staticmethod
    def _vandermonde(points):
        # GraXpert uses total-degree-zero augmentation, i.e. a constant term.
        return np.ones((len(points), 1), dtype=np.float64)

    def _kernel(self, radius):
        from scipy.special import xlogy

        if self.kernel == "multiquadric":
            return np.sqrt(radius ** 2 + 1.0)
        if self.kernel == "inverse":
            return 1.0 / np.sqrt(radius ** 2 + 1.0)
        if self.kernel == "gaussian":
            return np.exp(-(radius ** 2))
        if self.kernel == "linear":
            return radius
        if self.kernel == "cubic":
            return radius ** 3
        if self.kernel == "quintic":
            return radius ** 5
        if self.kernel == "thin_plate":
            return xlogy(radius ** 2, radius)
        raise ValueError(f"Unsupported GraXpert RBF kernel: {self.kernel}")

    def __call__(self, points, progress=None):
        from scipy.spatial.distance import cdist

        points = np.atleast_2d(points)
        result = np.empty(len(points), dtype=np.float64)
        step = max(1, int(10 * len(points) / max(1, self.points.size) + 1))
        for start in range(0, len(points), step):
            end = min(start + step, len(points))
            result[start:end] = (
                self._kernel(cdist(points[start:end], self.points)) @ self.rbf_coefficients
                + self.polynomial_coefficients[0]
            )
            if progress:
                progress(int(end * 100 / max(1, len(points))))
        return result


def _sample_modes(channel: np.ndarray, points: np.ndarray, sample_size: int, progress=None) -> np.ndarray:
    from astropy.stats import sigma_clipped_stats

    halfsize = max(1, int(sample_size))
    padded = np.pad(channel, ((halfsize, halfsize), (halfsize, halfsize)), mode="reflect")
    values = np.zeros(len(points), dtype=np.float64)
    for i, (x, y) in enumerate(points):
        patch = padded[int(y):int(y) + 2 * halfsize, int(x):int(x) + 2 * halfsize]
        values[i] = sigma_clipped_stats(patch, cenfunc="median", stdfunc="std", grow=4)[1]
        if progress and (i + 1 == len(points) or (i + 1) % max(1, len(points) // 20) == 0):
            progress(int((i + 1) * 100 / max(1, len(points))))
    return values


def _interpolate_channel(
    channel,
    points,
    kind,
    smoothing,
    downscale_factor,
    sample_size,
    rbf_kernel,
    spline_order,
    progress=None,
):
    from scipy import interpolate, linalg

    h, w = channel.shape
    x_sub = np.asarray(points[:, 0], dtype=int)
    y_sub = np.asarray(points[:, 1], dtype=int)
    values = _sample_modes(
        channel,
        points,
        sample_size,
        progress=lambda value: progress("Sampling background points", int(value * 0.3)) if progress else None,
    )
    if downscale_factor != 1:
        shape_scaled = (h // downscale_factor, w // downscale_factor)
        x_sub = x_sub / w * shape_scaled[1]
        y_sub = y_sub / h * shape_scaled[0]
    else:
        shape_scaled = (h, w)

    x_new = np.arange(shape_scaled[1], dtype=np.float64)
    y_new = np.arange(shape_scaled[0], dtype=np.float64)
    if kind == "RBF":
        if progress:
            progress("Building RBF model", 35)
        stacked = np.stack([x_sub, y_sub], axis=-1)
        rbf = _RadialBasisInterpolation(
            stacked,
            values,
            rbf_kernel,
            smoothing * linalg.norm(values) / math.sqrt(len(values)),
        )
        xx, yy = np.meshgrid(x_new, y_new)
        result = rbf(
            np.stack([xx.ravel(), yy.ravel()], axis=-1),
            progress=lambda value: progress("Interpolating background", 35 + int(value * 0.6)) if progress else None,
        ).reshape(shape_scaled)
    elif kind == "Splines":
        if progress:
            progress("Fitting background spline", 35)
        spline = interpolate.bisplrep(
            y_sub, x_sub, values, w=np.ones(len(x_sub)) / np.std(values),
            s=smoothing * len(x_sub), kx=int(spline_order), ky=int(spline_order),
        )
        if progress:
            progress("Evaluating background spline", 85)
        result = interpolate.bisplev(y_new, x_new, spline)
        if progress:
            progress("Spline interpolation complete", 95)
    elif kind == "Kriging":
        from pykrige.ok import OrdinaryKriging

        kriging = OrdinaryKriging(x_sub, y_sub, values, variogram_model="spherical", verbose=False, enable_plotting=False)
        if progress:
            progress("Building Kriging model", 35)
        result = np.zeros(shape_scaled, dtype=np.float32)
        num_iterations = shape_scaled[0] // 50
        for i in range(num_iterations):
            block, _ = kriging.execute("grid", xpoints=x_new, ypoints=y_new[i * 50:(i + 1) * 50], backend="vectorized")
            result[i * 50:(i + 1) * 50] = block
            if progress:
                progress("Interpolating background", 35 + int((i + 1) * 60 * 50 / max(1, shape_scaled[0])))
        block, _ = kriging.execute("grid", xpoints=x_new, ypoints=y_new[num_iterations * 50:], backend="vectorized")
        result[num_iterations * 50:] = block
        if progress:
            progress("Interpolating background", 95)
    else:
        raise ValueError(f"Unsupported GraXpert interpolation method: {kind}")

    if downscale_factor != 1:
        result = cv2.resize(np.asarray(result, dtype=np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    if progress:
        progress("Background map ready", 100)
    return result


def _run_ai(image: np.ndarray, model_path: str, smoothing: float, progress=None) -> np.ndarray:
    import onnxruntime as ort

    num_colors = image.shape[-1]
    padding = 8
    small = cv2.resize(image, (256 - 2 * padding, 256 - 2 * padding), interpolation=cv2.INTER_LINEAR)
    if small.ndim == 2:
        small = small[:, :, np.newaxis]
    small = np.pad(small, ((padding, padding), (padding, padding), (0, 0)), mode="edge")
    medians = np.median(small, axis=(0, 1))
    mads = np.median(np.abs(small - medians), axis=(0, 1))
    mads = np.maximum(mads, 1e-10)
    small = np.clip((small - medians) / mads * 0.04, -1.0, 1.0)
    if num_colors == 1:
        small = np.repeat(small, 3, axis=2)
    if progress:
        progress("Preparing AI input", 10, 10)
    available = set(ort.get_available_providers())
    candidates = [
        "DmlExecutionProvider",
        ("CoreMLExecutionProvider", {"flags": "COREML_FLAG_CREATE_MLPROGRAM"}),
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    providers = [provider for provider in candidates if (provider[0] if isinstance(provider, tuple) else provider) in available]
    session = ort.InferenceSession(model_path, providers=providers)
    if progress:
        progress("Loading AI model", 20, 20)
    background = session.run(None, {"gen_input_image": np.expand_dims(small, axis=0)})[0][0]
    if progress:
        progress("Estimating background with AI", 80, 80)
    if background.ndim == 2:
        background = background[:, :, np.newaxis]
    background = background / 0.04 * mads + medians
    if smoothing != 0:
        sigma = smoothing * 20
        background = cv2.GaussianBlur(background, gaussian_kernel(sigma), sigmaX=sigma, sigmaY=sigma)
    if progress:
        progress("Smoothing background map", 90, 90)
    if num_colors == 1:
        background = background[:, :, :1]
    background = background[padding:-padding, padding:-padding, :]
    background = cv2.GaussianBlur(background, gaussian_kernel(3.0), sigmaX=3.0, sigmaY=3.0)
    background = cv2.resize(background, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    if background.ndim == 2:
        background = background[:, :, np.newaxis]
    if progress:
        progress("Background map ready", 95, 95)
    return background.astype(np.float32)


def extract_background(
    image: np.ndarray,
    background_points: np.ndarray,
    interpolation_type: str = "AI",
    smoothing: float = 0.0,
    downscale_factor: int = 1,
    sample_size: int = 25,
    rbf_kernel: str = "thin_plate",
    spline_order: int = 3,
    correction_type: str = "Subtraction",
    ai_model_path: str | None = None,
    progress=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (corrected_image, estimated_background); input is float RGB [0,1]."""
    source = np.asarray(image, dtype=np.float32)
    if source.ndim == 2:
        source = source[:, :, np.newaxis]
    if source.ndim != 3 or source.shape[-1] not in (1, 3):
        raise ValueError("GraXpert background extraction expects a mono or RGB image.")
    source = np.nan_to_num(source, nan=0.0, posinf=0.0, neginf=0.0).copy()
    method = str(interpolation_type)
    if method == "AI":
        if not ai_model_path:
            raise ValueError("Select a GraXpert Background Extraction ONNX model in Preferences.")
        background = _run_ai(source, ai_model_path, float(smoothing), progress)
    else:
        points = np.asarray(background_points, dtype=int)
        if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
            raise ValueError("Add background sample points or generate a background grid.")
        if method == "Kriging" and len(points) < 2:
            raise ValueError("Kriging requires at least 2 sample points.")
        if method == "Splines" and len(points) < 16:
            raise ValueError("Splines requires at least 16 sample points.")
        background = np.empty_like(source)
        num_channels = source.shape[-1]
        for channel_index in range(source.shape[-1]):
            channel_start = 5 + int(channel_index * 85 / num_channels)
            channel_span = 85 / num_channels

            def _channel_progress(stage, current, channel_start=channel_start, channel_span=channel_span):
                if progress:
                    overall = int(channel_start + channel_span * max(0, min(100, current)) / 100)
                    progress(f"{stage} ({channel_index + 1}/{num_channels})", overall, current)

            background[:, :, channel_index] = _interpolate_channel(
                source[:, :, channel_index], points, method, float(smoothing),
                int(downscale_factor), int(sample_size), str(rbf_kernel), int(spline_order),
                progress=_channel_progress,
            )

    if progress:
        progress("Applying background correction", 95, 95)
    if correction_type == "Subtraction":
        source -= background
        source += np.mean(background)
    elif correction_type == "Division":
        for channel_index in range(source.shape[-1]):
            mean = np.mean(source[:, :, channel_index])
            safe_background = np.where(np.abs(background[:, :, channel_index]) < 1e-10, 1e-10, background[:, :, channel_index])
            source[:, :, channel_index] = source[:, :, channel_index] / safe_background * mean
    else:
        raise ValueError(f"Unsupported GraXpert correction type: {correction_type}")
    np.clip(source, 0.0, 1.0, out=source)
    if progress:
        progress("Background correction", 100, 100)
    return source, background
