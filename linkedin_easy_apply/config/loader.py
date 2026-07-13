"""YAML configuration loader with environment-variable expansion.

Supports ``${VAR}`` and ``${VAR:-default}`` style expansion inside string
values so that secrets and machine-specific paths can stay out of the file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from linkedin_easy_apply.config.models import AppConfig

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


class ConfigError(Exception):
    """Raised when a configuration file cannot be loaded or is invalid."""


def _expand_env(value: str) -> str:
    """Expand ``${VAR}`` / ``${VAR:-default}`` references inside *value*."""

    def _replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return os.environ.get(name, default if default is not None else "")

    return _ENV_PATTERN.sub(_replace, value)


def _expand_tree(node: Any) -> Any:
    """Recursively expand environment variables in every string leaf."""
    if isinstance(node, dict):
        return {key: _expand_tree(val) for key, val in node.items()}
    if isinstance(node, list):
        return [_expand_tree(item) for item in node]
    if isinstance(node, str):
        return _expand_env(node)
    return node


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a dict, expanding environment variables."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"Configuration file not found: {file_path}")
    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise ConfigError(f"Failed to parse YAML {file_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Top-level YAML in {file_path} must be a mapping")
    return _expand_tree(raw)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate an :class:`AppConfig` from a YAML file.

    Raises :class:`ConfigError` for missing files, malformed YAML, or
    validation failures.
    """
    data = load_yaml(path)
    try:
        return AppConfig.model_validate(data)
    except Exception as exc:  # pydantic ValidationError and friends
        raise ConfigError(f"Invalid configuration in {path}: {exc}") from exc
