"""
DoomScroll Detox - client/config.py

Local persisted user settings (major, goal, personality mode, timer
length) backed by a JSON file, plus static backend/runtime configuration.

Settings are stored at ~/.doomscroll_detox/settings.json by default so
they survive app restarts and aren't tied to the project source folder
(handy once this is packaged with PyInstaller, per the blueprint's Phase
4 roadmap). Tests and locked-down environments can override this with
DOOMSCROLL_SETTINGS_DIR.

Usage
-----
Other modules just do `import config` and read module-level attributes
like `config.STUDENT_MAJOR` -- these are populated from settings.json at
import time. To change settings from the UI (e.g. ui/dashboard.py), call
`config.update_settings(...)`, which persists to disk AND immediately
refreshes these module-level attributes so already-imported modules pick
up the new values on their next access.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

# --------------------------------------------------------------------------
# Backend connection (static, environment-driven -- not user-editable
# through the settings file)
# --------------------------------------------------------------------------

BACKEND_URL = os.environ.get("DOOMSCROLL_BACKEND_URL", "http://127.0.0.1:3000")
ROAST_ENDPOINT = f"{BACKEND_URL}/api/roast"
VERIFY_ENDPOINT = f"{BACKEND_URL}/api/verify"

POLL_INTERVAL_SECONDS = 3
BACKEND_REQUEST_TIMEOUT_SECONDS = 10

# Escalation timing windows (per the blueprint's lifecycle loop). If the
# user is still on a blacklisted window when a level's timer elapses,
# MonitorWorker escalates to the next level.
LEVEL1_WINDOW_SECONDS = 15  # local tray notification window
LEVEL2_WINDOW_SECONDS = 15  # soft, dismissible roast banner window

# --------------------------------------------------------------------------
# Persisted user profile settings
# --------------------------------------------------------------------------

SETTINGS_DIR = Path(
    os.environ.get("DOOMSCROLL_SETTINGS_DIR", Path.home() / ".doomscroll_detox")
)
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "username": "local_user",
    "student_major": "Computer Science",
    "goal": "Pass my exams",
    "personality_mode": "Aggressive Sarcastic Gen-Z peer",
    "timer_minutes": 10,  # length of the post-unlock grace window
    "blacklisted_apps": [
        "youtube",
        "tiktok",
        "reddit",
        "twitter",
        "x.com",
        "instagram",
        "facebook",
        "netflix",
        "twitch",
    ],
}

# Keys allowed to be written via update_settings(); prevents accidental
# junk keys from ending up in the settings file.
_VALID_KEYS = set(DEFAULT_SETTINGS.keys())


def _read_settings_file() -> Dict[str, Any]:
    """Reads settings.json off disk. Returns {} if missing or corrupt."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable file -- fall back to defaults rather than
        # crashing the app on startup.
        return {}


def load_settings() -> Dict[str, Any]:
    """
    Loads settings from disk, filling in any missing keys with defaults.
    If the file doesn't exist yet, or was missing keys, it's (re)written
    with the merged result so it's always complete on disk.
    """
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    stored = _read_settings_file()
    merged = dict(DEFAULT_SETTINGS)
    for key in _VALID_KEYS:
        if key in stored:
            merged[key] = stored[key]

    if merged != stored:
        save_settings(merged)

    return merged


def save_settings(settings: Dict[str, Any]) -> None:
    """Writes the given settings dict to settings.json, pretty-printed."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, sort_keys=True)


def update_settings(**changes: Any) -> None:
    """
    Updates one or more settings (e.g. update_settings(goal="Pass finals",
    timer_minutes=15)), persists the full settings dict to disk, and
    refreshes the module-level attributes (STUDENT_MAJOR, ACADEMIC_GOAL,
    etc.) so the rest of the running app sees the change immediately.
    """
    invalid_keys = set(changes) - _VALID_KEYS
    if invalid_keys:
        raise ValueError(f"Unknown setting(s): {', '.join(sorted(invalid_keys))}")

    if "timer_minutes" in changes:
        try:
            changes["timer_minutes"] = int(changes["timer_minutes"])
        except (TypeError, ValueError) as exc:
            raise ValueError("timer_minutes must be an integer.") from exc
        if changes["timer_minutes"] <= 0:
            raise ValueError("timer_minutes must be greater than zero.")

    if "blacklisted_apps" in changes:
        apps = changes["blacklisted_apps"]
        if not isinstance(apps, list) or not all(isinstance(a, str) for a in apps):
            raise ValueError("blacklisted_apps must be a list of strings.")
        if not apps:
            raise ValueError("blacklisted_apps cannot be empty.")

    current = load_settings()
    current.update(changes)
    save_settings(current)
    _apply_settings(current)


def _apply_settings(settings: Dict[str, Any]) -> None:
    """Populates module-level attributes from a settings dict."""
    global USERNAME, STUDENT_MAJOR, ACADEMIC_GOAL, PERSONALITY_MODE
    global TIMER_MINUTES, GRACE_PERIOD_SECONDS, BLACKLISTED_APPS

    USERNAME = settings["username"]
    STUDENT_MAJOR = settings["student_major"]
    ACADEMIC_GOAL = settings["goal"]
    PERSONALITY_MODE = settings["personality_mode"]
    TIMER_MINUTES = int(settings["timer_minutes"])
    GRACE_PERIOD_SECONDS = TIMER_MINUTES * 60
    BLACKLISTED_APPS = list(settings["blacklisted_apps"])


# Populate module-level attributes (USERNAME, STUDENT_MAJOR,
# ACADEMIC_GOAL, PERSONALITY_MODE, TIMER_MINUTES, GRACE_PERIOD_SECONDS)
# at import time.
_apply_settings(load_settings())


# --------------------------------------------------------------------------
# Manual test
# --------------------------------------------------------------------------

def _test_runner() -> None:
    print(f"[config] Settings file: {SETTINGS_FILE}")
    print(f"[config] Current settings: {load_settings()}")

    print("[config] Updating goal + timer_minutes...")
    update_settings(goal="Ace the databases final", timer_minutes=15)

    print(f"[config] STUDENT_MAJOR      = {STUDENT_MAJOR}")
    print(f"[config] ACADEMIC_GOAL      = {ACADEMIC_GOAL}")
    print(f"[config] PERSONALITY_MODE   = {PERSONALITY_MODE}")
    print(f"[config] TIMER_MINUTES      = {TIMER_MINUTES}")
    print(f"[config] GRACE_PERIOD_SECONDS = {GRACE_PERIOD_SECONDS}")


if __name__ == "__main__":
    _test_runner()
