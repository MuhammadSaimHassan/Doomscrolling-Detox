"""
DoomScroll Detox - client/core/ocr_processor.py

Phase 2: The Screen Reader (Privacy-Safe OCR)

When a distraction check triggers (e.g. from monitor.py detecting a
blacklisted window title), this module captures a low-resolution screenshot
of ONLY the active window, keeps it entirely in RAM as a PIL Image / numpy
array, and feeds it straight to a local EasyOCR reader instance.

Hard privacy guarantee: no image is ever written to disk. The screenshot
lives only as an in-memory array for the duration of this function call and
is garbage-collected as soon as OCR extraction completes.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PIL import ImageGrab, Image

try:
    from core.monitor import WindowMonitor
except ImportError:
    # Falls back to a plain sibling import when this file is run
    # standalone (e.g. `python core/ocr_processor.py`), where "core"
    # isn't on sys.path as a package.
    from monitor import WindowMonitor


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Downscale factor applied to the captured window before OCR. Lower
# resolution = faster OCR and less memory, at some cost to text accuracy
# on very small fonts.
DOWNSCALE_FACTOR = 0.6

# Discard any OCR-detected text fragment shorter than this many characters
# (filters out noise like stray punctuation, icons misread as letters, etc.)
MIN_TOKEN_LENGTH = 3

# EasyOCR languages to load. Add more language codes as needed, e.g. ['en', 'es'].
OCR_LANGUAGES = ["en"]


# --------------------------------------------------------------------------
# Active window bounding box (delegates to monitor.py's pywinctl-backed
# WindowMonitor, so there's only one place that talks to the OS window
# manager instead of two divergent implementations)
# --------------------------------------------------------------------------

_window_monitor = WindowMonitor()


def _get_active_window_bbox() -> Optional[Tuple[int, int, int, int]]:
    """
    Returns the (left, top, right, bottom) bounding box of the currently
    active window, or None if it can't be determined (in which case the
    caller should fall back to a full-screen capture).
    """
    return _window_monitor.get_active_window_bbox()


# --------------------------------------------------------------------------
# In-RAM screen capture
# --------------------------------------------------------------------------

def capture_active_window_in_ram() -> Image.Image:
    """
    Captures the active window (or, if unavailable, the full primary
    screen) directly into an in-memory PIL Image. Nothing touches disk.

    Returns a downscaled, RGB PIL Image object living purely in RAM.
    """
    bbox = _get_active_window_bbox()

    # ImageGrab.grab() captures straight into memory; no temp file is
    # ever created, regardless of whether bbox is provided.
    screenshot = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()

    if screenshot.mode != "RGB":
        screenshot = screenshot.convert("RGB")

    if DOWNSCALE_FACTOR != 1.0:
        new_size = (
            max(1, int(screenshot.width * DOWNSCALE_FACTOR)),
            max(1, int(screenshot.height * DOWNSCALE_FACTOR)),
        )
        screenshot = screenshot.resize(new_size, Image.LANCZOS)

    return screenshot


# --------------------------------------------------------------------------
# EasyOCR wrapper
# --------------------------------------------------------------------------

class ScreenTextExtractor:
    """
    Thin wrapper around a local EasyOCR Reader instance.

    The Reader is expensive to initialize (it loads model weights into
    memory), so this class is designed to be instantiated ONCE and reused
    across many extraction calls, rather than recreated per-check.
    """

    def __init__(self, languages: Optional[list] = None, gpu: bool = False) -> None:
        try:
            import easyocr
        except ImportError as exc:
            raise ImportError(
                "Missing dependency 'easyocr'. Install it with:\n"
                "    pip install easyocr"
            ) from exc

        self._reader = easyocr.Reader(languages or OCR_LANGUAGES, gpu=gpu)

    def extract_text(self, image: Image.Image) -> str:
        """
        Runs OCR on an in-memory PIL Image and returns a single
        consolidated, whitespace-joined string of the detected text
        fragments, with short/noisy fragments filtered out.

        The image is converted to a numpy array purely in RAM for EasyOCR
        (which expects an ndarray or file path) -- again, no disk I/O.
        """
        image_array = np.array(image)

        # readtext returns a list of (bbox, text, confidence) tuples.
        raw_results = self._reader.readtext(image_array)

        tokens = [
            text.strip()
            for (_bbox, text, _confidence) in raw_results
            if text and len(text.strip()) >= MIN_TOKEN_LENGTH
        ]

        # Explicitly drop references so the pixel data isn't lingering
        # any longer than necessary before garbage collection.
        del image_array

        return " ".join(tokens)


# --------------------------------------------------------------------------
# High-level convenience function
# --------------------------------------------------------------------------

def scan_active_window_for_text(extractor: ScreenTextExtractor) -> str:
    """
    Full privacy-safe pipeline for a single distraction check:
      1. Capture the active window into RAM.
      2. Feed it directly to EasyOCR.
      3. Return the consolidated extracted text.
      4. The captured image is discarded (out of scope) as soon as this
         function returns -- it is never persisted.
    """
    screenshot = capture_active_window_in_ram()
    extracted_text = extractor.extract_text(screenshot)
    del screenshot
    return extracted_text


# --------------------------------------------------------------------------
# Test runner
# --------------------------------------------------------------------------

def _test_runner() -> None:
    """
    Demonstrates the full flow: capture -> in-RAM OCR -> clean string
    output, run against whatever is currently on your screen.
    """
    print("[ocr_processor] Initializing EasyOCR reader (this can take a")
    print("[ocr_processor] moment the first time, while it downloads model weights)...")
    extractor = ScreenTextExtractor()

    print("[ocr_processor] Capturing active window and running OCR...")
    text = scan_active_window_for_text(extractor)

    print("\n[ocr_processor] Extracted text:")
    print("-" * 60)
    print(text if text else "<no text detected>")
    print("-" * 60)


if __name__ == "__main__":
    _test_runner()
