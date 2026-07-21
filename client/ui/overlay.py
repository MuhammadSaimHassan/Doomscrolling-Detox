"""
DoomScroll Detox - client/ui/overlay.py

Phase 4: Escalation UI (Level 2 and Level 3)

Defines two widgets:

  - SoftRoastOverlay: the Level 2 intervention. A small, dismissible
    banner near the top of the screen showing the roast. Does NOT block
    input to other windows and auto-dismisses after a timeout.

  - LockdownOverlay: the Level 3 intervention. A frameless, always-on-top,
    full-screen PyQt6 widget. It displays the AI-generated roast and
    blocks all input to the rest of the desktop until the user answers a
    verification challenge correctly.

LockdownOverlay is intentionally "unkillable" through normal means:
  - No window frame / title bar (nothing to click to close).
  - Qt.WindowStaysOnTopHint keeps it above every other window.
  - Escape and Alt+F4 are intercepted and swallowed.
  - closeEvent() refuses to close the window unless it has been
    explicitly unlocked first.

It does NOT attempt to block OS-level task manager / force-quit -- that is
outside the scope of a well-behaved desktop app, and the blueprint's
guardrails are about layering, not about defeating the OS.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QGuiApplication, QKeyEvent, QCloseEvent
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QApplication,
)


class LockdownOverlay(QWidget):
    """
    Full-screen blocking overlay.

    Parameters
    ----------
    roast_text:
        The AI-generated roast to display.
    challenge_question:
        The verification prompt shown above the input box (e.g. a
        flashcard question).
    verify_callback:
        A function taking the user's typed answer (str) and returning
        either a bool (True if correct) or a (bool, feedback_str) tuple.
        The tuple form lets the caller surface a message from the
        grading source -- e.g. Gemini's witty feedback from the backend
        /api/verify endpoint -- in the overlay's error/status label.
    on_unlocked:
        Optional callback fired once the user successfully unlocks, after
        the window has closed (e.g. to resume the monitor loop).
    """

    unlocked = pyqtSignal()

    def __init__(
        self,
        roast_text: str,
        challenge_question: str,
        verify_callback: Callable[[str], bool],
        on_unlocked: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._verify_callback = verify_callback
        self._on_unlocked = on_unlocked
        self._is_unlocked = False

        self._build_window_flags()
        self._build_ui(roast_text, challenge_question)
        self._cover_all_screens()

        if self._on_unlocked:
            self.unlocked.connect(self._on_unlocked)

    # -- Window setup ---------------------------------------------------

    def _build_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.X11BypassWindowManagerHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowState(Qt.WindowState.WindowFullScreen)

    def _cover_all_screens(self) -> None:
        """Sizes the overlay to cover the full virtual desktop geometry
        (all connected monitors), so switching displays doesn't reveal a
        gap."""
        virtual_geometry = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geometry)

    # -- UI ---------------------------------------------------------------

    def _build_ui(self, roast_text: str, challenge_question: str) -> None:
        # Styling comes from the centralized client/ui/styles.qss sheet,
        # loaded once app-wide in main.py. This widget only needs to set
        # objectName/class hooks (LockdownOverlay, roastLabel,
        # challengeLabel, errorLabel) for that sheet to target.
        outer_layout = QVBoxLayout(self)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.setSpacing(24)

        roast_label = QLabel(roast_text)
        roast_label.setObjectName("roastLabel")
        roast_label.setWordWrap(True)
        roast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roast_label.setMaximumWidth(760)
        roast_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))

        challenge_label = QLabel(challenge_question)
        challenge_label.setObjectName("challengeLabel")
        challenge_label.setWordWrap(True)
        challenge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        challenge_label.setMaximumWidth(600)

        self._error_label = QLabel("")
        self._error_label.setObjectName("errorLabel")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._answer_input = QLineEdit()
        self._answer_input.setPlaceholderText("Type your answer here...")
        self._answer_input.setFixedWidth(420)
        self._answer_input.returnPressed.connect(self._attempt_unlock)

        submit_button = QPushButton("Unlock")
        submit_button.setFixedWidth(140)
        submit_button.clicked.connect(self._attempt_unlock)

        input_row = QHBoxLayout()
        input_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_row.addWidget(self._answer_input)
        input_row.addWidget(submit_button)

        outer_layout.addWidget(roast_label)
        outer_layout.addWidget(challenge_label)
        outer_layout.addLayout(input_row)
        outer_layout.addWidget(self._error_label)

        self._answer_input.setFocus()

    # -- Unlock logic -----------------------------------------------------

    def _attempt_unlock(self) -> None:
        answer = self._answer_input.text().strip()
        if not answer:
            self._show_error("Type an answer first, bestie.")
            return

        self._answer_input.setEnabled(False)
        self._show_error("Checking your answer...")

        try:
            result = self._verify_callback(answer)
        except Exception as exc:  # noqa: BLE001
            self._answer_input.setEnabled(True)
            self._show_error(f"Verification error: {exc}")
            return

        # verify_callback may return a plain bool or a (bool, feedback) tuple.
        if isinstance(result, tuple):
            is_correct, feedback = result
        else:
            is_correct, feedback = bool(result), ""

        self._answer_input.setEnabled(True)

        if is_correct:
            self._is_unlocked = True
            self._show_error(feedback or "Correct! Unlocking...")
            self.unlocked.emit()
            self.close()
        else:
            self._show_error(feedback or "Nope. Try again.")
            self._answer_input.clear()
            self._answer_input.setFocus()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)

    # -- Escape hatches disabled --------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Swallow Escape and Alt+F4 so they can't close the window.
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        if event.key() == Qt.Key.Key_F4 and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._is_unlocked:
            event.accept()
        else:
            # Refuse to close via any programmatic or window-manager
            # initiated close request until unlocked.
            event.ignore()


# --------------------------------------------------------------------------
# SoftRoastOverlay -- Level 2 intervention
# --------------------------------------------------------------------------

class SoftRoastOverlay(QWidget):
    """
    A small, dismissible banner shown near the top of the screen for the
    Level 2 intervention. Unlike LockdownOverlay, this does NOT block
    input to the rest of the desktop and does NOT require answering
    anything -- it's a warning shot. It auto-dismisses after a timeout if
    the user ignores it, and MonitorWorker treats "still on the same
    distracting window after this banner's window elapses" as the signal
    to escalate to Level 3, independent of whether this banner itself was
    clicked away.
    """

    dismissed = pyqtSignal()

    def __init__(
        self,
        roast_text: str,
        auto_dismiss_seconds: int = 12,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("softRoastBanner")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui(roast_text)
        self._position_top_center()

        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._dismiss)
        self._auto_dismiss_timer.start(auto_dismiss_seconds * 1000)

    def _build_ui(self, roast_text: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 14, 14)
        layout.setSpacing(16)

        label = QLabel(roast_text)
        label.setObjectName("softRoastLabel")
        label.setWordWrap(True)
        label.setMaximumWidth(480)

        dismiss_button = QPushButton("Dismiss")
        dismiss_button.setObjectName("softRoastDismiss")
        dismiss_button.clicked.connect(self._dismiss)

        layout.addWidget(label, stretch=1)
        layout.addWidget(dismiss_button)

        self.setFixedWidth(600)
        self.adjustSize()

    def _position_top_center(self) -> None:
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        x = screen_geo.center().x() - self.width() // 2
        y = screen_geo.top() + 40
        self.move(x, y)

    def _dismiss(self) -> None:
        self._auto_dismiss_timer.stop()
        self.dismissed.emit()
        self.close()


# --------------------------------------------------------------------------
# Standalone manual test
# --------------------------------------------------------------------------

def _dummy_verify(answer: str) -> bool:
    return answer.strip().lower() == "focus"


def _test_runner() -> None:
    import sys

    app = QApplication(sys.argv)
    overlay = LockdownOverlay(
        roast_text=(
            "bestie you really opened Reddit mid-study-sesh? that's a "
            "certified skill issue. we are NOT cooked yet, get back to it."
        ),
        challenge_question="Type the word 'focus' to unlock.",
        verify_callback=_dummy_verify,
        on_unlocked=lambda: print("[overlay] Unlocked!"),
    )
    overlay.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _test_runner()
