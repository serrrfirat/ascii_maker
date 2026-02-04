"""Tests for media reader (GIF/MP4 frame extraction)."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ascii_maker.core.reader import (
    Frame,
    GifReader,
    MediaInfo,
    detect_format,
    open_media,
)


class TestDetectFormat:
    def test_gif(self):
        assert detect_format(Path("test.gif")) == "gif"

    def test_mp4(self):
        assert detect_format(Path("test.mp4")) == "mp4"

    def test_avi(self):
        assert detect_format(Path("test.avi")) == "mp4"

    def test_mov(self):
        assert detect_format(Path("test.mov")) == "mp4"

    def test_unsupported(self):
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format(Path("test.txt"))


class TestGifReader:
    @pytest.fixture
    def sample_gif(self, tmp_path):
        """Create a simple 3-frame animated GIF for testing."""
        frames = []
        for i in range(3):
            img = Image.new("RGB", (50, 50), (i * 80, 0, 0))
            frames.append(img)

        path = tmp_path / "test.gif"
        frames[0].save(
            str(path),
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )
        return path

    def test_open_gif(self, sample_gif):
        reader = GifReader(sample_gif)
        assert reader.frame_count == 3

    def test_gif_info(self, sample_gif):
        reader = GifReader(sample_gif)
        info = reader.info
        assert info.format == "gif"
        assert info.frame_count == 3
        assert info.width == 50
        assert info.height == 50

    def test_gif_frames_iterator(self, sample_gif):
        reader = GifReader(sample_gif)
        frames = list(reader.frames())
        assert len(frames) == 3
        for i, frame in enumerate(frames):
            assert isinstance(frame, Frame)
            assert frame.index == i
            assert frame.image.mode == "RGB"
            assert frame.duration_ms >= 10

    def test_gif_seek(self, sample_gif):
        reader = GifReader(sample_gif)
        frame = reader.seek(1)
        assert frame.index == 1
        assert frame.image.mode == "RGB"


class TestOpenMedia:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            open_media("/nonexistent/file.gif")

    def test_opens_gif(self, tmp_path):
        path = tmp_path / "test.gif"
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        img.save(str(path))

        reader = open_media(path)
        assert isinstance(reader, GifReader)
