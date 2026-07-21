"""
DoomScroll Detox - backend/ai_service.py

Shared Gemini business logic used by the unified serverless entry point
(api/index.py). This file deliberately lives OUTSIDE the api/ directory:
Vercel's Python builder auto-deploys every file directly inside api/ as
its own separate serverless function, so keeping shared code here (and
importing it from index.py) is what makes "one unified function" actually
true, instead of silently spinning up extra functions per file.
"""

import os
import json
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai



MODEL_NAME = "gemini-2.0-flash"

# --------------------------------------------------------------------------
# Roast generation (Phase 3)
# --------------------------------------------------------------------------

ROAST_REQUIRED_FIELDS = [
    "distraction_text",
    "app_title",
    "student_major",
    "goal",
    "personality_mode",
]

ROAST_SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are an opinionated, highly sarcastic Gen-Z peer who acts as a "
    "productivity coach. You will be given a student's current on-screen "
    "distraction, their active window title, their major, and their "
    "academic goal. Your job is to generate a devastating, witty roast "
    "under 50 words using modern internet slang (e.g. 'bestie', 'skill "
    "issue', 'cooked', 'glazing', 'we are so back') that calls out the "
    "distraction and pushes them to quit rotting their brain and get back "
    "to studying. Stay under 50 words. Do not use hateful, sexual, or "
    "self-harm-related language. Adopt this specific persona for the "
    "roast: {personality_mode}."
)

ROAST_USER_PROMPT_TEMPLATE = (
    "Active window title: {app_title}\n"
    "On-screen distraction content (OCR extracted): {distraction_text}\n"
    "Student's major: {student_major}\n"
    "Student's academic goal: {goal}\n\n"
    "Generate the roast now."
)


def validate_roast_payload(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return "Request body must be a JSON object."
    missing = [field for field in ROAST_REQUIRED_FIELDS if field not in payload]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    for field in ROAST_REQUIRED_FIELDS:
        if not isinstance(payload[field], str):
            return f"Field '{field}' must be a string."
    return None


def generate_roast(
    distraction_text: str,
    app_title: str,
    student_major: str,
    goal: str,
    personality_mode: str,
) -> str:
    _configure_gemini()

    system_instruction = ROAST_SYSTEM_INSTRUCTION_TEMPLATE.format(
        personality_mode=personality_mode
    )
    model = genai.GenerativeModel(
        model_name=MODEL_NAME, system_instruction=system_instruction
    )
    user_prompt = ROAST_USER_PROMPT_TEMPLATE.format(
        app_title=app_title,
        distraction_text=distraction_text,
        student_major=student_major,
        goal=goal,
    )

    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.9,
            max_output_tokens=120,
        ),
    )

    roast_text = (response.text or "").strip()
    if not roast_text:
        raise RuntimeError("Gemini returned an empty response.")
    return roast_text


# --------------------------------------------------------------------------
# Unlock question generation + semantic grading (Phase 4)
# --------------------------------------------------------------------------

GENERATE_SYSTEM_INSTRUCTION = (
    "You are a quiz-question generator for a student focus app. Given a "
    "student's major and their current academic goal, write ONE short "
    "conceptual question that tests a basic idea related to that goal. "
    "It should be answerable in one or two sentences by someone who "
    "actually understands the material -- not a trivia fact, not "
    "something Googleable in one click, and not something answerable "
    "with a single word. Keep the question under 30 words. "
    "Respond with ONLY a JSON object, no markdown fences, no preamble, "
    'in exactly this shape: {"question": "...", "model_answer": "..."} '
    "where model_answer is a brief (1-2 sentence) correct reference "
    "answer used only for grading."
)

VERIFY_SYSTEM_INSTRUCTION = (
    "You are grading a student's quick-recall answer to unlock their "
    "screen. You will receive the question, a reference answer, and the "
    "student's typed answer. Judge whether the student's answer is "
    "semantically correct and demonstrates real understanding -- accept "
    "reasonable paraphrases, partial phrasings, and minor typos. Reject "
    "answers that are blank, off-topic, gibberish, or clearly copy-pasted "
    "question text without an actual answer. "
    "Respond with ONLY a JSON object, no markdown fences, no preamble, "
    'in exactly this shape: {"correct": true, "feedback": "..."} where '
    "feedback is a short (under 20 words) reaction in a witty Gen-Z tone, "
    "either congratulating them or telling them to actually try."
)


