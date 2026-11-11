"""GUI-only counters and separately opted-in transient activity records."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from unicodedata import category

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

PROGRESS_ENV = "LEA_GUI_PROGRESS"
ACTIVITY_ENV = "LEA_GUI_ACTIVITY"
FRAME_START = "\x1eLEA_METRICS:"
FRAME_END = "\x1f"
MAX_FRAME = 16_384

Metric = Literal[
    "scanned",
    "applied",
    "skipped",
    "failed",
    "dry_runs",
    "unconfirmed",
    "hr_sent",
    "hr_drafted",
    "hr_declined",
    "hr_failed",
    "hr_dry_runs",
    "connect_total",
    "connect_processed",
    "connect_sent",
    "connect_already",
    "connect_skipped",
    "connect_failed",
    "connect_dry_runs",
]
METRICS: tuple[Metric, ...] = (
    "scanned",
    "applied",
    "skipped",
    "failed",
    "dry_runs",
    "unconfirmed",
    "hr_sent",
    "hr_drafted",
    "hr_declined",
    "hr_failed",
    "hr_dry_runs",
    "connect_total",
    "connect_processed",
    "connect_sent",
    "connect_already",
    "connect_skipped",
    "connect_failed",
    "connect_dry_runs",
)
RunAction = Literal["apply", "scan", "reapply", "connect"]
RunPhase = Literal["starting", "reviewing", "applying", "outreach", "connecting"]
Activity = Literal[
    "starting_browser",
    "searching_jobs",
    "opening_job",
    "checking_job",
    "skipping_job",
    "selecting_resume",
    "reviewing_resume",
    "ai_review",
    "building_resume",
    "preparing_application",
    "generating_cover_letter",
    "opening_application",
    "filling_application",
    "selecting_attachment",
    "uploading_document",
    "reviewing_application",
    "awaiting_input",
    "submitting_application",
    "verifying_submission",
    "discarding_application",
    "finding_contacts",
    "drafting_message",
    "sending_message",
    "loading_connections",
    "connecting",
    "saving_results",
    "writing_report",
    "pausing",
    "finishing",
]
Count = Annotated[int, Field(strict=True, ge=0)]


class ProgressSnapshot(BaseModel):
    """A complete versioned snapshot; no names, URLs, answers or message text."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Literal[1] = 1
    action: RunAction
    phase: RunPhase = "starting"
    run_id: Count | None = None
    dry_run: bool = False
    target: Count | None = None
    connect_dry_run: bool = False
    counts: dict[Metric, Count] = Field(default_factory=lambda: dict.fromkeys(METRICS, 0))

    @field_validator("counts")
    @classmethod
    def complete_counts(cls, counts: dict[Metric, int]) -> dict[Metric, int]:
        if counts.keys() != set(METRICS):
            raise ValueError("A progress snapshot must contain every counter.")
        return counts

    @field_validator("version", mode="before")
    @classmethod
    def exact_version_type(cls, version: object) -> object:
        if type(version) is not int:
            raise ValueError("The protocol version must be an integer.")
        return version


class ActivitySnapshot(BaseModel):
    """Local display metadata, not counters or proof of attachment/submission."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Literal[2] = 2
    activity: Activity
    resume_name: Annotated[str, Field(min_length=1, max_length=512)] | None = None

    @field_validator("version", mode="before")
    @classmethod
    def exact_version_type(cls, version: object) -> object:
        if type(version) is not int:
            raise ValueError("The protocol version must be an integer.")
        return version

    @field_validator("resume_name")
    @classmethod
    def filename_only(cls, name: str | None) -> str | None:
        if name is not None and (
            name in {".", ".."}
            or any(char in "/\\" or category(char) in {"Cc", "Zl", "Zp"} for char in name)
        ):
            raise ValueError("Only a filename is allowed, never a path or control characters.")
        return name


class RetryPreviewSnapshot(BaseModel):
    """Saved retry-batch history, never a live run or a send outcome."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Literal[3] = 3
    action: Literal["reapply-list"] = "reapply-list"
    targets: Count
    last_failed: Count
    last_aborted: Count
    prior_attempts: Count
    repeated_jobs: Count

    @field_validator("version", mode="before")
    @classmethod
    def exact_version_type(cls, version: object) -> object:
        if type(version) is not int:
            raise ValueError("The protocol version must be an integer.")
        return version


_RECORD: TypeAdapter[ProgressSnapshot | ActivitySnapshot | RetryPreviewSnapshot] = TypeAdapter(
    ProgressSnapshot | ActivitySnapshot | RetryPreviewSnapshot
)


def encode_progress(snapshot: ProgressSnapshot | ActivitySnapshot | RetryPreviewSnapshot) -> str:
    return FRAME_START + snapshot.model_dump_json() + FRAME_END


def _write_progress(snapshot: ProgressSnapshot | ActivitySnapshot | RetryPreviewSnapshot) -> None:
    sys.stderr.write(encode_progress(snapshot))
    sys.stderr.flush()


def gui_progress() -> ProgressReporter | None:
    """Opt in only for a GUI-owned child, leaving normal CLI/file logs unchanged."""
    if os.environ.get(PROGRESS_ENV) != "1":
        return None
    return ProgressReporter(
        _write_progress,
        activity_sink=_write_progress if os.environ.get(ACTIVITY_ENV) == "1" else None,
    )


