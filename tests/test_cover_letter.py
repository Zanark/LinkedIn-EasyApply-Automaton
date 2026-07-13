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
