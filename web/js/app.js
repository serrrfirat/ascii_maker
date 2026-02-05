/**
 * Main application logic for ASCII Maker web interface.
 */

import { loadGifFromFile, loadStaticImage, loadGifFromUrl } from "./gif-parser.js";
import { processFrame } from "./processor.js";
import { renderAsciiToCanvas, exportGif, downloadBlob } from "./renderer.js";

// Application state
const state = {
  frames: null, // Parsed frames from input
  processedFrames: null, // ASCII-converted frames
  sourceWidth: 0,
  sourceHeight: 0,
  currentFrame: 0,
  isPlaying: false,
  playbackTimer: null,
  settings: {
    charset: "simple",
    colorMode: "truecolor",
    dither: false,
    brightness: 0,
    contrast: 100,
    invert: false,
    width: 80,
    height: 24,
  },
};

// DOM elements
let elements = {};

/**
 * Initialize the application.
 */
export function init() {
  // Get DOM elements
  elements = {
    fileInput: document.getElementById("file-input"),
    dropZone: document.getElementById("drop-zone"),
    urlInput: document.getElementById("url-input"),
    urlLoadBtn: document.getElementById("url-load-btn"),
    previewCanvas: document.getElementById("preview-canvas"),
    playBtn: document.getElementById("play-btn"),
    prevBtn: document.getElementById("prev-btn"),
    nextBtn: document.getElementById("next-btn"),
    frameSlider: document.getElementById("frame-slider"),
    frameDisplay: document.getElementById("frame-display"),
    charsetSelect: document.getElementById("charset-select"),
    colorModeSelect: document.getElementById("color-mode-select"),
    ditherCheckbox: document.getElementById("dither-checkbox"),
    invertCheckbox: document.getElementById("invert-checkbox"),
    brightnessSlider: document.getElementById("brightness-slider"),
    brightnessValue: document.getElementById("brightness-value"),
    contrastSlider: document.getElementById("contrast-slider"),
    contrastValue: document.getElementById("contrast-value"),
    widthInput: document.getElementById("width-input"),
    heightInput: document.getElementById("height-input"),
    downloadBtn: document.getElementById("download-btn"),
    downloadProgress: document.getElementById("download-progress"),
    statusText: document.getElementById("status-text"),
  };

  // Bind event listeners
  bindEvents();

  // Set initial UI state
  updateUI();
}

/**
 * Bind all event listeners.
 */
function bindEvents() {
  // File input
  elements.fileInput.addEventListener("change", handleFileSelect);

  // Drag and drop
  elements.dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    elements.dropZone.classList.add("drag-over");
  });

  elements.dropZone.addEventListener("dragleave", () => {
    elements.dropZone.classList.remove("drag-over");
  });

  elements.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    elements.dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) loadFile(file);
  });

  elements.dropZone.addEventListener("click", () => {
    elements.fileInput.click();
  });

  // URL input
  elements.urlLoadBtn.addEventListener("click", handleUrlLoad);
  elements.urlInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      handleUrlLoad();
    }
  });

  // Playback controls
  elements.playBtn.addEventListener("click", togglePlayback);
  elements.prevBtn.addEventListener("click", prevFrame);
  elements.nextBtn.addEventListener("click", nextFrame);
  elements.frameSlider.addEventListener("input", handleSliderChange);

  // Settings
  elements.charsetSelect.addEventListener("change", handleSettingChange);
  elements.colorModeSelect.addEventListener("change", handleSettingChange);
  elements.ditherCheckbox.addEventListener("change", handleSettingChange);
  elements.invertCheckbox.addEventListener("change", handleSettingChange);

  elements.brightnessSlider.addEventListener("input", () => {
    elements.brightnessValue.textContent = elements.brightnessSlider.value;
  });
  elements.brightnessSlider.addEventListener("change", handleSettingChange);

  elements.contrastSlider.addEventListener("input", () => {
    elements.contrastValue.textContent = elements.contrastSlider.value;
  });
  elements.contrastSlider.addEventListener("change", handleSettingChange);

  elements.widthInput.addEventListener("change", handleDimensionChange);
  elements.heightInput.addEventListener("change", handleDimensionChange);

  // Download
  elements.downloadBtn.addEventListener("click", handleDownload);

  // Keyboard shortcuts
  document.addEventListener("keydown", handleKeyboard);
}

/**
 * Handle file selection from input.
 */
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) loadFile(file);
}

/**
 * Handle URL load button click.
 */
