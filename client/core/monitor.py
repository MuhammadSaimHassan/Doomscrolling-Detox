"""
DoomScroll Detox - client/core/monitor.py

Phase 1: The Local Spy

Runs a background loop that polls the active/foreground window every 3
seconds, prints its title, and raises a terminal alert if the title
matches a hardcoded blacklist of known distraction sources.

Uses `pywinctl` for active-window lookups, which is genuinely
cross-platform (Windows, macOS, and Linux/X11) under one API -- so unlike
the old pygetwindow (Windows-only) + raw AppKit/Quartz (macOS-only)
split, this file no longer needs to branch per OS at all.
"""

from __future__ import annotations

import sys
import time
import platform
from datetime import datetime
from typing import Optional


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 3

# Hardcoded blacklist of distraction phrases (case-insensitive substring
# match against the active window title). Extend this freely.
BLACKLISTED_PHRASES = [
    "youtube",
    "tiktok",
    "reddit",
    "twitter",
    "x.com",
    "instagram",
    "facebook",
    "netflix",
    "twitch",
]


# --------------------------------------------------------------------------
# Active window retrieval (pywinctl, cross-platform)
# --------------------------------------------------------------------------

class WindowMonitor:
    """
    Cross-platform active window title reader, backed by pywinctl.
    """

    def __init__(self) -> None:
        self.os_name = platform.system()  # "Windows", "Darwin", or "Linux" -- informational only now

        try:
            import pywinctl
        except ImportError as exc:
            raise ImportError(
                "Missing dependency 'pywinctl'. Install it with:\n"
                "    pip install pywinctl\n"
                "On macOS you'll also need: pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa\n"
                "On Linux you'll also need: pip install python3-xlib ewmh"
            ) from exc

        self._pywinctl = pywinctl

    # -- Public API ----------------------------------------------------------

    def get_active_window_title(self) -> Optional[str]:
        """Returns the current active window title, or None if unavailable."""
        try:
            active = self._pywinctl.getActiveWindow()
            if active is None:
                return None
            title = getattr(active, "title", None)
            return title.strip() if title else None
        except Exception as exc:
            print(f"[monitor] Warning: failed to read active window ({exc})")
            return None

    def get_active_window_bbox(self) -> Optional[tuple[int, int, int, int]]:
        """
        Returns the (left, top, right, bottom) bounding box of the active
        window, or None if unavailable. Used by ocr_processor.py to crop
        the in-RAM screenshot to just the active window.
        """
        try:
            active = self._pywinctl.getActiveWindow()
            if active is None:
                return None
            box = active.box  # pywinctl's Box(left, top, width, height)
            return (box.left, box.top, box.left + box.width, box.top + box.height)
        except Exception as exc:
            print(f"[monitor] Warning: failed to read active window bbox ({exc})")
            return None


# --------------------------------------------------------------------------
# Blacklist checking
# --------------------------------------------------------------------------

def is_blacklisted(title: str) -> Optional[str]:
    """
    Checks a window title against the user's configured blacklist
    (config.BLACKLISTED_APPS, set via the dashboard) if available, else
    falls back to the static BLACKLISTED_PHRASES list below so this
    module still works standalone (e.g. `python monitor.py`).
    Returns the matched phrase if found, else None.
    """
    lowered = title.lower()

    try:
        import config

        phrases = config.BLACKLISTED_APPS
    except ImportError:
        phrases = BLACKLISTED_PHRASES

    for phrase in phrases:
        if phrase.lower() in lowered:
            return phrase
    return None


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

def run_monitor_loop(poll_interval: int = POLL_INTERVAL_SECONDS) -> None:
    """
    Starts the blocking background monitor loop. Prints the active window
    title on each tick, and prints a CRITICAL alert if a blacklisted
    phrase is detected in that title.
    """
    monitor = WindowMonitor()
    print(f"[monitor] Detected platform: {monitor.os_name}")
    print(f"[monitor] Polling active window every {poll_interval}s. Ctrl+C to stop.\n")

    try:
        while True:
            timestamp = datetime.now().strftime("%H:%M:%S")
            title = monitor.get_active_window_title()

            if title:
                print(f"[{timestamp}] Active window: {title}")
                match = is_blacklisted(title)
                if match:
                    print(
                        f"[{timestamp}] CRITICAL: Distraction detected in "
                        f"active title! (matched phrase: '{match}')"
                    )
            else:
                print(f"[{timestamp}] Active window: <unavailable>")

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n[monitor] Stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    run_monitor_loop()
