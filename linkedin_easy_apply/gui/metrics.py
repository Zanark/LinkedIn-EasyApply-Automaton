"""Compact per-command counters, independent of console history and settings."""

from __future__ import annotations

import time
from typing import override

from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply.gui.widgets import tooltip
from linkedin_easy_apply.progress import Metric, ProgressSnapshot

_JOB_METRICS: tuple[Metric, ...] = ("scanned", "applied", "skipped", "failed", "hr_sent")
_CONNECT_METRICS: tuple[Metric, ...] = (
    "connect_processed",
    "connect_sent",
    "connect_already",
    "connect_skipped",
    "connect_failed",
)
_LABELS: dict[Metric, tuple[str, str, str, str]] = {
    "scanned": (
        "Scanned",
        "accent",
        "Unique jobs opened or discovered in this command, not database lifetime totals.",
        "One job appearing in two search pages increases Scanned only once.",
    ),
    "applied": (
        "Applied",
        "document",
        "Applications confirmed by the workflow; attempts and dry runs do not count.",
        "A confirmed submission counts immediately, even while hiring-team approval waits.",
    ),
    "skipped": (
        "Skipped",
        "warning",
        "Skip decisions, including scan-only jobs and completed dry runs, as in the final summary.",
        "Scan can show Scanned 10 and Skipped 10 while Applied stays 0.",
    ),
    "failed": (
        "Failed",
        "error",
        "Application failures reported by the workflow, separate from uncertain submissions.",
        "A failed form adds 1 here; a submission needing verification adds 1 to Unconfirmed.",
    ),
    "hr_sent": (
        "HR sent",
        "document",
        "Hiring-team messages reported sent by the engine, not drafts or invitations.",
        "Collecting three recruiter drafts leaves HR sent at 0 and shows Drafts 3 below.",
    ),
    "connect_processed": (
        "Profiles",
        "accent",
        "Distinct invitation targets with an outcome in this connection pass.",
        "A profile already connected counts as checked, not as a new invitation sent.",
    ),
    "connect_sent": (
        "Invites",
        "document",
        "Connection invitations reported sent, excluding simulated sends.",
        "A dry-run would-send increments Would-send below and leaves Invites at 0.",
    ),
    "connect_already": (
        "Already",
        "muted",
        "Profiles already connected or with an invitation pending.",
        "An existing pending invitation adds 1 here without sending a second one.",
    ),
    "connect_skipped": (
        "Skipped",
        "warning",
        "Invitation targets without a usable free Connect or note control.",
        "A profile with no Connect button adds 1 here, not to Invites.",
    ),
    "connect_failed": (
        "Failed",
        "error",
        "Connection attempts reported failed, separate from application failures.",
        "A failed invitation adds 1 here; reaching the weekly cap is not a failure.",
    ),
}
_PHASES = {
    "starting": "Starting",
    "reviewing": "Checking jobs",
    "applying": "Filling application",
    "outreach": "Hiring-team outreach",
    "connecting": "Connection invitations",
}


