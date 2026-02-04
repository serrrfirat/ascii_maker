"""Frame processing pipeline.

Resize → grayscale → brightness/contrast → dither/char-map → colorize.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from ascii_maker.core.charsets import (
    CHARSETS,
    CharsetName,
    braille_from_array,
)
from ascii_maker.core.color import ColorMode, colorize_line
from ascii_maker.core.dither import floyd_steinberg
from ascii_maker.core.reader import Frame


@dataclass(frozen=True)
class Settings:
    """Processing settings that affect output."""

    charset: CharsetName = CharsetName.SIMPLE
    color_mode: ColorMode = ColorMode.TRUECOLOR
    dither: bool = False
    brightness: int = 0  # -100 to 100
    contrast: int = 100  # 0 to 200 (100 = no change)
    invert: bool = False
    width: int = 80
    height: int = 24

    def hash(self) -> str:
        """Deterministic hash for cache keying."""
        data = (
            f"{self.charset}:{self.color_mode}:{self.dither}:"
            f"{self.brightness}:{self.contrast}:{self.invert}:"
            f"{self.width}:{self.height}"
        )
        return hashlib.md5(data.encode()).hexdigest()[:12]


@dataclass
class ProcessedFrame:
    """Result of processing a single frame."""

    lines: list[str]  # Plain text lines (no color)
    colored_lines: list[str]  # Lines with ANSI color escapes
    duration_ms: int
    index: int
    width: int = 0
    height: int = 0


def _resize_frame(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize image to target character grid dimensions.

    Characters are roughly 1:2 aspect ratio (tall), so we compensate.
    """
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _resize_for_braille(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize for braille: each braille char covers a 2x4 pixel grid."""
    pixel_w = width * 2
    pixel_h = height * 4
    return img.resize((pixel_w, pixel_h), Image.Resampling.LANCZOS)


def _to_grayscale(img: Image.Image) -> np.ndarray:
    """Convert to grayscale float array in [0.0, 1.0]."""
    return np.array(img.convert("L"), dtype=np.float64) / 255.0


def _adjust_brightness_contrast(
    gray: np.ndarray, brightness: int, contrast: int
) -> np.ndarray:
    """Apply brightness and contrast adjustments.

    brightness: -100 to 100 (added as offset)
    contrast: 0 to 200 (100 = no change, multiplied around midpoint)
    """
    result = gray.copy()

    # Brightness: shift
    if brightness != 0:
        result = result + brightness / 100.0

    # Contrast: scale around 0.5
    if contrast != 100:
        factor = contrast / 100.0
        result = (result - 0.5) * factor + 0.5

    return np.clip(result, 0.0, 1.0)


def _get_color_samples(
    img: Image.Image, width: int, height: int
) -> np.ndarray:
    """Get per-character RGB color by sampling center pixel of each cell.

    Returns array of shape (height, width, 3).
    """
    resized = img.resize((width, height), Image.Resampling.LANCZOS)
    return np.array(resized.convert("RGB"), dtype=np.uint8)


def _get_braille_color_samples(
    img: Image.Image, width: int, height: int
) -> np.ndarray:
    """Get per-braille-character RGB color by averaging each 2x4 block.

    Returns array of shape (height, width, 3).
    """
    pixel_w = width * 2
    pixel_h = height * 4
    resized = np.array(
        img.resize((pixel_w, pixel_h), Image.Resampling.LANCZOS).convert("RGB"),
        dtype=np.float64,
    )

    colors = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            block = resized[y * 4 : (y + 1) * 4, x * 2 : (x + 1) * 2, :]
            colors[y, x] = block.mean(axis=(0, 1)).astype(np.uint8)
    return colors


def process_frame(frame: Frame, settings: Settings) -> ProcessedFrame:
    """Process a single frame through the full pipeline."""
    charset = CHARSETS[settings.charset]
    is_braille = charset.is_braille
    w, h = settings.width, settings.height

    # Resize
    if is_braille:
        resized = _resize_for_braille(frame.image, w, h)
    else:
        resized = _resize_frame(frame.image, w, h)

    # Grayscale
    gray = _to_grayscale(resized)

    # Brightness / contrast
    gray = _adjust_brightness_contrast(gray, settings.brightness, settings.contrast)

    # Invert
    if settings.invert:
        gray = 1.0 - gray

    # Dither or direct mapping
    if is_braille:
        # Braille: threshold to binary, optionally with dithering
        if settings.dither:
            gray = floyd_steinberg(gray, levels=2)
        else:
            gray = (gray > 0.5).astype(np.float64)
        binary = (gray > 0.5).astype(np.uint8)
        plain_lines = braille_from_array(binary)
    else:
        if settings.dither:
            gray = floyd_steinberg(gray, levels=len(charset.chars))
        plain_lines = charset.map_array(gray)

    # Color
    if settings.color_mode != ColorMode.NONE:
        if is_braille:
            color_samples = _get_braille_color_samples(frame.image, w, h)
        else:
            color_samples = _get_color_samples(frame.image, w, h)

        # Apply invert to color samples too if inverted
        if settings.invert:
            color_samples = 255 - color_samples

        colored = []
        for row_idx, line in enumerate(plain_lines):
            if row_idx < color_samples.shape[0]:
                row_colors = color_samples[row_idx, : len(line), :]
                colored.append(colorize_line(line, row_colors, settings.color_mode))
            else:
                colored.append(line)
    else:
        colored = list(plain_lines)

    return ProcessedFrame(
        lines=plain_lines,
        colored_lines=colored,
        duration_ms=frame.duration_ms,
        index=frame.index,
        width=w,
        height=h,
    )
