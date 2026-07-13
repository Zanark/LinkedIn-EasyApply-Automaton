"""Filesystem path helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def project_root() -> Path:
    """Return the repository root (two levels above this file's package)."""
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: str | Path) -> Path:
    """Create *path* (and parents) if missing and return it as a ``Path``."""
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def timestamp_slug(moment: datetime | None = None) -> str:
    """Return a sortable, filesystem-safe timestamp such as ``20240131-153000-123``."""
    moment = moment or datetime.now()
    return moment.strftime("%Y%m%d-%H%M%S-%f")[:-3]