async function handleUrlLoad() {
  const url = elements.urlInput.value.trim();
  if (!url) {
    setStatus("Please enter a URL");
    return;
  }

  setStatus("Loading from URL...");
  elements.urlLoadBtn.disabled = true;

  try {
    const result = await loadGifFromUrl(url);

    state.frames = result.frames;
    state.sourceWidth = result.width;
    state.sourceHeight = result.height;
    state.currentFrame = 0;

    // Auto-calculate aspect ratio preserving dimensions
    const aspectRatio = result.width / result.height;
    const charAspect = aspectRatio * 2;
    if (charAspect > state.settings.width / state.settings.height) {
      state.settings.height = Math.round(state.settings.width / charAspect);
    } else {
      state.settings.width = Math.round(state.settings.height * charAspect);
    }

    elements.widthInput.value = state.settings.width;
    elements.heightInput.value = state.settings.height;

    // Update slider range
    elements.frameSlider.max = Math.max(0, state.frames.length - 1);
    elements.frameSlider.value = 0;

    // Process frames
    await processAllFrames();

    setStatus(`Loaded: ${result.width}x${result.height}, ${state.frames.length} frame(s)`);
    updateUI();
    renderCurrentFrame();
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`);
  } finally {
    elements.urlLoadBtn.disabled = false;
  }
}

/**
 * Load a file (GIF or static image).
 */
async function loadFile(file) {
  setStatus("Loading...");

  try {
    let result;
    if (file.type === "image/gif") {
      result = await loadGifFromFile(file);
    } else {
      result = await loadStaticImage(file);
    }

    state.frames = result.frames;
    state.sourceWidth = result.width;
    state.sourceHeight = result.height;
    state.currentFrame = 0;

    // Auto-calculate aspect ratio preserving dimensions
    const aspectRatio = result.width / result.height;
    // Terminal characters are ~2:1 tall, so adjust
    const charAspect = aspectRatio * 2;
    if (charAspect > state.settings.width / state.settings.height) {
      // Width-constrained
      state.settings.height = Math.round(state.settings.width / charAspect);
    } else {
      // Height-constrained
      state.settings.width = Math.round(state.settings.height * charAspect);
    }

    elements.widthInput.value = state.settings.width;
    elements.heightInput.value = state.settings.height;

    // Update slider range
    elements.frameSlider.max = Math.max(0, state.frames.length - 1);
    elements.frameSlider.value = 0;

    // Process frames
    await processAllFrames();

    setStatus(`Loaded: ${result.width}x${result.height}, ${state.frames.length} frame(s)`);
    updateUI();
    renderCurrentFrame();
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`);
  }
}

/**
 * Process all frames with current settings.
 */
async function processAllFrames() {
  if (!state.frames) return;

  setStatus("Processing...");
  state.processedFrames = [];

  for (let i = 0; i < state.frames.length; i++) {
    const frame = state.frames[i];
    const processed = processFrame(frame.imageData, state.settings);
    state.processedFrames.push({
      ...processed,
      delay: frame.delay,
    });

    // Update progress for large GIFs
    if (state.frames.length > 10 && i % 5 === 0) {
      setStatus(`Processing frame ${i + 1}/${state.frames.length}...`);
      // Allow UI to update
      await new Promise((r) => setTimeout(r, 0));
    }
  }

  setStatus(`Processed ${state.frames.length} frame(s)`);
}

/**
 * Render the current frame to the preview canvas.
 */
function renderCurrentFrame() {
  if (!state.processedFrames || state.processedFrames.length === 0) return;

  const frame = state.processedFrames[state.currentFrame];
  const ctx = elements.previewCanvas.getContext("2d");

  renderAsciiToCanvas(ctx, frame.lines, frame.colors, {
    fontSize: 14,
    bgColor: "#0f172a",
    defaultColor: "#e2e8f0",
  });

  // Update frame display
  elements.frameDisplay.textContent = `${state.currentFrame + 1} / ${state.processedFrames.length}`;
  elements.frameSlider.value = state.currentFrame;
}

/**
 * Toggle playback.
 */
function togglePlayback() {
  if (state.isPlaying) {
    stopPlayback();
  } else {
    startPlayback();
  }
}

/**
 * Start animation playback.
 */
function startPlayback() {
  if (!state.processedFrames || state.processedFrames.length <= 1) return;

  state.isPlaying = true;
  updatePlayButton(true);

  function tick() {
    if (!state.isPlaying) return;

    const frame = state.processedFrames[state.currentFrame];
    state.currentFrame = (state.currentFrame + 1) % state.processedFrames.length;
    renderCurrentFrame();

    state.playbackTimer = setTimeout(tick, frame.delay);
  }

  tick();
}

