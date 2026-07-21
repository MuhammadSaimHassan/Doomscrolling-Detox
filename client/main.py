"""
DoomScroll Detox - client/main.py

Final Phase 4 entry point, with the full 3-level escalation lifecycle
from the blueprint implemented end-to-end.

Initializes the QApplication and shows the configuration Dashboard
(ui/dashboard.py) first. Once the user selects their major, goal, roast
severity, and blacklist, and clicks "LOCK IN", this builds a system tray
icon with three actions -- "Start Session" / "End Session" (toggle),
"Settings...", and "Quit" -- and silently kicks off the background
window-monitoring loop. No other windows are shown after that; everything
lives in the tray until a distraction triggers an intervention.

Escalation lifecycle (run entirely on a background QThread):
  Level 1 -- Local notification (tray toast), config.LEVEL1_WINDOW_SECONDS
             window. If the user switches away in time, nothing further
             happens.
  Level 2 -- Soft, dismissible roast banner (ui/overlay.py's
             SoftRoastOverlay), fed by OCR + backend /api/roast.
             config.LEVEL2_WINDOW_SECONDS window before escalating.
  Level 3 -- Full-screen LockdownOverlay + local TTS (core/audio_shamer.py
             reads the roast out loud). Requires answering a Gemini-graded
             conceptual question (backend /api/verify) to unlock, then
             grants a config.GRACE_PERIOD_SECONDS grace window.

At every level, escalation is driven purely by whether the active window
is STILL blacklisted when that level's timer elapses -- dismissing a
banner or acknowledging a notification does not by itself stop escalation
if the user hasn't actually switched away from the distraction.
"""

from __future__ import annotations

import sys
import threading
import time
import os

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import config
from core.monitor import WindowMonitor, is_blacklisted
from core.ocr_processor import ScreenTextExtractor, scan_active_window_for_text
from core.audio_shamer import AudioShamer
from ui.overlay import LockdownOverlay, SoftRoastOverlay
from ui.dashboard import Dashboard


# --------------------------------------------------------------------------
# Background detection worker
# --------------------------------------------------------------------------

