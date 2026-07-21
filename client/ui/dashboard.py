"""
DoomScroll Detox - client/ui/dashboard.py

The configuration dashboard: major, goal, roast severity, and a
blacklist checklist, capped off with a "Lock In" button that saves the
profile and (on first launch) hands off to the tray + background
tracker loop.

This replaces the temporary SettingsDialog that used to live in
main.py. It's reused for two contexts:
  - First launch: "Lock In" saves settings AND emits `locked_in`, which
    main.py listens for to spin up the tray icon + MonitorWorker.
  - Reopened later via the tray's "Settings" action: saving just
    persists changes -- config.py's module-level attributes (which the
    worker reads live on every check) update immediately, no restart
    needed.
"""

from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import config


# --------------------------------------------------------------------------
# Static option data
# --------------------------------------------------------------------------

ACADEMIC_MAJORS: List[str] = [
    "Computer Science",
    "Computer Engineering",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Data Science",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Nursing",
    "Psychology",
    "Business Administration",
    "Economics",
    "Political Science",
    "English Literature",
    "Sociology",
    "Other",
]

SEVERITY_LEVELS: List[str] = ["Supportive", "Passive-Aggressive", "Toxic Bully"]

SEVERITY_TO_PERSONALITY: Dict[str, str] = {
    "Supportive": (
        "A warm, encouraging study buddy who gently and kindly reminds "
        "the student of their goals, no insults, lots of affirmation"
    ),
    "Passive-Aggressive": (
        "A dry, passive-aggressive friend who sighs, side-eyes the "
        "student's choices, and uses light sarcasm without being cruel"
    ),
    "Toxic Bully": (
        "An aggressive, highly sarcastic Gen-Z peer who mercilessly "
        "roasts the student using modern internet slang"
    ),
}

# display label -> phrases matched against the active window title
BLACKLIST_OPTIONS: Dict[str, List[str]] = {
    "YouTube": ["youtube"],
    "TikTok": ["tiktok"],
    "Reddit": ["reddit"],
    "Twitter / X": ["twitter", "x.com"],
    "Instagram": ["instagram"],
    "Facebook": ["facebook"],
    "Netflix": ["netflix"],
    "Twitch": ["twitch"],
    "Discord": ["discord"],
    "Snapchat": ["snapchat"],
    "Pinterest": ["pinterest"],
}


def _personality_to_severity(personality_mode: str) -> str:
    """Best-effort reverse lookup so a returning user sees their
    previously saved severity highlighted correctly."""
    for level, text in SEVERITY_TO_PERSONALITY.items():
        if text == personality_mode:
            return level
    return "Toxic Bully"  # default assumption for legacy/custom values


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

