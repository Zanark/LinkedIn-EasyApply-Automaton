"""Private-data-free, GUI-only progress snapshots on the child process stream."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

PROGRESS_ENV = "LEA_GUI_PROGRESS"
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


def encode_progress(snapshot: ProgressSnapshot) -> str:
    return FRAME_START + snapshot.model_dump_json() + FRAME_END


def _write_progress(snapshot: ProgressSnapshot) -> None:
    sys.stderr.write(encode_progress(snapshot))
    sys.stderr.flush()


def gui_progress() -> ProgressReporter | None:
    """Opt in only for a GUI-owned child, leaving normal CLI/file logs unchanged."""
    return ProgressReporter(_write_progress) if os.environ.get(PROGRESS_ENV) == "1" else None


class ProgressReporter:
    """Accumulate outcomes independently of delayed database/summary persistence."""

    def __init__(self, sink: Callable[[ProgressSnapshot], None] | None = None) -> None:
        self._sink = sink
        self._snapshot: ProgressSnapshot | None = None

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

    def _emit(self) -> None:
        if self._sink is not None and self._snapshot is not None:
            try:
                self._sink(self._snapshot.model_copy(deep=True))
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

    def feed(self, text: str) -> Iterator[str | ProgressSnapshot | ProgressError]:
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
                snapshot = ProgressSnapshot.model_validate_json(payload)
                if snapshot.model_fields_set != ProgressSnapshot.model_fields.keys():
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
