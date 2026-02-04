"""Frame extraction from GIF and MP4 files, including URL downloads.

Provides a unified lazy iterator interface for both formats.
GIF frames are composited onto a canvas to handle disposal methods correctly.
"""

from __future__ import annotations

import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import cv2
import numpy as np
from PIL import Image


@dataclass
class Frame:
    """A single video/animation frame."""

    image: Image.Image  # RGB PIL image
    duration_ms: int  # Display duration in milliseconds
    index: int


@dataclass
class MediaInfo:
    """Metadata about the input file."""

    path: Path
    format: str  # "gif" or "mp4"
    frame_count: int
    fps: float
    width: int
    height: int


def detect_format(path: Path) -> str:
    """Detect media format from file extension."""
    suffix = path.suffix.lower()
    if suffix == ".gif":
        return "gif"
    if suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return "mp4"
    raise ValueError(f"Unsupported format: {suffix}")


class GifReader:
    """Lazy frame iterator for GIF files with proper disposal handling."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._img = Image.open(path)
        self._frame_count = getattr(self._img, "n_frames", 1)
        self._canvas: Image.Image | None = None

    @property
    def info(self) -> MediaInfo:
        duration = self._img.info.get("duration", 100)
        fps = 1000.0 / max(duration, 1)
        return MediaInfo(
            path=self.path,
            format="gif",
            frame_count=self._frame_count,
            fps=fps,
            width=self._img.width,
            height=self._img.height,
        )

    def frames(self) -> Iterator[Frame]:
        """Yield all frames with proper GIF disposal compositing."""
        img = Image.open(self.path)
        canvas = Image.new("RGBA", img.size, (0, 0, 0, 255))

        for i in range(self._frame_count):
            img.seek(i)
            duration = img.info.get("duration", 100)

            # Handle disposal
            frame = img.convert("RGBA")
            canvas.paste(frame, (0, 0), frame)

            yield Frame(
                image=canvas.copy().convert("RGB"),
                duration_ms=max(duration, 10),  # Clamp absurdly short durations
                index=i,
            )

    def seek(self, frame_idx: int) -> Frame:
        """Get a specific frame by index (composites up to that frame)."""
        img = Image.open(self.path)
        canvas = Image.new("RGBA", img.size, (0, 0, 0, 255))

        for i in range(frame_idx + 1):
            img.seek(i)
            frame = img.convert("RGBA")
            canvas.paste(frame, (0, 0), frame)

        duration = img.info.get("duration", 100)
        return Frame(
            image=canvas.convert("RGB"),
            duration_ms=max(duration, 10),
            index=frame_idx,
        )

    @property
    def frame_count(self) -> int:
        return self._frame_count


class Mp4Reader:
    """Lazy frame iterator for MP4/video files using OpenCV."""

    def __init__(self, path: Path) -> None:
        self.path = path
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise IOError(f"Cannot open video: {path}")
        self._frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        self._width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

    @property
    def info(self) -> MediaInfo:
        return MediaInfo(
            path=self.path,
            format="mp4",
            frame_count=self._frame_count,
            fps=self._fps,
            width=self._width,
            height=self._height,
        )

    def frames(self) -> Iterator[Frame]:
        """Yield all frames lazily."""
        cap = cv2.VideoCapture(str(self.path))
        duration_ms = int(1000.0 / self._fps)
        idx = 0
        try:
            while True:
                ret, bgr = cap.read()
                if not ret:
                    break
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                yield Frame(image=pil_img, duration_ms=duration_ms, index=idx)
                idx += 1
        finally:
            cap.release()

    def seek(self, frame_idx: int) -> Frame:
        """Get a specific frame by index."""
        cap = cv2.VideoCapture(str(self.path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, bgr = cap.read()
        cap.release()
        if not ret:
            raise IndexError(f"Frame {frame_idx} not found")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        duration_ms = int(1000.0 / self._fps)
        return Frame(image=pil_img, duration_ms=duration_ms, index=frame_idx)

    @property
    def frame_count(self) -> int:
        return self._frame_count


def is_url(path: str) -> bool:
    """Check if the input looks like an HTTP(S) URL."""
    try:
        parsed = urlparse(str(path))
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def _guess_extension_from_url(url: str) -> str:
    """Extract file extension from a URL path."""
    parsed = urlparse(url)
    url_path = parsed.path.split("?")[0]  # Strip query params
    suffix = Path(url_path).suffix.lower()
    if suffix in (".gif", ".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return suffix
    # Default to .gif for ambiguous URLs
    return ".gif"


def download_media(
    url: str,
    on_progress: callable | None = None,
) -> Path:
    """Download a media file from a URL to a temp file.

    Args:
        url: HTTP(S) URL to download.
        on_progress: optional callback(bytes_downloaded, total_bytes).

    Returns:
        Path to the downloaded temporary file.

    Raises:
        ValueError: if the URL is unreachable or returns an error.
    """
    ext = _guess_extension_from_url(url)
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp_path = Path(tmp.name)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ascii-maker/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
        tmp.close()
    except urllib.error.URLError as e:
        tmp.close()
        tmp_path.unlink(missing_ok=True)
        raise ValueError(f"Failed to download {url}: {e}") from e
    except Exception:
        tmp.close()
        tmp_path.unlink(missing_ok=True)
        raise

    # Validate it's a real media file
    if tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        raise ValueError(f"Downloaded file is empty: {url}")

    return tmp_path


def open_media(path: str | Path) -> GifReader | Mp4Reader:
    """Open a media file and return the appropriate reader.

    Accepts local file paths or HTTP(S) URLs. URLs are downloaded
    to a temporary file first.
    """
    path_str = str(path)
    if is_url(path_str):
        local_path = download_media(path_str)
    else:
        local_path = Path(path_str)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_path}")

    fmt = detect_format(local_path)
    if fmt == "gif":
        return GifReader(local_path)
    return Mp4Reader(local_path)
