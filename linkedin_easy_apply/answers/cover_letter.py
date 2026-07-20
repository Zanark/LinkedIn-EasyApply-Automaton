"""Generate personalised cover letters from Jinja2 templates.

Works out-of-the-box with a built-in template and can also load templates from a
directory so users can supply their own. Rendered letters can be written to a
``.txt`` file (for reference / inline textareas) or a ``.pdf`` (the artefact
LinkedIn upload fields expect) for use by the Easy Apply workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
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

# Core PDF fonts (Helvetica) only support Latin-1. Map the punctuation Jinja/users
# most commonly introduce down to ASCII so PDF rendering never crashes on it.
_UNICODE_FALLBACKS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u2022": "-",
    "\u00a0": " ",
}


def _to_latin1(text: str) -> str:
    """Down-convert *text* to a Latin-1-safe string for the core PDF fonts."""
    for src, dst in _UNICODE_FALLBACKS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


@dataclass(frozen=True, slots=True)
class RenderedCoverLetter:
    """A rendered cover letter and the paths of its persisted artefacts."""

    text: str
    pdf_path: Path
    text_path: Path


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
        return self._write_text(text, context, output_dir)

    def render_pdf_to_file(
        self,
        context: dict[str, Any],
        output_dir: str | Path,
        template: str | None = None,
    ) -> Path:
        """Render and persist a ``.pdf`` cover letter; returns the file path."""
        text = self.render(context, template)
        return self._write_pdf(text, context, output_dir)

    def render_all(
        self,
        context: dict[str, Any],
        output_dir: str | Path,
        template: str | None = None,
    ) -> RenderedCoverLetter:
        """Render once and persist both a ``.pdf`` (for uploads) and ``.txt``.

        The text is also returned so callers can fill inline cover-letter
        textareas without re-reading a file.
        """
        text = self.render(context, template)
        pdf_path = self._write_pdf(text, context, output_dir)
        text_path = self._write_text(text, context, output_dir)
        return RenderedCoverLetter(text=text, pdf_path=pdf_path, text_path=text_path)

    def _write_text(self, text: str, context: dict[str, Any], output_dir: str | Path) -> Path:
        directory = ensure_dir(output_dir)
        target = directory / f"{self._stem(context)}.txt"
        target.write_text(text, encoding="utf-8")
        return target

    def _write_pdf(self, text: str, context: dict[str, Any], output_dir: str | Path) -> Path:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos

        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(20, 20, 20)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        for line in _to_latin1(text).split("\n"):
            if line.strip():
                pdf.multi_cell(0, 6, text=line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.ln(4)
        directory = ensure_dir(output_dir)
        target = directory / f"{self._stem(context)}.pdf"
        pdf.output(str(target))
        return target

    @staticmethod
    def _stem(context: dict[str, Any]) -> str:
        company = slugify(str(context.get("company", "company"))) or "company"
        return f"cover-{company}-{timestamp_slug()}"
