"""Tests for the hiring-team outreach feature.

Covers the message generator, the DB dedup/audit methods, and the draft-and-send
flow driven through a tiny fake of the Playwright locator API.
"""

from __future__ import annotations

from typing import Any

from linkedin_easy_apply.answers.hiring_message import HiringTeamMessenger
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.outreach import HiringTeamOutreach

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
    def __init__(self, section: _Node | None, overlay: bool = True) -> None:
        self.section = section
        self.compose = _Node("compose") if overlay else None
        self.send = _Node("send") if overlay else None
        self.close = _Node("close") if overlay else None
        self.keyboard = _Keyboard()

    def locator(self, selector: str) -> _Set:
        role = _FIRST.get(selector, "")
        node = {
            "section": self.section,
            "compose": self.compose,
            "send": self.send,
            "close": self.close,
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


def _page(cards: list[_Node], overlay: bool = True) -> _Page:
    section = _Node("section", children={"cards": cards})
    return _Page(section, overlay=overlay)


def _outreach(
    on_approve, has_messaged=lambda k: False, records=None, max_per_run=5, skip_if_messaged=True
) -> HiringTeamOutreach:
    def _record(**kwargs: Any) -> None:
        if records is not None:
            records.append(kwargs)

    return HiringTeamOutreach(
        HiringTeamMessenger(),
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


# -- DB dedup / audit ---------------------------------------------------------


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


# -- flow ---------------------------------------------------------------------


def test_outreach_sends_when_approved():
    seen: list[str] = []

    def approve(_name: str, message: str) -> str:
        seen.append(message)
        return message

    records: list[dict] = []
    flow = _outreach(approve, records=records)
    page = _page([_card("Mrunal B.")])

    sent = flow.reach_out(page, _CTX, run_id=1, job_id=2)

    assert sent == 1
    assert page.compose is not None and page.compose.filled == seen[0]
    assert page.send is not None and page.send.clicks == 1
    assert records[-1]["status"] == "sent"
    assert records[-1]["person_name"] == "Mrunal B."


def test_outreach_declined_is_not_sent():
    records: list[dict] = []
    flow = _outreach(lambda n, m: None, records=records)
    page = _page([_card("Mrunal B.")])

    sent = flow.reach_out(page, _CTX)

    assert sent == 0
    assert page.compose is not None and page.compose.filled is None
    assert records[-1]["status"] == "declined"


def test_outreach_skips_already_messaged():
    approvals: list[str] = []
    flow = _outreach(lambda n, m: approvals.append(n) or m, has_messaged=lambda k: True)
    page = _page([_card("Mrunal B.")])

    assert flow.reach_out(page, _CTX) == 0
    assert approvals == []  # never even drafted/approved


def test_outreach_skips_inmail_only_card():
    approvals: list[str] = []
    flow = _outreach(lambda n, m: approvals.append(n) or m)
    page = _page([_card("No Button", button=False)])

    assert flow.reach_out(page, _CTX) == 0
    assert approvals == []


def test_outreach_respects_per_run_cap():
    records: list[dict] = []
    flow = _outreach(lambda n, m: m, records=records, max_per_run=1)
    page = _page(
        [
            _card("First", href="https://www.linkedin.com/in/first"),
            _card("Second", href="https://www.linkedin.com/in/second"),
        ]
    )

    sent = flow.reach_out(page, _CTX)

    assert sent == 1
    assert sum(1 for r in records if r["status"] == "sent") == 1


def test_outreach_no_section_returns_zero():
    flow = _outreach(lambda n, m: m)
    assert flow.reach_out(_Page(section=None), _CTX) == 0
