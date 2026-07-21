"""
Static completion check for the DoomScroll Detox blueprint phases.

This script intentionally avoids importing project modules. Importing the
client would initialize GUI/OCR dependencies, and importing the backend may
require cloud SDK packages. The goal here is a fast structural check that can
run before heavier manual testing.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CHECKS: list[tuple[str, Path, list[str]]] = [
    (
        "Phase 1 active-window monitor",
        ROOT / "client" / "core" / "monitor.py",
        ["class WindowMonitor", "def get_active_window_title", "def is_blacklisted"],
    ),
    (
        "Phase 2 in-memory OCR pipeline",
        ROOT / "client" / "core" / "ocr_processor.py",
        ["ImageGrab.grab", "easyocr.Reader", "def scan_active_window_for_text"],
    ),
    (
        "Phase 3 Gemini service logic",
        ROOT / "backend" / "ai_service.py",
        ["gemini-2.5-flash", "def generate_roast", "def verify_answer"],
    ),
    (
        "Phase 3 serverless routes",
        ROOT / "backend" / "api" / "index.py",
        ['@app.route("/api/roast"', '@app.route("/api/verify"', "status_check"],
    ),
    (
        "Phase 4 desktop lifecycle",
        ROOT / "client" / "main.py",
        ["class MonitorWorker", "Level 1", "Level 2", "Level 3"],
    ),
    (
        "Phase 4 overlays",
        ROOT / "client" / "ui" / "overlay.py",
        ["class SoftRoastOverlay", "class LockdownOverlay", "WindowStaysOnTopHint"],
    ),
    (
        "Phase 4 dashboard",
        ROOT / "client" / "ui" / "dashboard.py",
        ["class Dashboard", "locked_in", "blacklisted_apps"],
    ),
    (
        "Phase 4 packaging",
        ROOT / "client" / "build.py",
        ["pyinstaller", "build.spec"],
    ),
    (
        "Environment template",
        ROOT / ".env.example",
        ["GEMINI_API_KEY", "SUPABASE_URL", "DOOMSCROLL_BACKEND_URL"],
    ),
    (
        "Project guide",
        ROOT / "README.md",
        ["Current Completion Status", "Running The Client", "Deploying The Backend"],
    ),
]


def _check_required_text(label: str, path: Path, needles: list[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{label}: missing file {path.relative_to(ROOT)}"]

    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            errors.append(
                f"{label}: missing expected marker {needle!r} in {path.relative_to(ROOT)}"
            )
    return errors


def _check_python_syntax() -> list[str]:
    errors: list[str] = []
    for path in [*ROOT.glob("backend/**/*.py"), *ROOT.glob("client/**/*.py")]:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            rel = path.relative_to(ROOT)
            errors.append(f"Syntax error in {rel}:{exc.lineno}: {exc.msg}")
    return errors


def main() -> int:
    errors: list[str] = []

    for label, path, needles in CHECKS:
        errors.extend(_check_required_text(label, path, needles))

    errors.extend(_check_python_syntax())

    if errors:
        print("DoomScroll Detox phase check: FAILED")
        for error in errors:
            print(f" - {error}")
        return 1

    print("DoomScroll Detox phase check: PASSED")
    print("Blueprint phases 1-4 have the expected files, routes, UI hooks, and packaging artifacts.")
    print("Next required validation: run the desktop app and backend in the target OS environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
