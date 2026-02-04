"""Command-line interface for ascii_maker.

Supports both interactive TUI mode and headless/JSON mode for agent integration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ascii_maker.core.charsets import CharsetName
from ascii_maker.core.color import ColorMode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ascii-maker",
        description="Convert GIF/MP4 to ASCII art or dithered animations.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- convert subcommand ---
    convert = subparsers.add_parser(
        "convert",
        help="Convert a media file to ASCII art.",
    )
    convert.add_argument("input", help="Input GIF or MP4 file path.")
    convert.add_argument(
        "-o", "--output",
        help="Output file path. Defaults to <input>_ascii.<ext>.",
    )
    convert.add_argument(
        "--charset",
        choices=[c.value for c in CharsetName],
        default="simple",
        help="Character set preset (default: simple).",
    )
    convert.add_argument(
        "--color",
        choices=[c.value for c in ColorMode],
        default="truecolor",
        help="Color mode (default: truecolor).",
    )
    convert.add_argument(
        "--dither",
        action="store_true",
        help="Enable Floyd-Steinberg dithering.",
    )
    convert.add_argument(
        "--brightness",
        type=int,
        default=0,
        help="Brightness adjustment, -100 to 100 (default: 0).",
    )
    convert.add_argument(
        "--contrast",
        type=int,
        default=100,
        help="Contrast adjustment, 0 to 200 (default: 100).",
    )
    convert.add_argument(
        "--invert",
        action="store_true",
        help="Invert luminance.",
    )
    convert.add_argument(
        "--width",
        type=int,
        default=80,
        help="Output width in characters (default: 80).",
    )
    convert.add_argument(
        "--height",
        type=int,
        default=24,
        help="Output height in characters (default: 24).",
    )
    convert.add_argument(
        "--font-size",
        type=int,
        default=14,
        help="Font size for rendered output (default: 14).",
    )
    convert.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON (pipe-friendly, no TUI).",
    )
    convert.add_argument(
        "--no-tui",
        action="store_true",
        help="Run headless (no interactive TUI).",
    )
    convert.add_argument(
        "--debug",
        action="store_true",
        help="Show stack traces on error (with --json).",
    )

    return parser


def _auto_output_path(input_path: Path, dither: bool) -> Path:
    """Generate default output path from input."""
    stem = input_path.stem
    suffix = input_path.suffix
    tag = "dithered" if dither else "ascii"
    return input_path.parent / f"{stem}_{tag}{suffix}"


def _json_error(message: str, code: str, debug: bool = False) -> None:
    """Print JSON error to stderr and exit with code 1."""
    err = {"status": "error", "error": message, "code": code}
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _run_convert(args: argparse.Namespace) -> None:
    """Run the headless convert pipeline."""
    from ascii_maker.core.processor import Settings, process_frame
    from ascii_maker.core.reader import is_url, open_media
    from ascii_maker.core.writer import save_output

    raw_input = args.input
    is_json = args.json
    is_remote = is_url(raw_input)

    if is_remote:
        if not is_json:
            print(f"Downloading {raw_input}...", file=sys.stderr)
        input_display = raw_input
    else:
        input_path = Path(raw_input).resolve()
        input_display = str(input_path)
        if not input_path.exists():
            if is_json:
                _json_error(f"File not found: {input_path}", "FILE_NOT_FOUND")
            else:
                print(f"Error: File not found: {input_path}", file=sys.stderr)
                sys.exit(1)

    try:
        reader = open_media(raw_input)
    except (ValueError, IOError, FileNotFoundError) as e:
        code = "DOWNLOAD_FAILED" if is_remote else "INVALID_INPUT"
        if is_json:
            _json_error(str(e), code)
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    info = reader.info
    input_path = info.path  # Actual local path (may be temp file for URLs)

    # Determine output path
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = _auto_output_path(input_path, args.dither)

    settings = Settings(
        charset=CharsetName(args.charset),
        color_mode=ColorMode(args.color),
        dither=args.dither,
        brightness=args.brightness,
        contrast=args.contrast,
        invert=args.invert,
        width=args.width,
        height=args.height,
    )

    frame_count = 0

    def processed_frames():
        nonlocal frame_count
        for raw_frame in reader.frames():
            yield process_frame(raw_frame, settings)
            frame_count += 1
            if not is_json:
                print(
                    f"\rProcessing frame {frame_count}/{info.frame_count}...",
                    end="",
                    file=sys.stderr,
                )

    try:
        save_output(
            processed_frames(),
            output_path,
            fps=info.fps,
            font_size=args.font_size,
        )
    except Exception as e:
        if is_json:
            if args.debug:
                import traceback
                traceback.print_exc(file=sys.stderr)
            _json_error(str(e), "PROCESSING_ERROR")
        else:
            print(f"\nError during processing: {e}", file=sys.stderr)
            sys.exit(1)

    if not is_json:
        print(f"\nSaved to {output_path}", file=sys.stderr)
    else:
        result = {
            "status": "success",
            "input": input_display,
            "output": str(output_path),
            "settings": {
                "charset": settings.charset.value,
                "color": settings.color_mode.value,
                "dither": settings.dither,
                "width": settings.width,
                "height": settings.height,
            },
            "metadata": {
                "input_frames": info.frame_count,
                "output_frames": frame_count,
                "fps": info.fps,
                "input_format": info.format,
                "output_format": output_path.suffix.lstrip("."),
            },
        }
        print(json.dumps(result, indent=2))


def main() -> None:
    """Main entry point.

    Routing:
      ascii-maker convert <file> [opts]  → convert subcommand
      ascii-maker <file>                 → launch TUI with file
      ascii-maker                        → launch TUI (file picker)
    """
    # If the first real arg isn't "convert", treat it as a direct TUI launch
    # to avoid argparse subparser consuming the file path as a subcommand.
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "convert":
        parser = _build_parser()
        args = parser.parse_args()
        if args.json or args.no_tui:
            _run_convert(args)
        else:
            from ascii_maker.app import run_app
            run_app(input_path=args.input)
    elif raw_args and not raw_args[0].startswith("-"):
        # Positional arg = file path → TUI
        from ascii_maker.app import run_app
        run_app(input_path=raw_args[0])
    elif raw_args and raw_args[0] in ("-h", "--help"):
        parser = _build_parser()
        parser.parse_args()
    else:
        # No args → TUI with file picker
        from ascii_maker.app import run_app
        run_app()
