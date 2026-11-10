"""Fictional fixtures covering native table sizing and retained editor behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from linkedin_easy_apply.database import Database


def _seed_tables(db: Database) -> None:
    db.initialize()
    run = db.start_run("apply")
    resume = db.register_resume("Fictional resume", str(db.path.parent / "fictional.pdf"))
    for index, status in enumerate(("submitted", "failed"), start=1):
        job = db.upsert_job(
            {
                "url": f"https://example.invalid/jobs/{index}",
                "title": f"Fictional distributed systems engineer {index}",
                "company": "Fictional Example Laboratory",
                "workplace_type": "remote",
                "experience_level": "Mid-Senior",
                "easy_apply": True,
            },
            run,
        )
        app = db.create_application(job, run, resume, status)
        db.update_application(app, reason="No progress" if status == "failed" else None, steps=2)
        question = "How many years of professional experience do you have with distributed systems?"
        qid = db.upsert_question(question, "fixture systems experience", "experience_total")
        db.record_application_answer(app, question, "2", "yaml", qid)
        if status == "failed":
            gap = db.upsert_question(
                "Which fictional scheduling option would you prefer?",
                "fixture scheduling option",
                "unknown",
                answer_type="text",
            )
            db.record_application_answer(
                app, "Which fictional scheduling option would you prefer?", None, "unanswered", gap
            )
        else:
            db.record_outreach(
                person_key="fictional-contact",
                person_name="Fictional Example Contact",
                profile_url="https://example.invalid/profile",
                message="An entirely fictional outreach draft.",
                note="Fictional connection note.",
                status="drafted",
                run_id=run,
                job_id=job,
            )
        db.record_skip(run, job, "below_threshold")
    approved = db.upsert_question("Fictional approved question?", "fixture approved", "unknown")
    db.set_answer_override("fixture approved", "Fictional approved answer", approved)
    old_job = db.upsert_job(
        {
            "url": "https://example.invalid/jobs/overdue",
            "title": "Fictional platform engineer",
            "company": "Fictional Older Application",
        },
        run,
    )
    old_app = db.create_application(old_job, run, resume, "submitted")
    old_date = (datetime.now() - timedelta(days=9)).isoformat(timespec="seconds")
    with db.connect() as conn:
        conn.execute(
            "UPDATE applications SET started_at=?, finished_at=? WHERE id=?",
            (old_date, old_date, old_app),
        )
    db.record_outreach(
        person_key="fictional-priority-contact",
        person_name="Fictional Priority Contact",
        profile_url="https://example.invalid/priority-profile",
        message="An entirely fictional priority draft.",
        note="Fictional priority connection note.",
        status="drafted",
        run_id=run,
        job_id=old_job,
    )


def _tables_script(database_path: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import streamlit as st

    import linkedin_easy_apply.dashboard.app as dashboard
    from linkedin_easy_apply.answers.resume_expectations import GradedAnswer, Verdict
    from linkedin_easy_apply.database import Database

    st.set_page_config(layout="wide")
    st.title("Fictional dashboard tables")
    db = Database(database_path)
    row = db.query("SELECT id, text FROM questions WHERE normalized='fixture systems experience'")[
        0
    ]
    mismatch = GradedAnswer(
        normalized="fixture systems experience",
        question_id=row["id"],
        question=row["text"],
        category="experience_total",
        skill=None,
        answered="2",
        verdict=Verdict.MISMATCH,
        expected_display="7 years",
        recommended="7",
        reason="The fictional resume lists additional relevant experience compared with the submitted answer.",
        override=db.get_answer_override("fixture systems experience"),
        apps=2,
        blocked_apps=1,
    )
    with (
        patch.object(st, "dataframe", wraps=st.dataframe) as frames,
        patch.object(st, "data_editor", wraps=st.data_editor) as editors,
    ):
        dashboard._focus_table(
            [
                {
                    "Job": "Fictional systems engineer",
                    "Company": "Example",
                    "url": "https://example.invalid",
                }
            ]
        )
        overview, submitted, details, attention, skipped, match, outreach = st.tabs(
            ["Overview", "Submitted", "Details", "Attention", "Skipped", "Resume match", "Outreach"]
        )
        with overview:
            dashboard._overview_section(db, db.stats())
        with submitted:
            dashboard._submitted_section(db)
        with details:
            dashboard._application_detail_section(db)
        with attention:
            dashboard._needs_attention_section(
                db, str(Path(database_path).parent / "configs" / "config.yaml")
            )
        with skipped:
            dashboard._skipped_section(db)
        with match:
            dashboard._resume_sync_editor(db, [mismatch], [])
            dashboard._resume_overrides_view(db)
        with outreach:
            dashboard._outreach_section(db)
        st.session_state["table_layouts"] = [
            {"kind": kind, **call.kwargs}
            for kind, calls in (
                ("dataframe", frames.call_args_list),
                ("editor", editors.call_args_list),
            )
            for call in calls
        ]


@pytest.fixture
def table_app(tmp_path: Path) -> tuple[AppTest, Database]:
    db = Database(tmp_path / "fictional.db")
    _seed_tables(db)
    app = AppTest.from_function(_tables_script, args=(str(db.path),), default_timeout=20).run()
    assert not app.exception
    return app, db


def test_all_dashboard_tables_default_to_content_sizing(
    table_app: tuple[AppTest, Database],
) -> None:
    app, _ = table_app
    layouts = app.session_state["table_layouts"]
    assert sum(layout["kind"] == "dataframe" for layout in layouts) == 12
    assert sum(layout["kind"] == "editor" for layout in layouts) == 3
    assert all(layout["width"] == "content" for layout in layouts)
    for layout in layouts:
        for column in (layout.get("column_config") or {}).values():
            assert column.get("width") is None

    app.run()
    assert not app.exception
    assert all(layout["width"] == "content" for layout in app.session_state["table_layouts"])


def _skip_drilldown_script(database_path: str) -> None:
    import streamlit as st

    import linkedin_easy_apply.dashboard.app as dashboard
    from linkedin_easy_apply.database import Database

    st.set_page_config(layout="wide")
    db = Database(database_path)
    skipped, overview = st.tabs(["Skipped", "Overview drilldown"])
    with skipped:
        dashboard._skipped_section(db)
    with overview:
        st.session_state["focus_category"] = "skipped"
        dashboard._focus_panel(db)


def _skip_lists(app: AppTest) -> list[pd.DataFrame]:
    return [
        element.value
        for element in app.dataframe
        if {"When", "Reason", "Explanation"} <= set(element.value.columns)
    ]


def test_skip_drilldown_filters_complete_history_in_both_entry_points(tmp_path: Path) -> None:
    db = Database(tmp_path / "fictional.db")
    _seed_tables(db)
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO skips (reason, created_at) VALUES (?, ?)",
            [("below_threshold", "2020-01-01T00:00:00")] * 5001,
        )
    db.record_skip(None, None, "scan_only", detail="Fictional scan without an application.")
    app = AppTest.from_function(
        _skip_drilldown_script, args=(str(db.path),), default_timeout=30
    ).run()
    assert not app.exception
    assert [len(frame) for frame in _skip_lists(app)] == [5004, 5004]
    original = db.path.read_bytes()
    for index, prefix in enumerate(("skipped", "focus_skipped")):
        app.selectbox(key=f"{prefix}_reason").set_value("below_threshold").run()
        assert not app.exception
        assert len(_skip_lists(app)[index]) == 5003
        assert set(_skip_lists(app)[index]["Reason"]) == {"below_threshold"}
        app.selectbox(key=f"{prefix}_reason").set_value("scan_only").run()
        selected = _skip_lists(app)[index]
        assert len(selected) == 1
        assert selected.iloc[0]["Explanation"] == "Fictional scan without an application."
        app.button(key=f"{prefix}_clear_reason").click().run()
        assert not app.exception
        assert len(_skip_lists(app)[index]) == 5004
    assert db.path.read_bytes() == original


def _skip_details_script(event: dict) -> None:
    from linkedin_easy_apply.dashboard.app import _skip_event_details

    _skip_event_details(event)


def _skip_missing_context_script(database_path: str) -> None:
    from unittest.mock import patch

    import streamlit as st

    from linkedin_easy_apply.dashboard.app import _skipped_section
    from linkedin_easy_apply.database import Database

    dataframe = st.dataframe

    def select_first(data, *args, **kwargs):
        result = dataframe(data, *args, **kwargs)
        if kwargs.get("selection_mode") == "single-row":
            return {"selection": {"rows": [0]}}
        return result

    with patch.object(st, "dataframe", side_effect=select_first):
        _skipped_section(Database(database_path))


@pytest.mark.parametrize(
    ("reason", "explanation"),
    [
        ("not_easy_apply", "No usable Easy Apply button was detected."),
        ("fictional_unknown_gate", "No explanation was recorded."),
    ],
)
def test_skip_drilldown_preserves_missing_context_in_mixed_history(
    tmp_path: Path, reason: str, explanation: str
) -> None:
    db = Database(tmp_path / "fictional.db")
    db.initialize()
    job = db.upsert_job(
        {
            "url": "https://example.invalid/jobs/known",
            "title": "Fictional known role",
            "company": "Fictional Company",
            "description": "A recorded fictional description.",
        }
    )
    db.record_skip(
        None,
        job,
        "below_threshold",
        detail="Recorded score below threshold.",
        score={"score": 20, "threshold": 70, "breakdown": {}},
    )
    db.record_skip(None, None, reason)
    original = db.path.read_bytes()
    app = AppTest.from_function(
        _skip_missing_context_script, args=(str(db.path),), default_timeout=20
    ).run()
    assert not app.exception
    selected = _skip_lists(app)[0].iloc[0]
    assert selected["Reason"] == reason
    assert selected["Explanation"] == explanation
    assert "Title not recorded @ Company not recorded" in [element.value for element in app.text]
    assert explanation in [element.value for element in app.text]
    assert "No job description was recorded." in [element.value for element in app.info]
    assert db.path.read_bytes() == original


@pytest.mark.parametrize("legacy", [False, True])
def test_skip_details_distinguish_legacy_data_and_keep_literal_description(
    tmp_path: Path,
    legacy: bool,
) -> None:
    db = Database(tmp_path / "fictional.db")
    db.initialize()
    description = "Literal <b>posting</b> with **stars** and [link](https://example.invalid)."
    job = db.upsert_job(
        {
            "url": "https://example.invalid/jobs/details",
            "title": "Fictional role",
            "company": "Fictional Company",
            "description": description,
        }
    )
    if legacy:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO skips (job_id, reason, created_at) VALUES (?, ?, ?)",
                (job, "historical_reason", "2020-01-01T00:00:00"),
            )
        db.record_score(job, 99, 10, True, {"later": 99})
    else:
        db.record_skip(
            None,
            job,
            "below_threshold",
            detail="0 < 30.",
            score={"score": 0, "threshold": 30, "breakdown": {}},
        )
    app = AppTest.from_function(
        _skip_details_script,
        args=(db.skip_events()[0],),
        default_timeout=20,
    ).run()
    assert not app.exception
    assert description in [element.value for element in app.text]
    if legacy:
        assert len(app.warning) == 1 and "Legacy event" in app.warning[0].value
        assert any("No decision-time score" in element.value for element in app.info)
    else:
        assert not app.warning
        assert any("score: 0 / threshold 30" in element.value for element in app.caption)


@pytest.mark.parametrize("column", ["Question", "Why"])
def test_resume_review_uses_native_column_measurement(
    table_app: tuple[AppTest, Database], column: str
) -> None:
    app, _ = table_app
    layout = next(
        item
        for item in app.session_state["table_layouts"]
        if item.get("key") == "resume_sync_editor"
    )
    assert layout["column_config"][column].get("width") is None
    assert column in layout["disabled"]
    assert layout["column_config"]["Approve"]["type_config"]["type"] == "checkbox"


def test_content_sized_editors_retain_controls_and_data(
    table_app: tuple[AppTest, Database],
) -> None:
    app, db = table_app
    outreach = next(
        item
        for item in app.session_state["table_layouts"]
        if item.get("key", "").startswith("outreach_done_editor_")
    )
    assert outreach["column_config"]["Profile"]["type_config"]["type"] == "link"
    assert outreach["column_config"]["Message sent"]["type_config"]["type"] == "checkbox"
    assert "Profile" in outreach["disabled"]
    resume = next(element.value for element in app.dataframe if "Approve" in element.value)
    assert resume["Approved value"].tolist() == ["7"]
    assert not resume["Approve"].any()
    assert db.get_answer_override("fixture systems experience") is None
    outreach_rows = [element.value for element in app.dataframe if "Message sent" in element.value]
    assert len(db.outreach_drafts()) == 2
    assert sorted(row_id for frame in outreach_rows for row_id in frame["_id"]) == [
        draft["id"] for draft in db.outreach_drafts()
    ]


def test_outreach_shows_application_dates_in_separate_readonly_queues(
    table_app: tuple[AppTest, Database],
) -> None:
    app, db = table_app
    layouts = [
        item
        for item in app.session_state["table_layouts"]
        if item.get("key", "").startswith(("outreach_done_editor_", "outreach_priority_editor_"))
    ]
    assert len(layouts) == 2
    for layout in layouts:
        assert "Applied on" in layout["column_order"]
        assert "Applied on" in layout["disabled"]
        assert layout["column_config"]["Profile"]["type_config"]["type"] == "link"
        assert layout["column_config"]["Message sent"]["type_config"]["type"] == "checkbox"
    queues = [element.value for element in app.dataframe if "Message sent" in element.value]
    assert queues[0]["Name"].tolist() == ["Fictional Priority Contact"]
    assert queues[1]["Name"].tolist() == ["Fictional Example Contact"]
    for frame in queues:
        draft = next(d for d in db.outreach_drafts() if d["id"] == frame.iloc[0]["_id"])
        expected = datetime.fromisoformat(draft["applied_at"]).strftime("%Y-%m-%d %H:%M")
        assert frame.iloc[0]["Applied on"] == expected


def test_outreach_contact_headers_follow_priority_and_note_state(
    table_app: tuple[AppTest, Database],
) -> None:
    app, db = table_app
    old = next(draft for draft in db.outreach_drafts() if "Priority" in draft["person_name"])
    db.record_outreach(
        person_key="fictional-unknown-date",
        person_name="Fictional Unknown Date Contact",
        status="drafted",
    )
    app.run()
    assert not app.exception

    def header(name: str) -> str:
        return next(element.label for element in app.expander if name in element.label)

    assert "Overdue outreach" in header("Fictional Priority Contact")
    assert "Overdue outreach" not in header("Fictional Example Contact")
    assert "Overdue outreach" not in header("Fictional Unknown Date Contact")

    app.button(key=f"outreach_note_{old['id']}").click().run()
    assert not app.exception
    assert "Overdue outreach" not in header("Fictional Priority Contact")
    assert "note sent" in header("Fictional Priority Contact")
    assert next(draft for draft in db.outreach_drafts() if draft["id"] == old["id"])["note_sent_at"]

    app.button(key=f"outreach_note_undo_{old['id']}").click().run()
    assert not app.exception
    assert "Overdue outreach" in header("Fictional Priority Contact")
    assert "note sent" not in header("Fictional Priority Contact")
    assert len(db.outreach_drafts()) == 3


@pytest.mark.parametrize(
    ("age", "note_sent", "unknown", "overdue"),
    [
        (timedelta(days=7, seconds=1), False, False, True),
        (timedelta(days=7), False, False, False),
        (timedelta(days=6, hours=23), False, False, False),
        (timedelta(days=-1), False, False, False),
        (timedelta(days=12), True, False, False),
        (timedelta(days=12), False, True, False),
    ],
)
def test_outreach_priority_requires_more_than_a_week_without_initial_outreach(
    age: timedelta, note_sent: bool, unknown: bool, overdue: bool
) -> None:
    from linkedin_easy_apply.dashboard.app import _split_outreach_drafts

    now = datetime(2026, 11, 10, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    draft = {
        "id": 1,
        "applied_at": None if unknown else (now - age).isoformat(),
        "note_sent_at": now.isoformat() if note_sent else None,
    }
    original = draft.copy()
    priority, regular = _split_outreach_drafts([draft], now=now)
    assert [row["id"] for row in priority] == ([1] if overdue else [])
    assert [row["id"] for row in regular] == ([] if overdue else [1])
    assert draft == original


def test_outreach_priority_handles_timezones_unknown_dates_and_oldest_first() -> None:
    from linkedin_easy_apply.dashboard.app import _split_outreach_drafts

    now = datetime(2026, 11, 10, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    oldest = now - timedelta(days=15)
    drafts = [
        {"id": 1, "applied_at": "2026-11-03T06:29:59Z"},
        {"id": 2, "applied_at": oldest.astimezone().replace(tzinfo=None).isoformat()},
        {"id": 3, "applied_at": "not a recorded date"},
        {"id": 4, "applied_at": "2026-11-03T06:30:00+00:00"},
        {"id": 5, "applied_at": ""},
    ]
    priority, regular = _split_outreach_drafts(drafts, now=now)
    assert [row["id"] for row in priority] == [2, 1]
    assert [row["id"] for row in regular] == [3, 4, 5]
    assert regular[0]["applied_at"] is None
    assert regular[-1]["applied_at"] is None


def test_outreach_bulk_completion_uses_checked_ids_from_both_queues(tmp_path: Path) -> None:
    from unittest.mock import patch

    import linkedin_easy_apply.dashboard.app as dashboard

    db = Database(tmp_path / "fictional-completion.db")
    _seed_tables(db)
    selected = {draft["id"] for draft in db.outreach_drafts()}
    untouched = db.record_outreach(
        person_key="fictional-unselected",
        person_name="Fictional Unselected Contact",
        status="drafted",
    )
    ui = MagicMock()
    ui.session_state = {}
    ui.columns.return_value = [MagicMock(), MagicMock()]
    ui.button.side_effect = lambda label, **kwargs: "Remove message-sent outreach" in label

    def select(frame: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        frame = frame.copy()
        frame["Message sent"] = frame["_id"].isin(selected)
        return frame

    ui.data_editor.side_effect = select
    with patch.object(dashboard, "st", ui):
        dashboard._outreach_section(db)
    assert [row["id"] for row in db.outreach_drafts()] == [untouched]
    assert ui.data_editor.call_count == 2
    ui.rerun.assert_called_once()


def test_outreach_queue_changes_replace_identity_in_equal_sized_lists(tmp_path: Path) -> None:
    from unittest.mock import patch

    import linkedin_easy_apply.dashboard.app as dashboard

    db = Database(tmp_path / "fictional-moving-queues.db")
    _seed_tables(db)
    recent, old = db.outreach_drafts()
    ui = MagicMock()
    ui.columns.return_value = [MagicMock(), MagicMock()]
    ui.button.return_value = False
    ui.data_editor.side_effect = lambda frame, **kwargs: frame
    with patch.object(dashboard, "st", ui):
        dashboard._outreach_section(db)
        initial = [call.kwargs["key"] for call in ui.data_editor.call_args_list]
        ui.data_editor.reset_mock()
        dashboard._outreach_section(db)
        assert [call.kwargs["key"] for call in ui.data_editor.call_args_list] == initial
        db.mark_outreach_note_sent([old["id"]])
        with db.connect() as conn:
            conn.execute(
                "UPDATE applications SET finished_at=? WHERE status='submitted'",
                ((datetime.now() - timedelta(days=10)).isoformat(),),
            )
        ui.data_editor.reset_mock()
        dashboard._outreach_section(db)
    assert [len(call.args[0]) for call in ui.data_editor.call_args_list] == [1, 1]
    changed = [call.kwargs["key"] for call in ui.data_editor.call_args_list]
    assert len(changed) == len(initial) == 2
    assert not set(changed) & set(initial)
    assert ui.data_editor.call_args_list[0].args[0]["_id"].tolist() == [recent["id"]]
    assert ui.data_editor.call_args_list[1].args[0]["_id"].tolist() == [old["id"]]
    assert len(db.outreach_drafts()) == 2


def test_resume_review_pairs_the_saved_answer_with_its_selection(
    table_app: tuple[AppTest, Database],
) -> None:
    app, _ = table_app
    layout = next(
        item
        for item in app.session_state["table_layouts"]
        if item.get("key") == "resume_sync_editor"
    )
    assert layout["column_order"][:3] == ["Question", "Approved value", "Approve"]
    columns = layout["column_config"]
    assert columns["Approved value"]["label"] == "Answer to save"
    assert columns["Approve"]["label"] == "Save this answer"
    assert columns["Answered"]["label"] == "Previous answer (read-only)"
    assert columns["Résumé expects"]["label"] == "Résumé reference (read-only)"
    assert set(layout["column_order"]) - set(layout["disabled"]) == {
        "Approved value",
        "Approve",
    }
    assert app.button(key="resume_sync_save").disabled
    assert any("You approve only" in message.value for message in app.info)


def test_resume_review_saves_only_selected_nonempty_edited_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import linkedin_easy_apply.dashboard.app as dashboard
    from linkedin_easy_apply.answers.resume_expectations import GradedAnswer, Verdict

    db = Database(tmp_path / "fictional-review.db")
    db.initialize()
    candidates = []
    for index in range(3):
        question = f"Fictional correction question {index}?"
        normalized = f"fixture correction {index}"
        qid = db.upsert_question(question, normalized, "unknown")
        candidates.append(
            GradedAnswer(
                normalized=normalized,
                question_id=qid,
                question=question,
                category="unknown",
                skill=None,
                answered=f"previous {index}",
                verdict=Verdict.MISMATCH,
                expected_display=f"reference {index}",
                recommended=f"recommended {index}",
                reason="Fictional reference comparison.",
                override=None,
                apps=0,
                blocked_apps=0,
            )
        )

    def edit(frame: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        frame = frame.copy()
        frame["Approved value"] = ["  reviewed answer  ", "unchecked answer", "  "]
        frame["Approve"] = [True, False, True]
        return frame

    ui = Mock()
    ui.checkbox.return_value = False
    ui.data_editor.side_effect = edit
    ui.button.return_value = True
    monkeypatch.setattr(dashboard, "st", ui)
    dashboard._resume_sync_editor(db, candidates, [])

    overrides = db.answer_overrides()
    assert len(overrides) == 1
    assert overrides[0]["normalized"] == candidates[0].normalized
    assert overrides[0]["question"] == candidates[0].question
    assert overrides[0]["value"] == "reviewed answer"
    assert ui.button.call_args.kwargs["disabled"] is False
    ui.warning.assert_called_once()
    ui.rerun.assert_called_once()
