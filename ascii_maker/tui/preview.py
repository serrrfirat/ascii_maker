"""ASCII preview widget for the TUI."""

from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from ascii_maker.core.processor import ProcessedFrame


def _ansi_to_rich_text(ansi_line: str) -> Text:
    """Convert a string with ANSI color escapes to a Rich Text object.

    Handles truecolor (38;2;r;g;b) and 256-color (38;5;N) escape sequences.
    """
    text = Text()
    current_style = ""
    i = 0

    while i < len(ansi_line):
        if ansi_line[i] == "\033" and i + 1 < len(ansi_line) and ansi_line[i + 1] == "[":
            # Parse escape sequence
            end = ansi_line.find("m", i)
            if end == -1:
                i += 1
                continue
            seq = ansi_line[i + 2 : end]
            parts = seq.split(";")

            if len(parts) >= 5 and parts[0] == "38" and parts[1] == "2":
                # Truecolor
                r = parts[2] if len(parts) > 2 else "255"
                g = parts[3] if len(parts) > 3 else "255"
                b = parts[4] if len(parts) > 4 else "255"
                current_style = f"rgb({r},{g},{b})"
            elif len(parts) >= 3 and parts[0] == "38" and parts[1] == "5":
                # 256-color
                current_style = f"color({parts[2]})"
            elif parts == ["0"]:
                current_style = ""

            i = end + 1
        else:
            text.append(ansi_line[i], style=current_style)
            i += 1

    return text


class AsciiPreview(Widget):
    """Widget that displays colored ASCII art frames.

    Converts ANSI escape codes to Rich Text objects for proper
    rendering within the Textual framework.
    """

    DEFAULT_CSS = """
    AsciiPreview {
        width: 1fr;
        height: 1fr;
        overflow: auto;
        background: $surface;
    }

    AsciiPreview #preview-content {
        width: auto;
        height: auto;
    }
    """

    class FrameUpdated(Message):
        """Posted when a new frame is displayed."""
        def __init__(self, frame_index: int) -> None:
            super().__init__()
            self.frame_index = frame_index

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_frame: ProcessedFrame | None = None

    def compose(self) -> ComposeResult:
        yield Static("No file loaded. Press 'o' to open a file.", id="preview-content")

    def update_frame(self, frame: ProcessedFrame) -> None:
        """Update the preview with a new processed frame."""
        self._current_frame = frame
        content = self.query_one("#preview-content", Static)

        # Convert ANSI-colored lines to Rich Text
        combined = Text()
        for i, line in enumerate(frame.colored_lines):
            if i > 0:
                combined.append("\n")
            if "\033[" in line:
                combined.append_text(_ansi_to_rich_text(line))
            else:
                combined.append(line)

        content.update(combined)
        self.post_message(self.FrameUpdated(frame.index))

    def clear(self) -> None:
        """Clear the preview."""
        self._current_frame = None
        content = self.query_one("#preview-content", Static)
        content.update("No file loaded. Press 'o' to open a file.")

    @property
    def current_frame(self) -> ProcessedFrame | None:
        return self._current_frame