/**
 * Stop animation playback.
 */
function stopPlayback() {
  state.isPlaying = false;
  updatePlayButton(false);
  if (state.playbackTimer) {
    clearTimeout(state.playbackTimer);
    state.playbackTimer = null;
  }
}

/**
 * Update play button icon.
 */
function updatePlayButton(isPlaying) {
  const playIcon = elements.playBtn.querySelector('.play-icon');
  const pauseIcon = elements.playBtn.querySelector('.pause-icon');
  if (playIcon && pauseIcon) {
    playIcon.classList.toggle('hidden', isPlaying);
    pauseIcon.classList.toggle('hidden', !isPlaying);
  }
}

/**
 * Go to previous frame.
 */
function prevFrame() {
  if (!state.processedFrames) return;
  stopPlayback();
  state.currentFrame =
    (state.currentFrame - 1 + state.processedFrames.length) %
    state.processedFrames.length;
  renderCurrentFrame();
}

/**
 * Go to next frame.
 */
function nextFrame() {
  if (!state.processedFrames) return;
  stopPlayback();
  state.currentFrame = (state.currentFrame + 1) % state.processedFrames.length;
  renderCurrentFrame();
}

/**
 * Handle frame slider change.
 */
function handleSliderChange() {
  if (!state.processedFrames) return;
  stopPlayback();
  state.currentFrame = parseInt(elements.frameSlider.value, 10);
  renderCurrentFrame();
}

/**
 * Handle setting changes.
 */
async function handleSettingChange() {
  state.settings.charset = elements.charsetSelect.value;
  state.settings.colorMode = elements.colorModeSelect.value;
  state.settings.dither = elements.ditherCheckbox.checked;
  state.settings.invert = elements.invertCheckbox.checked;
  state.settings.brightness = parseInt(elements.brightnessSlider.value, 10);
  state.settings.contrast = parseInt(elements.contrastSlider.value, 10);

  if (state.frames) {
    await processAllFrames();
    renderCurrentFrame();
  }
}

/**
 * Handle dimension changes.
 */
async function handleDimensionChange() {
  const width = parseInt(elements.widthInput.value, 10);
  const height = parseInt(elements.heightInput.value, 10);

  if (width > 0 && width <= 300 && height > 0 && height <= 100) {
    state.settings.width = width;
    state.settings.height = height;

    if (state.frames) {
      await processAllFrames();
      renderCurrentFrame();
    }
  }
}

/**
 * Handle download button click.
 */
async function handleDownload() {
  if (!state.processedFrames || state.processedFrames.length === 0) return;

  stopPlayback();
  elements.downloadBtn.disabled = true;
  elements.downloadProgress.style.display = "block";
  elements.downloadProgress.textContent = "Encoding GIF...";

  try {
    const blob = await exportGif(state.processedFrames, { fontSize: 14 }, (progress) => {
      elements.downloadProgress.textContent = `Encoding: ${progress}%`;
    });

    downloadBlob(blob, "ascii-art.gif");
    elements.downloadProgress.textContent = "Done!";
    setTimeout(() => {
      elements.downloadProgress.style.display = "none";
    }, 2000);
  } catch (err) {
    console.error(err);
    elements.downloadProgress.textContent = `Error: ${err.message}`;
  } finally {
    elements.downloadBtn.disabled = false;
  }
}

/**
 * Handle keyboard shortcuts.
 */
function handleKeyboard(e) {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;

  switch (e.key) {
    case " ":
      e.preventDefault();
      togglePlayback();
      break;
    case "ArrowLeft":
      e.preventDefault();
      prevFrame();
      break;
    case "ArrowRight":
      e.preventDefault();
      nextFrame();
      break;
  }
}

/**
 * Update UI state.
 */
function updateUI() {
  const hasFrames = state.processedFrames && state.processedFrames.length > 0;
  const multiFrame = hasFrames && state.processedFrames.length > 1;

  elements.playBtn.disabled = !multiFrame;
  elements.prevBtn.disabled = !multiFrame;
  elements.nextBtn.disabled = !multiFrame;
  elements.frameSlider.disabled = !multiFrame;
  elements.downloadBtn.disabled = !hasFrames;
}

/**
 * Set status text.
 */
function setStatus(text) {
  elements.statusText.textContent = text;
}

// Initialize on DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