def validate_generate_payload(payload: dict) -> str | None:
    for field in ("student_major", "goal"):
        if field not in payload or not isinstance(payload[field], str):
            return f"Missing or invalid required field: '{field}'"
    return None


def validate_verify_payload(payload: dict) -> str | None:
    for field in ("question", "model_answer", "user_answer"):
        if field not in payload or not isinstance(payload[field], str):
            return f"Missing or invalid required field: '{field}'"
    return None


def _call_gemini_json(system_instruction: str, user_prompt: str) -> dict:
    _configure_gemini()

    model = genai.GenerativeModel(
        model_name=MODEL_NAME, system_instruction=system_instruction
    )
    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=200,
            response_mime_type="application/json",
        ),
    )

    raw_text = (response.text or "").strip()
    if not raw_text:
        raise RuntimeError("Gemini returned an empty response.")
    return json.loads(raw_text)


def generate_question(student_major: str, goal: str) -> dict:
    user_prompt = (
        f"Student's major: {student_major}\n"
        f"Student's current academic goal: {goal}\n\n"
        "Generate the question now."
    )
    result = _call_gemini_json(GENERATE_SYSTEM_INSTRUCTION, user_prompt)

    if "question" not in result or "model_answer" not in result:
        raise RuntimeError("Gemini response missing required fields.")

    return {
        "question": str(result["question"]).strip(),
        "model_answer": str(result["model_answer"]).strip(),
    }


def verify_answer(question: str, model_answer: str, user_answer: str) -> dict:
    user_prompt = (
        f"Question: {question}\n"
        f"Reference answer: {model_answer}\n"
        f"Student's typed answer: {user_answer}\n\n"
        "Grade it now."
    )
    result = _call_gemini_json(VERIFY_SYSTEM_INSTRUCTION, user_prompt)

    if "correct" not in result:
        raise RuntimeError("Gemini response missing required fields.")

    return {
        "correct": bool(result["correct"]),
        "feedback": str(result.get("feedback", "")).strip(),
    }


# --------------------------------------------------------------------------
# Shared Gemini configuration
# --------------------------------------------------------------------------

def _configure_gemini() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)


# --------------------------------------------------------------------------
# Supabase logging (Step 1's user_profiles / fail_logs tables)
# --------------------------------------------------------------------------
# Both helpers are best-effort: Supabase isn't required for the app's core
# roast/verify functionality to work, so a missing config or a transient
# DB error is swallowed (logged to stderr) rather than breaking the
# response the client is waiting on.

_supabase_client = None
_supabase_client_initialized = False


def _get_supabase_client():
    """Lazily creates (and caches) a Supabase client. Returns None if
    SUPABASE_URL / SUPABASE_ANON_KEY aren't configured, or if the
    'supabase' package isn't installed."""
    global _supabase_client, _supabase_client_initialized

    if _supabase_client_initialized:
        return _supabase_client
    _supabase_client_initialized = True

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
    except Exception as exc:  # noqa: BLE001
        print(f"[ai_service] Supabase client init failed: {exc}")
        _supabase_client = None

    return _supabase_client


def upsert_user_profile(
    username: str, major: str, goal: str, personality_mode: str
) -> None:
    """Best-effort upsert into user_profiles, keyed on username."""
    client = _get_supabase_client()
    if client is None:
        return
    try:
        client.table("user_profiles").upsert(
            {
                "username": username,
                "major": major,
                "academic_goals": goal,
                "personality_mode": personality_mode,
            },
            on_conflict="username",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"[ai_service] Supabase upsert_user_profile failed: {exc}")


def log_fail(username: str, distracted_by: str) -> None:
    """Best-effort insert into fail_logs for this distraction event."""
    client = _get_supabase_client()
    if client is None:
        return
    try:
        client.table("fail_logs").insert(
            {"username": username, "distracted_by": distracted_by}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"[ai_service] Supabase log_fail failed: {exc}")
