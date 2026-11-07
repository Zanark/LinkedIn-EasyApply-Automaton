"""Read-only application resources and the writable desktop workspace."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def workspace_root() -> Path:
    override = os.environ.get("LEA_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local / "EasyApplyAutomaton"
    return resource_root()


def prepare_workspace() -> Path:
    """Create missing first-run examples, never replacing an existing file."""
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    if is_frozen():
        config_dir = root / "configs"
        config_dir.mkdir(exist_ok=True)
        for name in ("config", "answers", "searches"):
            target = config_dir / f"{name}.yaml"
            if target.exists():
                continue
            source = resource_root() / "configs" / f"{name}.example.yaml"
            with source.open("rb") as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    return root
