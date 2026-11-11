"""Tests for the free connection-note microservice (``linkedin_easy_apply.connect``).

Coverage:

* :class:`ProfileConnector` decision flow, driven through a tiny fake of the
  Playwright locator API (mirrors ``tests/automation/test_outreach.py``) - covers sending,
  dry-run, already-connected, the "More" menu fallback, a missing note field, the
  weekly-limit modal and note trimming.
* :class:`ConnectionInviteService` orchestration against a real temp DB with a
  scripted fake connector + fake browser - covers marking sent, de-dup across
  jobs, stopping on the weekly limit, and dry-run leaving the DB untouched.
* The ``pending_connection_invites`` query's filters, run scoping and cap.
* Real selectors against intercepted fictional pages in a fresh browser context;
  no live profiles, user browser state or external requests.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.connect.connector import ConnectOutcome, InviteTarget, ProfileConnector
from linkedin_easy_apply.connect.service import ConnectionInviteService
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.progress import ProgressReporter

# Map each selector list's FIRST candidate to a role so the fake can answer
# ``locator(selector)`` the way the real DOM would (the connector always matches
# on the first candidate before the overlapping fallbacks).
_ROLE_BY_SELECTOR = {
    selectors.PROFILE_PENDING[0]: "pending",
    selectors.PROFILE_CONNECT_BUTTON[0]: "connect",
    selectors.PROFILE_MORE_BUTTON[0]: "more",
    selectors.PROFILE_MORE_CONNECT[0]: "more_connect",
    selectors.INVITE_DIALOG[0]: "dialog",
    selectors.INVITE_DIALOG_HEADING[0]: "heading",
    selectors.INVITE_ADD_NOTE_BUTTON[0]: "add_note",
    selectors.INVITE_NOTE_TEXTAREA[0]: "textarea",
    selectors.INVITE_NOTE_DRAFT[0]: "textarea",
    selectors.INVITE_SEND_BUTTON[0]: "send",
    selectors.INVITE_SEND_WITHOUT_NOTE_BUTTON[0]: "send_without_note",
    selectors.INVITE_LIMIT_MODAL[0]: "limit",
    selectors.INVITE_DISMISS_BUTTON[0]: "dismiss",
    selectors.INVITE_SENT_CONFIRMATION[0]: "confirmation",
}


class _Loc:
    def __init__(self, page: _FakePage, role: str, present: bool) -> None:
        self._page = page
        self.role = role
        self._present = present

    def count(self) -> int:
        return 1 if self._present else 0

    @property
    def first(self) -> _Loc:
        return self

    def nth(self, index: int) -> _Loc:
        assert index == 0
        return self

    def is_visible(self) -> bool:
        return (
            self._present
            and self.role not in self._page.hidden
            and (self.role != "textarea" or self._page.note_revealed)
        )

    def is_enabled(self) -> bool:
        return self._present and self.role not in self._page.disabled

    def is_editable(self) -> bool:
        return self.is_enabled() and self.role not in self._page.readonly

    def get_attribute(self, name: str) -> str | None:
        return self._page.aria_labels.get(self.role) if name == "aria-label" else None

    def inner_text(self) -> str:
        if self.role == "more_connect":
            return self._page.more_connect_text
        if self.role == "send_without_note":
            return self._page.without_note_text
        if self.role == "send":
            return self._page.send_text
        if self.role == "add_note":
            return "Add a note"
        if self.role == "heading":
            return self._page.heading
        if self.role == "confirmation":
            return "Invitation sent"
        return ""

    def click(self) -> None:
        if (
            self.role in {"send", "send_without_note"} and self._page.fail_send
        ) or self.role in self._page.fail_click:
            raise RuntimeError("Fictional send failure")
        self._page.clicks.append(self.role)
        if self.role in {"connect", "more_connect"}:
            self._page.dialog_open = True
        if self.role == "add_note":
            self._page.note_revealed = True
        if self.role == "dismiss":
            self._page.dialog_open = False
        if self.role in {"send", "send_without_note"}:
            if self._page.limit_after_send:
                self._page.roles.add("limit")
            elif self._page.confirm_send:
                self._page.roles.add("pending")
                self._page.dialog_open = False

    def fill(self, text: str) -> None:
        if self._page.fail_fill:
            raise RuntimeError("Fictional note-fill failure")
        self._page.filled[self.role] = text

    def input_value(self) -> str:
        return self._page.filled.get(self.role, "")

    def locator(self, selector: str) -> _Loc:
        assert self.role == "dialog"
        return self._page.locator(selector)


class _FakePage:
    """A fake Playwright page whose element presence is set by role name."""

    def __init__(self, roles: set[str], *, more_connect_text: str = "Connect") -> None:
        self.roles = set(roles)
        self.more_connect_text = more_connect_text
        self.hidden: set[str] = set()
        self.disabled: set[str] = set()
        self.readonly: set[str] = set()
        self.aria_labels: dict[str, str] = {}
        self.heading = "Send an invitation"
        self.without_note_text = "Send without a note"
        self.send_text = "Send"
        self.dialog_open = False
        self.note_revealed = "add_note" not in roles
        self.fail_send = False
        self.fail_fill = False
        self.fail_click: set[str] = set()
        self.limit_after_send = False
        self.confirm_send = True
        self.clicks: list[str] = []
        self.filled: dict[str, str] = {}
        self.goto_url: str | None = None
        self.keyboard = SimpleNamespace(type=lambda text: self.filled.__setitem__("textarea", text))

    def goto(self, url: str) -> None:
        self.goto_url = url

    def wait_for_load_state(self, *args: Any, **kwargs: Any) -> None:
        pass

    def wait_for_timeout(self, *args: Any, **kwargs: Any) -> None:
        pass

    def locator(self, selector: str) -> _Loc:
        role = _ROLE_BY_SELECTOR.get(selector)
        present = self.dialog_open if role in {"dialog", "heading"} else role in self.roles
        return _Loc(self, role or "unknown", present)


def _target(note: str = "Hi Ria, I trust you are having an amazing day!") -> InviteTarget:
    return InviteTarget(
        id=1,
        person_name="Ria Talreja",
        profile_url="https://www.linkedin.com/in/ria/",
        note=note,
    )


# --------------------------------------------------------------------------- #
# ProfileConnector                                                            #
# --------------------------------------------------------------------------- #
def test_connector_sends_note_happy_path():
    page = _FakePage({"connect", "add_note", "textarea", "send"})
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.SENT
    assert page.goto_url == "https://www.linkedin.com/in/ria/"
    assert page.clicks == ["connect", "add_note", "textarea", "send"]
    assert page.filled["textarea"] == "Hi Ria, I trust you are having an amazing day!"


def test_connector_dry_run_types_note_but_never_sends():
    page = _FakePage({"connect", "add_note", "textarea", "send", "dismiss"})
    outcome = ProfileConnector(dry_run=True).send_invite(page, _target())
    assert outcome is ConnectOutcome.DRY_RUN
    assert "send" not in page.clicks
    assert page.filled["textarea"]  # the note was still typed
    assert "dismiss" in page.clicks  # backed out of the modal


def test_connector_skips_already_pending():
    page = _FakePage({"pending", "connect", "add_note", "textarea", "send"})
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.ALREADY
    assert page.clicks == []  # nothing was clicked


def test_connector_no_connect_button():
    page = _FakePage(set())
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.NO_BUTTON


def test_connector_connects_via_more_menu():
    page = _FakePage({"more", "more_connect", "add_note", "textarea", "send"})
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.SENT
    assert page.clicks[:2] == ["more", "more_connect"]
    assert "send" in page.clicks


def test_connector_more_menu_ignores_remove_connection():
    # An already-connected profile's "More" menu shows "Remove Connection", which
    # our :has-text('Connect') selector also matches. The connector must recognise
    # it is not a plain "Connect" and never click it (clicking would disconnect).
    page = _FakePage(
        {"more", "more_connect", "add_note", "textarea", "send"},
        more_connect_text="Remove Connection",
    )
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.NO_BUTTON
    assert "more_connect" not in page.clicks
    assert "send" not in page.clicks


def test_connector_note_field_unavailable():
    page = _FakePage({"connect", "dismiss"})  # Connect works, but no "Add a note"
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.NOTE_UNAVAILABLE
    assert "dismiss" in page.clicks
    assert "send" not in page.clicks


def _fictional_target() -> InviteTarget:
    return InviteTarget(
        id=1,
        person_name="Fictional Contact",
        profile_url="https://example.test/contact",
        note="A fictional connection note.",
    )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    "unavailable",
    [
        "missing_add_note",
        "hidden_add_note",
        "disabled_add_note",
        "missing_textarea",
        "hidden_textarea",
        "disabled_textarea",
    ],
)
def test_connector_plain_invite_requires_opt_in_and_unavailable_note(enabled, unavailable):
    page = _FakePage({"connect", "add_note", "textarea", "send", "send_without_note", "dismiss"})
    state, role = unavailable.split("_", 1)
    if state == "missing":
        page.roles.remove(role)
    elif state == "hidden":
        page.hidden.add(role)
    else:
        page.disabled.add(role)
    outcome = ProfileConnector(allow_without_note=enabled).send_invite(page, _fictional_target())
    assert outcome is (
        ConnectOutcome.SENT_WITHOUT_NOTE if enabled else ConnectOutcome.NOTE_UNAVAILABLE
    )
    assert ("send_without_note" in page.clicks) is enabled
    assert ("dismiss" in page.clicks) is not enabled
    assert "send" not in page.clicks
    assert not page.filled


def test_connector_enabled_fallback_still_prefers_the_note():
    page = _FakePage({"connect", "add_note", "textarea", "send", "send_without_note"})
    target = _fictional_target()
    outcome = ProfileConnector(allow_without_note=True).send_invite(page, target)
    assert outcome is ConnectOutcome.SENT
    assert page.filled["textarea"] == target.note
    assert "send" in page.clicks and "send_without_note" not in page.clicks


@pytest.mark.parametrize("role", ["add_note", "textarea", "send_without_note"])
@pytest.mark.parametrize("state", ["hidden", "disabled"])
def test_connector_ignores_unavailable_duplicate_controls(monkeypatch, role, state):
    roles = {"connect", "send", "send_without_note", "dismiss"}
    if role != "send_without_note":
        roles.update({"add_note", "textarea"})
    page = _FakePage(roles)
    getattr(page, state).add("shadow")
    controls = [_Loc(page, "shadow", True), _Loc(page, role, True)]

    class _Matches:
        def count(self) -> int:
            return len(controls)

        def nth(self, index: int) -> _Loc:
            return controls[index]

    original = page.locator
    monkeypatch.setattr(
        page,
        "locator",
        lambda selector: (
            _Matches() if _ROLE_BY_SELECTOR.get(selector) == role else original(selector)
        ),
    )
    outcome = ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
    assert outcome is (
        ConnectOutcome.SENT_WITHOUT_NOTE if role == "send_without_note" else ConnectOutcome.SENT
    )
    assert "shadow" not in page.clicks


def test_connector_plain_invite_dry_run_never_sends():
    page = _FakePage({"connect", "send_without_note", "dismiss"})
    outcome = ProfileConnector(dry_run=True, allow_without_note=True).send_invite(
        page, _fictional_target()
    )
    assert outcome is ConnectOutcome.DRY_RUN_WITHOUT_NOTE
    assert page.clicks == ["connect", "dismiss"]
    assert not page.filled


@pytest.mark.parametrize("unavailable", ["missing", "hidden", "disabled", "misleading", "error"])
def test_connector_plain_invite_does_not_use_an_unavailable_or_ambiguous_button(unavailable):
    page = _FakePage({"connect", "send", "send_without_note", "dismiss"})
    page.send_text = "Send message"
    if unavailable == "missing":
        page.roles.remove("send_without_note")
    elif unavailable == "hidden":
        page.hidden.add("send_without_note")
    elif unavailable == "disabled":
        page.disabled.add("send_without_note")
    elif unavailable == "misleading":
        page.without_note_text = "Do not send without a note"
    else:
        page.fail_send = True
    outcome = ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
    assert outcome is ConnectOutcome.FAILED
    assert "send" not in page.clicks and "send_without_note" not in page.clicks
    assert "dismiss" in page.clicks


@pytest.mark.parametrize("after_send", [False, True])
def test_connector_plain_invite_stops_at_weekly_limit(after_send):
    page = _FakePage({"connect", "send_without_note", "dismiss"})
    page.limit_after_send = after_send
    if not after_send:
        page.roles.add("limit")
    outcome = ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
    assert outcome is ConnectOutcome.LIMIT_REACHED
    assert ("send_without_note" in page.clicks) is after_send


def test_connector_note_send_errors_do_not_downgrade_to_plain_invites():
    page = _FakePage({"connect", "add_note", "textarea", "send", "send_without_note", "dismiss"})
    page.fail_send = True
    outcome = ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
    assert outcome is ConnectOutcome.FAILED
    assert "send_without_note" not in page.clicks


def test_connector_stops_on_weekly_limit_modal():
    page = _FakePage({"connect", "limit"})
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.LIMIT_REACHED


def test_connector_trims_note_to_300_chars():
    page = _FakePage({"connect", "add_note", "textarea", "send"})
    outcome = ProfileConnector().send_invite(page, _target(note="x" * 350))
    assert outcome is ConnectOutcome.SENT
    assert len(page.filled["textarea"]) == 300


@pytest.mark.parametrize("label", ["Send without a note", "SEND\n without   note"])
def test_connector_uses_clear_visible_action_despite_generic_aria(label):
    page = _FakePage({"connect", "send_without_note"})
    page.without_note_text = label
    page.aria_labels["send_without_note"] = "Send now"
    assert (
        ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
        is ConnectOutcome.SENT_WITHOUT_NOTE
    )


def test_connector_uses_already_open_note_without_add_note_button():
    page = _FakePage({"connect", "textarea", "send", "send_without_note"})
    target = _fictional_target()
    assert (
        ProfileConnector(allow_without_note=True).send_invite(page, target) is ConnectOutcome.SENT
    )
    assert page.filled["textarea"] == target.note
    assert page.clicks == ["connect", "textarea", "send"]


def test_connector_dry_run_leaves_a_matching_existing_draft_untouched():
    page = _FakePage({"connect", "textarea", "send", "dismiss"})
    target = _fictional_target()
    page.filled["textarea"] = target.note
    page.fail_fill = True
    assert ProfileConnector(dry_run=True).send_invite(page, target) is ConnectOutcome.DRY_RUN
    assert page.filled["textarea"] == target.note
    assert page.clicks == ["connect"]


@pytest.mark.parametrize("state", ["editable", "hidden", "disabled", "readonly"])
def test_connector_preserves_existing_note_draft_instead_of_plain_fallback(state):
    page = _FakePage({"connect", "textarea", "send", "send_without_note", "dismiss"})
    page.filled["textarea"] = "An existing fictional draft."
    if state != "editable":
        getattr(page, state).add("textarea")
    assert (
        ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
        is ConnectOutcome.FAILED
    )
    assert page.filled["textarea"] == "An existing fictional draft."
    assert not {"send", "send_without_note", "dismiss"}.intersection(page.clicks)


@pytest.mark.parametrize("stale_confirmation", [False, True])
@pytest.mark.parametrize("without_note", [False, True])
def test_connector_requires_fresh_delivery_evidence(without_note, stale_confirmation):
    roles = {"connect", "send_without_note"} if without_note else {"connect", "textarea", "send"}
    page = _FakePage(roles)
    page.confirm_send = False
    if stale_confirmation:
        page.roles.add("confirmation")
    assert (
        ProfileConnector(allow_without_note=without_note).send_invite(page, _fictional_target())
        is ConnectOutcome.FAILED
    )
    final = "send_without_note" if without_note else "send"
    assert page.clicks.count(final) == 1


def test_connector_fill_error_does_not_send_or_downgrade():
    page = _FakePage({"connect", "textarea", "send", "send_without_note"})
    page.fail_fill = True
    assert (
        ProfileConnector(allow_without_note=True).send_invite(page, _fictional_target())
        is ConnectOutcome.FAILED
    )
    assert not {"send", "send_without_note"}.intersection(page.clicks)


def test_connector_connect_click_error_returns_failure():
    page = _FakePage({"connect"})
    page.fail_click.add("connect")
    assert ProfileConnector().send_invite(page, _fictional_target()) is ConnectOutcome.FAILED


# Real selectors and dialog lifecycle: entirely fictional, intercepted HTTPS.
@pytest.fixture(scope="module")
def invitation_browser():
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        if Path(playwright.chromium.executable_path).is_file():
            browser = playwright.chromium.launch(headless=True)
        else:
            try:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            except Error as exc:
                if "is not found" not in str(exc) and "Executable doesn't exist" not in str(exc):
                    raise
                if os.environ.get("LEA_REQUIRE_INVITATION_BROWSER_TESTS") == "1":
                    pytest.fail("Invitation DOM checks require Chromium or installed Edge.")
                pytest.skip("Install Playwright Chromium or Edge to run invitation DOM checks.")
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def invitation_page(invitation_browser):
    context = invitation_browser.new_context()
    context.route("**/*", lambda route: route.abort())
    try:
        yield context.new_page()
    finally:
        context.close()


def _serve_invitation(page, dialog_html, *, delay_ms=0, note_delay_ms=0, confirmation="pending"):
    html = (
        """
        <main>
          <button aria-label="Invite Fictional Contact to connect" id="open">Connect</button>
          <button id="pending" hidden>Pending</button>
        </main>
        <section role="dialog" id="messages">
          <h2>Send a message</h2><textarea>Unrelated fictional message.</textarea>
          <button onclick="window.messageClicks++">Send</button>
          <button aria-label="Dismiss" onclick="window.messageDismissals++">Close</button>
        </section>
        """
        + dialog_html
        + """
        <script>
        window.finalClicks = 0;
        window.finalLabels = [];
        window.sentNote = null;
        window.dismissedNote = null;
        window.messageClicks = 0;
        window.messageDismissals = 0;
        const invite = document.getElementById('invite');
        document.getElementById('open').onclick = () => setTimeout(() => {
          invite.hidden = false;
          if (invite.tagName === 'DIALOG') invite.showModal();
        }, DELAY_MS);
        for (const button of invite.querySelectorAll('[data-add]')) {
          button.onclick = () => setTimeout(() => {
            const box = invite.querySelector('textarea');
            box.hidden = false;
            box.disabled = false;
          }, NOTE_DELAY_MS);
        }
        for (const button of invite.querySelectorAll('[data-final]')) {
          button.onclick = () => {
            window.finalClicks++;
            window.finalLabels.push(button.textContent.trim());
            window.sentNote = invite.querySelector('textarea')?.value ?? null;
            if ('CONFIRMATION' === 'pending') {
              setTimeout(() => {
                document.getElementById('pending').hidden = false;
                invite.remove();
              }, 30);
            } else if ('CONFIRMATION' === 'toast') {
              const status = document.createElement('div');
              status.role = 'status';
              status.textContent = 'Invitation sent';
              document.body.append(status);
              invite.remove();
            } else if ('CONFIRMATION' === 'close') {
              invite.remove();
            } else if ('CONFIRMATION' === 'limit') {
              invite.innerHTML = '<h2>You reached the weekly invitation limit</h2>';
            }
          };
        }
        for (const button of invite.querySelectorAll('[data-dismiss]')) {
          button.onclick = () => {
            window.dismissedNote = invite.querySelector('textarea')?.value ?? null;
            invite.remove();
          };
        }
        </script>
        """
    )
    html = (
        html.replace("NOTE_DELAY_MS", str(note_delay_ms))
        .replace("DELAY_MS", str(delay_ms))
        .replace("CONFIRMATION", confirmation)
    )
    page.route(
        "https://example.test/contact",
        lambda route: route.fulfill(body=html, content_type="text/html"),
    )


@pytest.mark.parametrize(
    "surface", ["section role='dialog'", "dialog", "section class='artdeco-modal'"]
)
@pytest.mark.parametrize("action", ["Send without a note", "Send without note", "Send", "Connect"])
def test_dom_plain_invite_layouts_and_visible_labels(invitation_page, surface, action):
    tag = surface.split()[0]
    _serve_invitation(
        invitation_page,
        f"""<{surface} id="invite" hidden>
        <h2>You can customize this invitation</h2>
        <button data-final aria-label="Send now">{action}</button></{tag}>""",
    )
    outcome = ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=250).send_invite(
        invitation_page, _fictional_target()
    )
    assert outcome is ConnectOutcome.SENT_WITHOUT_NOTE
    assert invitation_page.evaluate("window.finalClicks") == 1
    assert invitation_page.evaluate("window.messageClicks") == 0


def test_dom_identifies_invitation_from_dialog_accessible_name(invitation_page):
    _serve_invitation(
        invitation_page,
        """<section role="dialog" aria-label="Connect with Fictional Contact" id="invite" hidden>
        <button data-final>Send</button></section>""",
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=150).send_invite(
            invitation_page, _fictional_target()
        )
        is ConnectOutcome.SENT_WITHOUT_NOTE
    )
    assert invitation_page.evaluate("window.finalClicks") == 1
    assert invitation_page.evaluate("window.messageClicks") == 0


@pytest.mark.parametrize("dry_run", [False, True])
def test_dom_reuses_matching_draft_without_clearing_it_in_dry_run(invitation_page, dry_run):
    target = _fictional_target()
    _serve_invitation(
        invitation_page,
        f"""<section role="dialog" id="invite" hidden><h2>Send invitation</h2>
        <textarea name="message">{target.note}</textarea>
        <button data-final>Send</button><button data-dismiss aria-label="Dismiss">Close</button>
        </section>""",
    )
    assert ProfileConnector(dry_run=dry_run, settle_ms=0, modal_ms=150).send_invite(
        invitation_page, target
    ) is (ConnectOutcome.DRY_RUN if dry_run else ConnectOutcome.SENT)
    assert invitation_page.evaluate("window.finalClicks") == (0 if dry_run else 1)
    assert invitation_page.evaluate("window.dismissedNote") is None
    if dry_run:
        assert invitation_page.locator("#invite textarea").input_value() == target.note
    else:
        assert invitation_page.evaluate("window.sentNote") == target.note


@pytest.mark.parametrize("dry_run", [False, True])
def test_dom_waits_for_invitation_and_already_open_note(invitation_page, dry_run):
    _serve_invitation(
        invitation_page,
        """<dialog id="invite" hidden><h2>Send invitation</h2>
        <textarea name="message"></textarea>
        <button data-final>Send</button><button data-dismiss aria-label="Dismiss">Close</button>
        </dialog>""",
        delay_ms=160,
    )
    connector = ProfileConnector(
        dry_run=dry_run, allow_without_note=True, settle_ms=0, modal_ms=650
    )
    target = _fictional_target()
    assert connector.send_invite(invitation_page, target) is (
        ConnectOutcome.DRY_RUN if dry_run else ConnectOutcome.SENT
    )
    assert invitation_page.evaluate("window.finalClicks") == (0 if dry_run else 1)
    assert (
        invitation_page.evaluate("window.dismissedNote" if dry_run else "window.sentNote")
        == target.note
    )
    assert invitation_page.evaluate("window.messageClicks") == 0
    assert invitation_page.evaluate("window.messageDismissals") == 0
    assert (
        invitation_page.locator("#messages textarea").input_value()
        == "Unrelated fictional message."
    )


def test_dom_waits_for_note_after_add_instead_of_sending_plain(invitation_page):
    _serve_invitation(
        invitation_page,
        """<section role="dialog" id="invite" hidden><h2>Send an invitation</h2>
        <button data-add>Add a note</button><textarea name="message" hidden disabled></textarea>
        <button data-final>Send</button><button data-final>Send without a note</button></section>""",
        note_delay_ms=180,
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=650).send_invite(
            invitation_page, _fictional_target()
        )
        is ConnectOutcome.SENT
    )
    assert invitation_page.evaluate("window.finalClicks") == 1
    assert invitation_page.evaluate("window.finalLabels") == ["Send"]
    assert invitation_page.evaluate("window.sentNote") == _fictional_target().note


@pytest.mark.parametrize("enabled,dry_run", [(False, False), (True, True)])
def test_dom_plain_invite_opt_in_and_dry_run_never_send(invitation_page, enabled, dry_run):
    _serve_invitation(
        invitation_page,
        """<dialog id="invite" hidden><h2>Send invitation</h2>
        <button data-final>Send</button><button data-dismiss aria-label="Dismiss">Close</button>
        </dialog>""",
    )
    assert ProfileConnector(
        allow_without_note=enabled, dry_run=dry_run, settle_ms=0, modal_ms=150
    ).send_invite(invitation_page, _fictional_target()) is (
        ConnectOutcome.DRY_RUN_WITHOUT_NOTE if enabled else ConnectOutcome.NOTE_UNAVAILABLE
    )
    assert invitation_page.evaluate("window.finalClicks") == 0
    assert invitation_page.evaluate("window.messageDismissals") == 0


def test_dom_rejects_unrelated_or_misleading_send_actions(invitation_page):
    _serve_invitation(
        invitation_page,
        """<section role="dialog" id="invite" hidden><h2>Send a message</h2>
        <button data-final aria-label="Send without a note">Do not send without a note</button>
        <button data-final>Send</button></section>""",
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=150).send_invite(
            invitation_page, _fictional_target()
        )
        is ConnectOutcome.FAILED
    )
    assert invitation_page.evaluate("window.finalClicks") == 0
    assert invitation_page.evaluate("window.messageClicks") == 0


def test_dom_ignores_hidden_and_disabled_duplicate_actions(invitation_page):
    _serve_invitation(
        invitation_page,
        """<section role="dialog" id="invite" hidden><h2>Send invitation</h2>
        <button data-final hidden>Send without a note</button>
        <button data-final disabled>Send without a note</button>
        <button data-final>Send without a note</button></section>""",
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=200).send_invite(
            invitation_page, _fictional_target()
        )
        is ConnectOutcome.SENT_WITHOUT_NOTE
    )
    assert invitation_page.evaluate("window.finalClicks") == 1


@pytest.mark.parametrize("readonly", [False, True])
def test_dom_preserves_existing_draft_without_dismissing(invitation_page, readonly):
    attribute = "readonly" if readonly else ""
    _serve_invitation(
        invitation_page,
        f"""<section role="dialog" id="invite" hidden><h2>Send invitation</h2>
        <textarea name="message" {attribute}>An existing fictional draft.</textarea>
        <button data-final>Send</button><button data-final>Send without a note</button>
        <button data-dismiss aria-label="Dismiss">Close</button></section>""",
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=150).send_invite(
            invitation_page, _fictional_target()
        )
        is ConnectOutcome.FAILED
    )
    assert (
        invitation_page.locator("#invite textarea").input_value() == "An existing fictional draft."
    )
    assert invitation_page.evaluate("window.finalClicks") == 0


@pytest.mark.parametrize(
    "confirmation,outcome",
    [
        ("pending", ConnectOutcome.SENT_WITHOUT_NOTE),
        ("toast", ConnectOutcome.SENT_WITHOUT_NOTE),
        ("none", ConnectOutcome.FAILED),
        ("close", ConnectOutcome.FAILED),
        ("limit", ConnectOutcome.LIMIT_REACHED),
    ],
)
def test_dom_requires_delivery_confirmation_and_prioritizes_limits(
    invitation_page, confirmation, outcome
):
    _serve_invitation(
        invitation_page,
        """<section role="dialog" id="invite" hidden><h2>Send invitation</h2>
        <button data-final>Send without a note</button></section>""",
        confirmation=confirmation,
    )
    assert (
        ProfileConnector(allow_without_note=True, settle_ms=0, modal_ms=200).send_invite(
            invitation_page, _fictional_target()
        )
        is outcome
    )
    assert invitation_page.evaluate("window.finalClicks") == 1


# --------------------------------------------------------------------------- #
# service harness                                                             #
# --------------------------------------------------------------------------- #
class _FakeBrowser:
    def __init__(self) -> None:
        self.page = SimpleNamespace()

    def __enter__(self) -> _FakeBrowser:
        return self

    def __exit__(self, *args: Any) -> bool:
        return False


class _ScriptConnector:
    """A fake connector that returns scripted outcomes and records targets seen."""

    def __init__(self, outcomes: list[ConnectOutcome]) -> None:
        self._outcomes = outcomes
        self._i = 0
        self.seen: list[InviteTarget] = []

    def send_invite(self, page: Any, target: InviteTarget) -> ConnectOutcome:
        self.seen.append(target)
        outcome = self._outcomes[self._i] if self._i < len(self._outcomes) else ConnectOutcome.SENT
        self._i += 1
        return outcome


def _service(
    db: Database,
    connector: _ScriptConnector,
    *,
    dry_run: bool = False,
    progress: ProgressReporter | None = None,
):
    return ConnectionInviteService(
        AppConfig(),
        db,
        dry_run=dry_run,
        connector=connector,  # type: ignore[arg-type]
        sleeper=lambda _seconds: None,
        browser_factory=lambda: _FakeBrowser(),
        progress=progress,
    )


def _seed(db: Database, rows: list[dict[str, Any]]) -> int:
    run = db.start_run("apply")
    for row in rows:
        db.record_outreach(
            person_key=row["key"],
            person_name=row.get("name"),
            profile_url=row.get("url"),
            message=row.get("message", "the long message"),
            note=row.get("note", "the short note"),
            status="drafted",
            run_id=run,
        )
    return run


# --------------------------------------------------------------------------- #
# ConnectionInviteService                                                     #
# --------------------------------------------------------------------------- #
def test_service_sends_and_marks_notes(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    run = _seed(
        db,
        [
            {"key": "a", "name": "A", "url": "https://www.linkedin.com/in/a/", "note": "hi A"},
            {"key": "b", "name": "B", "url": "https://www.linkedin.com/in/b/", "note": "hi B"},
        ],
    )
    connector = _ScriptConnector([ConnectOutcome.SENT, ConnectOutcome.SENT])
    summary = _service(db, connector).run(run)

    assert summary.total == 2
    assert summary.sent == 2
    assert len(connector.seen) == 2
    assert db.pending_connection_invites(run) == []  # both marked note-sent


def test_connection_activity_surrounds_browser_processing_and_actual_pacing(tmp_path):
    db = Database(tmp_path / "activity.db")
    db.initialize()
    run = _seed(
        db,
        [
            {"key": "a", "url": "https://example.test/a", "note": "Hello"},
            {"key": "b", "url": "https://example.test/b", "note": "Hello"},
        ],
    )
    events = []
    reporter = ProgressReporter(activity_sink=events.append)

    class ObservedBrowser(_FakeBrowser):
        def __enter__(self):
            assert events[-1].activity == "starting_browser"
            return self

    class ObservedConnector(_ScriptConnector):
        def send_invite(self, page, target):
            assert events[-1].activity == "connecting"
            return super().send_invite(page, target)

    def sleep(_seconds):
        assert events[-1].activity == "pausing"

    config = AppConfig()
    config.outreach.connect_min_delay_seconds = 0.01
    config.outreach.connect_max_delay_seconds = 0.01
    service = ConnectionInviteService(
        config,
        db,
        progress=reporter,
        browser_factory=ObservedBrowser,
        connector=ObservedConnector([ConnectOutcome.DRY_RUN, ConnectOutcome.DRY_RUN]),
        sleeper=sleep,
    )
    assert service.run(run).sent == 2
    assert [event.activity for event in events] == [
        "loading_connections",
        "starting_browser",
        "connecting",
        "pausing",
        "connecting",
    ]
    assert all(event.resume_name is None for event in events)


def test_service_dedups_same_person_and_marks_all_rows(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    url = "https://www.linkedin.com/in/ria/"
    run = _seed(
        db,
        [
            {"key": "ria-job1", "name": "Ria", "url": url, "note": "hi from job 1"},
            {"key": "ria-job2", "name": "Ria", "url": url + "?trk=x", "note": "hi from job 2"},
        ],
    )
    connector = _ScriptConnector([ConnectOutcome.SENT])
    summary = _service(db, connector).run(run)

    assert summary.total == 1  # one invite for the person
    assert len(connector.seen) == 1
    assert db.pending_connection_invites(run) == []  # BOTH rows marked, none left pending


def test_service_stops_on_weekly_limit(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    run = _seed(
        db,
        [
            {"key": "a", "url": "https://www.linkedin.com/in/a/", "note": "hi"},
            {"key": "b", "url": "https://www.linkedin.com/in/b/", "note": "hi"},
            {"key": "c", "url": "https://www.linkedin.com/in/c/", "note": "hi"},
        ],
    )
    connector = _ScriptConnector([ConnectOutcome.SENT, ConnectOutcome.LIMIT_REACHED])
    summary = _service(db, connector).run(run)

    assert summary.limit_reached is True
    assert summary.sent == 1
    assert len(connector.seen) == 2  # stopped right after the limit outcome
    # the third target was never attempted and remains pending
    assert len(db.pending_connection_invites(run)) == 2


def test_service_dry_run_leaves_db_untouched(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    run = _seed(db, [{"key": "a", "url": "https://www.linkedin.com/in/a/", "note": "hi"}])
    connector = _ScriptConnector([ConnectOutcome.DRY_RUN])
    summary = _service(db, connector, dry_run=True).run(run)

    assert summary.dry_run is True
    assert summary.sent == 1  # would-be sent
    assert len(db.pending_connection_invites(run)) == 1  # still pending - not marked


@pytest.mark.parametrize("dry_run", [False, True])
def test_service_plain_invite_dedup_persistence_and_live_metrics(tmp_path, dry_run):
    db = Database(tmp_path / "fictional.db")
    db.initialize()
    run = _seed(
        db,
        [
            {"key": "fictional-a", "url": "https://example.test/contact", "note": "Hello"},
            {"key": "fictional-b", "url": "https://example.test/contact/?trk=x", "note": "Hello"},
        ],
    )
    snapshots = []
    outcome = ConnectOutcome.DRY_RUN_WITHOUT_NOTE if dry_run else ConnectOutcome.SENT_WITHOUT_NOTE
    connector = _ScriptConnector([outcome])
    summary = _service(
        db, connector, dry_run=dry_run, progress=ProgressReporter(snapshots.append)
    ).run(run)
    assert summary.sent == summary.sent_without_note == 1
    assert len(connector.seen) == 1
    for row in db.outreach_drafts(run):
        assert bool(row["invitation_sent_at"]) is not dry_run
        assert row["note_sent_at"] is None
        assert row["note"] == "Hello"
        assert row["message"] == "the long message"
    assert len(db.pending_connection_invites(run)) == (2 if dry_run else 0)
    counts = snapshots[-1].counts
    assert counts["connect_processed"] == 1
    assert counts["connect_sent"] == (0 if dry_run else 1)
    assert counts["connect_dry_runs"] == (1 if dry_run else 0)
    assert counts["connect_skipped"] == counts["connect_failed"] == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_standalone_connect_wires_fallback_and_reports_actual_delivery(
    tmp_path, monkeypatch, enabled
):
    from io import StringIO

    from rich.console import Console

    from linkedin_easy_apply.cli import main

    db = Database(tmp_path / "fictional.db")
    db.initialize()
    run = _seed(
        db,
        [{"key": "fictional-contact", "url": "https://example.test/contact", "note": "Hello"}],
    )
    config = AppConfig()
    config.outreach.connect_without_note = enabled
    browser = _FakeBrowser()
    browser.page = _FakePage({"connect", "send_without_note", "dismiss"})
    output = StringIO()
    monkeypatch.setattr(main, "_load", lambda _path: config)
    monkeypatch.setattr(main, "_database", lambda _config: db)
    monkeypatch.setattr(main, "gui_progress", lambda: None)
    monkeypatch.setattr(main, "console", Console(file=output, width=100))
    monkeypatch.setattr(
        "linkedin_easy_apply.connect.service.BrowserManager", lambda _config: browser
    )
    main.connect(config=tmp_path / "unused.yaml", dry_run=False, limit=None, run_id=run, yes=True)
    [row] = db.outreach_drafts(run)
    assert bool(row["invitation_sent_at"]) is enabled
    assert row["note_sent_at"] is None
    assert ("send_without_note" in browser.page.clicks) is enabled
    assert "Connection invitations" in output.getvalue()
    assert "Without note" in output.getvalue()
    assert ("No-note fallback enabled" in output.getvalue()) is enabled


def test_service_no_pending_never_opens_browser(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()

    def _boom():  # pragma: no cover - must not be called
        raise AssertionError("browser must not be launched when nothing is pending")

    service = ConnectionInviteService(
        AppConfig(),
        db,
        connector=_ScriptConnector([]),  # type: ignore[arg-type]
        sleeper=lambda _s: None,
        browser_factory=_boom,
    )
    summary = service.run()
    assert summary.total == 0
    assert summary.sent == 0


@pytest.mark.parametrize("attached", [False, True])
def test_connection_progress_is_live_distinct_and_preserves_application_totals(tmp_path, attached):
    db = Database(tmp_path / "metrics.db")
    db.initialize()
    run = _seed(
        db,
        [
            {"key": str(index), "url": f"https://example.test/people/{index}", "note": "Hello"}
            for index in range(7)
        ],
    )
    snapshots = []
    reporter = ProgressReporter(snapshots.append)
    if attached:
        reporter.start("apply", target=5)
        reporter.increment({"applied": 2, "hr_drafted": 7})
    connector = _ScriptConnector(
        [
            ConnectOutcome.SENT,
            ConnectOutcome.DRY_RUN,
            ConnectOutcome.ALREADY,
            ConnectOutcome.NO_BUTTON,
            ConnectOutcome.FAILED,
            ConnectOutcome.LIMIT_REACHED,
        ]
    )
    summary = _service(db, connector, progress=reporter).run(run)
    assert [s.counts["connect_processed"] for s in snapshots if s.phase == "connecting"] == list(
        range(7)
    )
    counts = snapshots[-1].counts
    assert counts["connect_total"] == 7
    assert counts["connect_sent"] == counts["connect_dry_runs"] == 1
    assert counts["connect_already"] == counts["connect_skipped"] == counts["connect_failed"] == 1
    assert counts["applied"] == (2 if attached else 0)
    assert counts["hr_drafted"] == (7 if attached else 0)
    assert snapshots[-1].action == ("apply" if attached else "connect")
    assert snapshots[-1].target == (5 if attached else 7)
    assert summary.sent == 2 and summary.limit_reached
    assert len(db.pending_connection_invites(run)) == 6


# --------------------------------------------------------------------------- #
# pending_connection_invites query                                            #
# --------------------------------------------------------------------------- #
def test_pending_query_filters_scopes_and_caps(tmp_path):
    db = Database(tmp_path / "c.db")
    db.initialize()
    run1 = db.start_run("apply")
    run2 = db.start_run("apply")
    db.record_outreach(person_key="ok", profile_url="https://x/a", note="hi", run_id=run1)
    db.record_outreach(person_key="nonote", profile_url="https://x/b", note=None, run_id=run1)
    db.record_outreach(person_key="nourl", profile_url=None, note="hi", run_id=run1)
    db.record_outreach(person_key="blank", profile_url="https://x/c", note="   ", run_id=run1)
    db.record_outreach(person_key="other", profile_url="https://x/d", note="hi", run_id=run2)

    # Only rows with a note AND a profile URL AND note_sent_at IS NULL qualify.
    assert {r["profile_url"] for r in db.pending_connection_invites()} == {
        "https://x/a",
        "https://x/d",
    }
    # Scope to one run.
    assert {r["profile_url"] for r in db.pending_connection_invites(run1)} == {"https://x/a"}
    # Once marked sent, a row drops out.
    ids = [r["id"] for r in db.pending_connection_invites(run1)]
    db.mark_outreach_note_sent(ids)
    assert db.pending_connection_invites(run1) == []
    # Cap limits the number of rows returned.
    assert len(db.pending_connection_invites(limit=1)) == 1


# --------------------------------------------------------------------------- #
# Orchestrator end-of-run connect pass -> second summary table wiring          #
# --------------------------------------------------------------------------- #
def _orchestrator(tmp_path, *, send: bool):
    from linkedin_easy_apply.answers.store import AnswerStore
    from linkedin_easy_apply.orchestrator import Orchestrator

    config = AppConfig()
    config.database.path = tmp_path / "o.db"
    config.outreach.send_connection_notes = send
    db = Database(config.database.path)
    db.initialize()
    return Orchestrator(config, db, AnswerStore({}))


@pytest.mark.parametrize("without_note", [0, 1])
def test_apply_run_stores_connect_summary_for_second_table(tmp_path, monkeypatch, without_note):
    """The apply run must surface the full ConnectSummary so the CLI can print
    a second 'Connection invitations' table (not just the sent count)."""
    from linkedin_easy_apply.connect.service import ConnectSummary
    from linkedin_easy_apply.orchestrator import RunSummary

    result = ConnectSummary(
        total=3, sent=2, sent_without_note=without_note, skipped=1, dry_run=False
    )

    class _FakeService:
        def __init__(self, config: AppConfig, *args: Any, **kwargs: Any) -> None:
            assert config.outreach.connect_without_note

        def run(self, run_id: int | None = None, *, limit: int | None = None) -> ConnectSummary:
            return result

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.ConnectionInviteService", _FakeService)
    orch = _orchestrator(tmp_path, send=True)
    orch._config.outreach.connect_without_note = True
    summary = RunSummary(run_id=1, mode="apply")
    orch._maybe_send_connection_invites(1, summary)

    assert summary.connect_summary is result  # full tally reaches the CLI
    assert summary.connection_notes_sent == 2 - without_note


def test_apply_run_stores_zero_connect_summary(tmp_path, monkeypatch):
    """Even with nothing pending the summary is stored, so the table still
    renders '0 outreach' when the feature is enabled."""
    from linkedin_easy_apply.connect.service import ConnectSummary
    from linkedin_easy_apply.orchestrator import RunSummary

    class _FakeService:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, run_id: int | None = None, *, limit: int | None = None) -> ConnectSummary:
            return ConnectSummary(total=0, dry_run=False)

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.ConnectionInviteService", _FakeService)
    orch = _orchestrator(tmp_path, send=True)
    summary = RunSummary(run_id=1, mode="apply")
    orch._maybe_send_connection_invites(1, summary)

    assert summary.connect_summary is not None
    assert summary.connect_summary.total == 0


def test_apply_run_skips_connect_summary_when_disabled(tmp_path, monkeypatch):
    """With the feature off, no service is built and no table is printed."""
    from linkedin_easy_apply.orchestrator import RunSummary

    def _boom(*args: Any, **kwargs: Any) -> None:  # pragma: no cover - must not run
        raise AssertionError("connect service must not run when disabled")

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.ConnectionInviteService", _boom)
    orch = _orchestrator(tmp_path, send=False)
    summary = RunSummary(run_id=1, mode="apply")
    orch._maybe_send_connection_invites(1, summary)

    assert summary.connect_summary is None
