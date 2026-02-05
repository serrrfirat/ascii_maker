/**
 * Canvas rendering for ASCII preview and GIF export.
 */

/**
 * Render ASCII text with colors to a canvas.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string[]} lines - ASCII text lines
 * @param {number[][][]} colors - 2D array of [r,g,b] per character (or null for no color)
 * @param {Object} options
 * @param {number} options.fontSize
 * @param {string} options.fontFamily
 * @param {string} options.bgColor
 * @param {string} options.defaultColor
 */
export function renderAsciiToCanvas(ctx, lines, colors, options = {}) {
  const {
    fontSize = 14,
    fontFamily = "monospace",
    bgColor = "#1a1a2e",
    defaultColor = "#e0e0e0",
  } = options;

  const canvas = ctx.canvas;

  // Set font to measure character dimensions
  ctx.font = `${fontSize}px ${fontFamily}`;
  const charWidth = ctx.measureText("M").width;
  const lineHeight = fontSize * 1.2;

  // Calculate required canvas size
  const maxLineLen = Math.max(...lines.map((l) => l.length));
  const requiredWidth = Math.ceil(charWidth * maxLineLen) + 4;
  const requiredHeight = Math.ceil(lineHeight * lines.length) + 4;

  // Resize canvas if needed
  if (canvas.width !== requiredWidth || canvas.height !== requiredHeight) {
    canvas.width = requiredWidth;
    canvas.height = requiredHeight;
    // Re-set font after resize (canvas resize clears context state)
    ctx.font = `${fontSize}px ${fontFamily}`;
  }

  // Clear with background
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw text
  ctx.textBaseline = "top";

  for (let y = 0; y < lines.length; y++) {
    const line = lines[y];
    const rowColors = colors?.[y];

    for (let x = 0; x < line.length; x++) {
      const char = line[x];
      if (char === " ") continue; // Skip spaces for performance

      if (rowColors && rowColors[x]) {
        const [r, g, b] = rowColors[x];
        ctx.fillStyle = `rgb(${r},${g},${b})`;
      } else {
        ctx.fillStyle = defaultColor;
      }

      ctx.fillText(char, x * charWidth + 2, y * lineHeight + 2);
    }
  }
}

/**
 * Create a canvas with ASCII art rendered.
 * @param {string[]} lines
 * @param {number[][][]} colors
 * @param {Object} options
 * @returns {HTMLCanvasElement}
 */
export function createAsciiCanvas(lines, colors, options = {}) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  renderAsciiToCanvas(ctx, lines, colors, options);
  return canvas;
}

/**
 * Export processed frames as an animated GIF.
 * Uses gif.js library.
 * @param {Object[]} frames - Array of { lines, colors, delay }
 * @param {Object} options
 * @param {number} options.fontSize
 * @param {Function} onProgress - callback(percent)
 * @returns {Promise<Blob>}
 */
export async function exportGif(frames, options = {}, onProgress = null) {
  const { fontSize = 14 } = options;

  // Create GIF encoder
  // gif.js is loaded globally from CDN
  const gif = new GIF({
    workers: 2,
    quality: 10,
    workerScript: "https://unpkg.com/gif.js@0.2.0/dist/gif.worker.js",
  });

  // Render each frame
  for (const frame of frames) {
    const canvas = createAsciiCanvas(frame.lines, frame.colors, { fontSize });
    gif.addFrame(canvas, { delay: frame.delay, copy: true });
  }

  // Return promise that resolves with blob
  return new Promise((resolve, reject) => {
    gif.on("finished", (blob) => {
      resolve(blob);
    });

    gif.on("progress", (p) => {
      if (onProgress) {
        onProgress(Math.round(p * 100));
      }
    });

    gif.render();
  });
}

/**
 * Download a blob as a file.
 * @param {Blob} blob
 * @param {string} filename
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
