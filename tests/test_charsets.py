"""Tests for character set presets and braille encoding."""

import numpy as np
import pytest

from ascii_maker.core.charsets import (
    CHARSETS,
    CharsetName,
    braille_char,
    braille_from_array,
)


class TestCharsets:
    def test_simple_charset_exists(self):
        cs = CHARSETS[CharsetName.SIMPLE]
        assert cs.name == CharsetName.SIMPLE
        assert len(cs.chars) > 0

    def test_char_for_luminance_boundaries(self):
        cs = CHARSETS[CharsetName.SIMPLE]
        # Black (0.0) should give first char (space)
        assert cs.char_for_luminance(0.0) == cs.chars[0]
        # White (1.0) should give last char
        assert cs.char_for_luminance(1.0) == cs.chars[-1]
        # Mid-range
        mid = cs.char_for_luminance(0.5)
        assert mid in cs.chars

    def test_map_array_shape(self):
        cs = CHARSETS[CharsetName.SIMPLE]
        arr = np.random.rand(10, 20)
        lines = cs.map_array(arr)
        assert len(lines) == 10
        assert all(len(line) == 20 for line in lines)

    def test_map_array_all_black(self):
        cs = CHARSETS[CharsetName.SIMPLE]
        arr = np.zeros((3, 5))
        lines = cs.map_array(arr)
        # All black = all spaces (first char)
        for line in lines:
            assert line == cs.chars[0] * 5

    def test_map_array_all_white(self):
        cs = CHARSETS[CharsetName.SIMPLE]
        arr = np.ones((3, 5))
        lines = cs.map_array(arr)
        # All white = all last char
        for line in lines:
            assert line == cs.chars[-1] * 5

    def test_detailed_charset_length(self):
        cs = CHARSETS[CharsetName.DETAILED]
        assert len(cs.chars) > 20  # Should have many characters

    def test_blocks_charset(self):
        cs = CHARSETS[CharsetName.BLOCKS]
        assert "█" in cs.chars
        assert " " == cs.chars[0]

    def test_braille_charset_is_braille(self):
        cs = CHARSETS[CharsetName.BRAILLE]
        assert cs.is_braille is True


class TestBraille:
    def test_braille_char_empty(self):
        """All zeros should give blank braille (U+2800)."""
        dots = np.zeros((4, 2), dtype=bool)
        assert braille_char(dots) == "⠀"

    def test_braille_char_full(self):
        """All ones should give full braille (U+28FF)."""
        dots = np.ones((4, 2), dtype=bool)
        assert braille_char(dots) == "⣿"

    def test_braille_char_top_left(self):
        """Only top-left dot should be U+2801."""
        dots = np.zeros((4, 2), dtype=bool)
        dots[0, 0] = True
        assert braille_char(dots) == "⠁"

    def test_braille_from_array_basic(self):
        """4x2 binary array should produce 1 line of 1 braille char."""
        binary = np.ones((4, 2), dtype=np.uint8)
        lines = braille_from_array(binary)
        assert len(lines) == 1
        assert len(lines[0]) == 1
        assert lines[0] == "⣿"

    def test_braille_from_array_dimensions(self):
        """8x4 array should produce 2 lines of 2 chars each."""
        binary = np.zeros((8, 4), dtype=np.uint8)
        lines = braille_from_array(binary)
        assert len(lines) == 2
        assert all(len(line) == 2 for line in lines)

    def test_braille_from_array_padding(self):
        """Non-multiple dimensions should be padded."""
        binary = np.zeros((5, 3), dtype=np.uint8)
        lines = braille_from_array(binary)
        # Padded to 8x4 → 2 lines of 2 chars
        assert len(lines) == 2
        assert all(len(line) == 2 for line in lines)
