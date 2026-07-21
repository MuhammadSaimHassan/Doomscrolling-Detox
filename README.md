# DoomScroll Detox

DoomScroll Detox is a privacy-first desktop focus agent. The local client watches the active window, performs OCR on in-memory screenshots, escalates distractions through PyQt6 interventions, and calls a small serverless backend for Gemini-generated roasts and unlock challenges.

## Current Completion Status

The codebase covers the four blueprint phases:

| Phase | Blueprint goal | Implementation |
| --- | --- | --- |
| Phase 1: Local Spy | Read active window titles and flag blacklisted apps | `client/core/monitor.py` |
| Phase 2: Screen Reader | Capture active window pixels in RAM and run local OCR | `client/core/ocr_processor.py` |
| Phase 3: Brain Integration | Serverless Gemini roast and verification endpoints | `backend/api/index.py`, `backend/ai_service.py` |
| Phase 4: Interface & Gamification | PyQt6 dashboard, tray loop, overlays, TTS, packaging | `client/main.py`, `client/ui/`, `client/build.py`, `client/build.spec` |

The backend uses a unified Vercel function at `backend/api/index.py`. It exposes `/api/roast` and `/api/verify`; separate `roast.py` and `verify.py` files are intentionally not used because each file directly under `api/` becomes its own Vercel function.

## Project Layout

```text
doomscroll-detox/
  backend/
    api/index.py
    ai_service.py
    requirements.txt
    vercel.json
  client/
    assets/
    core/
    ui/
    build.py
    build.spec
    config.py
    main.py
    requirements.txt
  scripts/
    phase_check.py
  .env.example
  blueprint.md
  README.md
```

## Requirements

- Python 3.12 recommended for the backend, matching `backend/vercel.json`
- Python 3.10+ for the desktop client
- A Gemini API key from Google AI Studio
- Optional Supabase project for profile/failure logging
- Vercel CLI for deployment

On Windows, the client uses SAPI through `pyttsx3` for local TTS. On macOS and Linux, follow the platform notes in `client/requirements.txt`.

## Local Setup

Create and activate a virtual environment from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install client dependencies:

```powershell
pip install -r client\requirements.txt
```

Install backend dependencies when running or testing the backend locally:

```powershell
pip install -r backend\requirements.txt
```

Copy the sample environment file and fill real values:

```powershell
Copy-Item .env.example .env
```

Required backend value:

```text
GEMINI_API_KEY=...
```

Optional Supabase values:

```text
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Client backend override after deployment:

```text
DOOMSCROLL_BACKEND_URL=https://your-project.vercel.app
```

If `DOOMSCROLL_BACKEND_URL` is not set, the desktop client defaults to `http://localhost:3000`.

Optional settings-directory override for tests or locked-down machines:

```text
DOOMSCROLL_SETTINGS_DIR=E:\path\to\settings-folder
```

## Supabase Schema

Run this in the Supabase SQL editor if you want profile and failure logging:

```sql
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT UNIQUE NOT NULL,
  major TEXT DEFAULT 'Computer Science',
  academic_goals TEXT DEFAULT 'Pass My Exams',
  personality_mode TEXT DEFAULT 'Sarcastic',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE fail_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT NOT NULL,
  distracted_by TEXT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT now()
);
```

Supabase failures are best-effort and do not block roast or verification responses.

## Running The Client

From the `client` directory:

```powershell
python main.py
```

The dashboard opens first. After saving the profile, the app moves into the system tray and starts monitoring. The escalation flow is:

1. Level 1: tray warning notification
2. Level 2: dismissible soft roast overlay
3. Level 3: full-screen lockdown overlay with local TTS and AI verification

Useful standalone checks:

```powershell
python core\monitor.py
python core\ocr_processor.py
python ui\overlay.py
```

These manual checks require desktop permissions for active-window reads, screen capture, and always-on-top windows.

## Running The Backend Locally

From the `backend` directory:

```powershell
vercel dev
```

Health check:

```powershell
Invoke-RestMethod http://localhost:3000/
```

Roast endpoint:

```powershell
Invoke-RestMethod http://localhost:3000/api/roast -Method Post -ContentType "application/json" -Body '{"distraction_text":"short videos and comments","app_title":"YouTube","student_major":"Computer Science","goal":"Pass data structures midterm","personality_mode":"Aggressive Sarcastic Gen-Z peer","username":"local_user"}'
```

Verification endpoint:

```powershell
Invoke-RestMethod http://localhost:3000/api/verify -Method Post -ContentType "application/json" -Body '{"action":"generate_question","student_major":"Computer Science","goal":"Pass data structures midterm"}'
```

## Deploying The Backend

From the `backend` directory:

```powershell
vercel --prod
```

Set these environment variables in the Vercel dashboard:

- `GEMINI_API_KEY`
- `SUPABASE_URL` optional
- `SUPABASE_ANON_KEY` optional

After deployment, set `DOOMSCROLL_BACKEND_URL` on the client machine to the Vercel project URL.

## Packaging The Desktop App

From the `client` directory:

```powershell
pip install pyinstaller
python build.py
```

The distributable is written to:

```text
client/dist/DoomScrollDetox/
```

## Phase Completion Check

Run this from the project root:

```powershell
python scripts\phase_check.py
```

This performs lightweight static checks for the blueprint phase files, routes, packaging files, and environment template. It does not replace manual OS-level testing because screen capture, active-window permissions, tray behavior, and full-screen overlays depend on the target desktop environment.
