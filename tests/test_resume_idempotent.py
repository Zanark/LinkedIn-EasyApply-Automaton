"""Resume selection must happen once per application, not on every step.

Later steps (notably the read-only review step) re-render the resume as a
summary card with no upload control. Re-running selection there mis-detects the
card and spuriously tries to "upload" again, emitting a scary "Could not upload"
warning even though the resume was already attached on the resume step.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import linkedin_easy_apply.forms.easy_apply as ea
from linkedin_easy_apply.forms.easy_apply import EasyApplyWorkflow
from linkedin_easy_apply.forms.field import FieldKind, FormField

_RESUME = "generated/resume/Example_backend.pdf"


def _workflow() -> EasyApplyWorkflow:
    wf = object.__new__(EasyApplyWorkflow)
    wf._page = MagicMock()
    wf._resume_selected_done = False
    return wf


def test_resume_selected_once_then_skipped():
    wf = _workflow()
    container = MagicMock()
    wf._resume_cards = MagicMock(return_value=[("Example_backend.pdf", container)])
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
    wf._resume_cards = MagicMock(return_value=[("Example_backend.pdf", MagicMock())])
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True

    # Step 4: a non-matching summary card would normally trigger an upload; the
    # idempotency guard returns True before _resume_cards is even consulted.
    wf._resume_cards = MagicMock(return_value=[("Example_FullStack.pdf", MagicMock())])
    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True
    wf._resume_cards.assert_not_called()
    wf._upload_via_file_chooser.assert_not_called()
    wf._ask_manual_upload.assert_not_called()


def test_no_resume_path_is_noop():
    wf = _workflow()
    assert wf._ensure_resume_selected(MagicMock(), None) is False
    assert wf._resume_selected_done is False


def test_contact_page_does_not_use_a_hidden_page_wide_upload(monkeypatch):
    wf = _workflow()
    wf._resume_cards = MagicMock(return_value=[])
    wf._upload_via_file_chooser = MagicMock()
    upload = MagicMock()
    modal = MagicMock()
    monkeypatch.setattr(ea, "first", lambda scope, selectors: upload if scope is wf._page else None)

    assert wf._ensure_resume_selected(modal, _RESUME) is False
    upload.set_input_files.assert_not_called()
    wf._upload_via_file_chooser.assert_not_called()
    assert wf._resume_selected_done is False


def test_uploaded_radio_is_discovered_without_legacy_classes():
    wf = _workflow()
    radio = MagicMock()
    radio.get_attribute.return_value = "Example_backend.pdf"
    modal = MagicMock()
    modal.get_by_role.return_value.count.return_value = 1
    modal.get_by_role.return_value.nth.return_value = radio

    assert wf._resume_cards(modal) == [("Example_backend.pdf", radio)]


def test_existing_resume_is_selected_and_verified_without_upload():
    wf = _workflow()
    radio = MagicMock()
    radio.evaluate_handle.return_value.as_element.return_value = None
    radio.is_checked.side_effect = [False, True]
    wf._resume_cards = MagicMock(return_value=[("Example_backend.pdf", radio)])
    wf._upload_via_file_chooser = MagicMock()

    assert wf._ensure_resume_selected(MagicMock(), _RESUME) is True
    radio.check.assert_called_once()
    wf._upload_via_file_chooser.assert_not_called()


def test_hidden_resume_radio_is_selected_through_its_associated_label():
    wf = _workflow()
    checked = {"value": False}
    radio = MagicMock()
    radio.is_checked.side_effect = lambda: checked["value"]
    radio.check.side_effect = RuntimeError("Radio input is hidden")
    radio.click.side_effect = RuntimeError("Radio input is hidden")
    radio.locator.return_value.count.return_value = 0
    label = radio.evaluate_handle.return_value.as_element.return_value
    label.click.side_effect = lambda **kwargs: checked.update(value=True)
    wf._resume_cards = MagicMock(return_value=[("Example_backend.pdf", radio)])
    wf._upload_via_file_chooser = MagicMock()

    assert wf._ensure_resume_selected(MagicMock(), _RESUME)
    label.click.assert_called_once()
    assert radio.is_checked()
    wf._upload_via_file_chooser.assert_not_called()


def test_selection_is_verified_after_the_picker_remounts_its_controls():
    wf = _workflow()
    before = MagicMock()
    before.is_checked.return_value = False
    before.locator.return_value.count.return_value = 0
    after = MagicMock()
    after.is_checked.return_value = True
    wf._resume_cards = MagicMock(
        side_effect=[
            [("Example_backend.pdf", before)],
            [("Example_backend.pdf", after)],
        ]
    )
    wf._upload_via_file_chooser = MagicMock()

    assert wf._ensure_resume_selected(MagicMock(), _RESUME)
    after.is_checked.assert_called_once()
    wf._upload_via_file_chooser.assert_not_called()


def test_failed_existing_selection_does_not_upload_a_duplicate():
    wf = _workflow()
    radio = MagicMock()
    wf._resume_cards = MagicMock(return_value=[("Example_backend.pdf", radio)])
    wf._card_selected = MagicMock(return_value=False)
    wf._select_card = MagicMock(return_value=False)
    wf._upload_via_file_chooser = MagicMock()

    with pytest.raises(RuntimeError, match="already-uploaded"):
        wf._ensure_resume_selected(MagicMock(), _RESUME)
    assert wf._resume_selected_done is False
    wf._upload_via_file_chooser.assert_not_called()


def test_missing_resume_uploads_once_then_confirms_selection(monkeypatch):
    wf = _workflow()
    modal = MagicMock()
    upload = MagicMock()
    button = MagicMock()
    card = MagicMock()
    wf._resume_cards = MagicMock(side_effect=[[], [("Example_backend.pdf", card)]])
    wf._card_selected = MagicMock(return_value=True)
    monkeypatch.setattr(
        ea,
        "first",
        lambda scope, selectors: (
            button if selectors is ea.selectors.RESUME_UPLOAD_BUTTON else upload
        ),
    )

    assert wf._ensure_resume_selected(modal, _RESUME) is True
    upload.set_input_files.assert_called_once_with(_RESUME)
    assert wf._resume_selected_done is True


def test_generic_filler_does_not_change_the_verified_resume_picker():
    wf = _workflow()
    wf._parser = MagicMock()
    field = FormField(
        "Resume",
        FieldKind.RADIO,
        options=["Example_backend.pdf", "Example_ai.pdf"],
    )
    wf._fill_field(field, [], _RESUME, None, resume_handled=True)
    wf._parser.parse.assert_not_called()
