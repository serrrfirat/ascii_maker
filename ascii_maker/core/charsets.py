"""Character set presets for ASCII art conversion.

Each charset maps luminance values (0=black, 255=white) to characters.
Braille uses a separate 2x4 bit-mapping code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class CharsetName(str, Enum):
    SIMPLE = "simple"
    DETAILED = "detailed"
    BLOCKS = "blocks"
    BRAILLE = "braille"


# Ordered dark → light (low luminance → high luminance)
SIMPLE_CHARS = " .:-=+*#%@"

DETAILED_CHARS = (
    " .`'^\",:;Il!i><~+_-?][}{1)(|\\/"
    "tfjrxnuvczXYUJCLQ0OZmwqpdbkhao"
    "*#MW&8%B@$"
)

# Unicode block elements, bottom-up fill (dark → light)
BLOCK_CHARS = " ▁▂▃▄▅▆▇█"


@dataclass(frozen=True)
class Charset:
    name: CharsetName
    chars: str
    is_braille: bool = False

    def char_for_luminance(self, luminance: float) -> str:
        """Map a luminance value (0.0-1.0) to a character."""
        idx = int(luminance * (len(self.chars) - 1))
        idx = max(0, min(idx, len(self.chars) - 1))
        return self.chars[idx]

    def map_array(self, luminance: np.ndarray) -> list[str]:
        """Map a 2D luminance array (0.0-1.0) to lines of characters.

        For braille, use braille_from_array() instead.
        """
        indices = (luminance * (len(self.chars) - 1)).astype(int)
        indices = np.clip(indices, 0, len(self.chars) - 1)
        lines = []
        for row in indices:
            lines.append("".join(self.chars[i] for i in row))
        return lines


CHARSETS: dict[CharsetName, Charset] = {
    CharsetName.SIMPLE: Charset(CharsetName.SIMPLE, SIMPLE_CHARS),
    CharsetName.DETAILED: Charset(CharsetName.DETAILED, DETAILED_CHARS),
    CharsetName.BLOCKS: Charset(CharsetName.BLOCKS, BLOCK_CHARS),
    CharsetName.BRAILLE: Charset(CharsetName.BRAILLE, "⠀⠁", is_braille=True),
}


# --- Braille encoding ---
# Braille characters use a 2-wide x 4-tall dot grid per character.
# Unicode braille block starts at U+2800.
# Dot positions (col 0, col 1):
#   row 0: bit 0, bit 3
#   row 1: bit 1, bit 4
#   row 2: bit 2, bit 5
#   row 3: bit 6, bit 7

BRAILLE_BASE = 0x2800

# Bit positions for each (row, col) in the 4x2 grid
BRAILLE_DOT_BITS: list[list[int]] = [
    [0, 3],  # row 0
    [1, 4],  # row 1
    [2, 5],  # row 2
    [6, 7],  # row 3
]


def braille_char(dots: np.ndarray) -> str:
    """Convert a 4x2 boolean array to a single braille character.

    Args:
        dots: shape (4, 2) boolean array where True = raised dot.
    """
    code = 0
    for row in range(4):
        for col in range(2):
            if dots[row, col]:
                code |= 1 << BRAILLE_DOT_BITS[row][col]
    return chr(BRAILLE_BASE + code)


def braille_from_array(binary: np.ndarray) -> list[str]:
    """Convert a 2D binary (thresholded) array to braille art lines.

    The input array height must be divisible by 4 and width by 2.
    Values > 0 are treated as raised dots.

    Args:
        binary: 2D numpy array (height, width), values 0 or 1.

    Returns:
        List of strings, one per braille row (height // 4 lines).
    """
    h, w = binary.shape
    # Pad to multiples of 4 (height) and 2 (width) if needed
    pad_h = (4 - h % 4) % 4
    pad_w = (2 - w % 2) % 2
    if pad_h or pad_w:
        binary = np.pad(binary, ((0, pad_h), (0, pad_w)), constant_values=0)
        h, w = binary.shape

    lines = []
    for y in range(0, h, 4):
        line_chars = []
        for x in range(0, w, 2):
            block = binary[y : y + 4, x : x + 2]
            line_chars.append(braille_char(block))
        lines.append("".join(line_chars))
    return lines
