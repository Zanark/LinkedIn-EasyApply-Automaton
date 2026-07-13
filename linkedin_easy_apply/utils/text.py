"""Text normalisation helpers used by the parser, scoring and answer store."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lower-case, strip accents/punctuation and collapse whitespace.

    Used to produce a canonical form for fuzzy comparisons.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _NON_WORD_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Return the normalised whitespace-separated tokens of *text*."""
    normalized = normalize(text)
    return normalized.split() if normalized else []


def slugify(text: str) -> str:
    """Produce a filesystem/identifier friendly slug from *text*."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _SLUG_RE.sub("-", text.lower()).strip("-")
