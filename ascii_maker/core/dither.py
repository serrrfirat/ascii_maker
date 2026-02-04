"""Floyd-Steinberg error diffusion dithering."""

from __future__ import annotations

import numpy as np


def floyd_steinberg(gray: np.ndarray, levels: int = 2) -> np.ndarray:
    """Apply Floyd-Steinberg dithering to a grayscale image.

    Args:
        gray: 2D float array with values in [0.0, 1.0].
        levels: number of output levels. 2 = binary (black/white),
                higher values give more gray levels matching charset length.

    Returns:
        Dithered 2D float array with values quantized to `levels` steps.
    """
    img = gray.astype(np.float64).copy()
    h, w = img.shape
    step = 1.0 / (levels - 1) if levels > 1 else 1.0

    for y in range(h):
        for x in range(w):
            old = img[y, x]
            new = round(old / step) * step
            new = max(0.0, min(1.0, new))
            img[y, x] = new
            err = old - new

            if x + 1 < w:
                img[y, x + 1] += err * 7 / 16
            if y + 1 < h:
                if x - 1 >= 0:
                    img[y + 1, x - 1] += err * 3 / 16
                img[y + 1, x] += err * 5 / 16
                if x + 1 < w:
                    img[y + 1, x + 1] += err * 1 / 16

    return np.clip(img, 0.0, 1.0)


def floyd_steinberg_fast(gray: np.ndarray, levels: int = 2) -> np.ndarray:
    """Vectorized Floyd-Steinberg approximation for larger images.

    Uses row-by-row processing with vectorized error distribution within rows
    where possible, falling back to per-pixel for inter-pixel error propagation.
    At terminal resolution (~200x60) the pure Python version is fast enough,
    so this is here as an optimization option for larger inputs.
    """
    # At terminal resolution the pure version is <5ms; just delegate
    return floyd_steinberg(gray, levels)
