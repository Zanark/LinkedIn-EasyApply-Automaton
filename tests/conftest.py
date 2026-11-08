"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from linkedin_easy_apply.answers.store import AnswerStore


@pytest.fixture
def answers_data() -> dict:
    return {
        "full_name": "Jane Doe",
        "phone": "+91-9000000000",
        "email": "jane@example.com",
        "linkedin": "https://linkedin.com/in/jane",
        "github": "https://github.com/jane",
        "years_experience": 8,
        "expected_ctc": 5000000,
        "current_ctc": 3500000,
        "notice_period": "30 days",
        "city": "Bengaluru",
        "country": "India",
        "authorization": True,
        "visa": False,
        "relocation": True,
        "remote": True,
        "skills": {
            "Java": {"years": 6, "aliases": ["Core Java", "Java Programming"]},
            "Kubernetes": {"years": 4, "aliases": ["K8s"]},
            "Python": 5,
        },
        "aliases": {"mobile": "phone", "expected compensation": "expected_ctc"},
        "defaults": {"onsite": True},
    }


@pytest.fixture
def answers_store(answers_data: dict) -> AnswerStore:
    return AnswerStore(answers_data)


@pytest.fixture(scope="session")
def qt_app():
    """Keep one application alive until its native widgets have been destroyed."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
    application.closeAllWindows()
    for widget in application.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
