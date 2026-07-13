"""Generate personalised cover letters from Jinja2 templates.

Works out-of-the-box with a built-in template and can also load templates from a
directory so users can supply their own. Rendered letters can be written to a
file for upload by the Easy Apply workflow.
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

from linkedin_easy_apply.utils.paths import ensure_dir, timestamp_slug
from linkedin_easy_apply.utils.text import slugify

_DEFAULT_TEMPLATE = """Dear {{ hiring_manager | default('Hiring Manager') }},

I am excited to apply for the {{ role }} position at {{ company }}.
{% if tech_stack %}My background aligns closely with your stack, particularly {{ tech_stack | join(', ') }}.{% endif %}
{% if summary %}{{ summary }}{% endif %}

{% if years_experience %}With {{ years_experience }}+ years of professional experience, I {% else %}I {% endif %}am confident I can contribute quickly to your team and would welcome the opportunity to discuss how I can help {{ company }} succeed.

Thank you for your time and consideration.

Sincerely,
{{ candidate_name | default('') }}
"""

_DEFAULT_TEMPLATE_NAME = "__default__"


class CoverLetterGenerator:
    """Render cover letters from a template and a context dict."""

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        loaders: list[BaseLoader] = [DictLoader({_DEFAULT_TEMPLATE_NAME: _DEFAULT_TEMPLATE})]
        self._templates_dir = Path(templates_dir) if templates_dir else None
        if self._templates_dir and self._templates_dir.is_dir():
            loaders.insert(0, FileSystemLoader(str(self._templates_dir)))
        self._env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(enabled_extensions=(), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, context: dict[str, Any], template: str | None = None) -> str:
        """Render *template* (or the built-in default) with *context*."""
        name = template or _DEFAULT_TEMPLATE_NAME
        tpl = self._env.get_template(name)
        return tpl.render(**context).strip() + "\n"

    def render_to_file(
        self,
        context: dict[str, Any],
        output_dir: str | Path,
        template: str | None = None,
    ) -> Path:
        """Render and persist a ``.txt`` cover letter; returns the file path."""
        text = self.render(context, template)
        directory = ensure_dir(output_dir)
        company = slugify(str(context.get("company", "company"))) or "company"
        target = directory / f"cover-{company}-{timestamp_slug()}.txt"
        target.write_text(text, encoding="utf-8")
        return target
