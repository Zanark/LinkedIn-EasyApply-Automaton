"""Persist validated private run presets without editing the saved config."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from linkedin_easy_apply.config import ConfigError, load_config


def write_run_config(source: Path, overrides: dict[str, Any], workspace: Path) -> Path:
    """Merge dotted-key overrides into a private, reusable CLI configuration."""
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {source}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("The saved configuration must be a YAML mapping.")
    data = deepcopy(raw)
    for dotted, value in overrides.items():
        parts = dotted.split(".")
        node = data
        for part in parts[:-1]:
            section = node.setdefault(part, {})
            if not isinstance(section, dict):
                raise ConfigError(f"Configuration section '{part}' must be a mapping.")
            node = section
        node[parts[-1]] = value
    directory = workspace / "logs" / "gui-runs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"settings-{uuid4().hex}.yaml"
    with target.open("x", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    try:
        load_config(target)
    except ConfigError:
        target.unlink()
        raise
    return target
