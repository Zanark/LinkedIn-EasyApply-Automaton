"""Resume selection must happen once per application, not on every step.

Later steps (notably the read-only review step) re-render the resume as a
summary card with no upload control. Re-running selection there mis-detects the
card and spuriously tries to "upload" again, emitting a scary "Could not upload"
warning even though the resume was already attached on the resume step.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from linkedin_easy_apply.forms.easy_apply import EasyApplyWorkflow

_RESUME = "generated/resume/Debashish_Mishra_backend.pdf"


def _workflow() -> EasyApplyWorkflow:
    wf = object.__new__(EasyApplyWorkflow)
    wf._page = MagicMock()
    wf._resume_selected_done = False
    return wf


def test_resume_selected_once_then_skipped():
    wf = _workflow()
    container = MagicMock()
    wf._resume_cards = MagicMock(return_value=[("Debashish_Mishra_backend.pdf", container)])
    wf._card_selected = MagicMock(return_value=True)
    wf._select_card = MagicMock()
    wf._upload_via_file_chooser = MagicMock(return_value=False)
    wf._ask_manual_upload = MagicMock()

    # Step 2 (resume step): finds and selects the card.
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True
    assert wf._resume_selected_done is True
    assert wf._resume_cards.call_count == 1

    # Step 4 (review step): skipped entirely - no re-detection, no upload attempt.
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True
    assert wf._resume_cards.call_count == 1  # not called again
    wf._upload_via_file_chooser.assert_not_called()
    wf._ask_manual_upload.assert_not_called()


def test_review_step_does_not_spuriously_upload():
    """The exact bug: step 2 selected the resume; step 4 shows a card whose name
    no longer matches, but selection is skipped so no bogus upload runs."""
    wf = _workflow()
    wf._card_selected = MagicMock(return_value=True)
    wf._select_card = MagicMock()
    wf._upload_via_file_chooser = MagicMock(return_value=False)
    wf._ask_manual_upload = MagicMock()

    # Step 2: matching card -> selected.
    wf._resume_cards = MagicMock(return_value=[("Debashish_Mishra_backend.pdf", MagicMock())])
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True

    # Step 4: a non-matching summary card would normally trigger an upload; the
    # idempotency guard returns True before _resume_cards is even consulted.
    wf._resume_cards = MagicMock(return_value=[("Debashish_Mishra_FullStack.pdf", MagicMock())])
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True
    wf._resume_cards.assert_not_called()
    wf._upload_via_file_chooser.assert_not_called()
    wf._ask_manual_upload.assert_not_called()


def test_no_resume_path_is_noop():
    wf = _workflow()
    assert wf._ensure_resume_selected(MagicMock(), None) is False
    assert wf._resume_selected_done is False
