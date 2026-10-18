"""Precision-preserving integer export without full-size float64 temporaries."""
from __future__ import annotations

import numpy as np


def normalized_to_uint16(image: np.ndarray, chunk_pixels: int = 262144) -> np.ndarray:
    """Convert normalized floats/native unsigned integers with float64 rounding.

    Input range normalization and channel layout belong to the caller. Chunking
    retains the former arithmetic exactly while bounding scratch memory.
    """
    source = np.asarray(image)
    result = np.empty(source.shape, dtype=np.uint16)
    scale = 65535.0 / float(np.iinfo(source.dtype).max) if np.issubdtype(source.dtype, np.unsignedinteger) else 65535.0
    rows = max(1, chunk_pixels // max(1, int(np.prod(source.shape[1:]))))
    for start in range(0, source.shape[0], rows):
        work = source[start:start + rows].astype(np.float64)
        work *= scale
        np.rint(work, out=work)
        np.clip(work, 0, 65535, out=work)
        result[start:start + rows] = work.astype(np.uint16)
    return result
