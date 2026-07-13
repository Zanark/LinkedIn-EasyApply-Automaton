"""Dynamic form detection and the Easy Apply workflow engine."""

from __future__ import annotations

from linkedin_easy_apply.forms.detector import FormFieldDetector
from linkedin_easy_apply.forms.easy_apply import (
    AnsweredQuestion,
    ApplyResult,
    ApplyStatus,
    EasyApplyWorkflow,
    WorkflowSettings,
)
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller

__all__ = [
    "FormFieldDetector",
    "FormFiller",
    "FormField",
    "FieldKind",
    "EasyApplyWorkflow",
    "WorkflowSettings",
    "ApplyResult",
    "ApplyStatus",
    "AnsweredQuestion",
]
