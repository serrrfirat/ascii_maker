# ascii_maker

Convert GIF/MP4 files (or URLs) to ASCII art animations. Supports multiple character sets, color modes, and Floyd-Steinberg dithering.

## Installation

```bash
git clone https://github.com/serrrfirat/ascii_maker.git
cd ascii_maker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.11+.

## CLI Usage

### Headless conversion (recommended for agents)

```bash
ascii-maker convert <input> -o <output> [options] --json
```

Always use `--json` for structured, parseable output. Progress goes to stderr; the JSON result goes to stdout.

### Input formats

- Local files: GIF, MP4, AVI, MOV, MKV, WebM
- HTTP/HTTPS URLs (downloaded automatically)

### Output formats

- `.gif` — animated GIF
- `.mp4`, `.avi`, `.mov` — video via OpenCV

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-o, --output` | path | auto | Output path. Defaults to `<input>_ascii.<ext>` or `<input>_dithered.<ext>` with `--dither`. |
| `--charset` | choice | `simple` | `simple` (10 chars), `detailed` (70 chars), `blocks` (Unicode blocks), `braille` (2x4 bit-mapped, 256 codepoints) |
| `--color` | choice | `truecolor` | `none`, `256` (ANSI 256), `truecolor` (24-bit RGB) |
| `--dither` | flag | off | Enable Floyd-Steinberg error-diffusion dithering |
| `--brightness` | int | 0 | -100 to 100 |
| `--contrast` | int | 100 | 0 to 200 (100 = no change) |
| `--invert` | flag | off | Invert luminance |
| `--width` | int | 80 | Output width in characters |
| `--height` | int | 24 | Output height in characters |
| `--font-size` | int | 14 | Font size for rendered image output |
| `--json` | flag | off | Structured JSON output to stdout |
| `--no-tui` | flag | off | Headless mode without JSON |
| `--debug` | flag | off | Stack traces on error (with `--json`) |

## JSON output

### Success

```json
{
  "status": "success",
  "input": "/path/to/input.gif",
  "output": "/path/to/output.gif",
  "settings": {
    "charset": "simple",
    "color": "truecolor",
    "dither": false,
    "width": 80,
    "height": 24
  },
  "metadata": {
    "input_frames": 48,
    "output_frames": 48,
    "fps": 12.0,
    "input_format": "gif",
    "output_format": "gif"
  }
}
```

### Error (stderr, exit code 1)

```json
{
  "status": "error",
  "error": "File not found: /bad/path.gif",
  "code": "FILE_NOT_FOUND"
}
```

Error codes: `FILE_NOT_FOUND`, `DOWNLOAD_FAILED`, `INVALID_INPUT`, `PROCESSING_ERROR`.

## Examples

Convert a local GIF with default settings:

```bash
ascii-maker convert input.gif -o output.gif --json
```

Convert from URL with braille charset:

```bash
ascii-maker convert https://example.com/animation.gif -o output.gif --charset braille --json
```

High-detail dithered output:

```bash
ascii-maker convert input.gif -o output.gif --charset detailed --dither --json
```

Larger output with adjusted brightness:

```bash
ascii-maker convert input.mp4 -o output.gif --width 120 --height 40 --brightness 20 --json
```

## Charset guide

| Charset | Best for | Detail level |
|---------|----------|-------------|
| `simple` | General use, small outputs | Low (10 characters) |
| `detailed` | High-fidelity ASCII art | High (70 characters) |
| `blocks` | Bold, chunky look | Medium (Unicode block elements) |
| `braille` | Maximum spatial resolution | Very high (2x4 sub-cell mapping, 256 patterns) |

## Tips

- `--dither` pairs well with `detailed` or `simple` for a halftone look.
- `braille` gives the highest effective resolution since each character cell encodes a 2x4 pixel grid.
- For dark source material, try `--brightness 20 --contrast 120`.
- For light-on-dark inversion, use `--invert`.
- Output file extension determines format: use `.gif` for animated GIFs, `.mp4` for video.