class ProgressReporter:
    """Accumulate outcomes independently of delayed database/summary persistence."""

    def __init__(
        self,
        sink: Callable[[ProgressSnapshot | RetryPreviewSnapshot], None] | None = None,
        *,
        activity_sink: Callable[[ActivitySnapshot], None] | None = None,
    ) -> None:
        self._sink = sink
        self._activity_sink = activity_sink
        self._snapshot: ProgressSnapshot | None = None

    def retry_preview(self, snapshot: RetryPreviewSnapshot) -> None:
        """Publish the retrieved history without starting or changing a live run."""
        self._emit(snapshot)

    def activity(self, activity: Activity, *, resume_path: Path | None = None) -> None:
        """Report an operation; only an explicit filename changes the retained display."""
        if self._activity_sink is None:
            return
        try:
            snapshot = ActivitySnapshot(
                activity=activity,
                resume_name=resume_path.name if resume_path is not None else None,
            )
        except ValidationError:
            self._activity_sink = None
            logger.warning("Live activity unavailable: invalid display metadata.")
            return
        try:
            self._activity_sink(snapshot)
        except OSError as exc:
            self._activity_sink = None
            logger.warning("Live activity unavailable: {}", exc)

    def start(
        self,
        action: str,
        *,
        run_id: int | None = None,
        dry_run: bool = False,
        target: int | None = None,
    ) -> None:
        self._snapshot = ProgressSnapshot.model_validate(
            {"action": action, "run_id": run_id, "dry_run": dry_run, "target": target}
        )
        self._emit()

    def increment(
        self, increments: Mapping[Metric, int] | None = None, *, phase: RunPhase | None = None
    ) -> None:
        if self._snapshot is None:
            return
        data = self._snapshot.model_dump()
        counts = data["counts"]
        for key, amount in (increments or {}).items():
            if key not in counts or type(amount) is not int or amount < 0:
                raise ValueError("Invalid live-metrics increment.")
            counts[key] += amount
        if phase is not None:
            data["phase"] = phase
        self._snapshot = ProgressSnapshot.model_validate(data)
        self._emit()

    def outreach(self, outcome: str) -> None:
        metrics: dict[str, Metric] = {
            "sent": "hr_sent",
            "drafted": "hr_drafted",
            "declined": "hr_declined",
            "failed": "hr_failed",
            "dry_run": "hr_dry_runs",
        }
        self.increment({metrics[outcome]: 1})

    def connections(self, total: int, *, dry_run: bool) -> None:
        if self._snapshot is None:
            self.start("connect", dry_run=dry_run, target=total)
        assert self._snapshot is not None
        data = self._snapshot.model_dump()
        data["phase"] = "connecting"
        data["connect_dry_run"] = dry_run
        data["counts"]["connect_total"] = total
        if self._snapshot.action == "connect":
            data["target"] = total
        self._snapshot = ProgressSnapshot.model_validate(data)
        self._emit()

    def _emit(self, snapshot: ProgressSnapshot | RetryPreviewSnapshot | None = None) -> None:
        snapshot = snapshot if snapshot is not None else self._snapshot
        if self._sink is not None and snapshot is not None:
            try:
                self._sink(snapshot.model_copy(deep=True))
            except OSError as exc:
                self._sink = None
                logger.warning("Live metrics unavailable: {}", exc)


@dataclass(frozen=True, slots=True)
class ProgressError:
    message: str


class ProgressStream:
    """Separate bounded framed records without delaying ordinary output/prompts."""

    def __init__(self) -> None:
        self._pending = ""
        self._discarding = False

    def feed(
        self, text: str
    ) -> Iterator[str | ProgressSnapshot | ActivitySnapshot | RetryPreviewSnapshot | ProgressError]:
        self._pending += text
        while self._pending:
            if self._discarding:
                end = self._pending.find(FRAME_END)
                self._pending = "" if end < 0 else self._pending[end + len(FRAME_END) :]
                if end < 0:
                    return
                self._discarding = False
            start = self._pending.find(FRAME_START)
            if start < 0:
                keep = next(
                    (
                        length
                        for length in range(len(FRAME_START) - 1, 0, -1)
                        if self._pending.endswith(FRAME_START[:length])
                    ),
                    0,
                )
                visible = self._pending[:-keep] if keep else self._pending
                self._pending = self._pending[-keep:] if keep else ""
                if visible:
                    yield visible
                return
            if start:
                yield self._pending[:start]
                self._pending = self._pending[start:]
            end = self._pending.find(FRAME_END, len(FRAME_START))
            restart = self._pending.find(FRAME_START, len(FRAME_START))
            if restart >= 0 and (end < 0 or restart < end):
                self._pending = self._pending[restart:]
                yield ProgressError("Incomplete live-metrics record; previous counters retained.")
                continue
            if end < 0:
                if len(self._pending) - len(FRAME_START) > MAX_FRAME:
                    self._pending = ""
                    self._discarding = True
                    yield ProgressError("Live-metrics record exceeded its size limit.")
                return
            payload = self._pending[len(FRAME_START) : end]
            self._pending = self._pending[end + len(FRAME_END) :]
            if len(payload) > MAX_FRAME:
                yield ProgressError("Live-metrics record exceeded its size limit.")
                continue
            try:
                snapshot = _RECORD.validate_json(payload)
                if snapshot.model_fields_set != type(snapshot).model_fields.keys():
                    yield ProgressError(
                        "Incomplete live-metrics snapshot; previous counters retained."
                    )
                else:
                    yield snapshot
            except ValidationError:
                yield ProgressError(
                    "Invalid or unsupported live-metrics record; previous counters retained."
                )

    def finish(self) -> Iterator[str | ProgressError]:
        if self._pending.startswith(FRAME_START) or self._discarding:
            yield ProgressError("Incomplete live-metrics record; previous counters retained.")
        elif self._pending:
            yield self._pending
        self._pending = ""
        self._discarding = False
