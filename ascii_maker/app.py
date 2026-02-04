"""Main Textual application for ascii_maker TUI."""

from __future__ import annotations

import asyncio
import platform
import subprocess
from pathlib import Path
from typing import Iterator

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Static,
)
from textual.worker import Worker, get_current_worker

from ascii_maker.core.processor import ProcessedFrame, Settings, process_frame
from ascii_maker.core.reader import Frame, GifReader, Mp4Reader, open_media
from ascii_maker.tui.controls import ControlPanel
from ascii_maker.tui.preview import AsciiPreview
from ascii_maker.tui.timeline import Timeline
from ascii_maker.utils.cache import FrameCache
from ascii_maker.utils.terminal import fit_to_terminal


class SaveScreen(ModalScreen[str | None]):
    """Modal screen for saving output."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def action_cancel(self) -> None:
        self.dismiss(None)

    DEFAULT_CSS = """
    SaveScreen {
        align: center middle;
    }

    SaveScreen #save-dialog {
        width: 60;
        height: 16;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    SaveScreen #save-title {
        text-style: bold;
        margin-bottom: 1;
    }

    SaveScreen Input {
        margin: 1 0;
    }

    SaveScreen .button-row {
        margin-top: 1;
        align: center middle;
        height: 3;
    }

    SaveScreen Button {
        margin: 0 1;
    }

    SaveScreen #save-status {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, default_path: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._default_path = default_path

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog"):
            yield Static("Save Output", id="save-title")
            yield Label("Output file path:")
            yield Input(
                value=self._default_path,
                placeholder="output.gif",
                id="save-path",
            )
            yield Label("Font size:")
            yield Input(
                value="14",
                placeholder="14",
                id="font-size-input",
            )
            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")
            yield Static("", id="save-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            path_input = self.query_one("#save-path", Input)
            self.dismiss(path_input.value)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)


