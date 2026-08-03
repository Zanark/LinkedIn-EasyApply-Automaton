"""Tests for the hiring-team outreach feature.

Covers the message generator, the DB dedup/audit + draft-query methods, the
plain-text report renderer, and both outreach modes (default ``draft`` which
only collects contacts, and opt-in ``send`` which types + sends) driven through
a tiny fake of the Playwright locator API.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from linkedin_easy_apply.answers.hiring_message import HiringTeamMessenger
from linkedin_easy_apply.answers.hiring_report import render_outreach_report
from linkedin_easy_apply.config.models import OutreachConfig, OutreachMode
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.outreach import HiringTeamOutreach
from linkedin_easy_apply.orchestrator import Orchestrator

# Map each selector list's FIRST candidate to a role so the fake can answer
# ``locator(selector)`` the way the real DOM would (the code always matches on
# the first candidate before falling through to the overlapping ones).
_FIRST = {
    selectors.HIRING_TEAM_SECTION[0]: "section",
    selectors.HIRING_TEAM_CARD[0]: "cards",
    selectors.HIRING_TEAM_NAME[0]: "name",
    selectors.HIRING_TEAM_PROFILE_LINK[0]: "link",
    selectors.HIRING_TEAM_MESSAGE_BUTTON[0]: "button",
    selectors.MSG_COMPOSE_BOX[0]: "compose",
    selectors.MSG_SEND_BUTTON[0]: "send",
    selectors.MSG_OVERLAY_CLOSE[0]: "close",
    selectors.POST_APPLY_UPSELL_DISMISS[0]: "upsell",
}


class _Set:
    def __init__(self, nodes: list[Any]) -> None:
        self._nodes = nodes

    def count(self) -> int:
        return len(self._nodes)

    @property
    def first(self) -> Any:
        return self._nodes[0]

    def nth(self, index: int) -> Any:
        return self._nodes[index]


class _Node:
    def __init__(
        self,
        role: str,
        *,
        text: str = "",
        href: str | None = None,
        visible: bool = True,
        children: dict[str, list[Any]] | None = None,
    ) -> None:
        self.role = role
        self._text = text
        self._href = href
        self._visible = visible
        self.children = children or {}
        self.clicks = 0
        self.filled: str | None = None

    def locator(self, selector: str) -> _Set:
        return _Set(self.children.get(_FIRST.get(selector, ""), []))

    def inner_text(self) -> str:
        return self._text

    def is_visible(self) -> bool:
        return self._visible

    def get_attribute(self, name: str) -> str | None:
        return self._href if name == "href" else None

    def click(self) -> None:
        self.clicks += 1

    def fill(self, text: str) -> None:
        self.filled = text


class _Keyboard:
    def type(self, text: str) -> None:  # pragma: no cover - fallback path
        pass


class _Page:
    def __init__(self, section: _Node | None, overlay: bool = True, upsell: bool = False) -> None:
        self.section = section
        self.compose = _Node("compose") if overlay else None
        self.send = _Node("send") if overlay else None
        self.close = _Node("close") if overlay else None
        self.upsell = _Node("upsell") if upsell else None
        self.keyboard = _Keyboard()

    def locator(self, selector: str) -> _Set:
        role = _FIRST.get(selector, "")
        node = {
            "section": self.section,
            "compose": self.compose,
            "send": self.send,
            "close": self.close,
            "upsell": self.upsell,
        }.get(role)
        return _Set([node] if node is not None else [])

    def wait_for_timeout(self, _ms: int) -> None:
        pass


def _card(
    name: str,
    href: str | None = "https://www.linkedin.com/in/foo",
    button: bool = True,
    visible: bool = True,
) -> _Node:
    children: dict[str, list[Any]] = {"name": [_Node("name", text=name)]}
    if href:
        children["link"] = [_Node("link", href=href)]
    if button:
        children["button"] = [_Node("button", visible=visible)]
    return _Node("card", children=children)


def _page(cards: list[_Node], overlay: bool = True, upsell: bool = False) -> _Page:
    section = _Node("section", children={"cards": cards})
    return _Page(section, overlay=overlay, upsell=upsell)


def _outreach(
    on_approve=None,
    *,
    mode: str = "draft",
    has_messaged=lambda k: False,
    records=None,
    max_per_run=5,
    skip_if_messaged=True,
) -> HiringTeamOutreach:
    def _record(**kwargs: Any) -> None:
        if records is not None:
            records.append(kwargs)

    return HiringTeamOutreach(
        HiringTeamMessenger(),
        mode=mode,
        on_approve=on_approve,
        has_messaged=has_messaged,
        record=_record,
        max_per_run=max_per_run,
        skip_if_messaged=skip_if_messaged,
    )


_CTX = {
    "role": "Backend Engineer",
    "company": "Acme",
    "candidate_name": "Jane Doe",
    "tech_stack": ["Java"],
    "years_experience": 8,
}


# -- messenger ----------------------------------------------------------------


def test_message_render_personalises():
    msg = HiringTeamMessenger().render({**_CTX, "recruiter_first_name": "Mrunal"})
    assert msg.startswith("Hi Mrunal,")
    assert "Backend Engineer" in msg
    assert "Acme" in msg
    assert "Jane Doe" in msg
    assert "Java" in msg


def test_message_render_defaults_recruiter():
    msg = HiringTeamMessenger().render({"role": "SRE", "company": "Globex"})
    assert "Hi there," in msg
    assert "SRE" in msg


# -- connection note (<=300-char invite variant) ------------------------------


_NOTE_CTX = {**_CTX, "portfolio_url": "https://jane.dev"}


def test_note_render_within_limit_and_personalises():
    note = HiringTeamMessenger().render_note({**_NOTE_CTX, "recruiter_first_name": "Ria"})
    assert len(note) <= 300
    assert note.startswith("Hi Ria,")
    assert "Jane Doe" in note
    assert "Backend Engineer" in note
    assert "Acme" in note
    assert "https://jane.dev" in note  # portfolio included when it fits


def test_note_omits_portfolio_when_absent():
    note = HiringTeamMessenger().render_note({**_CTX, "recruiter_first_name": "Ria"})
    assert "Portfolio:" not in note
    assert len(note) <= 300


def test_note_trims_tech_stack_to_stay_within_limit():
    # A huge matched-keyword list would blow past 300; the note must still fit
    # while keeping the intro and reason for reaching out intact.
    ctx = {
        **_NOTE_CTX,
        "recruiter_first_name": "Ria",
        "tech_stack": [f"skill-number-{i}" for i in range(60)],
    }
    note = HiringTeamMessenger().render_note(ctx)
    assert len(note) <= 300
    assert note.startswith("Hi Ria,")
    assert "would love to connect" in note


def test_note_hard_truncates_when_even_intro_is_too_long():
    # Pathological: role/company alone exceed 300 -> guarantee still holds.
    ctx = {
        "recruiter_first_name": "Ria",
        "candidate_name": "Jane Doe",
        "role": "Principal " + "Very " * 80 + "Senior Engineer",
        "company": "A" * 200,
    }
    note = HiringTeamMessenger().render_note(ctx)
    assert len(note) <= 300
    assert note.endswith("…")


def test_note_respects_custom_limit():
    note = HiringTeamMessenger().render_note(
        {**_NOTE_CTX, "recruiter_first_name": "Ria"}, limit=120
    )
    assert len(note) <= 120


# -- DB dedup / audit / draft query -------------------------------------------


def test_db_records_and_dedups_outreach(tmp_path):
    db = Database(tmp_path / "t.db")
    db.initialize()
    assert db.has_messaged_person("in/mrunal") is False
    db.record_outreach(person_key="in/mrunal", person_name="Mrunal B.", status="sent")
    assert db.has_messaged_person("in/mrunal") is True
    # A different person is unaffected; a declined record does not count as messaged.
    assert db.has_messaged_person("in/other") is False
    db.record_outreach(person_key="in/declined", status="declined")
    assert db.has_messaged_person("in/declined") is False


def test_db_outreach_drafts_returns_only_drafted(tmp_path):
    db = Database(tmp_path / "t.db")
    db.initialize()
    r1 = db.start_run("apply", ["s"])
    r2 = db.start_run("apply", ["s"])
    db.record_outreach(
        person_key="in/a",
        person_name="Ada L.",
        profile_url="https://www.linkedin.com/in/a",
        message="Hi Ada",
        status="drafted",
        run_id=r1,
    )
    db.record_outreach(person_key="in/b", person_name="Bob", status="sent", run_id=r1)
    db.record_outreach(person_key="in/c", person_name="Cara", status="drafted", run_id=r2)

    run1 = db.outreach_drafts(r1)
    assert [d["person_name"] for d in run1] == ["Ada L."]
    assert run1[0]["profile_url"] == "https://www.linkedin.com/in/a"
    assert run1[0]["message"] == "Hi Ada"
    # No run filter -> every drafted row (not the sent one).
    assert {d["person_name"] for d in db.outreach_drafts()} == {"Ada L.", "Cara"}


def test_outreach_drafts_includes_submitted_resume(tmp_path):
    """The draft join surfaces the résumé submitted for that job (to attach)."""
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    job = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/9/", "title": "Backend Eng", "company": "Acme"},
        run,
    )
    resume = db.register_resume("FullStack", "generated/resume/FullStack.pdf")
    db.create_application(job, run, resume, "submitted")
    db.record_outreach(
        person_key="in/a",
        person_name="Ada",
        profile_url="https://www.linkedin.com/in/a",
        message="Hi Ada",
        status="drafted",
        run_id=run,
        job_id=job,
    )
    [draft] = db.outreach_drafts(run)
    assert draft["job_title"] == "Backend Eng"
    assert draft["job_company"] == "Acme"
    assert draft["resume_name"] == "FullStack"
    assert draft["resume_path"].endswith("FullStack.pdf")


def test_db_outreach_records_and_returns_note(tmp_path):
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    db.record_outreach(
        person_key="in/a",
        person_name="Ada",
        message="Full message",
        note="Short connection note",
        status="drafted",
        run_id=run,
    )
    [draft] = db.outreach_drafts(run)
    assert draft["message"] == "Full message"
    assert draft["note"] == "Short connection note"


def test_outreach_drafts_expose_id(tmp_path):
    """Each draft carries its row id so the dashboard can target it for removal."""
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    db.record_outreach(person_key="in/a", person_name="Ada", status="drafted", run_id=run)
    [draft] = db.outreach_drafts(run)
    assert isinstance(draft["id"], int)
    assert draft["id"] > 0


def test_delete_outreach_removes_row_and_all_related(tmp_path):
    """Marking an outreach completed deletes the whole row — message, note and all."""
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    db.record_outreach(
        person_key="in/a",
        person_name="Ada",
        message="Full message",
        note="Short note",
        status="drafted",
        run_id=run,
    )
    db.record_outreach(person_key="in/b", person_name="Bob", status="drafted", run_id=run)
    drafts = db.outreach_drafts(run)
    ada = next(d for d in drafts if d["person_name"] == "Ada")

    removed = db.delete_outreach([ada["id"]])
    assert removed == 1
    remaining = db.outreach_drafts(run)
    assert [d["person_name"] for d in remaining] == ["Bob"]
    # Nothing related to Ada survives (message + note gone with the row).
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outreach_messages").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM outreach_messages WHERE message='Full message'"
            ).fetchone()[0]
            == 0
        )


def test_delete_outreach_empty_is_noop(tmp_path):
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    db.record_outreach(person_key="in/a", person_name="Ada", status="drafted", run_id=run)
    assert db.delete_outreach([]) == 0
    assert len(db.outreach_drafts(run)) == 1


def test_delete_outreach_multiple_ids(tmp_path):
    db = Database(tmp_path / "t.db")
    db.initialize()
    run = db.start_run("apply", ["s"])
    for key in ("in/a", "in/b", "in/c"):
        db.record_outreach(person_key=key, person_name=key, status="drafted", run_id=run)
    ids = [d["id"] for d in db.outreach_drafts(run)]
    removed = db.delete_outreach(ids[:2])
    assert removed == 2
    assert [d["person_name"] for d in db.outreach_drafts(run)] == ["in/c"]


# -- draft mode (default) -----------------------------------------------------


def test_outreach_draft_collects_without_clicking():
    records: list[dict] = []
    flow = _outreach(records=records)
    page = _page([_card("Mrunal B.")], upsell=True)

    collected = flow.reach_out(page, _CTX, run_id=1, job_id=2)

    assert collected == 1
    rec = records[-1]
    assert rec["status"] == "drafted"
    assert rec["person_name"] == "Mrunal B."
    assert rec["profile_url"] == "https://www.linkedin.com/in/foo"
    assert rec["message"].startswith("Hi Mrunal,")
    # Nothing was clicked or typed - not even the upsell "Not now".
    assert page.compose is not None and page.compose.filled is None
    assert page.send is not None and page.send.clicks == 0
    assert page.upsell is not None and page.upsell.clicks == 0


def test_outreach_draft_records_connection_note():
    records: list[dict] = []
    flow = _outreach(records=records)
    page = _page([_card("Mrunal B.")])

    assert flow.reach_out(page, {**_CTX, "portfolio_url": "https://jane.dev"}) == 1
    rec = records[-1]
    assert rec["note"] and len(rec["note"]) <= 300
    assert rec["note"].startswith("Hi Mrunal,")
    assert rec["note"] != rec["message"]  # the note is the shorter invite variant


def test_outreach_draft_collects_inmail_only_card():
    # No free Message button, but we can still report the profile URL to message
    # by hand, so draft mode collects it (send mode would skip it).
    records: list[dict] = []
    flow = _outreach(records=records)
    page = _page([_card("No Button", button=False)])

    assert flow.reach_out(page, _CTX) == 1
    assert records[-1]["status"] == "drafted"
    assert records[-1]["person_name"] == "No Button"


def test_outreach_draft_dedups_same_person_across_cards():
    records: list[dict] = []
    flow = _outreach(records=records)
    page = _page(
        [
            _card("Dup Person", href="https://www.linkedin.com/in/dup"),
            _card("Dup Person", href="https://www.linkedin.com/in/dup"),
        ]
    )

    assert flow.reach_out(page, _CTX) == 1
    assert sum(1 for r in records if r["status"] == "drafted") == 1


def test_outreach_draft_skips_previously_messaged():
    records: list[dict] = []
    flow = _outreach(records=records, has_messaged=lambda k: True)
    page = _page([_card("Mrunal B.")])

    assert flow.reach_out(page, _CTX) == 0
    assert records == []


def test_outreach_draft_respects_per_run_cap():
    records: list[dict] = []
    flow = _outreach(records=records, max_per_run=1)
    page = _page(
        [
            _card("First", href="https://www.linkedin.com/in/first"),
            _card("Second", href="https://www.linkedin.com/in/second"),
        ]
    )

    assert flow.reach_out(page, _CTX) == 1
    assert sum(1 for r in records if r["status"] == "drafted") == 1


# -- send mode (opt-in) -------------------------------------------------------


def test_outreach_sends_when_approved():
    seen: list[str] = []

    def approve(_name: str, message: str) -> str:
        seen.append(message)
        return message

    records: list[dict] = []
    flow = _outreach(approve, mode="send", records=records)
    page = _page([_card("Mrunal B.")])

    sent = flow.reach_out(page, _CTX, run_id=1, job_id=2)

    assert sent == 1
    assert page.compose is not None and page.compose.filled == seen[0]
    assert page.send is not None and page.send.clicks == 1
    assert records[-1]["status"] == "sent"
    assert records[-1]["person_name"] == "Mrunal B."


def test_outreach_send_dismisses_post_apply_upsell():
    # The "Turn your resume into a profile" upsell modal overlays the page and
    # blocks the Message button; send mode must click its "Not now" and still send.
    flow = _outreach(lambda n, m: m, mode="send")
    page = _page([_card("Mrunal B.")], upsell=True)

    sent = flow.reach_out(page, _CTX)

    assert sent == 1
    assert page.upsell is not None and page.upsell.clicks >= 1  # "Not now" clicked
    assert page.send is not None and page.send.clicks == 1  # message still sent


def test_outreach_declined_is_not_sent():
    records: list[dict] = []
    flow = _outreach(lambda n, m: None, mode="send", records=records)
    page = _page([_card("Mrunal B.")])

    sent = flow.reach_out(page, _CTX)

    assert sent == 0
    assert page.compose is not None and page.compose.filled is None
    assert records[-1]["status"] == "declined"


def test_outreach_send_skips_already_messaged():
    approvals: list[str] = []
    flow = _outreach(
        lambda n, m: approvals.append(n) or m, mode="send", has_messaged=lambda k: True
    )
    page = _page([_card("Mrunal B.")])

    assert flow.reach_out(page, _CTX) == 0
    assert approvals == []  # never even drafted/approved


def test_outreach_send_skips_inmail_only_card():
    approvals: list[str] = []
    flow = _outreach(lambda n, m: approvals.append(n) or m, mode="send")
    page = _page([_card("No Button", button=False)])

    assert flow.reach_out(page, _CTX) == 0
    assert approvals == []


def test_outreach_send_respects_per_run_cap():
    records: list[dict] = []
    flow = _outreach(lambda n, m: m, mode="send", records=records, max_per_run=1)
    page = _page(
        [
            _card("First", href="https://www.linkedin.com/in/first"),
            _card("Second", href="https://www.linkedin.com/in/second"),
        ]
    )

    sent = flow.reach_out(page, _CTX)

    assert sent == 1
    assert sum(1 for r in records if r["status"] == "sent") == 1


def test_outreach_send_without_handler_degrades_to_draft():
    # Asking for send mode but wiring no approval handler must never click/send;
    # it collects a draft instead so the report is still produced.
    records: list[dict] = []
    flow = _outreach(None, mode="send", records=records)
    page = _page([_card("Mrunal B.")])

    assert flow.reach_out(page, _CTX) == 1
    assert records[-1]["status"] == "drafted"
    assert page.send is not None and page.send.clicks == 0


def test_outreach_no_section_returns_zero():
    flow = _outreach()
    assert flow.reach_out(_Page(section=None), _CTX) == 0


# -- report renderer ----------------------------------------------------------


def test_render_outreach_report_lists_contacts():
    drafts = [
        {
            "person_name": "Ada Lovelace",
            "profile_url": "https://www.linkedin.com/in/ada",
            "message": "Hi Ada,\nGreat to connect.",
            "job_title": "Backend Engineer",
            "job_company": "Acme",
            "resume_name": "Debashish_FullStack",
            "resume_path": "generated/resume/Debashish_FullStack.pdf",
        },
        {
            "person_name": "Bob",
            "profile_url": "",
            "message": "Hi Bob",
            "job_title": "",
            "job_company": "Globex",
        },
    ]
    text = render_outreach_report(drafts, run_id=42)

    assert "2 contact(s)" in text
    assert "Run #42" in text
    assert "Ada Lovelace" in text
    assert "https://www.linkedin.com/in/ada" in text
    assert "Backend Engineer @ Acme" in text
    assert "Great to connect." in text
    # The résumé that was submitted is named so the user knows what to attach.
    assert "Debashish_FullStack" in text
    assert "generated/resume/Debashish_FullStack.pdf" in text
    # A missing profile URL is called out rather than left blank.
    assert "(profile URL not found)" in text
    assert "Globex" in text


def test_render_outreach_report_empty():
    text = render_outreach_report([])
    assert "No hiring-team recruiters" in text
    assert "0 contact(s)" in text


def test_render_outreach_report_includes_connection_note():
    note = "Hi Ada, I'm Jane. I just applied for Backend Engineer at Acme—would love to connect."
    drafts = [
        {
            "person_name": "Ada Lovelace",
            "profile_url": "https://www.linkedin.com/in/ada",
            "message": "Hi Ada,\nGreat to connect.",
            "note": note,
            "job_title": "Backend Engineer",
            "job_company": "Acme",
        }
    ]
    text = render_outreach_report(drafts)
    assert "CONNECTION NOTE" in text
    assert "MESSAGE (send once connected):" in text
    assert note in text
    assert f"{len(note)}/300" in text  # char count surfaced so the 300 cap is visible


# -- orchestrator gating ------------------------------------------------------


def _orch_with(outreach_cfg: OutreachConfig) -> Orchestrator:
    orch = object.__new__(Orchestrator)
    orch._config = SimpleNamespace(outreach=outreach_cfg)
    orch._db = MagicMock()
    return orch


def test_make_outreach_builds_draft_without_handler():
    # Draft mode is the default and needs no approval handler, so it builds even
    # with no handler wired (runs under --yes).
    flow = _orch_with(OutreachConfig(enabled=True))._make_outreach(None, None)
    assert flow is not None
    assert flow._mode == "draft"


def test_make_outreach_disabled_returns_none():
    assert _orch_with(OutreachConfig(enabled=False))._make_outreach(None, None) is None


def test_make_outreach_flag_overrides_config_enabled():
    # The CLI passes the resolved --message-hiring-team flag; it wins over config.
    orch = _orch_with(OutreachConfig(enabled=False))
    assert orch._make_outreach(None, True) is not None
    assert orch._make_outreach(lambda n, m: m, False) is None


def test_make_outreach_send_mode_with_handler():
    orch = _orch_with(OutreachConfig(enabled=True, mode=OutreachMode.SEND))
    flow = orch._make_outreach(lambda n, m: m, None)
    assert flow is not None
    assert flow._mode == "send"


def test_make_outreach_send_mode_degrades_without_handler():
    orch = _orch_with(OutreachConfig(enabled=True, mode=OutreachMode.SEND))
    flow = orch._make_outreach(None, None)
    assert flow is not None
    assert flow._mode == "draft"  # degraded so the report still gets produced
