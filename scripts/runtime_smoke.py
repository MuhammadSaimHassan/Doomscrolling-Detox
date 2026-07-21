"""
Runtime smoke checks for DoomScroll Detox.

These checks verify that installed dependencies can import and that the Flask
routes behave correctly with mocked AI/Supabase calls. The script avoids
opening PyQt windows, initializing EasyOCR models, capturing the screen, or
calling external Gemini/Supabase services.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CLIENT = ROOT / "client"

os.environ.setdefault("DOOMSCROLL_SETTINGS_DIR", str(ROOT / ".test_state"))

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(CLIENT))


REQUIRED_IMPORTS = [
    "flask",
    "google.generativeai",
    "supabase",
    "PyQt6",
    "pywinctl",
    "easyocr",
    "pyttsx3",
    "PIL",
    "requests",
    "numpy",
]

PROJECT_IMPORTS = [
    "config",
    "core.monitor",
    "core.ocr_processor",
    "core.audio_shamer",
    "ui.dashboard",
    "ui.overlay",
    "ai_service",
    "api.index",
]


def _import_all(names: list[str]) -> list[str]:
    errors: list[str] = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report exact smoke failure
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return errors


def _check_backend_routes() -> list[str]:
    errors: list[str] = []

    api_index = importlib.import_module("api.index")
    ai_service = importlib.import_module("ai_service")

    def fake_generate_roast(**_kwargs):
        return "mock roast"

    def fake_generate_question(_major, _goal):
        return {"question": "What is abstraction?", "model_answer": "Hiding detail."}

    def fake_verify_answer(_question, _model_answer, user_answer):
        return {"correct": user_answer.lower() == "hiding detail", "feedback": "ok"}

    ai_service.generate_roast = fake_generate_roast
    ai_service.generate_question = fake_generate_question
    ai_service.verify_answer = fake_verify_answer
    ai_service.upsert_user_profile = lambda **_kwargs: None
    ai_service.log_fail = lambda **_kwargs: None

    client = api_index.app.test_client()

    health = client.get("/")
    if health.status_code != 200 or health.get_json() != {"status": "active"}:
        errors.append(f"GET / returned {health.status_code}: {health.get_data(as_text=True)}")

    invalid_roast = client.post("/api/roast", json={})
    if invalid_roast.status_code != 400:
        errors.append(f"POST /api/roast invalid payload returned {invalid_roast.status_code}")

    roast = client.post(
        "/api/roast",
        json={
            "distraction_text": "video feed",
            "app_title": "YouTube",
            "student_major": "Computer Science",
            "goal": "Pass data structures",
            "personality_mode": "Aggressive Sarcastic Gen-Z peer",
            "username": "smoke_test",
        },
    )
    if roast.status_code != 200 or roast.get_json().get("roast") != "mock roast":
        errors.append(f"POST /api/roast valid payload returned {roast.status_code}: {roast.get_data(as_text=True)}")

    question = client.post(
        "/api/verify",
        json={
            "action": "generate_question",
            "student_major": "Computer Science",
            "goal": "Pass data structures",
        },
    )
    if question.status_code != 200 or "question" not in question.get_json():
        errors.append(f"POST /api/verify generate_question returned {question.status_code}: {question.get_data(as_text=True)}")

    answer = client.post(
        "/api/verify",
        json={
            "action": "verify_answer",
            "question": "What is abstraction?",
            "model_answer": "Hiding detail.",
            "user_answer": "hiding detail",
        },
    )
    if answer.status_code != 200 or answer.get_json().get("correct") is not True:
        errors.append(f"POST /api/verify verify_answer returned {answer.status_code}: {answer.get_data(as_text=True)}")

    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(_import_all(REQUIRED_IMPORTS))
    errors.extend(_import_all(PROJECT_IMPORTS))

    if not errors:
        errors.extend(_check_backend_routes())

    if errors:
        print("DoomScroll Detox runtime smoke: FAILED")
        for error in errors:
            print(f" - {error}")
        return 1

    print("DoomScroll Detox runtime smoke: PASSED")
    print("Dependencies import, project modules load, and mocked backend routes respond correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