class AsciiMakerApp(App):
    """Main TUI application."""

    TITLE = "ascii_maker"
    CSS = """
    #main-area {
        height: 1fr;
        width: 1fr;
    }

    #preview-container {
        width: 1fr;
        height: 1fr;
    }

    #status-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("space", "play_pause", "Play/Pause", priority=True),
        Binding("s", "save", "Save", priority=True),
        Binding("c", "copy", "Copy", priority=True),
        Binding("o", "open_file", "Open", priority=True),
        Binding("left", "prev_frame", "Prev Frame", priority=True),
        Binding("right", "next_frame", "Next Frame", priority=True),
        Binding("tab", "toggle_panel", "Toggle Panel"),
    ]

    def __init__(self, input_path: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._input_path = input_path
        self._reader: GifReader | Mp4Reader | None = None
        self._cache = FrameCache(max_size=64)
        self._current_frame_idx = 0
        self._playing = False
        self._playback_worker: Worker | None = None
        self._preview_worker: Worker | None = None
        self._settings = Settings()
        self._panel_visible = True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            with Vertical(id="preview-container"):
                yield AsciiPreview()
            yield ControlPanel(self._settings, id="control-panel")
        yield Timeline(total_frames=1, id="timeline")
        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        if self._input_path:
            self._load_file(self._input_path)

    def _load_file(self, path: str) -> None:
        """Load a media file."""
        try:
            self._reader = open_media(path)
            info = self._reader.info
            self.title = f"ascii_maker - {info.path.name}"

            # Calculate dimensions based on available preview space
            preview = self.query_one(AsciiPreview)
            pw = preview.size.width or 80
            ph = preview.size.height or 24
            char_w, char_h = fit_to_terminal(
                info.width, info.height, max_width=pw - 2, max_height=ph - 2
            )

            # Update settings dimensions
            panel = self.query_one(ControlPanel)
            panel.update_dimensions(char_w, char_h)
            self._settings = panel.settings

            # Update timeline
            timeline = self.query_one(Timeline)
            timeline.set_total_frames(info.frame_count)

            # Clear cache and show first frame
            self._cache.clear()
            self._current_frame_idx = 0
            self._update_status(f"Loaded {info.path.name} ({info.frame_count} frames)")
            self._render_current_frame()

        except Exception as e:
            self._update_status(f"Error: {e}")

    def _update_status(self, text: str) -> None:
        try:
            status = self.query_one("#status-bar", Static)
            status.update(text)
        except Exception:
            pass

    @work(thread=True, exclusive=True, group="preview")
    def _render_current_frame(self) -> None:
        """Render the current frame in a background thread."""
        if self._reader is None:
            return

        worker = get_current_worker()
        idx = self._current_frame_idx
        settings = self._settings
        cache_key = settings.hash()

        # Check cache
        cached = self._cache.get(idx, cache_key)
        if cached is not None:
            if not worker.is_cancelled:
                self.call_from_thread(self._display_frame, cached)
            return

        # Process frame
        try:
            raw_frame = self._reader.seek(idx)
            processed = process_frame(raw_frame, settings)
            self._cache.put(idx, cache_key, processed)
            if not worker.is_cancelled:
                self.call_from_thread(self._display_frame, processed)
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(self._update_status, f"Error: {e}")

    def _display_frame(self, frame: ProcessedFrame) -> None:
        """Display a processed frame (called on main thread)."""
        preview = self.query_one(AsciiPreview)
        preview.update_frame(frame)
        timeline = self.query_one(Timeline)
        timeline.set_frame(frame.index)

    @work(thread=True, exclusive=True, group="playback")
    def _playback_loop(self) -> None:
        """Playback loop running in a background thread."""
        if self._reader is None:
            return

        worker = get_current_worker()
        info = self._reader.info
        settings = self._settings
        cache_key = settings.hash()

        while self._playing and not worker.is_cancelled:
            idx = self._current_frame_idx

            # Check cache
            cached = self._cache.get(idx, cache_key)
            if cached is not None:
                frame = cached
            else:
                try:
                    raw_frame = self._reader.seek(idx)
                    frame = process_frame(raw_frame, settings)
                    self._cache.put(idx, cache_key, frame)
                except Exception:
                    break

            if worker.is_cancelled:
                break

            self.call_from_thread(self._display_frame, frame)

            # Wait for frame duration
            import time
            time.sleep(frame.duration_ms / 1000.0)

            # Advance
            self._current_frame_idx += 1
            if self._current_frame_idx >= info.frame_count:
                self._current_frame_idx = 0  # Loop

        self.call_from_thread(self._on_playback_stopped)

    def _on_playback_stopped(self) -> None:
        self._playing = False
        timeline = self.query_one(Timeline)
        timeline.set_playing(False)

    # --- Actions ---

    def action_play_pause(self) -> None:
        if self._reader is None:
            return
        self._playing = not self._playing
        timeline = self.query_one(Timeline)
        timeline.set_playing(self._playing)
        if self._playing:
            self._playback_loop()
        self._update_status("Playing" if self._playing else "Paused")

    def action_prev_frame(self) -> None:
        if self._reader is None:
            return
        self._playing = False
        info = self._reader.info
        self._current_frame_idx = max(0, self._current_frame_idx - 1)
        self._render_current_frame()

    def action_next_frame(self) -> None:
        if self._reader is None:
            return
        self._playing = False
        info = self._reader.info
        self._current_frame_idx = min(
            info.frame_count - 1, self._current_frame_idx + 1
        )
        self._render_current_frame()

    def action_save(self) -> None:
        if self._reader is None:
            self._update_status("No file loaded")
            return
        info = self._reader.info
        default_name = f"{info.path.stem}_ascii{info.path.suffix}"
        default_path = str(info.path.parent / default_name)
        self.push_screen(SaveScreen(default_path), self._on_save_result)

    def _on_save_result(self, path: str | None) -> None:
        if path is None:
            return
        self._do_save(path)

    @work(thread=True, exclusive=True, group="save")
    def _do_save(self, output_path: str) -> None:
        """Save all frames to file in a background thread."""
        from ascii_maker.core.writer import save_output

        if self._reader is None:
            return

        worker = get_current_worker()
        info = self._reader.info
        settings = self._settings
        out = Path(output_path)

        self.call_from_thread(self._update_status, "Saving...")

        def frame_generator() -> Iterator[ProcessedFrame]:
            for raw_frame in self._reader.frames():
                if worker.is_cancelled:
                    return
                processed = process_frame(raw_frame, settings)
                self.call_from_thread(
                    self._update_status,
                    f"Saving frame {raw_frame.index + 1}/{info.frame_count}...",
                )
                yield processed

        try:
            save_output(frame_generator(), out, fps=info.fps)
            if not worker.is_cancelled:
                self.call_from_thread(
                    self._update_status, f"Saved to {out}"
                )
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(self._update_status, f"Save error: {e}")

    def action_copy(self) -> None:
        """Copy the current frame's ASCII art to the system clipboard."""
        preview = self.query_one(AsciiPreview)
        frame = preview.current_frame
        if frame is None:
            self._update_status("No frame to copy")
            return

        text = "\n".join(frame.lines)
        try:
            system = platform.system()
            if system == "Darwin":
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            elif system == "Linux":
                proc = subprocess.Popen(
                    ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE
                )
            elif system == "Windows":
                proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            else:
                self._update_status("Clipboard not supported on this platform")
                return
            proc.communicate(text.encode("utf-8"))
            if proc.returncode == 0:
                self._update_status(f"Copied frame {frame.index + 1} to clipboard")
            else:
                self._update_status("Failed to copy to clipboard")
        except FileNotFoundError:
            self._update_status("Clipboard tool not found (pbcopy/xclip/clip)")
        except Exception as e:
            self._update_status(f"Copy failed: {e}")

    def action_open_file(self) -> None:
        # Simple input-based file open
        self.push_screen(OpenFileScreen(), self._on_file_selected)

    def _on_file_selected(self, path: str | None) -> None:
        if path:
            self._load_file(path)

    def action_toggle_panel(self) -> None:
        panel = self.query_one("#control-panel", ControlPanel)
        self._panel_visible = not self._panel_visible
        panel.display = self._panel_visible

    # --- Message handlers ---

    def on_control_panel_settings_changed(
        self, event: ControlPanel.SettingsChanged
    ) -> None:
        self._settings = event.settings
        self._cache.clear()
        if self._reader and not self._playing:
            self._render_current_frame()

    def on_timeline_frame_seek(self, event: Timeline.FrameSeek) -> None:
        if self._reader is None:
            return
        self._playing = False
        self._current_frame_idx = event.frame_index
        self._render_current_frame()

    def on_timeline_play_pause(self, event: Timeline.PlayPause) -> None:
        self.action_play_pause()

    def on_timeline_step_forward(self, event: Timeline.StepForward) -> None:
        self.action_next_frame()

    def on_timeline_step_backward(self, event: Timeline.StepBackward) -> None:
        self.action_prev_frame()

    def on_timeline_seek_start(self, event: Timeline.SeekStart) -> None:
        if self._reader is None:
            return
        self._playing = False
        self._current_frame_idx = 0
        self._render_current_frame()

    def on_timeline_seek_end(self, event: Timeline.SeekEnd) -> None:
        if self._reader is None:
            return
        self._playing = False
        self._current_frame_idx = self._reader.info.frame_count - 1
        self._render_current_frame()


class OpenFileScreen(ModalScreen[str | None]):
    """Simple modal for entering a file path."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def action_cancel(self) -> None:
        self.dismiss(None)

    DEFAULT_CSS = """
    OpenFileScreen {
        align: center middle;
    }

    OpenFileScreen #open-dialog {
        width: 60;
        height: 10;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    OpenFileScreen #open-title {
        text-style: bold;
        margin-bottom: 1;
    }

    OpenFileScreen .button-row {
        margin-top: 1;
        align: center middle;
        height: 3;
    }

    OpenFileScreen Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="open-dialog"):
            yield Static("Open File", id="open-title")
            yield Input(placeholder="Path to GIF or MP4 file...", id="file-input")
            with Horizontal(classes="button-row"):
                yield Button("Open", variant="primary", id="btn-open")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-open":
            inp = self.query_one("#file-input", Input)
            self.dismiss(inp.value if inp.value else None)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value if event.value else None)


def run_app(input_path: str | None = None) -> None:
    """Launch the TUI application."""
    app = AsciiMakerApp(input_path=input_path)
    app.run()
