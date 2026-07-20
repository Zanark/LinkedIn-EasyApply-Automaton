from __future__ import annotations

from linkedin_easy_apply.answers.cover_letter import CoverLetterGenerator


def _context() -> dict:
    return {
        "role": "Backend Engineer",
        "company": "Acme Corp",
        "candidate_name": "Jane Doe",
        "tech_stack": ["Java", "AWS"],
        "years_experience": 8,
        "summary": "I build reliable services.",
    }


def test_render_contains_key_fields():
    text = CoverLetterGenerator().render(_context())
    assert "Backend Engineer" in text
    assert "Acme Corp" in text
    assert "Jane Doe" in text
    assert "Java, AWS" in text
    assert "8+ years" in text


def test_render_defaults_when_optional_missing():
    text = CoverLetterGenerator().render({"role": "SRE", "company": "Globex"})
    assert "Hiring Manager" in text
    assert "SRE" in text


def test_render_to_file(tmp_path):
    path = CoverLetterGenerator().render_to_file(_context(), tmp_path)
    assert path.exists()
    assert path.suffix == ".txt"
    content = path.read_text(encoding="utf-8")
    assert "Acme Corp" in content


def test_render_pdf_to_file(tmp_path):
    path = CoverLetterGenerator().render_pdf_to_file(_context(), tmp_path)
    assert path.exists()
    assert path.suffix == ".pdf"
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_render_all_returns_text_and_both_artifacts(tmp_path):
    result = CoverLetterGenerator().render_all(_context(), tmp_path)
    assert result.pdf_path.suffix == ".pdf"
    assert result.text_path.suffix == ".txt"
    assert result.pdf_path.exists() and result.text_path.exists()
    assert result.pdf_path.read_bytes().startswith(b"%PDF")
    # The returned text matches the persisted .txt and drives inline textareas.
    assert result.text == result.text_path.read_text(encoding="utf-8")
    assert "Acme Corp" in result.text


def test_render_pdf_tolerates_unicode(tmp_path):
    # Smart punctuation / non-Latin-1 glyphs must not crash the core-font PDF.
    ctx = {
        "role": "SRE",
        "company": "Globex \u2014 India",
        "candidate_name": "Jos\u00e9 \u201cAce\u201d",
        "summary": "99.9% uptime \u2013 always.",
    }
    path = CoverLetterGenerator().render_pdf_to_file(ctx, tmp_path)
    assert path.read_bytes().startswith(b"%PDF")


# -- inline cover-letter textarea auto-fill -------------------------------------


class _FakeFiller:
    def __init__(self):
        self.filled = None

    def matches_current(self, field_, resolution, current):
        return False

    def fill(self, field_, resolution, file_path=None):
        self.filled = resolution
        return True


def _cover_workflow(filler):
    from unittest.mock import MagicMock

    from linkedin_easy_apply.forms.easy_apply import EasyApplyWorkflow
    from linkedin_easy_apply.parser.question_parser import QuestionParser

    wf = object.__new__(EasyApplyWorkflow)
    wf._parser = QuestionParser()
    wf._filler = filler
    wf._resolver = MagicMock()
    wf._answer_lookup = None
    wf._record = MagicMock()
    wf._fill_file_field = MagicMock()
    return wf


def test_cover_textarea_filled_from_generated_text():
    from linkedin_easy_apply.forms.field import FieldKind, FormField

    filler = _FakeFiller()
    wf = _cover_workflow(filler)
    field_ = FormField(label="Cover letter", kind=FieldKind.TEXTAREA)

    wf._fill_field(field_, [], None, None, "Dear Hiring Manager, ...")

    assert filler.filled is not None
    assert filler.filled.value == "Dear Hiring Manager, ..."
    assert filler.filled.source == "cover_letter"
    # The generic resolver must be bypassed for the inline cover-letter path.
    wf._resolver.resolve.assert_not_called()


def test_cover_file_field_routes_to_upload_not_textarea():
    from linkedin_easy_apply.forms.field import FieldKind, FormField

    filler = _FakeFiller()
    wf = _cover_workflow(filler)
    field_ = FormField(label="Cover letter", kind=FieldKind.FILE)

    wf._fill_field(field_, [], None, "cover.pdf", "Dear Hiring Manager, ...")

    wf._fill_file_field.assert_called_once()
    assert filler.filled is None  # never filled as a textarea
