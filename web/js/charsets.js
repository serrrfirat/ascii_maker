/**
 * Character set presets for ASCII art conversion.
 * Ported from ascii_maker/core/charsets.py
 */

// Ordered dark → light (low luminance → high luminance)
export const CHARSETS = {
  simple: " .:-=+*#%@",
  detailed:
    " .`'^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
  blocks: " ▁▂▃▄▅▆▇█",
  braille: "⠀⠁", // placeholder; braille uses bit-mapping
};

/**
 * Map a luminance value (0.0-1.0) to a character index.
 */
export function charIndexForLuminance(charset, luminance) {
  const chars = CHARSETS[charset];
  const idx = Math.floor(luminance * (chars.length - 1));
  return Math.max(0, Math.min(idx, chars.length - 1));
}

/**
 * Map a luminance value (0.0-1.0) to a character.
 */
export function charForLuminance(charset, luminance) {
  return CHARSETS[charset][charIndexForLuminance(charset, luminance)];
}

/**
 * Map a 2D luminance array to lines of characters.
 * @param {string} charset - charset name
 * @param {Float32Array[]} luminanceRows - array of rows, each row is Float32Array of luminance values
 * @returns {string[]} - array of strings
 */
export function mapArrayToChars(charset, luminanceRows) {
  const chars = CHARSETS[charset];
  const maxIdx = chars.length - 1;
  const lines = [];

  for (const row of luminanceRows) {
    let line = "";
    for (let i = 0; i < row.length; i++) {
      let idx = Math.floor(row[i] * maxIdx);
      idx = Math.max(0, Math.min(idx, maxIdx));
      line += chars[idx];
    }
    lines.push(line);
  }
  return lines;
}

// --- Braille encoding ---
// Braille characters use a 2-wide x 4-tall dot grid per character.
// Unicode braille block starts at U+2800.
// Dot positions (col 0, col 1):
//   row 0: bit 0, bit 3
//   row 1: bit 1, bit 4
//   row 2: bit 2, bit 5
//   row 3: bit 6, bit 7

const BRAILLE_BASE = 0x2800;

const BRAILLE_DOT_BITS = [
  [0, 3], // row 0
  [1, 4], // row 1
  [2, 5], // row 2
  [6, 7], // row 3
];

/**
 * Convert a 4x2 boolean array to a single braille character.
 * @param {boolean[][]} dots - 4 rows, 2 cols
 * @returns {string}
 */
export function brailleChar(dots) {
  let code = 0;
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 2; col++) {
      if (dots[row][col]) {
        code |= 1 << BRAILLE_DOT_BITS[row][col];
      }
    }
  }
  return String.fromCharCode(BRAILLE_BASE + code);
}

/**
 * Convert a 2D binary (thresholded) array to braille art lines.
 * Input height should be divisible by 4, width by 2.
 * @param {Uint8Array[]} binary - array of rows, values 0 or 1
 * @returns {string[]} - braille lines
 */
export function brailleFromArray(binary) {
  let h = binary.length;
  let w = binary[0]?.length || 0;

  // Pad to multiples of 4 (height) and 2 (width) if needed
  const padH = (4 - (h % 4)) % 4;
  const padW = (2 - (w % 2)) % 2;

  if (padH > 0 || padW > 0) {
    const newH = h + padH;
    const newW = w + padW;
    const padded = [];
    for (let y = 0; y < newH; y++) {
      const row = new Uint8Array(newW);
      if (y < h) {
        row.set(binary[y]);
      }
      padded.push(row);
    }
    binary = padded;
    h = newH;
    w = newW;
  }

  const lines = [];
  for (let y = 0; y < h; y += 4) {
    let lineChars = "";
    for (let x = 0; x < w; x += 2) {
      const dots = [
        [binary[y][x] > 0, binary[y][x + 1] > 0],
        [binary[y + 1][x] > 0, binary[y + 1][x + 1] > 0],
        [binary[y + 2][x] > 0, binary[y + 2][x + 1] > 0],
        [binary[y + 3][x] > 0, binary[y + 3][x + 1] > 0],
      ];
      lineChars += brailleChar(dots);
    }
    lines.push(lineChars);
  }
  return lines;
}
