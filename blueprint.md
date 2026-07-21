# **DoomScroll Detox (The Dopamine-Aware Screentime Agent)**

**"Your current screen time limits are a joke. You click 'Ignore Limit for 15 Minutes' and go right back to rotting your brain on TikTok. You don't need a passive blocker; you need an active, AI-driven, highly opinionated digital guardian that actually knows what you're looking at and bullies you back into being productive."**

## **📐 System Architecture & Data Flow**

This project utilizes a **privacy-first, local-cloud hybrid architecture**. Heavy tasks (such as taking screenshots and processing OCR) run locally to eliminate API costs and safeguard user data. Lightweight AI prompt completions are delegated to free serverless cloud platforms.

### **The Lifecycle Loop**

\[User Starts Focus Session\]   
       │  
       ▼  
\[Local Background Loop (Every 10s)\]   
  ├── Captures Active Window Title  
  └── Takes temporary screenshot ──\> Runs local OCR (RAM only, instantly deleted)  
       │  
       ▼  
\[Is Content Blacklisted / Semantic Distraction Detected?\]   
  ├── NO  ──\> Continue Loop  
  └── YES ──\> Trigger Intervention  
               │  
               ▼  
      \[Level 1: Local Warning Notification (15s Window)\]  
               │ (Ignored?)  
               ▼  
      \[Level 2: Soft Roast Overlay on Active Screen\]  
               │ (Ignored?)  
               ▼  
      \[Level 3: Full Screen Lockdown & Local TTS Out Loud Reading\]  
               │  
               ▼  
      \[Solve Dynamic AI Flashcard or Lock out / Wait Timer\] ──\> Unlocked\!

## **🛠️ The Tech Stack (100% Free)**

| Layer | Technology | Cost / Free Tier Terms | Purpose |
| :---- | :---- | :---- | :---- |
| **Desktop Client UI** | **PyQt6 (Python)** | Free (Open-source) | Cross-platform, professional desktop UI and system tray integration. |
| **Local OCR** | **EasyOCR** (Python) | Free (Open-source) | Extracts text from screenshots locally without cloud costs. |
| **Backend API Server** | **Vercel Functions** (Python) | Free Tier (Up to 100k executions/mo) | Hosts serverless server code for API calls. |
| **Database** | **Supabase (PostgreSQL)** | Free Tier (2 projects, 500MB database space) | Stores flashcards, progress logs, user settings, and major info. |
| **The AI Brain** | **Gemini 2.5 Flash API** | Free Tier (Up to 15 RPM, 1M context limit) | Evaluates context, generates personalized roasts, and verifies test responses. |
| **Local Audio Engine** | **pyttsx3** (Python) | Free (Open-source) | Runs local offline Text-To-Speech (TTS) for the voice-shame escalation. |

## **📂 Project Directory Structure**

Use this folder layout for organizing the files:

Plaintext  
doomscroll-detox/  
├── backend/                  \# Serverless Vercel backend  
│   ├── api/  
│   │   ├── index.py          \# Main Vercel serverless entry point  
│   │   ├── roast.py          \# LLM route to generate tailored roasts  
│   │   └── verify.py         \# Route to verify flashcard test answers  
│   ├── requirements.txt      \# Backend library dependencies  
│   └── vercel.json           \# Vercel deployment configuration  
├── client/                   \# Local desktop client application  
│   ├── assets/               \# Local icons, sounds, stylesheets  
│   │   └── tray\_icon.png  
│   ├── core/  
│   │   ├── monitor.py        \# Process & Screen monitoring logic  
│   │   ├── ocr\_processor.py  \# Local screen capture & EasyOCR processing  
│   │   └── audio\_shamer.py   \# pyttsx3 Text-to-Speech logic  
│   ├── ui/  
│   │   ├── dashboard.py      \# PyQt6 main configurations window  
│   │   ├── overlay.py        \# PyQt6 full screen blocker window  
│   │   └── styles.qss        \# Custom modern Gen-Z QSS stylesheet  
│   ├── config.py             \# User local state, DB credentials, focus profiles  
│   ├── requirements.txt      \# Client-side Python dependencies  
│   └── main.py               \# Main app loop and tray initialization  
├── .env.example              \# Environment variable template  
└── README.md                 \# Project guide

## **🔑 Device Permissions & Security Guardrails**

To run correctly on user machines, the Python desktop client requires key system-level hooks:

1. **Accessibility & Window Reading Permissions (pygetwindow / psutil):** Essential for retrieving current app context titles and determining active window parameters.  
2. **Screen Capture Permissions (Pillow / PyAutoGUI):** Used to read active window pixels.  
3. **Always-On-Top Layering (Qt.WindowStaysOnTopHint):** PyQt overlay parameter ensuring locked screens remain unbypassed by traditional task switching commands.  
4. **Local Data Isolation Safeguard:** **No visual screenshot is ever saved to disk or dispatched to any external cloud API.** It exists solely as an array in computer RAM, is immediately fed to the local EasyOCR instance, and is garbage-collected.

## **🛠️ Non-Coding Steps & Deployment Guides**

### **Step 1: Set Up Your Supabase Database**

