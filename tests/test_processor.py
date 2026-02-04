"""Tests for the frame processing pipeline."""

import numpy as np
import pytest
from PIL import Image

from ascii_maker.core.charsets import CharsetName
from ascii_maker.core.color import ColorMode
from ascii_maker.core.processor import (
    ProcessedFrame,
    Settings,
    process_frame,
)
from ascii_maker.core.reader import Frame


def _make_test_frame(width: int = 100, height: int = 100, color=(128, 128, 128)):
    """Create a solid-color test frame."""
    img = Image.new("RGB", (width, height), color)
    return Frame(image=img, duration_ms=100, index=0)


class TestSettings:
    def test_default_settings(self):
        s = Settings()
        assert s.charset == CharsetName.SIMPLE
        assert s.color_mode == ColorMode.TRUECOLOR
        assert s.dither is False
        assert s.brightness == 0
        assert s.contrast == 100

    def test_hash_deterministic(self):
        s1 = Settings()
        s2 = Settings()
        assert s1.hash() == s2.hash()

    def test_hash_changes_with_settings(self):
        s1 = Settings()
        s2 = Settings(dither=True)
        assert s1.hash() != s2.hash()


class TestProcessFrame:
    def test_basic_processing(self):
        frame = _make_test_frame()
        settings = Settings(width=40, height=20, color_mode=ColorMode.NONE)
        result = process_frame(frame, settings)

        assert isinstance(result, ProcessedFrame)
        assert len(result.lines) == 20
        assert all(len(line) == 40 for line in result.lines)
        assert result.duration_ms == 100
        assert result.index == 0

    def test_colored_output(self):
        frame = _make_test_frame(color=(255, 0, 0))
        settings = Settings(width=10, height=5, color_mode=ColorMode.TRUECOLOR)
        result = process_frame(frame, settings)

        # Colored lines should contain ANSI escapes
        for line in result.colored_lines:
            assert "\033[" in line

    def test_no_color_output(self):
        frame = _make_test_frame()
        settings = Settings(width=10, height=5, color_mode=ColorMode.NONE)
        result = process_frame(frame, settings)

        # No ANSI escapes in colored_lines when color is off
        for line in result.colored_lines:
            assert "\033[" not in line

    def test_dithered_output(self):
        frame = _make_test_frame()
        settings = Settings(
            width=20, height=10, dither=True, color_mode=ColorMode.NONE
        )
        result = process_frame(frame, settings)
        assert len(result.lines) == 10

    def test_inverted_output(self):
        frame = _make_test_frame(color=(0, 0, 0))  # Black
        s_normal = Settings(width=10, height=5, color_mode=ColorMode.NONE)
        s_invert = Settings(width=10, height=5, color_mode=ColorMode.NONE, invert=True)

        normal = process_frame(frame, s_normal)
        inverted = process_frame(frame, s_invert)

        # Inverted black should produce different chars than normal black
        assert normal.lines != inverted.lines

    def test_braille_output(self):
        frame = _make_test_frame()
        settings = Settings(
            width=20,
            height=10,
            charset=CharsetName.BRAILLE,
            color_mode=ColorMode.NONE,
        )
        result = process_frame(frame, settings)
        assert len(result.lines) == 10

        # All chars should be braille
        for line in result.lines:
            for ch in line:
                assert 0x2800 <= ord(ch) <= 0x28FF

    def test_different_charsets(self):
        frame = _make_test_frame(color=(128, 128, 128))
        for charset_name in [CharsetName.SIMPLE, CharsetName.DETAILED, CharsetName.BLOCKS]:
            settings = Settings(
                width=10, height=5, charset=charset_name, color_mode=ColorMode.NONE
            )
            result = process_frame(frame, settings)
            assert len(result.lines) == 5

    def test_brightness_adjustment(self):
        frame = _make_test_frame(color=(128, 128, 128))
        s_bright = Settings(width=10, height=5, brightness=50, color_mode=ColorMode.NONE)
        s_dark = Settings(width=10, height=5, brightness=-50, color_mode=ColorMode.NONE)

        bright = process_frame(frame, s_bright)
        dark = process_frame(frame, s_dark)

        # Different brightness should produce different output
        assert bright.lines != dark.lines
