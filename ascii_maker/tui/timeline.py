"""Playback timeline widget with transport controls and frame scrubber."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar, Static


class Timeline(Widget):
    """Playback transport controls and frame scrubber."""

    DEFAULT_CSS = """
    Timeline {
        height: 3;
        width: 1fr;
        background: $panel;
        border-top: solid $accent;
        layout: horizontal;
        padding: 0 1;
        align: center middle;
    }

    Timeline Button {
        min-width: 5;
        margin: 0 0;
    }

    Timeline #frame-label {
        width: 14;
        text-align: center;
        margin: 0 1;
    }

    Timeline #frame-bar {
        width: 1fr;
        margin: 0 1;
    }
    """

    class FrameSeek(Message):
        """User requested a specific frame."""
        def __init__(self, frame_index: int) -> None:
            super().__init__()
            self.frame_index = frame_index

    class PlayPause(Message):
        """User toggled play/pause."""
        pass

    class StepForward(Message):
        pass

    class StepBackward(Message):
        pass

    class SeekStart(Message):
        pass

    class SeekEnd(Message):
        pass

    def __init__(self, total_frames: int = 1, **kwargs) -> None:
        super().__init__(**kwargs)
        self._total_frames = max(total_frames, 1)
        self._current_frame = 0
        self._playing = False

    def compose(self) -> ComposeResult:
        yield Button("|<", id="btn-start", variant="default")
        yield Button("<", id="btn-prev", variant="default")
        yield Button("▶", id="btn-play", variant="primary")
        yield Button(">", id="btn-next", variant="default")
        yield Button(">|", id="btn-end", variant="default")
        yield Label(
            f"1/{self._total_frames}",
            id="frame-label",
        )
        yield ProgressBar(
            total=max(self._total_frames, 1),
            show_eta=False,
            show_percentage=False,
            id="frame-bar",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-start":
            self.post_message(self.SeekStart())
        elif btn_id == "btn-prev":
            self.post_message(self.StepBackward())
        elif btn_id == "btn-play":
            self._playing = not self._playing
            event.button.label = "||" if self._playing else "▶"
            self.post_message(self.PlayPause())
        elif btn_id == "btn-next":
            self.post_message(self.StepForward())
        elif btn_id == "btn-end":
            self.post_message(self.SeekEnd())

    def set_frame(self, index: int) -> None:
        """Update the displayed frame position (from playback)."""
        self._current_frame = index
        self._update_label()
        self._update_bar()

    def set_total_frames(self, total: int) -> None:
        """Update total frame count (when a new file is loaded)."""
        self._total_frames = max(total, 1)
        self._current_frame = 0
        self._update_label()
        try:
            bar = self.query_one("#frame-bar", ProgressBar)
            bar.update(total=self._total_frames, progress=0)
        except Exception:
            pass

    def set_playing(self, playing: bool) -> None:
        """Update play/pause button state."""
        self._playing = playing
        try:
            btn = self.query_one("#btn-play", Button)
            btn.label = "||" if playing else "▶"
        except Exception:
            pass

    def _update_label(self) -> None:
        try:
            label = self.query_one("#frame-label", Label)
            label.update(f"{self._current_frame + 1}/{self._total_frames}")
        except Exception:
            pass

    def _update_bar(self) -> None:
        try:
            bar = self.query_one("#frame-bar", ProgressBar)
            bar.update(progress=self._current_frame + 1)
        except Exception:
            pass