class RunMetrics(QFrame):
    """Retain the last reported snapshot until another command is accepted."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RunMetrics")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._snapshot: ProgressSnapshot | None = None
        self._action: str | None = None
        self._started_at: float | None = None
        self._elapsed = 0
        self._state = "Ready"
        self._warning = False
        self._narrow: bool | None = None
        self.caption = QLabel("Live counters")
        self.caption.setObjectName("MetricsCaption")
        self.caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.caption.setMinimumWidth(0)
        self.caption.setToolTip(
            tooltip(
                "Identify the actual child command, its engine target and elapsed process time.",
                "Apply #12 | 3/10 | 02:14 means three completions toward ten, not an ETA.",
            )
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        self._rows: list[QHBoxLayout] = []
        self._row_widgets: list[QWidget] = []
        for _ in range(2):
            row = QWidget(self)
            row.setObjectName("MetricsRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            self._rows.append(row_layout)
            self._row_widgets.append(row)
            layout.addWidget(row)
        self._cards: list[QFrame] = []
        self._titles: list[QLabel] = []
        self._values: list[QLabel] = []
        for _ in _JOB_METRICS:
            card = QFrame(self)
            card.setObjectName("RunMetric")
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            box = QVBoxLayout(card)
            box.setContentsMargins(8, 4, 8, 4)
            box.setSpacing(0)
            value = QLabel("--", card)
            value.setObjectName("MetricValue")
            value.setMinimumWidth(0)
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            title = QLabel(card)
            title.setObjectName("MetricTitle")
            box.addWidget(value)
            box.addWidget(title)
            self._cards.append(card)
            self._titles.append(title)
            self._values.append(value)
        self._details = QLabel("Current command only; drafts and dry runs are not sends.")
        self._details.setObjectName("MetricsDetails")
        self._details.setWordWrap(True)
        self._details.setToolTip(
            tooltip(
                "Show separate dry-run, draft, uncertain and invitation totals for this command.",
                "Drafts 3 and HR sent 0 means contacts were collected, not messaged.",
            )
        )
        layout.addWidget(self._details)
        self._target = QProgressBar()
        self._target.setObjectName("RunTarget")
        self._target.setRange(0, 1000)
        self._target.setTextVisible(False)
        self._target.setFixedHeight(3)
        self._target.hide()
        self._target.setToolTip(
            tooltip(
                "Show progress toward this phase's target; an early exit does not fill the bar.",
                "Scan uses discovered jobs; Apply uses submitted or completed dry-run forms.",
            )
        )
        layout.addWidget(self._target)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._render()
        self._arrange()

    def prepare(self, action: str | None) -> None:
        self._timer.stop()
        self._snapshot = None
        self._action = action
        self._started_at = None
        self._elapsed = 0
        self._state = "Waiting"
        self._warning = False
        self.setVisible(action is not None)
        self.caption.setVisible(action is not None)
        self._render()

    def begin(self) -> None:
        self._started_at = time.monotonic()
        self._state = "Running"
        self._timer.start()
        self._render()

    def update_progress(self, snapshot: ProgressSnapshot) -> None:
        self._snapshot = snapshot
        self._action = snapshot.action
        self._warning = False
        self.show()
        self.caption.show()
        self._render()

    def warn(self, message: str) -> None:
        self._warning = True
        self._render()

    def finish(self, state: str) -> None:
        self._tick()
        self._timer.stop()
        self._state = state
        self._render()

    def _tick(self) -> None:
        if self._started_at is not None:
            self._elapsed = int(time.monotonic() - self._started_at)
        self._render_caption()

    def _goal(self) -> tuple[int, int | None]:
        snapshot = self._snapshot
        if snapshot is None:
            return 0, None
        counts = snapshot.counts
        if snapshot.phase == "connecting":
            return counts["connect_processed"], counts["connect_total"]
        if snapshot.action == "scan":
            return counts["scanned"], snapshot.target
        return counts["applied"] + counts["dry_runs"], snapshot.target

    def _render_caption(self) -> None:
        snapshot = self._snapshot
        elapsed = f"{self._elapsed // 60:02}:{self._elapsed % 60:02}"
        if snapshot is None:
            action = self._action.title() if self._action else "Live counters"
            self.caption.setText(f"{action} | {elapsed}" if self._started_at else action)
            return
        action = snapshot.action.title()
        if snapshot.run_id is not None:
            action += f" #{snapshot.run_id}"
        done, target = self._goal()
        progress = f"{done:,}/{target:,} | {elapsed}" if target else elapsed
        text = f"{action} | {progress}"
        if self.caption.fontMetrics().horizontalAdvance(text) > self.caption.contentsRect().width():
            text = f"{action}\n{progress}"
        self.caption.setText(text)

    def _render(self) -> None:
        snapshot = self._snapshot
        metrics = _CONNECT_METRICS if self._action == "connect" else _JOB_METRICS
        for card, title, value, metric in zip(
            self._cards, self._titles, self._values, metrics, strict=True
        ):
            label, role, purpose, example = _LABELS[metric]
            title.setText(label)
            value.setText(f"{snapshot.counts[metric]:,}" if snapshot else "--")
            value.setProperty("tone", role)
            value.style().unpolish(value)
            value.style().polish(value)
            for widget in (card, title, value):
                widget.setToolTip(tooltip(purpose, example))
        if snapshot is None:
            details = (
                "Current command only; drafts and dry runs are not sends."
                if self._state == "Ready"
                else f"{self._state}: no run metrics received."
            )
        else:
            counts = snapshot.counts
            live = self._state == "Running"
            phase = _PHASES[snapshot.phase] if live else f"{self._state} - last reported"
            if snapshot.dry_run or (snapshot.phase == "connecting" and snapshot.connect_dry_run):
                phase += " [DRY RUN]"
            if snapshot.action == "connect":
                details = f"{phase} | Would-send {counts['connect_dry_runs']:,}"
            else:
                details = (
                    f"{phase} | Drafts {counts['hr_drafted']:,}"
                    f" | Dry runs {counts['dry_runs']:,}"
                    f" | Unconfirmed {counts['unconfirmed']:,}"
                    f" | Invites {counts['connect_sent']:,}"
                )
                if counts["connect_total"] or counts["connect_dry_runs"]:
                    details += (
                        f" | Profiles {counts['connect_processed']:,}/{counts['connect_total']:,}"
                        f" | Would-send {counts['connect_dry_runs']:,}"
                        f" | Already {counts['connect_already']:,}"
                        f" | Invite skipped {counts['connect_skipped']:,}"
                        f" | Invite failed {counts['connect_failed']:,}"
                    )
            for metric, label in (
                ("hr_declined", "HR declined"),
                ("hr_failed", "HR failed"),
                ("hr_dry_runs", "HR would-send"),
            ):
                if counts[metric]:
                    details += f" | {label} {counts[metric]:,}"
        if self._warning:
            details = "Metrics interrupted - " + details
        self._details.setText(details)
        done, target = self._goal()
        self._target.setVisible(bool(target))
        self._target.setValue(min(1000, done * 1000 // target) if target else 0)
        self._render_caption()

    def _arrange(self) -> None:
        narrow = self.width() < 540
        if narrow == self._narrow:
            return
        self._narrow = narrow
        for row_layout in self._rows:
            while row_layout.count():
                row_layout.takeAt(0)
        for index, card in enumerate(self._cards):
            row_index = 1 if narrow and index >= 3 else 0
            self._rows[row_index].addWidget(card, 1)
            card.show()
        self._row_widgets[1].setVisible(narrow)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._arrange()
        self._render_caption()