class Dashboard(QWidget):
    """
    The main configuration window. Emits `locked_in` after settings have
    been validated and persisted to disk via config.update_settings().
    """

    locked_in = pyqtSignal()

    def __init__(self, is_initial_launch: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._is_initial_launch = is_initial_launch

        self.setWindowTitle("DoomScroll Detox - Dashboard")
        self.setMinimumSize(540, 680)
        self._build_ui()
        self._load_current_settings()

    # -- Layout -------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #0a0a10; }")

        container = QWidget()
        container.setStyleSheet("background-color: #0a0a10;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        title = QLabel("DoomScroll Detox")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Set up your focus profile before you lock in.")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_major_goal_card())
        layout.addWidget(self._build_severity_card())
        layout.addWidget(self._build_blacklist_card())

        self._lock_in_button = QPushButton(
            "LOCK IN" if self._is_initial_launch else "SAVE CHANGES"
        )
        self._lock_in_button.setObjectName("lockInButton")
        self._lock_in_button.clicked.connect(self._handle_lock_in)
        layout.addWidget(self._lock_in_button)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _build_major_goal_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        major_label = QLabel("ACADEMIC MAJOR")
        major_label.setObjectName("sectionLabel")
        self._major_combo = QComboBox()
        self._major_combo.setEditable(True)
        self._major_combo.addItems(ACADEMIC_MAJORS)

        goal_label = QLabel("CURRENT STUDY GOAL")
        goal_label.setObjectName("sectionLabel")
        self._goal_input = QLineEdit()
        self._goal_input.setPlaceholderText("e.g. Pass data structures midterm")

        layout.addWidget(major_label)
        layout.addWidget(self._major_combo)
        layout.addWidget(goal_label)
        layout.addWidget(self._goal_input)
        return card

    def _build_severity_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        section_label = QLabel("AI ROASTING SEVERITY")
        section_label.setObjectName("sectionLabel")

        self._severity_value_label = QLabel(SEVERITY_LEVELS[-1])
        self._severity_value_label.setObjectName("severityLabel")
        self._severity_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._severity_slider = QSlider(Qt.Orientation.Horizontal)
        self._severity_slider.setMinimum(0)
        self._severity_slider.setMaximum(len(SEVERITY_LEVELS) - 1)
        self._severity_slider.setSingleStep(1)
        self._severity_slider.setPageStep(1)
        self._severity_slider.setTickInterval(1)
        self._severity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._severity_slider.valueChanged.connect(self._on_severity_changed)

        tick_row = QHBoxLayout()
        for level in SEVERITY_LEVELS:
            tick_label = QLabel(level)
            tick_label.setObjectName("tickLabel")
            tick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tick_row.addWidget(tick_label)

        layout.addWidget(section_label)
        layout.addWidget(self._severity_value_label)
        layout.addWidget(self._severity_slider)
        layout.addLayout(tick_row)
        return card

    def _build_blacklist_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        section_label = QLabel("BLACKLISTED APPS / SITES")
        section_label.setObjectName("sectionLabel")

        self._blacklist_widget = QListWidget()
        for display_name in BLACKLIST_OPTIONS:
            item = QListWidgetItem(display_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._blacklist_widget.addItem(item)

        layout.addWidget(section_label)
        layout.addWidget(self._blacklist_widget)
        return card

    # -- Data binding -------------------------------------------------------

    def _load_current_settings(self) -> None:
        major_index = self._major_combo.findText(config.STUDENT_MAJOR)
        if major_index >= 0:
            self._major_combo.setCurrentIndex(major_index)
        else:
            self._major_combo.setCurrentText(config.STUDENT_MAJOR)

        self._goal_input.setText(config.ACADEMIC_GOAL)

        severity = _personality_to_severity(config.PERSONALITY_MODE)
        self._severity_slider.setValue(SEVERITY_LEVELS.index(severity))
        self._severity_value_label.setText(severity)

        current_blacklist = set(getattr(config, "BLACKLISTED_APPS", []))
        for i in range(self._blacklist_widget.count()):
            item = self._blacklist_widget.item(i)
            phrases = BLACKLIST_OPTIONS[item.text()]
            if any(phrase in current_blacklist for phrase in phrases):
                item.setCheckState(Qt.CheckState.Checked)

    def _on_severity_changed(self, index: int) -> None:
        self._severity_value_label.setText(SEVERITY_LEVELS[index])

    # -- Lock In -------------------------------------------------------------

    def _handle_lock_in(self) -> None:
        goal_text = self._goal_input.text().strip()
        if not goal_text:
            QMessageBox.warning(
                self, "Missing goal", "Type your current study goal first."
            )
            return

        selected_phrases: List[str] = []
        for i in range(self._blacklist_widget.count()):
            item = self._blacklist_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_phrases.extend(BLACKLIST_OPTIONS[item.text()])

        if not selected_phrases:
            confirm = QMessageBox.question(
                self,
                "No apps blacklisted",
                "You haven't selected anything to block. Continue anyway?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        severity = SEVERITY_LEVELS[self._severity_slider.value()]

        try:
            config.update_settings(
                student_major=self._major_combo.currentText().strip(),
                goal=goal_text,
                personality_mode=SEVERITY_TO_PERSONALITY[severity],
                blacklisted_apps=selected_phrases,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return

        self.locked_in.emit()
        self.hide()


# --------------------------------------------------------------------------
# Standalone manual test
# --------------------------------------------------------------------------

def _test_runner() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dashboard = Dashboard(is_initial_launch=True)
    dashboard.locked_in.connect(lambda: print("[dashboard] Locked in! Settings saved."))
    dashboard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _test_runner()
