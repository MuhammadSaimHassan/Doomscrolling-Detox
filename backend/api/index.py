"""
DoomScroll Detox - backend/api/index.py

Unified serverless entry point.

Vercel's Python builder auto-detects the WSGI-compatible `app` object
below and routes ALL traffic through this single function -- so this one
file is the entire backend surface:

  GET  /             -> {"status": "active"} health check
  POST /api/roast     -> Gemini-generated roast (logic in ../ai_service.py)
  POST /api/verify     -> Gemini question generation + semantic grading
                           (logic in ../ai_service.py)

IMPORTANT: backend/api/roast.py and backend/api/verify.py should be
REMOVED from the api/ directory once this file is in place. Any .py file
that lives directly inside api/ is auto-deployed by Vercel as its OWN
separate serverless function, regardless of what vercel.json's rewrites
say -- so leaving those files in place would silently spin up 3 functions
instead of the 1 unified one this file is meant to provide. Their logic
now lives in backend/ai_service.py, shared by the routes below.
"""

import os
import sys

# backend/ai_service.py lives one directory above this file (backend/),
# not inside api/, specifically so it is NOT auto-deployed as its own
# function. Add that directory to sys.path so it's importable here.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Auto-load root .env file if running locally
_root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if os.path.exists(_root_env):
    with open(_root_env, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

from flask import Flask, request, jsonify, send_from_directory  # noqa: E402
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError  # noqa: E402

import ai_service  # noqa: E402




app = Flask(__name__)


# --------------------------------------------------------------------------
# Landing route -- Serves single-page web app studio
# --------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def status_check():
    public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")
    index_file = os.path.join(public_dir, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(public_dir, "index.html")
    return jsonify({"status": "active"}), 200



# --------------------------------------------------------------------------
# /api/roast
# --------------------------------------------------------------------------

@app.route("/api/roast", methods=["GET", "POST"])
def roast_route():
    if request.method == "GET":
        return jsonify({"status": "roast endpoint is live. POST to use it."}), 200

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    validation_error = ai_service.validate_roast_payload(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        roast_text = ai_service.generate_roast(
            distraction_text=payload["distraction_text"],
            app_title=payload["app_title"],
            student_major=payload["student_major"],
            goal=payload["goal"],
            personality_mode=payload["personality_mode"],
        )

        # Best-effort Supabase logging -- never blocks or fails the roast
        # response itself (see ai_service.py's swallowed-exception design).
        username = payload.get("username", "anonymous")
        ai_service.upsert_user_profile(
            username=username,
            major=payload["student_major"],
            goal=payload["goal"],
            personality_mode=payload["personality_mode"],
        )
        ai_service.log_fail(username=username, distracted_by=payload["app_title"])

        return jsonify({"roast": roast_text}), 200

    except ResourceExhausted:
        return jsonify(
            {"error": "Rate limit reached on the AI backend. Try again shortly."}
        ), 429
    except GoogleAPIError as exc:
        return jsonify({"error": f"AI backend error: {str(exc)}"}), 502
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001 - final safety net
        return jsonify({"error": f"Unexpected server error: {str(exc)}"}), 500


# --------------------------------------------------------------------------
# /api/verify
# --------------------------------------------------------------------------

@app.route("/api/verify", methods=["GET", "POST"])
def verify_route():
    if request.method == "GET":
        return jsonify({"status": "verify endpoint is live. POST to use it."}), 200

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    if not isinstance(payload, dict) or "action" not in payload:
        return jsonify({"error": "Missing required field: 'action'"}), 400

    action = payload["action"]

    try:
        if action == "generate_question":
            validation_error = ai_service.validate_generate_payload(payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            result = ai_service.generate_question(
                payload["student_major"], payload["goal"]
            )
            return jsonify(result), 200

        elif action == "verify_answer":
            validation_error = ai_service.validate_verify_payload(payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            result = ai_service.verify_answer(
                payload["question"], payload["model_answer"], payload["user_answer"]
            )
            return jsonify(result), 200

        else:
            return jsonify(
                {
                    "error": (
                        f"Unknown action '{action}'. Expected 'generate_question' "
                        "or 'verify_answer'."
                    )
                }
            ), 400

    except ResourceExhausted:
        return jsonify(
            {"error": "Rate limit reached on the AI backend. Try again shortly."}
        ), 429
    except GoogleAPIError as exc:
        return jsonify({"error": f"AI backend error: {str(exc)}"}), 502
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001 - final safety net
        return jsonify({"error": f"Unexpected server error: {str(exc)}"}), 500


# --------------------------------------------------------------------------
# Fallback for anything else
# --------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found."}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)

