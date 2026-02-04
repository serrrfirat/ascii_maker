"""Save processed ASCII frames as GIF or MP4.

Renders text lines onto images using Pillow, then saves as animated GIF
or MP4 via OpenCV VideoWriter.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ascii_maker.core.processor import ProcessedFrame

# Monospace font size and metrics
DEFAULT_FONT_SIZE = 14
CHAR_WIDTH_RATIO = 0.6  # Approximate char width / font size for monospace


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _get_font(size: int = DEFAULT_FONT_SIZE) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a monospace font for rendering."""
    # Try common monospace fonts
    for name in [
        "DejaVuSansMono.ttf",
        "Menlo.ttc",
        "Consolas.ttf",
        "CourierNew.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _parse_ansi_colors(colored_line: str) -> list[tuple[str, tuple[int, int, int]]]:
    """Parse ANSI-colored text into (char, rgb) pairs.

    Handles truecolor (38;2;r;g;b) and 256-color (38;5;N) sequences.
    Returns list of (character, (r, g, b)) tuples.
    """
    result: list[tuple[str, tuple[int, int, int]]] = []
    current_color = (255, 255, 255)
    i = 0
    line = colored_line

    while i < len(line):
        if line[i] == "\033" and i + 1 < len(line) and line[i + 1] == "[":
            # Parse escape sequence
            end = line.find("m", i)
            if end == -1:
                i += 1
                continue
            seq = line[i + 2 : end]
            parts = seq.split(";")

            if len(parts) >= 5 and parts[0] == "38" and parts[1] == "2":
                # Truecolor
                r = int(parts[2]) if parts[2].isdigit() else 255
                g = int(parts[3]) if parts[3].isdigit() else 255
                b = int(parts[4]) if parts[4].isdigit() else 255
                current_color = (r, g, b)
            elif len(parts) >= 3 and parts[0] == "38" and parts[1] == "5":
                # 256-color - convert to approximate RGB
                idx = int(parts[2]) if parts[2].isdigit() else 7
                current_color = _ansi256_to_rgb(idx)
            elif parts == ["0"]:
                current_color = (255, 255, 255)

            i = end + 1
        else:
            result.append((line[i], current_color))
            i += 1

    return result


def _ansi256_to_rgb(idx: int) -> tuple[int, int, int]:
    """Convert ANSI 256-color index to approximate RGB."""
    if idx < 16:
        # Standard colors (approximate)
        basic = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
        ]
        return basic[idx]
    if idx < 232:
        # 6x6x6 color cube
        idx -= 16
        b = (idx % 6) * 51
        g = ((idx // 6) % 6) * 51
        r = (idx // 36) * 51
        return (r, g, b)
    # Grayscale ramp
    gray = (idx - 232) * 10 + 8
    return (gray, gray, gray)


def render_frame_to_image(
    frame: ProcessedFrame,
    font_size: int = DEFAULT_FONT_SIZE,
    bg_color: tuple[int, int, int] = (0, 0, 0),
    use_color: bool = True,
) -> Image.Image:
    """Render a ProcessedFrame to a PIL Image.

    Args:
        frame: the processed frame with text lines.
        font_size: pixel size for the monospace font.
        bg_color: background color RGB tuple.
        use_color: if True, parse ANSI colors from colored_lines.

    Returns:
        PIL Image with rendered text.
    """
    font = _get_font(font_size)

    # Calculate image dimensions
    char_w = int(font_size * CHAR_WIDTH_RATIO)
    char_h = font_size + 2
    lines = frame.colored_lines if use_color else frame.lines
    max_line_len = max((len(_strip_ansi(l)) for l in lines), default=0)

    img_w = max(max_line_len * char_w, 1)
    img_h = max(len(lines) * char_h, 1)

    img = Image.new("RGB", (img_w, img_h), bg_color)
    draw = ImageDraw.Draw(img)

    for row_idx, line in enumerate(lines):
        y = row_idx * char_h
        if use_color and "\033" in line:
            # Parse colored text and render char by char
            parsed = _parse_ansi_colors(line)
            for col_idx, (ch, color) in enumerate(parsed):
                x = col_idx * char_w
                draw.text((x, y), ch, fill=color, font=font)
        else:
            draw.text((0, y), line, fill=(255, 255, 255), font=font)

    return img


def save_gif(
    frames: Iterator[ProcessedFrame],
    output_path: Path,
    font_size: int = DEFAULT_FONT_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
    total_frames: int = 0,
) -> None:
    """Save processed frames as an animated GIF.

    Args:
        frames: iterator of ProcessedFrame objects.
        output_path: path to write the GIF.
        font_size: font size for rendering.
        on_progress: callback(current_frame, total_frames).
        total_frames: total frame count for progress reporting.
    """
    images: list[Image.Image] = []
    durations: list[int] = []

    for i, frame in enumerate(frames):
        img = render_frame_to_image(frame, font_size)
        images.append(img)
        durations.append(frame.duration_ms)
        if on_progress:
            on_progress(i + 1, total_frames)

    if not images:
        raise ValueError("No frames to save")

    # Normalize all frames to the same size (max dimensions)
    max_w = max(img.width for img in images)
    max_h = max(img.height for img in images)
    normalized = []
    for img in images:
        if img.width != max_w or img.height != max_h:
            canvas = Image.new("RGB", (max_w, max_h), (0, 0, 0))
            canvas.paste(img, (0, 0))
            normalized.append(canvas)
        else:
            normalized.append(img)

    normalized[0].save(
        str(output_path),
        save_all=True,
        append_images=normalized[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )


def save_mp4(
    frames: Iterator[ProcessedFrame],
    output_path: Path,
    fps: float = 24.0,
    font_size: int = DEFAULT_FONT_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
    total_frames: int = 0,
) -> None:
    """Save processed frames as an MP4 video.

    Args:
        frames: iterator of ProcessedFrame objects.
        output_path: path to write the MP4.
        fps: output frame rate.
        font_size: font size for rendering.
        on_progress: callback(current_frame, total_frames).
        total_frames: total frame count for progress reporting.
    """
    writer: cv2.VideoWriter | None = None

    try:
        for i, frame in enumerate(frames):
            img = render_frame_to_image(frame, font_size)
            arr = np.array(img)
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            if writer is None:
                h, w = bgr.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

            writer.write(bgr)
            if on_progress:
                on_progress(i + 1, total_frames)
    finally:
        if writer is not None:
            writer.release()


def save_output(
    frames: Iterator[ProcessedFrame],
    output_path: Path,
    fps: float = 24.0,
    font_size: int = DEFAULT_FONT_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
    total_frames: int = 0,
) -> None:
    """Save frames in format determined by output file extension."""
    suffix = output_path.suffix.lower()
    if suffix == ".gif":
        save_gif(frames, output_path, font_size, on_progress, total_frames)
    elif suffix in (".mp4", ".avi", ".mov"):
        save_mp4(frames, output_path, fps, font_size, on_progress, total_frames)
    else:
        raise ValueError(f"Unsupported output format: {suffix}")
