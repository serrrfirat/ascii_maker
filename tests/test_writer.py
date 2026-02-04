"""Tests for the output writer."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from ascii_maker.core.processor import ProcessedFrame, Settings, process_frame
from ascii_maker.core.reader import Frame
from ascii_maker.core.writer import (
    _strip_ansi,
    render_frame_to_image,
    save_gif,
)


def _make_processed_frame(width=20, height=10, index=0):
    """Create a test ProcessedFrame."""
    img = Image.new("RGB", (100, 100), (128, 128, 128))
    raw = Frame(image=img, duration_ms=100, index=index)
    settings = Settings(width=width, height=height)
    return process_frame(raw, settings)


class TestStripAnsi:
    def test_no_ansi(self):
        assert _strip_ansi("hello world") == "hello world"

    def test_with_color(self):
        text = "\033[38;2;255;0;0mX\033[0m"
        assert _strip_ansi(text) == "X"

    def test_with_256_color(self):
        text = "\033[38;5;196mA\033[0m"
        assert _strip_ansi(text) == "A"


class TestRenderFrame:
    def test_produces_image(self):
        frame = _make_processed_frame()
        img = render_frame_to_image(frame)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.width > 0
        assert img.height > 0

    def test_no_color_render(self):
        frame = _make_processed_frame()
        img = render_frame_to_image(frame, use_color=False)
        assert isinstance(img, Image.Image)


class TestSaveGif:
    def test_save_single_frame_gif(self, tmp_path):
        frame = _make_processed_frame(index=0)
        output = tmp_path / "test_output.gif"

        save_gif(iter([frame]), output, total_frames=1)

        assert output.exists()
        # Verify it's a valid GIF
        img = Image.open(str(output))
        assert img.format == "GIF"

    def test_save_multi_frame_gif(self, tmp_path):
        # Use different colors so frames aren't identical (Pillow deduplicates)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        frames = []
        for i, color in enumerate(colors):
            img = Image.new("RGB", (100, 100), color)
            raw = Frame(image=img, duration_ms=100, index=i)
            settings = Settings(width=20, height=10)
            frames.append(process_frame(raw, settings))
        output = tmp_path / "test_multi.gif"

        save_gif(iter(frames), output, total_frames=3)

        assert output.exists()
        img = Image.open(str(output))
        assert img.format == "GIF"
        # Check it's animated
        assert getattr(img, "n_frames", 1) == 3

    def test_progress_callback(self, tmp_path):
        frames = [_make_processed_frame(index=i) for i in range(3)]
        output = tmp_path / "test_progress.gif"
        progress = []

        def on_progress(current, total):
            progress.append((current, total))

        save_gif(iter(frames), output, total_frames=3, on_progress=on_progress)

        assert len(progress) == 3
        assert progress[-1] == (3, 3)

    def test_empty_frames_raises(self, tmp_path):
        output = tmp_path / "empty.gif"
        with pytest.raises(ValueError, match="No frames"):
            save_gif(iter([]), output)