1. Go to [Supabase](https://supabase.com/) and create a free account.  
2. Spin up a new project named DoomScrollDetox.  
3. Go to the SQL Editor and execute this schema setup:  
4. SQL

\-- Table for user configs  
CREATE TABLE user\_profiles (  
  id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
  username TEXT UNIQUE NOT NULL,  
  major TEXT DEFAULT 'Computer Science',  
  academic\_goals TEXT DEFAULT 'Pass My Exams',  
  personality\_mode TEXT DEFAULT 'Sarcastic',  
  created\_at TIMESTAMPTZ DEFAULT now()  
);

\-- Table for logging failures/distractions  
CREATE TABLE fail\_logs (  
  id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
  username TEXT NOT NULL,  
  distracted\_by TEXT NOT NULL,  
  timestamp TIMESTAMPTZ DEFAULT now()  
);

5.   
6. 

### **Step 2: Get a Free Gemini API Key**

1. Visit [Google AI Studio](https://aistudio.google.com/).  
2. Click **Create API Key**. Save this string somewhere safe. Do not commit this to GitHub.

### **Step 3: Deploy the Backend to Vercel**

1. Install the Vercel CLI locally: npm install \-g vercel.  
2. Navigate to the backend/ folder.  
3. Deploy to production using the command: vercel \--prod.  
4. In your Vercel Dashboard, navigate to your project settings and configure the environment variables:  
   * GEMINI\_API\_KEY (Your API Key)  
   * SUPABASE\_URL (From Supabase API settings)  
   * SUPABASE\_ANON\_KEY (From Supabase API settings)

## **📅 Roadmap: Development Phases**

* **Phase 1: Local Spy (Week 1-2):** Code the Python scripts in client/core/monitor.py to identify current focus applications and log window titles. Keep terminal print statements to confirm logic.  
* **Phase 2: Screen Reader (Week 3-4):** Set up client/core/ocr\_processor.py. Configure screenshotting to capture focused windows, feed the images straight to EasyOCR, convert to raw text, and run simple word-matching loops.  
* **Phase 3: The Brain Integration (Week 5-6):** Write the backend serverless endpoints to connect client data with the Gemini API. Perfect the prompt engineering setups to process the text metadata.  
* **Phase 4: Interface & Gamification (Week 7-8):** Construct the UI layouts using PyQt6 for configuration and overlays. Test lock-unlock logic loops locally. Use PyInstaller to generate target distributions (.exe / .app).

## **🤖 The LLM AI Prompt Chain (Save and Feed to your AI Coder)**

*Below is a pre-constructed prompt pipeline. Feed these numbered prompts to your AI coding assistant step-by-step as you progress through the development phases.*

### **Prompt 1: The Local Client Foundation (Phase 1\)**

Plaintext  
I am building a Python desktop client for an app called "DoomScroll Detox".  
I need a file named 'client/core/monitor.py' that runs in the background. It must:  
1\. Identify the platform (Windows vs macOS) and regularly scan for the currently active window in focus.  
2\. Print out the active window title every 3 seconds.  
3\. Reference a list of hardcoded blacklisted phrases (e.g., "YouTube", "TikTok", "Reddit", "Twitter", "Instagram"). If the title contains any of these, print a terminal alert warning: "CRITICAL: Distraction detected in active title\!"  
Provide clean, structured Python code. Explain any dependencies (like 'psutil' or 'pygetwindow' / 'AppKit') and how to install them.

### **Prompt 2: Local Screen Capture & Privacy-Safe OCR (Phase 2\)**

Plaintext  
Now let's build 'client/core/ocr\_processor.py'.  
This file should integrate with our window monitor. If a distraction check triggers, the application needs to:  
1\. Capture a low-resolution screenshot of only the active window (using Pillow or PyAutoGUI).  
2\. Load the screenshot into RAM as a byte-array, and feed it immediately to local 'EasyOCR'. Do NOT write the image file to the disk.  
3\. Extract text from the OCR output. Discard any short string elements (less than 3 characters).  
4\. Return the consolidated string of extracted words.  
5\. Provide a test runner function in this script showing this flow executing on current screen pixels and returning clean string values.

### **Prompt 3: Serverless Backend Interface & The AI Burn Engine (Phase 3\)**

Plaintext  
Now let's write the Serverless backend API. I want a Python script running on a Vercel serverless platform. Provide code for 'backend/api/roast.py' that:  
1\. Receives a JSON payload via POST containing:  
   \- "distraction\_text": (Extracted OCR string)  
   \- "app\_title": (Active window title)  
   \- "student\_major": (e.g., "Computer Science")  
   \- "goal": (e.g., "Pass data structures midterms")  
   \- "personality": (e.g., "Aggressive Sarcastic Gen-Z peer")  
2\. Interacts with the Gemini 2.5 Flash API.  
3\. Instruct the Gemini model through system prompt rules:  
   "You are an opinionated, highly sarcastic Gen-Z peer who acts as a productivity coach. Look at the student's current distraction, their active title, and their goal. Generate a devastating, witty roast under 50 words using modern internet slang ('bestie', 'skill issue', 'cooked', 'glazing', 'we are so back') reminding them to quit rotting their brain and return to studying."  
4\. Deliver the response payload cleanly. Include error handling in case the API rate limit is reached.

### **Prompt 4: PyQt6 Block Screen Overlay & System Integration (Phase 4\)**

Plaintext  
Let's build 'client/ui/overlay.py' and 'client/main.py'.  
I need a PyQt6 overlay blocker window. It must:  
1\. Display in borderless full-screen mode, with 'Qt.WindowStaysOnTopHint' so it overlays on top of everything.  
2\. Dim the user's screen with a semi-opaque dark gray background.  
3\. Render the dynamic AI roast text from our backend API in clean, modern typography.  
4\. Feature a locked text entry field where the user must type the correct answer to an AI-generated verification challenge.  
5\. Create a system tray loop logic inside 'main.py' so the background application starts minimized, launches the overlay when a level 3 block is triggered, and cleanly disappears once the user unlocks their screen.  
