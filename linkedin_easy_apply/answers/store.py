"""The user's answer store, loaded from ``answers.yaml``.

The store holds three kinds of data:

* **fields** - flat personal / preference values (phone, email, notice_period...)
* **skills** - a mapping of skill -> years of experience (with aliases)
* **aliases** - alternative names that resolve to a canonical field

Lookups are alias-aware and normalised so ``"Java"``, ``"Core Java"`` and
``"Years of Java Experience"`` all resolve to the same skill entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from linkedin_easy_apply.utils.text import normalize

_RESERVED = {"skills", "aliases", "defaults"}

_TRUTHY = {"yes", "true", "y", "1", "authorized", "authorised"}
_FALSY = {"no", "false", "n", "0"}


class AnswerStore:
    """In-memory, alias-aware view over the user's answers."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        self._fields: dict[str, Any] = {
            key: value for key, value in data.items() if key not in _RESERVED
        }
        self._defaults: dict[str, Any] = dict(data.get("defaults") or {})
        self._aliases: dict[str, str] = {
            normalize(alias): normalize(target)
            for alias, target in (data.get("aliases") or {}).items()
        }
        self._skill_years: dict[str, float] = {}
        self._load_skills(data.get("skills") or {})

    def _load_skills(self, skills: dict[str, Any]) -> None:
        for name, spec in skills.items():
            years: float | None
            aliases: list[str] = []
            if isinstance(spec, dict):
                years = _to_float(spec.get("years"))
                aliases = [str(a) for a in (spec.get("aliases") or [])]
            else:
                years = _to_float(spec)
            if years is None:
                continue
            for key in [name, *aliases]:
                self._skill_years[normalize(key)] = years

    # -- constructors ---------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path) -> AnswerStore:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"answers file not found: {file_path}")
        data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("answers.yaml must contain a mapping at the top level")
        return cls(data)

    # -- field access ---------------------------------------------------------
    def _canonical(self, key: str) -> str:
        norm = normalize(key)
        return self._aliases.get(norm, norm)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key* (alias-aware), else *default*."""
        canonical = self._canonical(key)
        for field, value in self._fields.items():
            if normalize(field) == canonical:
                return value
        if canonical in self._defaults:
            return self._defaults[canonical]
        return default

    def get_str(self, key: str, default: str | None = None) -> str | None:
        value = self.get(key)
        return str(value) if value is not None else default

    def get_bool(self, key: str) -> bool | None:
        """Interpret a stored value as a boolean, if possible."""
        value = self.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        token = normalize(str(value))
        if token in _TRUTHY:
            return True
        if token in _FALSY:
            return False
        return None

    # -- skills ---------------------------------------------------------------
    def get_skill_years(self, skill: str) -> float | None:
        """Years of experience for *skill*, resolving aliases; ``None`` if unknown."""
        return self._skill_years.get(normalize(skill))

    def known_skills(self) -> list[str]:
        return sorted(self._skill_years)

    def default(self, key: str, fallback: Any = None) -> Any:
        return self._defaults.get(normalize(key), fallback)

    @property
    def fields(self) -> dict[str, Any]:
        return dict(self._fields)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
