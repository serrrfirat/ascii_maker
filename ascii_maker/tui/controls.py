"""Settings control panel for the TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
    Static,
)

from ascii_maker.core.charsets import CharsetName
from ascii_maker.core.color import ColorMode
from ascii_maker.core.processor import Settings


class ControlPanel(Widget):
    """Settings panel with controls for ASCII conversion parameters."""

    DEFAULT_CSS = """
    ControlPanel {
        width: 30;
        height: 1fr;
        background: $panel;
        padding: 1;
        border-left: solid $accent;
    }

    ControlPanel Label {
        margin-top: 1;
        color: $text-muted;
    }

    ControlPanel Select {
        width: 100%;
        margin-bottom: 0;
    }

    ControlPanel Checkbox {
        margin-top: 1;
    }

    ControlPanel #panel-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    ControlPanel .num-row {
        height: 3;
        margin-top: 1;
    }

    ControlPanel .num-row Label {
        width: 12;
        margin-top: 0;
        padding-top: 1;
    }

    ControlPanel .num-row Button {
        min-width: 3;
        margin: 0;
    }

    ControlPanel .num-row Input {
        width: 1fr;
        margin: 0;
    }
    """

    class SettingsChanged(Message):
        """Posted when any setting changes."""
        def __init__(self, settings: Settings) -> None:
            super().__init__()
            self.settings = settings

    def __init__(self, settings: Settings | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._settings = settings or Settings()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Settings", id="panel-title")

            yield Label("Charset")
            yield Select(
                [(c.value, c.value) for c in CharsetName],
                value=self._settings.charset.value,
                id="charset-select",
            )

            yield Label("Color")
            yield Select(
                [(c.value, c.value) for c in ColorMode],
                value=self._settings.color_mode.value,
                id="color-select",
            )

            yield Checkbox("Dither", value=self._settings.dither, id="dither-check")
            yield Checkbox("Invert", value=self._settings.invert, id="invert-check")

            with Horizontal(classes="num-row"):
                yield Label("Brightness")
                yield Button("-", id="bright-dec")
                yield Input(
                    value=str(self._settings.brightness),
                    id="brightness-input",
                    type="integer",
                )
                yield Button("+", id="bright-inc")

            with Horizontal(classes="num-row"):
                yield Label("Contrast")
                yield Button("-", id="contrast-dec")
                yield Input(
                    value=str(self._settings.contrast),
                    id="contrast-input",
                    type="integer",
                )
                yield Button("+", id="contrast-inc")

    @property
    def settings(self) -> Settings:
        return self._settings

    def _update_settings(self, **overrides) -> None:
        """Create new settings with overrides and emit change."""
        self._settings = Settings(
            charset=overrides.get("charset", self._settings.charset),
            color_mode=overrides.get("color_mode", self._settings.color_mode),
            dither=overrides.get("dither", self._settings.dither),
            brightness=overrides.get("brightness", self._settings.brightness),
            contrast=overrides.get("contrast", self._settings.contrast),
            invert=overrides.get("invert", self._settings.invert),
            width=overrides.get("width", self._settings.width),
            height=overrides.get("height", self._settings.height),
        )
        self.post_message(self.SettingsChanged(self._settings))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "charset-select" and event.value is not None:
            self._update_settings(charset=CharsetName(event.value))
        elif event.select.id == "color-select" and event.value is not None:
            self._update_settings(color_mode=ColorMode(event.value))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "dither-check":
            self._update_settings(dither=event.value)
        elif event.checkbox.id == "invert-check":
            self._update_settings(invert=event.value)

    def _adjust_brightness(self, delta: int) -> None:
        new_val = max(-100, min(100, self._settings.brightness + delta))
        try:
            self.query_one("#brightness-input", Input).value = str(new_val)
        except Exception:
            pass
        self._update_settings(brightness=new_val)

    def _adjust_contrast(self, delta: int) -> None:
        new_val = max(0, min(200, self._settings.contrast + delta))
        try:
            self.query_one("#contrast-input", Input).value = str(new_val)
        except Exception:
            pass
        self._update_settings(contrast=new_val)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "bright-dec":
            self._adjust_brightness(-10)
        elif btn == "bright-inc":
            self._adjust_brightness(10)
        elif btn == "contrast-dec":
            self._adjust_contrast(-10)
        elif btn == "contrast-inc":
            self._adjust_contrast(10)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            val = int(event.value)
        except ValueError:
            return
        if event.input.id == "brightness-input":
            self._update_settings(brightness=max(-100, min(100, val)))
        elif event.input.id == "contrast-input":
            self._update_settings(contrast=max(0, min(200, val)))

    def update_dimensions(self, width: int, height: int) -> None:
        """Update the target output dimensions."""
        self._settings = Settings(
            charset=self._settings.charset,
            color_mode=self._settings.color_mode,
            dither=self._settings.dither,
            brightness=self._settings.brightness,
            contrast=self._settings.contrast,
            invert=self._settings.invert,
            width=width,
            height=height,
        )
