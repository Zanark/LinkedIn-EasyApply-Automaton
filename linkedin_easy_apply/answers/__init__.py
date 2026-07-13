"""Answer store, resume selection and cover-letter generation."""

from __future__ import annotations

from linkedin_easy_apply.answers.cover_letter import CoverLetterGenerator
from linkedin_easy_apply.answers.resolver import AnswerResolution, AnswerResolver
from linkedin_easy_apply.answers.resume_selector import ResumeSelector
from linkedin_easy_apply.answers.store import AnswerStore

__all__ = [
    "AnswerStore",
    "AnswerResolver",
    "AnswerResolution",
    "ResumeSelector",
    "CoverLetterGenerator",
]
