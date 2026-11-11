from __future__ import annotations

from pathlib import Path

from linkedin_easy_apply.answers.resume_selector import ResumeSelector
from linkedin_easy_apply.config.models import ResumeConfig


def _make_resumes(directory: Path, names: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"%PDF-1.4 fake")


def test_available_resumes(tmp_path):
    _make_resumes(tmp_path, ["backend_java.pdf", "frontend_react.pdf", "notes.txt"])
    selector = ResumeSelector(ResumeConfig(directory=tmp_path))
    available = selector.available_resumes()
    assert set(available) == {"backend_java.pdf", "frontend_react.pdf"}  # .txt ignored


def test_mapping_match_wins(tmp_path):
    _make_resumes(tmp_path, ["backend_java.pdf", "general.pdf"])
    config = ResumeConfig(
        directory=tmp_path,
        default="general.pdf",
        mapping={"backend engineer": "backend_java.pdf"},
    )
    choice = ResumeSelector(config).select("Senior Backend Engineer", "Java microservices")
    assert choice is not None
    assert choice.name == "backend_java.pdf"


def test_falls_back_to_default(tmp_path):
    _make_resumes(tmp_path, ["backend_java.pdf", "general.pdf"])
    config = ResumeConfig(
        directory=tmp_path,
        default="general.pdf",
        mapping={"backend engineer": "backend_java.pdf"},
    )
    choice = ResumeSelector(config).select("Marketing Manager", "Brand strategy")
    assert choice is not None
    assert choice.name == "general.pdf"
    assert "default" in choice.reason


def test_keyword_overlap_selection(tmp_path):
    _make_resumes(tmp_path, ["python_backend.pdf", "react_frontend.pdf"])
    config = ResumeConfig(directory=tmp_path)  # no mapping, no default
    choice = ResumeSelector(config).select("Python Backend Developer")
    assert choice is not None
    assert choice.name == "python_backend.pdf"


def test_no_resume_available(tmp_path):
    selector = ResumeSelector(ResumeConfig(directory=tmp_path / "missing"))
    assert selector.select("Anything") is None
