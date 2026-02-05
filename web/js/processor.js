/**
 * Frame processing pipeline.
 * Resize → grayscale → brightness/contrast → dither/char-map → colorize.
 * Ported from ascii_maker/core/processor.py
 */

import { CHARSETS, mapArrayToChars, brailleFromArray } from "./charsets.js";
import { floydSteinberg } from "./dither.js";

/**
 * Resize ImageData to target dimensions using canvas.
 * @param {ImageData} imageData
 * @param {number} width
 * @param {number} height
 * @returns {ImageData}
 */
function resizeImageData(imageData, width, height) {
  // Create source canvas
  const srcCanvas = document.createElement("canvas");
  srcCanvas.width = imageData.width;
  srcCanvas.height = imageData.height;
  const srcCtx = srcCanvas.getContext("2d");
  srcCtx.putImageData(imageData, 0, 0);

  // Create dest canvas and draw scaled
  const dstCanvas = document.createElement("canvas");
  dstCanvas.width = width;
  dstCanvas.height = height;
  const dstCtx = dstCanvas.getContext("2d");
  dstCtx.imageSmoothingEnabled = true;
  dstCtx.imageSmoothingQuality = "high";
  dstCtx.drawImage(srcCanvas, 0, 0, width, height);

  return dstCtx.getImageData(0, 0, width, height);
}

/**
 * Convert ImageData to grayscale float array.
 * @param {ImageData} imageData
 * @returns {Float32Array[]} - 2D array of rows, values [0, 1]
 */
function toGrayscale(imageData) {
  const { width, height, data } = imageData;
  const rows = [];

  for (let y = 0; y < height; y++) {
    const row = new Float32Array(width);
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      // Standard luminance formula
      const lum = (0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) / 255;
      row[x] = lum;
    }
    rows.push(row);
  }
  return rows;
}

/**
 * Apply brightness and contrast adjustments.
 * @param {Float32Array[]} gray
 * @param {number} brightness - -100 to 100
 * @param {number} contrast - 0 to 200 (100 = no change)
 * @returns {Float32Array[]}
 */
function adjustBrightnessContrast(gray, brightness, contrast) {
  const h = gray.length;
  const w = gray[0]?.length || 0;
  const result = gray.map((row) => new Float32Array(row));

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let val = result[y][x];

      // Brightness: shift
      if (brightness !== 0) {
        val = val + brightness / 100.0;
      }

      // Contrast: scale around 0.5
      if (contrast !== 100) {
        const factor = contrast / 100.0;
        val = (val - 0.5) * factor + 0.5;
      }

      result[y][x] = Math.max(0.0, Math.min(1.0, val));
    }
  }
  return result;
}

/**
 * Get per-character RGB colors by sampling resized image.
 * @param {ImageData} imageData - original image
 * @param {number} width - target width
 * @param {number} height - target height
 * @returns {Uint8Array[][]} - 2D array of [r, g, b] values
 */
function getColorSamples(imageData, width, height) {
  const resized = resizeImageData(imageData, width, height);
  const { data } = resized;
  const colors = [];

  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      row.push([data[i], data[i + 1], data[i + 2]]);
    }
    colors.push(row);
  }
  return colors;
}

/**
 * Get per-braille-character RGB colors by averaging 2x4 blocks.
 * @param {ImageData} imageData - original image
 * @param {number} width - character width
 * @param {number} height - character height
 * @returns {Uint8Array[][]}
 */
function getBrailleColorSamples(imageData, width, height) {
  const pixelW = width * 2;
  const pixelH = height * 4;
  const resized = resizeImageData(imageData, pixelW, pixelH);
  const { data } = resized;
  const colors = [];

  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      let rSum = 0,
        gSum = 0,
        bSum = 0;
      const count = 8; // 2x4 block

      for (let dy = 0; dy < 4; dy++) {
        for (let dx = 0; dx < 2; dx++) {
          const px = x * 2 + dx;
          const py = y * 4 + dy;
          const i = (py * pixelW + px) * 4;
          rSum += data[i];
          gSum += data[i + 1];
          bSum += data[i + 2];
        }
      }

      row.push([
        Math.round(rSum / count),
        Math.round(gSum / count),
        Math.round(bSum / count),
      ]);
    }
    colors.push(row);
  }
  return colors;
}

/**
 * Process a frame through the full pipeline.
 * @param {ImageData} imageData - source frame
 * @param {Object} settings
 * @param {string} settings.charset - 'simple', 'detailed', 'blocks', 'braille'
 * @param {string} settings.colorMode - 'none', 'truecolor'
 * @param {boolean} settings.dither
 * @param {number} settings.brightness - -100 to 100
 * @param {number} settings.contrast - 0 to 200
 * @param {boolean} settings.invert
 * @param {number} settings.width
 * @param {number} settings.height
 * @returns {Object} - { lines, colors, width, height }
 */
export function processFrame(imageData, settings) {
  const {
    charset,
    colorMode,
    dither,
    brightness,
    contrast,
    invert,
    width,
    height,
  } = settings;

  const isBraille = charset === "braille";

  // Resize
  let resizedWidth, resizedHeight;
  if (isBraille) {
    resizedWidth = width * 2;
    resizedHeight = height * 4;
  } else {
    resizedWidth = width;
    resizedHeight = height;
  }

  const resized = resizeImageData(imageData, resizedWidth, resizedHeight);

  // Grayscale
  let gray = toGrayscale(resized);

  // Brightness / contrast
  gray = adjustBrightnessContrast(gray, brightness, contrast);

  // Invert
  if (invert) {
    for (let y = 0; y < gray.length; y++) {
      for (let x = 0; x < gray[y].length; x++) {
        gray[y][x] = 1.0 - gray[y][x];
      }
    }
  }

  let plainLines;

  if (isBraille) {
    // Braille: threshold to binary, optionally with dithering
    if (dither) {
      gray = floydSteinberg(gray, 2);
    }
    // Convert to binary
    const binary = gray.map((row) => {
      const binRow = new Uint8Array(row.length);
      for (let x = 0; x < row.length; x++) {
        binRow[x] = row[x] > 0.5 ? 1 : 0;
      }
      return binRow;
    });
    plainLines = brailleFromArray(binary);
  } else {
    // Normal charsets
    if (dither) {
      gray = floydSteinberg(gray, CHARSETS[charset].length);
    }
    plainLines = mapArrayToChars(charset, gray);
  }

  // Color samples
  let colorSamples = null;
  if (colorMode !== "none") {
    if (isBraille) {
      colorSamples = getBrailleColorSamples(imageData, width, height);
    } else {
      colorSamples = getColorSamples(imageData, width, height);
    }

    // Apply invert to colors too
    if (invert) {
      for (let y = 0; y < colorSamples.length; y++) {
        for (let x = 0; x < colorSamples[y].length; x++) {
          colorSamples[y][x] = [
            255 - colorSamples[y][x][0],
            255 - colorSamples[y][x][1],
            255 - colorSamples[y][x][2],
          ];
        }
      }
    }
  }

  return {
    lines: plainLines,
    colors: colorSamples,
    width,
    height,
  };
}
