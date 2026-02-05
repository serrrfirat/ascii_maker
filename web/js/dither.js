/**
 * Floyd-Steinberg error diffusion dithering.
 * Ported from ascii_maker/core/dither.py
 */

/**
 * Apply Floyd-Steinberg dithering to a grayscale image.
 * @param {Float32Array[]} gray - 2D array of rows, values in [0.0, 1.0]
 * @param {number} levels - number of output levels (2 = binary)
 * @returns {Float32Array[]} - dithered array
 */
export function floydSteinberg(gray, levels = 2) {
  const h = gray.length;
  const w = gray[0]?.length || 0;

  // Copy the array
  const img = gray.map((row) => new Float32Array(row));

  const step = levels > 1 ? 1.0 / (levels - 1) : 1.0;

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const old = img[y][x];
      let newVal = Math.round(old / step) * step;
      newVal = Math.max(0.0, Math.min(1.0, newVal));
      img[y][x] = newVal;
      const err = old - newVal;

      if (x + 1 < w) {
        img[y][x + 1] += err * (7 / 16);
      }
      if (y + 1 < h) {
        if (x - 1 >= 0) {
          img[y + 1][x - 1] += err * (3 / 16);
        }
        img[y + 1][x] += err * (5 / 16);
        if (x + 1 < w) {
          img[y + 1][x + 1] += err * (1 / 16);
        }
      }
    }
  }

  // Clamp values
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      img[y][x] = Math.max(0.0, Math.min(1.0, img[y][x]));
    }
  }

  return img;
}
