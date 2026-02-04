"""Tests for color mapping functions."""

import numpy as np
import pytest

from ascii_maker.core.color import (
    RESET,
    ColorMode,
    colorize_char,
    colorize_line,
    rgb_to_ansi256,
    truecolor_fg,
    ansi256_fg,
)


class TestRgbToAnsi256:
    def test_black(self):
        idx = rgb_to_ansi256(0, 0, 0)
        assert idx == 16  # Darkest in 6x6x6 cube

    def test_white(self):
        idx = rgb_to_ansi256(255, 255, 255)
        assert idx == 231  # Lightest in grayscale

    def test_gray(self):
        idx = rgb_to_ansi256(128, 128, 128)
        # Should be in grayscale ramp (232-255)
        assert 232 <= idx <= 255

    def test_pure_red(self):
        idx = rgb_to_ansi256(255, 0, 0)
        # Should be in the color cube
        assert 16 <= idx <= 231

    def test_returns_int(self):
        assert isinstance(rgb_to_ansi256(100, 150, 200), int)


class TestEscapes:
    def test_truecolor_format(self):
        esc = truecolor_fg(255, 128, 0)
        assert esc == "\033[38;2;255;128;0m"

    def test_ansi256_format(self):
        esc = ansi256_fg(196)
        assert esc == "\033[38;5;196m"


class TestColorize:
    def test_none_mode(self):
        result = colorize_char("X", 255, 0, 0, ColorMode.NONE)
        assert result == "X"

    def test_truecolor_mode(self):
        result = colorize_char("X", 255, 0, 0, ColorMode.TRUECOLOR)
        assert "\033[38;2;255;0;0m" in result
        assert "X" in result
        assert RESET in result

    def test_ansi256_mode(self):
        result = colorize_char("X", 255, 0, 0, ColorMode.ANSI256)
        assert "\033[38;5;" in result
        assert "X" in result

    def test_colorize_line_none(self):
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = colorize_line("ABC", colors, ColorMode.NONE)
        assert result == "ABC"

    def test_colorize_line_truecolor(self):
        colors = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
        result = colorize_line("AB", colors, ColorMode.TRUECOLOR)
        assert "A" in result
        assert "B" in result
        assert "\033[38;2;" in result
        assert RESET in result

    def test_colorize_line_deduplicates_escapes(self):
        """Same color repeated should not repeat escape code."""
        colors = np.array([[255, 0, 0], [255, 0, 0]], dtype=np.uint8)
        result = colorize_line("AB", colors, ColorMode.TRUECOLOR)
        # Should have exactly one color escape (plus one reset)
        assert result.count("\033[38;2;255;0;0m") == 1
