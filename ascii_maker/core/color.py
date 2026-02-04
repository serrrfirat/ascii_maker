"""RGB to ANSI color mapping for terminal output."""

from __future__ import annotations

from enum import Enum

import numpy as np


class ColorMode(str, Enum):
    NONE = "none"
    ANSI256 = "256"
    TRUECOLOR = "truecolor"


def rgb_to_ansi256(r: int, g: int, b: int) -> int:
    """Map an RGB color to the nearest ANSI 256-color index.

    Uses the 6x6x6 color cube (indices 16-231) and grayscale ramp (232-255).
    """
    # Check if close to grayscale
    if abs(r - g) < 10 and abs(g - b) < 10:
        gray = (r + g + b) // 3
        if gray < 8:
            return 16
        if gray > 248:
            return 231
        return 232 + round((gray - 8) / 247 * 23)

    # Map to 6x6x6 cube
    ri = round(r / 255 * 5)
    gi = round(g / 255 * 5)
    bi = round(b / 255 * 5)
    return 16 + 36 * ri + 6 * gi + bi


def ansi256_fg(color_idx: int) -> str:
    """Return ANSI escape for 256-color foreground."""
    return f"\033[38;5;{color_idx}m"


def truecolor_fg(r: int, g: int, b: int) -> str:
    """Return ANSI escape for truecolor (24-bit) foreground."""
    return f"\033[38;2;{r};{g};{b}m"


RESET = "\033[0m"


def colorize_char(char: str, r: int, g: int, b: int, mode: ColorMode) -> str:
    """Wrap a character with ANSI color escapes."""
    if mode == ColorMode.NONE:
        return char
    if mode == ColorMode.ANSI256:
        idx = rgb_to_ansi256(r, g, b)
        return f"{ansi256_fg(idx)}{char}{RESET}"
    # truecolor
    return f"{truecolor_fg(r, g, b)}{char}{RESET}"


def colorize_line(
    chars: str,
    colors: np.ndarray,
    mode: ColorMode,
) -> str:
    """Colorize a line of characters using per-character RGB values.

    Args:
        chars: string of characters for this line.
        colors: array of shape (len(chars), 3) with RGB values (uint8).
        mode: color mode to use.

    Returns:
        String with ANSI color escapes.
    """
    if mode == ColorMode.NONE:
        return chars

    parts: list[str] = []
    prev_escape = ""
    for i, ch in enumerate(chars):
        r, g, b = int(colors[i, 0]), int(colors[i, 1]), int(colors[i, 2])
        if mode == ColorMode.TRUECOLOR:
            esc = truecolor_fg(r, g, b)
        else:
            esc = ansi256_fg(rgb_to_ansi256(r, g, b))

        # Avoid repeating the same escape code
        if esc != prev_escape:
            parts.append(esc)
            prev_escape = esc
        parts.append(ch)

    if prev_escape:
        parts.append(RESET)
    return "".join(parts)
