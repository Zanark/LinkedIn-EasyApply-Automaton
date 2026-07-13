"""Dynamic question recognition."""

from __future__ import annotations

from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import ParsedQuestion, QuestionParser

__all__ = ["QuestionParser", "ParsedQuestion", "QuestionCategory", "AnswerType"]
