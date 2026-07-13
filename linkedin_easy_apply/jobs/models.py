"""The :class:`Job` model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Job:
    """A LinkedIn job posting and its extracted metadata."""

    url: str
    external_id: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    applicants: int | None = None
    posting_age: str | None = None
    salary: str | None = None
    description: str | None = None
    recruiter: str | None = None
    easy_apply: bool = False
    already_applied: bool = False
    search_name: str | None = None

    def to_db_dict(self) -> dict[str, Any]:
        """Serialise to the flat dict shape expected by ``Database.upsert_job``."""
        return asdict(self)

    @property
    def summary(self) -> str:
        return f"{self.title or '?'} @ {self.company or '?'} ({self.location or '?'})"
