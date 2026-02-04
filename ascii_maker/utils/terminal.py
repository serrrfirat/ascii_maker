"""Terminal size detection utilities."""

from __future__ import annotations

import os
import shutil


def get_terminal_size(
    fallback_width: int = 80,
    fallback_height: int = 24,
) -> tuple[int, int]:
    """Get current terminal size in columns and rows.

    Returns (width, height). Falls back to provided defaults
    if terminal size cannot be determined.
    """
    try:
        size = shutil.get_terminal_size(fallback=(fallback_width, fallback_height))
        return size.columns, size.lines
    except (ValueError, OSError):
        return fallback_width, fallback_height


def fit_to_terminal(
    img_width: int,
    img_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
    char_aspect: float = 0.5,
) -> tuple[int, int]:
    """Calculate dimensions that fit within terminal while preserving aspect ratio.

    Characters are roughly twice as tall as they are wide, so we compensate
    with char_aspect (width/height of a character cell, typically ~0.5).

    Args:
        img_width: original image width in pixels.
        img_height: original image height in pixels.
        max_width: maximum character columns (defaults to terminal width).
        max_height: maximum character rows (defaults to terminal height - 2 for UI).
        char_aspect: character cell aspect ratio (width/height).

    Returns:
        (char_width, char_height) tuple.
    """
    if max_width is None or max_height is None:
        tw, th = get_terminal_size()
        if max_width is None:
            max_width = tw
        if max_height is None:
            max_height = max(th - 4, 10)  # Leave room for UI chrome

    # Image aspect ratio adjusted for character cells
    img_aspect = (img_width / img_height) * (1.0 / char_aspect)

    if img_aspect > max_width / max_height:
        # Width-constrained
        char_w = max_width
        char_h = max(1, int(char_w / img_aspect))
    else:
        # Height-constrained
        char_h = max_height
        char_w = max(1, int(char_h * img_aspect))

    return char_w, char_h
