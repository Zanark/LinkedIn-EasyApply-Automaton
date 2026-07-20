"""Data types describing a detected form field."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FieldKind(StrEnum):
    """The control type of a form field."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    DATE = "date"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class FormField:
    """A single field discovered inside an Easy Apply step.

    ``control`` and ``container`` hold Playwright locators (typed as ``Any`` to
    avoid a hard import dependency). ``options`` lists selectable labels for
    select/radio controls.
    """

    label: str
    kind: FieldKind
    control: Any = None
    container: Any = None
    options: list[str] = field(default_factory=list)
    option_controls: list[Any] = field(default_factory=list)
    required: bool = False
    current_value: str | None = None  # value the control already holds, if any

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FormField(label={self.label!r}, kind={self.kind.value}, options={self.options})"
