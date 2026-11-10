"""Transient current-operation and retained application-resume indicators."""

from __future__ import annotations

from html import escape
from typing import Literal, override

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

from linkedin_easy_apply.gui.theme import Palette
from linkedin_easy_apply.gui.widgets import tooltip
from linkedin_easy_apply.progress import Activity, ActivitySnapshot

Lifecycle = Literal["ready", "starting", "running", "finished", "stopped", "error", "unavailable"]
_SP = QStyle.StandardPixmap
_STATES: dict[Activity | Lifecycle, tuple[str, QStyle.StandardPixmap, str]] = {
    "ready": ("Ready", _SP.SP_DialogApplyButton, "muted"),
    "starting": ("Starting command", _SP.SP_MediaPlay, "accent"),
    "running": ("Running command", _SP.SP_MediaPlay, "accent"),
    "finished": ("Command finished", _SP.SP_DialogApplyButton, "document"),
    "stopped": ("Stopped", _SP.SP_MediaStop, "warning"),
    "error": ("Command error", _SP.SP_MessageBoxCritical, "error"),
    "unavailable": ("Status unavailable", _SP.SP_MessageBoxWarning, "warning"),
    "starting_browser": ("Opening browser", _SP.SP_ComputerIcon, "accent"),
    "searching_jobs": ("Searching jobs", _SP.SP_FileDialogContentsView, "accent"),
    "opening_job": ("Opening job", _SP.SP_DirOpenIcon, "accent"),
    "checking_job": ("Checking job", _SP.SP_FileDialogDetailedView, "accent"),
    "skipping_job": ("Skipping job", _SP.SP_MediaSkipForward, "muted"),
    "selecting_resume": ("Selecting resume", _SP.SP_FileDialogListView, "accent"),
    "reviewing_resume": ("Resume review pause", _SP.SP_FileDialogInfoView, "warning"),
    "ai_review": ("AI job review", _SP.SP_MessageBoxInformation, "accent"),
    "building_resume": ("Building resume", _SP.SP_FileDialogNewFolder, "accent"),
    "preparing_application": ("Preparing application", _SP.SP_FileIcon, "accent"),
    "generating_cover_letter": ("Writing cover letter", _SP.SP_FileDialogNewFolder, "accent"),
    "opening_application": ("Opening application", _SP.SP_DialogOpenButton, "accent"),
    "filling_application": ("Filling application", _SP.SP_FileDialogDetailedView, "accent"),
    "selecting_attachment": ("Selecting attachment", _SP.SP_FileDialogListView, "accent"),
    "uploading_document": ("Uploading document", _SP.SP_ArrowUp, "accent"),
    "reviewing_application": ("Reviewing application", _SP.SP_FileDialogInfoView, "accent"),
    "awaiting_input": ("Waiting for you", _SP.SP_MessageBoxQuestion, "warning"),
    "submitting_application": ("Submitting application", _SP.SP_ArrowForward, "accent"),
    "verifying_submission": ("Checking submission", _SP.SP_BrowserReload, "accent"),
    "discarding_application": ("Discarding application", _SP.SP_TrashIcon, "warning"),
    "finding_contacts": ("Finding hiring team", _SP.SP_DirHomeIcon, "accent"),
    "drafting_message": ("Drafting outreach", _SP.SP_FileIcon, "accent"),
    "sending_message": ("Sending outreach", _SP.SP_ArrowForward, "accent"),
    "loading_connections": ("Loading invitations", _SP.SP_DialogOpenButton, "accent"),
    "connecting": ("Processing invitation", _SP.SP_DialogYesButton, "accent"),
    "saving_results": ("Saving results", _SP.SP_DialogSaveButton, "accent"),
    "writing_report": ("Writing report", _SP.SP_FileDialogDetailedView, "accent"),
    "pausing": ("Pacing pause", _SP.SP_MediaPause, "warning"),
    "finishing": ("Finishing run", _SP.SP_BrowserReload, "accent"),
}


class RunActivity(QFrame):
    """Display explicit engine operations independently of outcome counters."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self._palette = palette
        self._state: Activity | Lifecycle = "ready"
        self.setObjectName("RunActivity")
        self.setFixedWidth(112)
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        self.caption = QLabel("CURRENT ACTION")
        self.caption.setObjectName("MetricTitle")
        self.icon = QLabel()
        self.name = QLabel()
        self.name.setObjectName("ActivityName")
        self.name.setTextFormat(Qt.TextFormat.PlainText)
        self.name.setWordWrap(True)
        self.name.setMinimumHeight(36)
        for label in (self.caption, self.icon, self.name):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.caption)
        layout.addStretch(1)
        layout.addWidget(self.icon)
        layout.addWidget(self.name)
        layout.addStretch(1)
        self.set_state("ready")

    def set_state(self, state: Activity | Lifecycle) -> None:
        self._state = state
        name, standard_icon, tone = _STATES[state]
        self.name.setText(name)
        self.name.setProperty("tone", tone)
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)
        pixmap = self.style().standardIcon(standard_icon).pixmap(32, 32)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(self._palette[tone]))
        painter.end()
        self.icon.setPixmap(pixmap)
        self.setAccessibleName(f"Current action: {name}")
        help_text = tooltip(
            f"Current engine operation: {name}; this is not an application outcome.",
            "Waiting for you means answer the current prompt; Applied counts only confirmed submissions.",
        )
        for widget in (self, self.caption, self.icon, self.name):
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
