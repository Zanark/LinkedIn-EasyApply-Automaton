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
{% if tech_stack %}My background is a strong match, especially {{ tech_stack | join(', ') }}.{% endif %}
{% if years_experience %}With {{ years_experience }}+ years of experience, I'm {% else %}I'm {% endif %}confident I can add value to your team.

Would love to connect and share more about how I can help. Thank you for your time!

Best,
{{ candidate_name | default('') }}"""

_DEFAULT_TEMPLATE_NAME = "__default__"


class HiringTeamMessenger:
    """Render outreach messages from a template and a context dict."""

    def __init__(self, template_path: str | Path | None = None) -> None:
        loaders: list[BaseLoader] = [DictLoader({_DEFAULT_TEMPLATE_NAME: _DEFAULT_TEMPLATE})]
        self._template_name = _DEFAULT_TEMPLATE_NAME
        path = Path(template_path) if template_path else None
        if path and path.is_file():
            loaders.insert(0, FileSystemLoader(str(path.parent)))
            self._template_name = path.name
        self._env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(enabled_extensions=(), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, context: dict[str, Any]) -> str:
        """Render the outreach message with *context* and tidy blank lines."""
        tpl = self._env.get_template(self._template_name)
        text = tpl.render(**context)
        # Collapse the runs of blank lines the conditional blocks can leave behind.
        lines = [ln.rstrip() for ln in text.splitlines()]
        cleaned: list[str] = []
        for line in lines:
            if not line and cleaned and not cleaned[-1]:
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()