class MonitorWorker(QThread):
    """
    Runs the poll -> escalate (Level 1 -> 2 -> 3) pipeline off the GUI
    thread.

    Signals
    -------
    level1_notify(str):
        Emitted with the distracting app_title the instant a blacklist
        match is detected. Main thread shows a tray notification.
    level2_soft_roast(str):
        Emitted with roast_text if the user is still distracted after
        the Level 1 window. Main thread shows a dismissible banner.
    distraction_ready(str, str, str):
        Emitted with (roast_text, question, model_answer) if the user is
        STILL distracted after the Level 2 window. Main thread shows the
        full-screen LockdownOverlay.
    status_update(str):
        Human-readable status strings, shown in the tray tooltip.
    """

    level1_notify = pyqtSignal(str)
    level2_soft_roast = pyqtSignal(str)
    distraction_ready = pyqtSignal(str, str, str)
    status_update = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._running = threading.Event()
        self._running.set()

        # Set while the user is NOT locked out. The worker blocks on this
        # while the Level 3 overlay is up, and again during the
        # post-unlock grace window (checked via _grace_until below).
        self._unlocked_event = threading.Event()
        self._unlocked_event.set()
        self._grace_until = 0.0

        self._window_monitor = WindowMonitor()
        self._ocr_extractor: ScreenTextExtractor | None = None

    def stop(self) -> None:
        self._running.clear()
        self._unlocked_event.set()  # don't leave the thread blocked on exit

    def notify_unlocked(self) -> None:
        """Called by the main thread once the Level 3 overlay reports
        success. Grants a grace window before distraction checks resume."""
        self._grace_until = time.time() + config.GRACE_PERIOD_SECONDS
        self._unlocked_event.set()

    def run(self) -> None:
        # Lazily init EasyOCR here (not in __init__) so model loading
        # happens on the worker thread and doesn't stall app startup.
        self.status_update.emit("Initializing local OCR engine...")
        self._ocr_extractor = ScreenTextExtractor()
        self.status_update.emit("Monitoring active.")

        while self._running.is_set():
            self._unlocked_event.wait()
            if not self._running.is_set():
                break

            remaining_grace = self._grace_until - time.time()
            if remaining_grace > 0:
                self.status_update.emit(
                    f"Grace period active ({int(remaining_grace // 60)}m left)."
                )
                time.sleep(min(5, remaining_grace))
                continue

            title = self._window_monitor.get_active_window_title()
            if title:
                matched_phrase = is_blacklisted(title)
                if matched_phrase:
                    self.status_update.emit(f"Distraction detected: {title}")
                    self._run_escalation(title)

            time.sleep(config.POLL_INTERVAL_SECONDS)

    # -- Escalation state machine --------------------------------------------

    def _run_escalation(self, app_title: str) -> None:
        # ---- LEVEL 1: local notification -----------------------------
        self.level1_notify.emit(app_title)
        if self._wait_and_check(config.LEVEL1_WINDOW_SECONDS):
            self.status_update.emit("Resolved after Level 1 notice.")
            return

        # ---- LEVEL 2: soft, dismissible roast banner -------------------
        try:
            distraction_text = scan_active_window_for_text(self._ocr_extractor)
        except Exception as exc:  # noqa: BLE001
            self.status_update.emit(f"OCR failed: {exc}")
            distraction_text = ""

        roast_text = self._fetch_roast(distraction_text, app_title)
        self.level2_soft_roast.emit(roast_text)
        if self._wait_and_check(config.LEVEL2_WINDOW_SECONDS):
            self.status_update.emit("Resolved after Level 2 soft roast.")
            return

        # ---- LEVEL 3: full lockdown -------------------------------------
        question, model_answer = self._fetch_challenge_question()
        self._unlocked_event.clear()
        self.distraction_ready.emit(roast_text, question, model_answer)

    def _wait_and_check(self, seconds: int) -> bool:
        """
        Waits up to `seconds`, polling once per second whether the active
        window is still blacklisted. Returns True the moment the user has
        switched away (de-escalate, stop here) or the worker is stopping;
        returns False if the user is STILL on a blacklisted window when
        time runs out (escalate to the next level).
        """
        deadline = time.time() + seconds
        while time.time() < deadline:
            if not self._running.is_set():
                return True
            time.sleep(1)
            title = self._window_monitor.get_active_window_title()
            if not title or not is_blacklisted(title):
                return True
        return False

    # -- Backend calls --------------------------------------------------------

    def _fetch_roast(self, distraction_text: str, app_title: str) -> str:
        payload = {
            "distraction_text": distraction_text or "unclear on-screen content",
            "app_title": app_title,
            "student_major": config.STUDENT_MAJOR,
            "goal": config.ACADEMIC_GOAL,
            "personality_mode": config.PERSONALITY_MODE,
            "username": config.USERNAME,
        }
        try:
            response = requests.post(
                config.ROAST_ENDPOINT,
                json=payload,
                timeout=config.BACKEND_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json().get("roast", "Get back to work. Now.")
        except requests.RequestException as exc:
            self.status_update.emit(f"Backend roast request failed: {exc}")
            return (
                "bestie the roast backend is down but you're still cooked "
                "for doomscrolling. get back to studying."
            )

    def _fetch_challenge_question(self) -> tuple[str, str]:
        payload = {
            "action": "generate_question",
            "student_major": config.STUDENT_MAJOR,
            "goal": config.ACADEMIC_GOAL,
        }
        try:
            response = requests.post(
                config.VERIFY_ENDPOINT,
                json=payload,
                timeout=config.BACKEND_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return data["question"], data["model_answer"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            self.status_update.emit(f"Backend question request failed: {exc}")
            fallback_question = (
                f"In one sentence, explain one core concept from "
                f"{config.STUDENT_MAJOR} relevant to: {config.ACADEMIC_GOAL}."
            )
            return fallback_question, ""


# --------------------------------------------------------------------------
# Application shell
# --------------------------------------------------------------------------

class DoomScrollDetoxApp:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self._load_stylesheet()
        # Before lock-in, the Dashboard is the only window -- closing it
        # should quit the app like any normal window. Once the tray icon
        # is built (see _on_locked_in), this is switched off so closing
        # the Settings dashboard later doesn't kill the background tray.
        self.app.setQuitOnLastWindowClosed(True)

        self._overlay: LockdownOverlay | None = None
        self._soft_roast_overlay: SoftRoastOverlay | None = None
        self._current_question: str | None = None
        self._current_model_answer: str | None = None

        self._dashboard: Dashboard | None = None       # initial launch screen
        self._settings_dashboard: Dashboard | None = None  # reopened via tray
        self._tray_icon: QSystemTrayIcon | None = None
        self._session_action: QAction | None = None
        self._worker: MonitorWorker | None = None

        # One AudioShamer instance reused across every Level 3 lockdown --
        # it's already internally thread-safe (see core/audio_shamer.py).
        self._audio_shamer = AudioShamer()

    # -- Styling -----------------------------------------------------------

    def _load_stylesheet(self) -> None:
        """Loads and applies client/ui/styles.qss app-wide, once. Every
        widget's dark-synthwave look (colors, borders, hover states) comes
        from this single sheet -- no widget sets its own inline QSS."""
        qss_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "ui", "styles.qss"
        )
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.app.setStyleSheet(f.read())
        except OSError as exc:
            print(f"[main] Warning: could not load styles.qss ({exc}). "
                  "Falling back to default Qt styling.")

    # -- Initial launch flow -------------------------------------------------

    def _show_initial_dashboard(self) -> None:
        self._dashboard = Dashboard(is_initial_launch=True)
        self._dashboard.locked_in.connect(self._on_locked_in)
        self._dashboard.show()

    def _on_locked_in(self) -> None:
        """Fired once from the initial Dashboard's 'LOCK IN' button.
        Builds the tray icon and silently kicks off monitoring."""
        if self._tray_icon is not None:
            return  # already locked in; nothing to do
        self.app.setQuitOnLastWindowClosed(False)
        self._tray_icon = self._build_tray_icon()
        self._start_worker()

    def _start_worker(self) -> None:
        self._worker = MonitorWorker()
        self._worker.level1_notify.connect(self._on_level1_notify)
        self._worker.level2_soft_roast.connect(self._on_level2_soft_roast)
        self._worker.distraction_ready.connect(self._show_lockdown_overlay)
        self._worker.status_update.connect(self._on_status_update)
        self._worker.start()

    # -- Tray -------------------------------------------------------------

    def _build_tray_icon(self) -> QSystemTrayIcon:
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "tray_icon.png"
        )
        tray_icon = QSystemTrayIcon(QIcon(icon_path), self.app)
        tray_icon.setToolTip("DoomScroll Detox")

        menu = QMenu()

        self._session_action = QAction("End Session")  # loop starts running
        self._session_action.triggered.connect(self._toggle_session)
        menu.addAction(self._session_action)

        settings_action = QAction("Settings...")
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        quit_action = QAction("Quit")
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        tray_icon.setContextMenu(menu)
        tray_icon.show()
        return tray_icon

    def _toggle_session(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._session_action.setText("Start Session")
            self._tray_icon.setToolTip("DoomScroll Detox - session ended")
        else:
            self._start_worker()
            self._session_action.setText("End Session")
            self._tray_icon.setToolTip("DoomScroll Detox - session active")

    def _open_settings(self) -> None:
        # Reopening the same dashboard used at launch, in "settings" mode:
        # saving here just persists changes -- config's module-level
        # attributes update immediately, no restart needed.
        self._settings_dashboard = Dashboard(is_initial_launch=False)
        self._settings_dashboard.locked_in.connect(
            lambda: self._on_status_update("Settings updated.")
        )
        self._settings_dashboard.show()
        self._settings_dashboard.raise_()
        self._settings_dashboard.activateWindow()

    def _on_status_update(self, message: str) -> None:
        if self._tray_icon is not None:
            self._tray_icon.setToolTip(f"DoomScroll Detox - {message}")

    # -- Level 1: tray notification --------------------------------------------

    def _on_level1_notify(self, app_title: str) -> None:
        if self._tray_icon is None:
            return
        self._tray_icon.showMessage(
            "DoomScroll Detox",
            f"Heads up -- get back to it. ({app_title})",
            QSystemTrayIcon.MessageIcon.Warning,
            config.LEVEL1_WINDOW_SECONDS * 1000,
        )

    # -- Level 2: soft roast banner ---------------------------------------------

    def _on_level2_soft_roast(self, roast_text: str) -> None:
        self._soft_roast_overlay = SoftRoastOverlay(
            roast_text=roast_text,
            auto_dismiss_seconds=config.LEVEL2_WINDOW_SECONDS,
        )
        self._soft_roast_overlay.dismissed.connect(self._on_soft_roast_dismissed)
        self._soft_roast_overlay.show()

    def _on_soft_roast_dismissed(self) -> None:
        self._soft_roast_overlay = None

    # -- Level 3: full lockdown overlay -----------------------------------------

    def _show_lockdown_overlay(
        self, roast_text: str, question: str, model_answer: str
    ) -> None:
        self._current_question = question
        self._current_model_answer = model_answer

        self._overlay = LockdownOverlay(
            roast_text=roast_text,
            challenge_question=question,
            verify_callback=self._verify_answer,
            on_unlocked=self._on_overlay_unlocked,
        )
        self._overlay.show()
        self._overlay.raise_()
        self._overlay.activateWindow()

        # Read the roast out loud -- the Level 3 voice-shame escalation.
        self._audio_shamer.shame_user_out_loud(roast_text)

    def _verify_answer(self, answer: str) -> tuple[bool, str]:
        payload = {
            "action": "verify_answer",
            "question": self._current_question or "",
            "model_answer": self._current_model_answer or "",
            "user_answer": answer,
        }
        try:
            response = requests.post(
                config.VERIFY_ENDPOINT,
                json=payload,
                timeout=config.BACKEND_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return bool(data.get("correct", False)), str(data.get("feedback", ""))
        except (requests.RequestException, ValueError) as exc:
            self._on_status_update(f"Backend verify request failed: {exc}")
            return False, "Couldn't reach the verification server. Try again."

    def _on_overlay_unlocked(self) -> None:
        self._audio_shamer.stop()  # cut off the TTS immediately on unlock
        self._overlay = None
        self._current_question = None
        self._current_model_answer = None
        self._worker.notify_unlocked()
        self._tray_icon.setToolTip(
            f"DoomScroll Detox - grace period ({config.TIMER_MINUTES}m)"
        )

    # -- Lifecycle ----------------------------------------------------------

    def _quit(self) -> None:
        self._audio_shamer.stop()
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(2000)
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self.app.quit()

    def run(self) -> int:
        # Show the configuration Dashboard first. The tray icon and
        # monitoring loop only start once the user clicks "LOCK IN"
        # (see _on_locked_in).
        self._show_initial_dashboard()
        return self.app.exec()


if __name__ == "__main__":
    app = DoomScrollDetoxApp()
    sys.exit(app.run())
