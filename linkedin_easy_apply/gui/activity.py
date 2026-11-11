"""Transient current-operation and retained application-resume indicators."""

from __future__ import annotations

from functools import cache
from html import escape
from pathlib import Path
from typing import Literal, override

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

from linkedin_easy_apply.gui.activity_icons import activity_icon
from linkedin_easy_apply.gui.theme import Palette
from linkedin_easy_apply.gui.widgets import tooltip
from linkedin_easy_apply.progress import Activity, ActivitySnapshot

Lifecycle = Literal["ready", "starting", "running", "finished", "stopped", "error", "unavailable"]
_SP = QStyle.StandardPixmap
_STATES: dict[Activity | Lifecycle, tuple[str, str]] = {
    "ready": ("Ready", "information"),
    "starting": ("Starting command", "information"),
    "running": ("Running command", "information"),
    "finished": ("Command finished", "document"),
    "stopped": ("Stopped", "warning"),
    "error": ("Command error", "error"),
    "unavailable": ("Status unavailable", "warning"),
    "starting_browser": ("Opening browser", "information"),
    "searching_jobs": ("Searching jobs", "information"),
    "opening_job": ("Opening job", "information"),
    "checking_job": ("Checking job", "information"),
    "skipping_job": ("Skipping job", "warning"),
    "selecting_resume": ("Selecting resume", "accent"),
    "reviewing_resume": ("Resume review pause", "warning"),
    "ai_review": ("AI job review", "information"),
    "building_resume": ("Building resume", "accent"),
    "preparing_application": ("Preparing application", "information"),
    "generating_cover_letter": ("Writing cover letter", "accent"),
    "opening_application": ("Opening application", "information"),
    "filling_application": ("Filling application", "information"),
    "selecting_attachment": ("Selecting attachment", "accent"),
    "uploading_document": ("Uploading document", "information"),
    "reviewing_application": ("Reviewing application", "information"),
    "awaiting_input": ("Waiting for you", "warning"),
    "submitting_application": ("Submitting application", "information"),
    "verifying_submission": ("Checking submission", "information"),
    "discarding_application": ("Discarding application", "error"),
    "finding_contacts": ("Finding hiring team", "information"),
    "drafting_message": ("Drafting outreach", "accent"),
    "sending_message": ("Sending outreach", "information"),
    "loading_connections": ("Loading invitations", "information"),
    "connecting": ("Processing invitation", "information"),
    "saving_results": ("Saving results", "accent"),
    "writing_report": ("Writing report", "accent"),
    "pausing": ("Pacing pause", "warning"),
    "finishing": ("Finishing run", "accent"),
}


@cache
def _load_action_font() -> None:
    source = Path(__file__).with_name("fonts") / "Nunito.ttf"
    font_id = QFontDatabase.addApplicationFont(str(source))
    if "Nunito" not in QFontDatabase.applicationFontFamilies(font_id):
        raise ValueError(f"Bundled action font could not be loaded: {source}")


class RunActivity(QFrame):
    """Display explicit engine operations independently of outcome counters."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        _load_action_font()
        self._palette = palette
        self._state: Activity | Lifecycle = "ready"
        self.setObjectName("RunActivity")
        self.setFixedWidth(112)
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(16)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        self.icon = QLabel()
        self.icon.setFixedSize(64, 64)
        self.name = QLabel()
        self.name.setObjectName("ActivityName")
        self.name.setTextFormat(Qt.TextFormat.PlainText)
        self.name.setWordWrap(True)
        self.name.setFixedWidth(90)
        for label in (self.icon, self.name):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.name, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.set_state("ready")

    def set_state(self, state: Activity | Lifecycle) -> None:
        self._state = state
        name, tone = _STATES[state]
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        glow_color = QColor(self._palette[tone])
        glow_color.setAlpha(145 if self._palette.is_dark else 105)
        self._glow.setColor(glow_color)
        self.name.setText(name)
        self.name.setProperty("tone", tone)
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)
        self.name.setFixedHeight(self.name.heightForWidth(self.name.width()))
        self.icon.setPixmap(
            activity_icon(state, self._palette, pixel_ratio=self.devicePixelRatioF())
        )
        self.setAccessibleName(f"Current action: {name}")
        help_text = tooltip(
            f"Current engine operation: {name}; this is not an application outcome.",
            "Waiting for you means answer the current prompt; Applied counts only confirmed submissions.",
        )
        for widget in (self, self.icon, self.name):
            widget.setToolTip(help_text)

    def update_activity(self, snapshot: ActivitySnapshot) -> None:
        self.set_state(snapshot.activity)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.set_state(self._state)

    def warn(self, _message: str) -> None:
        self.set_state("unavailable")


class _Filename(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.value = "No resume selected yet"
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(self.value)

    def set_value(self, value: str) -> None:
        self.value = value
        self._elide()

    def _elide(self) -> None:
        self.setText(
            self.fontMetrics().elidedText(
                self.value, Qt.TextElideMode.ElideMiddle, max(0, self.contentsRect().width())
            )
        )

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._elide()


class ResumeDisplay(QFrame):
    """Keep the final application choice until a later explicit choice replaces it."""

    def __init__(self) -> None:
        super().__init__()
        self.filename: str | None = None
        self.setObjectName("ResumeDisplay")
        self.setMinimumWidth(160)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(self.style().standardIcon(_SP.SP_FileIcon).pixmap(20, 20))
        layout.addWidget(icon)
        caption = QLabel("RESUME")
        caption.setObjectName("MetricTitle")
        self.name = _Filename()
        self.name.setObjectName("ResumeName")
        layout.addWidget(caption)
        layout.addWidget(self.name, 1)
        self._help_widgets = (self, icon, caption, self.name)
        self._update_help()

    def update_activity(self, snapshot: ActivitySnapshot) -> None:
        if snapshot.resume_name is not None:
            self.filename = snapshot.resume_name
            self.name.set_value(snapshot.resume_name)
            self._update_help()

    def _update_help(self) -> None:
        selection = self.filename or "No application resume has been selected in this window"
        self.setAccessibleName(f"Last selected application resume: {selection}")
        help_text = tooltip(
            f"{selection}; selection alone does not confirm attachment or submission.",
            "A tailored resume replaces the previous filename; scans and finished runs keep it.",
        )
        purpose, example = help_text.splitlines()
        help_text = f"<qt>{escape(purpose)}<br/>\n{escape(example)}</qt>"
        for widget in self._help_widgets:
            widget.setToolTip(help_text)
