"""Generate short, personalised messages to hiring-team recruiters.

Mirrors :class:`~linkedin_easy_apply.answers.cover_letter.CoverLetterGenerator`:
a built-in template renders out-of-the-box, and a user template file can be
supplied to override it. The rendered text is what the outreach flow types into
LinkedIn's message compose box after a successful application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    DictLoader,
    Environment,
    FileSystemLoader,
    select_autoescape,
)

_DEFAULT_TEMPLATE = """Hi {{ recruiter_first_name | default('there') }},

I just applied for the {{ role }} role at {{ company }} and wanted to introduce myself.
{% if tech_stack %}My background is a strong match, especially {{ tech_stack | join(', ') }}.
{% endif %}{% if years_experience %}With {{ years_experience }}+ years of experience, I'm {% else %}I'm {% endif %}confident I can add value to your team.

Would love to connect and share more about how I can help. Thank you for your time!

Best,
{{ candidate_name | default('') }}"""

_DEFAULT_TEMPLATE_NAME = "__default__"

# LinkedIn caps the note attached to a connection *invitation* at 300 characters
# (the free message you can send before they accept). ``render_note`` guarantees
# its output never exceeds this.
NOTE_CHAR_LIMIT = 300

# A compact, one-paragraph variant sized for that 300-char invite note: it always
# introduces the candidate and says why they're reaching out; the tech-stack list
# and portfolio link are trimmed first if space runs short (see ``render_note``).
_DEFAULT_NOTE_TEMPLATE = (
    "Hi {{ recruiter_first_name | default('there') }}, "
    "I'm {{ candidate_name | default('a recent applicant', true) }}. "
    "I just applied for the {{ role }} role at {{ company }} and would love to connect."
    "{% if tech_stack %} Strong background in {{ tech_stack | join(', ') }}"
    "{% if years_experience %} ({{ years_experience }}+ yrs){% endif %}.{% endif %}"
    "{% if portfolio_url %} Portfolio: {{ portfolio_url }}{% endif %}"
)
_DEFAULT_NOTE_TEMPLATE_NAME = "__default_note__"


def _truncate_note(text: str, limit: int) -> str:
    """Hard-cap *text* at *limit* chars, preferring a word boundary + ellipsis."""
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rstrip()
    if " " in clipped:
        clipped = clipped[: clipped.rfind(" ")].rstrip(" ,.;:-")
    return clipped + "…"


class HiringTeamMessenger:
    """Render outreach messages from a template and a context dict."""

    def __init__(
        self,
        template_path: str | Path | None = None,
        *,
        note_template_path: str | Path | None = None,
    ) -> None:
        loaders: list[BaseLoader] = [
            DictLoader(
                {
                    _DEFAULT_TEMPLATE_NAME: _DEFAULT_TEMPLATE,
                    _DEFAULT_NOTE_TEMPLATE_NAME: _DEFAULT_NOTE_TEMPLATE,
                }
            )
        ]
        self._template_name = _DEFAULT_TEMPLATE_NAME
        self._note_template_name = _DEFAULT_NOTE_TEMPLATE_NAME
        search_dirs: list[str] = []
        msg_path = Path(template_path) if template_path else None
        if msg_path and msg_path.is_file():
            search_dirs.append(str(msg_path.parent))
            self._template_name = msg_path.name
        note_path = Path(note_template_path) if note_template_path else None
        if note_path and note_path.is_file():
            search_dirs.append(str(note_path.parent))
            self._note_template_name = note_path.name
        if search_dirs:
            loaders.insert(0, FileSystemLoader(search_dirs))
        self._env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(enabled_extensions=(), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, context: dict[str, Any]) -> str:
        """Render the full outreach message (typed into the LinkedIn compose box)."""
        return self._render(self._template_name, context)

    def render_note(self, context: dict[str, Any], *, limit: int = NOTE_CHAR_LIMIT) -> str:
        """Render the short connection-invite note, guaranteed ``<= limit`` chars.

        LinkedIn caps invitation notes at 300 characters, so this keeps the intro
        and the reason for reaching out intact while trimming the least essential
        parts to fit: first the tech-stack list (shortening it keyword by keyword),
        then the portfolio link, and only as a last resort a word-boundary
        truncation with an ellipsis.
        """
        tech = [str(t) for t in (context.get("tech_stack") or []) if t]
        for keep in range(len(tech), -1, -1):
            note = self._render(self._note_template_name, {**context, "tech_stack": tech[:keep]})
            if len(note) <= limit:
                return note
        # Even with no tech the note is too long (very long role/company): drop the
        # portfolio link, then hard-truncate as the final guarantee.
        note = self._render(
            self._note_template_name, {**context, "tech_stack": [], "portfolio_url": ""}
        )
        return _truncate_note(note, limit)

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render *template_name* with *context* and tidy blank lines."""
        tpl = self._env.get_template(template_name)
        text = tpl.render(**context)
        # Collapse the runs of blank lines the conditional blocks can leave behind.
        lines = [ln.rstrip() for ln in text.splitlines()]
        cleaned: list[str] = []
        for line in lines:
            if not line and cleaned and not cleaned[-1]:
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()
