/**
 * GIF parser using gifuct-js library.
 * Handles GIF parsing with proper disposal method support.
 */

// Import gifuct-js from CDN (loaded via importmap in HTML)
import { parseGIF, decompressFrames } from "gifuct-js";

/**
 * Parse a GIF file into frames.
 * @param {ArrayBuffer} buffer - GIF file data
 * @returns {Object[]} - Array of { imageData, delay, disposalType }
 */
export function parseGifBuffer(buffer) {
  const gif = parseGIF(buffer);
  const frames = decompressFrames(gif, true);
  return frames;
}

/**
 * Build full frames from GIF patch frames, handling disposal methods.
 * GIF frames can be patches that need compositing onto previous frames.
 * @param {Object[]} rawFrames - from parseGifBuffer
 * @param {number} width - GIF width
 * @param {number} height - GIF height
 * @returns {Object[]} - Array of { imageData: ImageData, delay: number }
 */
export function buildFullFrames(rawFrames, width, height) {
  // Create a canvas for compositing
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  // Previous frame for disposal
  let previousImageData = null;

  const fullFrames = [];

  for (const frame of rawFrames) {
    const { dims, patch, delay, disposalType } = frame;

    // Save current state if disposal is "restore to previous"
    if (disposalType === 3 && previousImageData) {
      // Will restore to this after drawing
    }

    // If disposal of previous frame was "restore to background", clear that area
    // (handled implicitly by fresh frame composition for type 2)

    // Create ImageData for this patch
    const patchCanvas = document.createElement("canvas");
    patchCanvas.width = dims.width;
    patchCanvas.height = dims.height;
    const patchCtx = patchCanvas.getContext("2d");
    const patchImageData = patchCtx.createImageData(dims.width, dims.height);
    patchImageData.data.set(patch);
    patchCtx.putImageData(patchImageData, 0, 0);

    // Draw patch onto main canvas at correct position
    ctx.drawImage(patchCanvas, dims.left, dims.top);

    // Capture the full frame
    const fullImageData = ctx.getImageData(0, 0, width, height);
    fullFrames.push({
      imageData: fullImageData,
      delay: delay || 100, // default 100ms if not specified
    });

    // Handle disposal
    if (disposalType === 2) {
      // Restore to background (clear the frame area)
      ctx.clearRect(dims.left, dims.top, dims.width, dims.height);
    } else if (disposalType === 3) {
      // Restore to previous - restore the saved state
      if (previousImageData) {
        ctx.putImageData(previousImageData, 0, 0);
      }
    } else {
      // disposalType 0 or 1: do not dispose, keep current state
      previousImageData = ctx.getImageData(0, 0, width, height);
    }
  }

  return fullFrames;
}

// CORS proxies to try in order
const CORS_PROXIES = [
  (url) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  (url) => `https://corsproxy.io/?${encodeURIComponent(url)}`,
  (url) => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(url)}`,
];

/**
 * Load and parse an image from a URL (GIF or static image).
 * Automatically uses a CORS proxy if direct fetch fails.
 * @param {string} url
 * @returns {Promise<{frames: Object[], width: number, height: number}>}
 */
export async function loadGifFromUrl(url) {
  let response;
  let lastError;

  // Try direct fetch first
  try {
    response = await fetch(url);
    if (response.ok) {
      return await processResponse(response);
    }
  } catch (err) {
    console.log("Direct fetch failed, trying CORS proxies...");
  }

  // Try each proxy
  for (const proxyFn of CORS_PROXIES) {
    const proxyUrl = proxyFn(url);
    try {
      console.log("Trying proxy:", proxyUrl.substring(0, 50) + "...");
      response = await fetch(proxyUrl);
      if (response.ok) {
        return await processResponse(response);
      }
    } catch (err) {
      lastError = err;
      console.log("Proxy failed, trying next...");
    }
  }

  throw new Error("Failed to fetch URL (all proxies failed). Try uploading the file directly.");
}

/**
 * Process a successful response into frames.
 */
async function processResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const buffer = await response.arrayBuffer();

  // Check if it's a GIF by content type or by inspecting magic bytes
  const isGif = contentType.includes("gif") || isGifBuffer(buffer);

  if (isGif) {
    return parseGifFromBuffer(buffer);
  } else {
    // Static image - load via Image element
    return loadStaticImageFromBuffer(buffer, contentType);
  }
}

/**
 * Check if buffer starts with GIF magic bytes.
 */
function isGifBuffer(buffer) {
  const arr = new Uint8Array(buffer, 0, 6);
  const magic = String.fromCharCode(...arr);
  return magic === "GIF87a" || magic === "GIF89a";
}

/**
 * Load a static image from an ArrayBuffer.
 */
function loadStaticImageFromBuffer(buffer, contentType) {
  return new Promise((resolve, reject) => {
    const blob = new Blob([buffer], { type: contentType || "image/png" });
    const img = new Image();
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      URL.revokeObjectURL(url);

      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);

      const imageData = ctx.getImageData(0, 0, img.width, img.height);
      resolve({
        frames: [{ imageData, delay: 100 }],
        width: img.width,
        height: img.height,
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load image from URL"));
    };

    img.src = url;
  });
}

/**
 * Parse a GIF from an ArrayBuffer.
 * @param {ArrayBuffer} buffer
 * @returns {{frames: Object[], width: number, height: number}}
 */
export function parseGifFromBuffer(buffer) {
  const rawFrames = parseGifBuffer(buffer);

  if (rawFrames.length === 0) {
    throw new Error("No frames found in GIF");
  }

  // Get dimensions from first frame's dims or the GIF logical screen
  const width = rawFrames[0].dims.width;
  const height = rawFrames[0].dims.height;

  // Actually need the logical screen size, check if there's top/left offset
  let maxWidth = width;
  let maxHeight = height;
  for (const frame of rawFrames) {
    maxWidth = Math.max(maxWidth, frame.dims.left + frame.dims.width);
    maxHeight = Math.max(maxHeight, frame.dims.top + frame.dims.height);
  }

  const frames = buildFullFrames(rawFrames, maxWidth, maxHeight);

  return {
    frames,
    width: maxWidth,
    height: maxHeight,
  };
}

/**
 * Load a GIF from a File object.
 * @param {File} file
 * @returns {Promise<{frames: Object[], width: number, height: number}>}
 */
export async function loadGifFromFile(file) {
  const buffer = await file.arrayBuffer();
  return parseGifFromBuffer(buffer);
}

/**
 * Load a static image (PNG/JPG) as a single frame.
 * @param {File|Blob} file
 * @returns {Promise<{frames: Object[], width: number, height: number}>}
 */
export async function loadStaticImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);

      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);

      const imageData = ctx.getImageData(0, 0, img.width, img.height);
      resolve({
        frames: [{ imageData, delay: 100 }],
        width: img.width,
        height: img.height,
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load image"));
    };

    img.src = url;
  });
}
