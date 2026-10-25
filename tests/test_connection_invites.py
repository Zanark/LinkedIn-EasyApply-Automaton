"""Tests for the free connection-note microservice (``linkedin_easy_apply.connect``).

Two layers:

* :class:`ProfileConnector` decision flow, driven through a tiny fake of the
  Playwright locator API (mirrors ``tests/test_outreach.py``) - covers sending,
  dry-run, already-connected, the "More" menu fallback, a missing note field, the
  weekly-limit modal and note trimming.
* :class:`ConnectionInviteService` orchestration against a real temp DB with a
  scripted fake connector + fake browser - covers marking sent, de-dup across
  jobs, stopping on the weekly limit, and dry-run leaving the DB untouched.
* The ``pending_connection_invites`` query's filters, run scoping and cap.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.connect.connector import ConnectOutcome, InviteTarget, ProfileConnector
from linkedin_easy_apply.connect.service import ConnectionInviteService
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import selectors

# Map each selector list's FIRST candidate to a role so the fake can answer
# ``locator(selector)`` the way the real DOM would (the connector always matches
# on the first candidate before the overlapping fallbacks).
_ROLE_BY_SELECTOR = {
    selectors.PROFILE_PENDING[0]: "pending",
    selectors.PROFILE_CONNECT_BUTTON[0]: "connect",
    selectors.PROFILE_MORE_BUTTON[0]: "more",
    selectors.PROFILE_MORE_CONNECT[0]: "more_connect",
    selectors.INVITE_ADD_NOTE_BUTTON[0]: "add_note",
    selectors.INVITE_NOTE_TEXTAREA[0]: "textarea",
    selectors.INVITE_SEND_BUTTON[0]: "send",
    selectors.INVITE_LIMIT_MODAL[0]: "limit",
    selectors.INVITE_DISMISS_BUTTON[0]: "dismiss",
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

    def is_visible(self) -> bool:
        return self._present

    def inner_text(self) -> str:
        # Only the More-menu Connect entry is text-inspected by the connector's
        # "Remove Connection" guard; the scenario controls what that text is.
        if self.role == "more_connect":
            return self._page.more_connect_text
        return ""

    def click(self) -> None:
        self._page.clicks.append(self.role)

    def fill(self, text: str) -> None:
        self._page.filled[self.role] = text


class _FakePage:
    """A fake Playwright page whose element presence is set by role name."""

    def __init__(self, roles: set[str], *, more_connect_text: str = "Connect") -> None:
        self.roles = set(roles)
        self.more_connect_text = more_connect_text
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
        return _Loc(self, role or "unknown", bool(role) and role in self.roles)


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


def test_connector_stops_on_weekly_limit_modal():
    page = _FakePage({"connect", "limit"})
    outcome = ProfileConnector().send_invite(page, _target())
    assert outcome is ConnectOutcome.LIMIT_REACHED


def test_connector_trims_note_to_300_chars():
    page = _FakePage({"connect", "add_note", "textarea", "send"})
    outcome = ProfileConnector().send_invite(page, _target(note="x" * 350))
    assert outcome is ConnectOutcome.SENT
    assert len(page.filled["textarea"]) == 300


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


def _service(db: Database, connector: _ScriptConnector, *, dry_run: bool = False):
    return ConnectionInviteService(
        AppConfig(),
        db,
        dry_run=dry_run,
        connector=connector,  # type: ignore[arg-type]
        sleeper=lambda _seconds: None,
        browser_factory=lambda: _FakeBrowser(),
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


def test_apply_run_stores_connect_summary_for_second_table(tmp_path, monkeypatch):
    """The apply run must surface the full ConnectSummary so the CLI can print
    a second 'Connection notes' table (not just the sent count)."""
    from linkedin_easy_apply.connect.service import ConnectSummary
    from linkedin_easy_apply.orchestrator import RunSummary

    result = ConnectSummary(total=3, sent=2, already=0, skipped=1, failed=0, dry_run=False)

    class _FakeService:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, run_id: int | None = None, *, limit: int | None = None) -> ConnectSummary:
            return result

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.ConnectionInviteService", _FakeService)
    orch = _orchestrator(tmp_path, send=True)
    summary = RunSummary(run_id=1, mode="apply")
    orch._maybe_send_connection_invites(1, summary)

    assert summary.connect_summary is result  # full tally reaches the CLI
    assert summary.connection_notes_sent == 2  # back-compat scalar stays in sync


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
