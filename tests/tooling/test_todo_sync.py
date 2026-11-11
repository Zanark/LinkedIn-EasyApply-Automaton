"""Offline tracking tests. Fixtures never load credentials or applicant records."""

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "todo_sync", Path(__file__).resolve().parents[2] / "tools" / "todo_sync.py"
)
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class FakeGitHub:
    def __init__(self):
        self.issues = []
        self.items = []
        self.writes = []
        self.fail = None
        self.after = None

    def mutate(self, operation):
        if self.fail == operation:
            raise sync.SyncError("fixture permission/timeout failure")
        self.writes.append(operation)

    def finish(self, operation):
        if self.after == operation:
            raise sync.SyncError("fixture uncertain response")

    def inventory(self, config):
        if self.fail == "inventory":
            raise sync.SyncError("fixture failed inventory")
        return "Zanark", copy.deepcopy(self.issues), copy.deepcopy(self.items)

    def issue(self, identifier):
        return copy.deepcopy(next(issue for issue in self.issues if issue["id"] == identifier))

    def item(self, identifier):
        return copy.deepcopy(next(item for item in self.items if item["id"] == identifier))

    def create_issue(self, repository, title, body):
        self.mutate("create")
        number = len(self.issues) + 1
        issue = {
            "id": f"I{number}",
            "number": number,
            "title": title,
            "body": body,
            "state": "OPEN",
            "stateReason": None,
            "url": f"https://github.com/Zanark/fixture/issues/{number}",
            "updatedAt": "fixture",
        }
        self.issues.append(issue)
        self.finish("create")
        return copy.deepcopy(issue)

    def update_issue(self, identifier, title, body):
        self.mutate("update")
        issue = next(issue for issue in self.issues if issue["id"] == identifier)
        issue.update(title=title, body=body)
        self.finish("update")

    def lifecycle(self, identifier, state, reason):
        self.mutate("lifecycle")
        issue = next(issue for issue in self.issues if issue["id"] == identifier)
        issue.update(state=state, stateReason=reason)
        self.finish("lifecycle")

    def add_item(self, project, issue):
        self.mutate("add")
        item = {
            "id": "P" + str(len(self.items) + 1),
            "project": {"id": project},
            "isArchived": False,
            "content": {"id": issue},
            "fieldValueByName": None,
        }
        self.items.append(item)
        self.finish("add")
        return item["id"]

    def set_status(self, project, identifier, field, option):
        self.mutate("status")
        item = next(item for item in self.items if item["id"] == identifier)
        item["fieldValueByName"] = {"optionId": option}
        self.finish("status")


def source(status="DONE"):
    return f"""# Reviewed feature
Workstream-ID: lea-01
Publication: PUBLIC_SAFE_PROJECTION
Source-record: fixture only
Status: {status}
Milestone: Bounded feature
Dependencies: None

## Purpose
Demonstrate the reviewed behavior.

## Tasks
- [x] Implement the behavior.

## Acceptance criteria
- [x] Focused verification exists.

## Completion evidence
Fixture evidence only, not a live-system claim.

## Completion log
- Historical fixture record.
"""


@pytest.fixture
def setup(tmp_path):
    root = tmp_path
    (root / "todo").mkdir()
    (root / ".github").mkdir()
    config = {
        "schema": 1,
        "account": "Zanark",
        "repository": "Zanark/fixture",
        "repository_id": "R1",
        "private": False,
        "branch": "main",
        "todo_dir": "todo",
        "state_file": ".github\\todo-sync-state.json",
        "project": {
            "id": "PROJECT",
            "url": "https://github.com/users/Zanark/projects/123",
            "public": False,
            "status_field_id": "STATUS",
            "options": {
                "Backlog": "backlog",
                "Ready": "ready",
                "In progress": "progress",
                "In review": "review",
                "Done": "done",
            },
            "option_names": {
                "Backlog": "Backlog",
                "Ready": "Ready",
                "In progress": "In Progress",
                "In review": "In review",
                "Done": "Done",
            },
        },
        "exclude": {"00_INDEX.todo": "navigation"},
        "workstreams": {"lea-01": "01_FEATURE.todo"},
    }
    config_path = root / ".github" / "todo-sync.json"
    sync.save_json(config_path, config)
    path = root / "todo" / "01_FEATURE.todo"
    path.write_text(source(), encoding="utf-8")
    api = FakeGitHub()

    def run(apply=True, selected=None):
        return sync.run(config_path, apply, selected, api, root)

    return SimpleNamespace(
        root=root, config=config, config_path=config_path, path=path, api=api, run=run
    )


def mapping(setup):
    return sync.load_json(setup.root / setup.config["state_file"])


def revise(setup, old, new):
    setup.path.write_text(
        setup.path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8"
    )


def test_preview_is_read_only_then_apply_is_idempotent(setup):
    before = setup.path.read_bytes()
    assert setup.run(False) == 0
    assert setup.api.writes == [] and setup.path.read_bytes() == before
    assert not (setup.root / setup.config["state_file"]).exists()
    assert setup.run() == 0
    assert len(setup.api.issues) == len(setup.api.items) == 1
    assert setup.api.issues[0]["stateReason"] == "COMPLETED"
    state_path = setup.root / setup.config["state_file"]
    before_state = state_path.read_bytes(), state_path.stat().st_mtime_ns
    setup.api.writes.clear()
    assert setup.run() == 0
    assert setup.api.writes == []
    assert (state_path.read_bytes(), state_path.stat().st_mtime_ns) == before_state
    assert "GitHub-Issue: https://github.com/Zanark/fixture/issues/1" in setup.path.read_text()


@pytest.mark.parametrize(
    ("status", "state", "reason", "stage"),
    [
        ("NOT_STARTED", "OPEN", None, "backlog"),
        ("DEFERRED", "OPEN", None, "backlog"),
        ("READY", "OPEN", None, "ready"),
        ("IN_PROGRESS", "OPEN", None, "progress"),
        ("IN_REVIEW", "OPEN", None, "review"),
        ("DONE", "CLOSED", "COMPLETED", "done"),
        ("CANCELLED", "CLOSED", "NOT_PLANNED", "backlog"),
        ("SUPERSEDED", "CLOSED", "NOT_PLANNED", "backlog"),
    ],
)
def test_exact_lifecycle_transitions_and_reopening(setup, status, state, reason, stage):
    assert setup.run() == 0
    revise(setup, "Status: DONE", "Status: " + status)
    assert setup.run() == 0
    assert (setup.api.issues[0]["state"], setup.api.issues[0]["stateReason"]) == (state, reason)
    assert setup.api.items[0]["fieldValueByName"]["optionId"] == stage
    revise(setup, "Status: " + status, "Status: IN_PROGRESS")
    assert setup.run() == 0
    assert setup.api.issues[0]["state"] == "OPEN"
    assert setup.api.items[0]["fieldValueByName"]["optionId"] == "progress"
    assert len(setup.api.issues) == 1


def test_blocked_preserves_stage_and_requires_reason(setup):
    revise(
        setup, "Status: DONE", "Status: BLOCKED\nBlocked-stage: In review\nBlocker: Target access"
    )
    assert setup.run() == 0
    assert setup.api.issues[0]["state"] == "OPEN"
    assert setup.api.items[0]["fieldValueByName"]["optionId"] == "review"
    revise(setup, "Blocker: Target access", "")
    assert setup.run() == 1


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Status: DONE", "Status: DONE locally; deployment BLOCKED"),
        ("- [x] Implement", "- [ ] Implement"),
        ("- [x] Focused", "- [ ] Focused"),
        ("Fixture evidence only, not a live-system claim.", "Not completed."),
        ("Publication: PUBLIC_SAFE_PROJECTION", "Publication: PRIVATE"),
        ("Dependencies: None", "Dependencies: "),
        ("## Tasks", "## Missing"),
    ],
)
def test_invalid_or_incomplete_projection_never_creates(setup, old, new):
    revise(setup, old, new)
    assert setup.run() == 1 and not setup.api.writes


def test_human_sections_survive_local_description_update(setup):
    assert setup.run() == 0
    setup.api.issues[0]["body"] = (
        "Human introduction\n\n" + setup.api.issues[0]["body"] + "\nHuman tail"
    )
    revise(setup, "Demonstrate the reviewed behavior.", "Updated reviewed behavior.")
    assert setup.run() == 0
    body = setup.api.issues[0]["body"]
    assert body.startswith("Human introduction") and body.endswith("Human tail")
    assert "Updated reviewed behavior." in body


@pytest.mark.parametrize("dimension", ["title", "body", "state", "status"])
def test_human_managed_edits_are_conflicts(setup, dimension):
    assert setup.run() == 0
    setup.api.writes.clear()
    if dimension == "status":
        setup.api.items[0]["fieldValueByName"] = {"optionId": "review"}
    elif dimension == "state":
        setup.api.issues[0].update(state="OPEN", stateReason=None)
    elif dimension == "body":
        setup.api.issues[0]["body"] = setup.api.issues[0]["body"].replace(
            "reviewed behavior", "human edit"
        )
    else:
        setup.api.issues[0]["title"] = "Human changed title"
    assert setup.run() == 1 and not setup.api.writes


@pytest.mark.parametrize("operation", ["create", "add"])
def test_uncertain_success_recovers_without_duplicate(setup, operation):
    setup.api.after = operation
    assert setup.run() == 1
    assert len(setup.api.issues) == 1
    setup.api.after = None
    assert setup.run() == 0
    assert len(setup.api.issues) == len(setup.api.items) == 1
    assert setup.api.writes.count("create") == setup.api.writes.count("add") == 1
    assert not any(
        key in mapping(setup)["workstreams"]["lea-01"] for key in ("creating", "pending")
    )


@pytest.mark.parametrize("operation", ["create", "add"])
def test_invisible_uncertain_outcome_is_not_blindly_retried(setup, operation):
    setup.api.fail = operation
    assert setup.run() == 1
    setup.api.fail = None
    before = list(setup.api.writes)
    assert setup.run() == 1 and setup.api.writes == before


def test_partial_status_then_new_local_target_retains_recoverable_origin(setup):
    assert setup.run() == 0
    revise(setup, "Demonstrate the reviewed behavior.", "First update.")
    revise(setup, "Status: DONE", "Status: IN_PROGRESS")
    setup.api.fail = "status"
    assert setup.run() == 1
    revise(setup, "First update.", "Second update.")
    setup.api.fail = "update"
    assert setup.run() == 1
    setup.api.fail = None
    assert setup.run() == 0
    assert "Second update." in setup.api.issues[0]["body"]
    assert len(setup.api.issues) == len(setup.api.items) == 1


def test_failed_backlink_retains_remote_progress_and_retries_only_local_write(setup, monkeypatch):
    original = sync.write_backlink
    monkeypatch.setattr(
        sync, "write_backlink", lambda *args: (_ for _ in ()).throw(OSError("fixture disk failure"))
    )
    assert setup.run() == 1
    monkeypatch.setattr(sync, "write_backlink", original)
    setup.api.writes.clear()
    assert setup.run() == 0
    assert setup.api.writes == [] and len(setup.api.issues) == 1


def test_failed_inventory_never_becomes_an_empty_baseline(setup):
    setup.api.fail = "inventory"
    with pytest.raises(sync.SyncError, match="inventory"):
        setup.run()
    assert not setup.api.writes


def test_one_conflicting_workstream_does_not_block_independent_safe_item(setup):
    setup.config["workstreams"]["lea-02"] = "02_OTHER.todo"
    sync.save_json(setup.config_path, setup.config)
    other = setup.root / "todo" / "02_OTHER.todo"
    other.write_text(
        source().replace("lea-01", "lea-02").replace("Reviewed feature", "Other reviewed feature"),
        encoding="utf-8",
    )
    revise(setup, "Status: DONE", "Status: UNREVIEWED")
    assert setup.run() == 1
    assert len(setup.api.issues) == len(setup.api.items) == 1
    assert "lea-02" in setup.api.issues[0]["body"]
    assert set(mapping(setup)["workstreams"]) == {"lea-02"}


def test_bounded_eventual_consistency_readback(setup, monkeypatch):
    original = setup.api.issue
    reads = []

    def stale_then_visible(identifier):
        issue = original(identifier)
        reads.append(identifier)
        if len(reads) < 3:
            issue.update(state="OPEN", stateReason=None)
        return issue

    monkeypatch.setattr(setup.api, "issue", stale_then_visible)
    monkeypatch.setattr(sync.time, "sleep", lambda delay: None)
    assert setup.run() == 0
    assert len(reads) == 3 and setup.api.writes.count("create") == 1


def test_unmapped_or_duplicate_marked_issue_is_not_automatically_recreated(setup):
    assert setup.run() == 0
    setup.api.issues.append(copy.deepcopy(setup.api.issues[0]))
    setup.api.writes.clear()
    assert setup.run() == 1 and not setup.api.writes
    setup.api.issues.pop()
    state_path = setup.root / setup.config["state_file"]
    state = sync.load_json(state_path)
    state["workstreams"] = {}
    sync.save_json(state_path, state)
    assert setup.run() == 1 and not setup.api.writes


@pytest.mark.parametrize("kind", ["removed", "archived", "duplicate", "wrong-project"])
def test_changed_project_membership_blocks_recreation(setup, kind):
    assert setup.run() == 0
    setup.api.writes.clear()
    if kind == "removed":
        setup.api.items.clear()
    elif kind == "archived":
        setup.api.items[0]["isArchived"] = True
    elif kind == "wrong-project":
        setup.api.items[0]["project"]["id"] = "OTHER"
    else:
        setup.api.items.append(copy.deepcopy(setup.api.items[0]))
    assert setup.run() == 1 and not setup.api.writes


def test_file_and_repository_rename_keep_stable_issue_identity(setup):
    assert setup.run() == 0
    setup.path.rename(setup.path.with_name("02_RENAMED.todo"))
    setup.path = setup.path.with_name("02_RENAMED.todo")
    setup.config["workstreams"]["lea-01"] = setup.path.name
    setup.config["repository_aliases"] = ["Zanark/fixture"]
    setup.config["repository"] = "Zanark/renamed"
    setup.api.issues[0]["url"] = "https://github.com/Zanark/renamed/issues/1"
    sync.save_json(setup.config_path, setup.config)
    assert setup.run() == 0
    assert len(setup.api.issues) == 1
    assert "https://github.com/Zanark/renamed/issues/1" in setup.path.read_text()
    setup.path.unlink()
    assert setup.run() == 1 and len(setup.api.issues) == 1


@pytest.mark.parametrize(
    "value",
    [
        r"C:\private\record",
        r"\\server\private",
        "../.agent-context/STATE.md",
        "configs/answers.yaml",
        "generated/resume/private.pdf",
        "api_key=fixture-secret",
        "ghp_" + "x" * 30,
        "private-person@personal.invalid",
        "[Private](../.env)",
        "[Escape](../../outside.md)",
        "[Insecure](http://example.org)",
    ],
)
def test_private_payloads_and_links_are_blocked(setup, value):
    revise(setup, "Demonstrate the reviewed behavior.", value)
    assert setup.run() == 1 and not setup.api.writes


def test_title_is_privacy_checked_and_public_https_is_not_a_drive_path(setup):
    revise(setup, "# Reviewed feature", r"# C:\private\contact")
    assert setup.run() == 1 and not setup.api.writes
    setup.path.write_text(source(), encoding="utf-8")
    revise(setup, "Demonstrate the reviewed behavior.", "[Guide](https://example.org/guide)")
    assert setup.run() == 0 and "https://example.org/guide" in setup.api.issues[0]["body"]


def test_conflicting_backlink_does_not_overwrite(setup):
    assert setup.run() == 0
    revise(setup, "/issues/1", "/issues/99")
    setup.api.writes.clear()
    assert setup.run() == 1 and not setup.api.writes


def test_duplicate_selection_and_excluded_workstream_block(setup):
    with pytest.raises(sync.SyncError, match="duplicate selected"):
        setup.run(selected=["lea-01", "lea-01"])
    setup.config["exclude"]["01_FEATURE.todo"] = "private"
    sync.save_json(setup.config_path, setup.config)
    with pytest.raises(sync.SyncError, match="excluded"):
        setup.run()
    assert not setup.api.writes


def test_existing_writer_lock_is_never_stolen(tmp_path):
    path = tmp_path / ".todo-sync.lock"
    path.write_text("fixture other writer")
    with pytest.raises(sync.SyncError, match="Writer lock"):
        with sync.writer_lock(tmp_path):
            pytest.fail("must not enter")
    assert path.read_text() == "fixture other writer"


def test_local_edit_during_apply_is_not_reported_as_verified(setup, monkeypatch):
    original = setup.api.set_status

    def change_file(*args):
        original(*args)
        revise(setup, "Demonstrate the reviewed behavior.", "Concurrent local edit.")

    monkeypatch.setattr(setup.api, "set_status", change_file)
    assert setup.run() == 1
    assert mapping(setup)["workstreams"]["lea-01"]["pending"]
    assert "GitHub-Issue" not in setup.path.read_text()


def test_connection_paginates_and_rejects_repeated_cursor(monkeypatch):
    api = sync.GitHub()
    pages = iter(
        [
            {"list": {"nodes": [1], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}},
            {"list": {"nodes": [2], "pageInfo": {"hasNextPage": False, "endCursor": None}}},
        ]
    )
    monkeypatch.setattr(api, "request", lambda *args, **kwargs: next(pages))
    assert api.connection("query", ("list",)) == [1, 2]
    monkeypatch.setattr(
        api,
        "request",
        lambda *args, **kwargs: {
            "list": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "same"}}
        },
    )
    with pytest.raises(sync.SyncError, match="cursor"):
        api.connection("query", ("list",))


def test_read_retries_but_mutation_timeout_is_never_retried(monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired("gh", 120)

    monkeypatch.setattr(sync.subprocess, "run", timeout)
    monkeypatch.setattr(sync.time, "sleep", lambda delay: None)
    api = sync.GitHub()
    with pytest.raises(sync.SyncError, match="timeout"):
        api.request("query { viewer { login } }")
    assert len(calls) == 3
    calls.clear()
    with pytest.raises(sync.SyncError, match="uncertain"):
        api.request("mutation { fixture }")
    assert len(calls) == 1


def test_partial_graphql_error_is_not_treated_as_success(monkeypatch):
    monkeypatch.setattr(
        sync.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"data": {"partial": True}, "errors": [{}]})
        ),
    )
    with pytest.raises(sync.SyncError, match="GraphQL"):
        sync.GitHub().request("mutation { fixture }")


def test_transport_redacts_dummy_token_and_drops_debug(monkeypatch):
    dummy = "dummy-fixture-value"
    monkeypatch.setenv("GH_TOKEN", dummy)
    monkeypatch.setenv("GH_DEBUG", "api")
    seen = []

    def fail(*args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(returncode=1, stderr="permission denied " + dummy)

    monkeypatch.setattr(sync.subprocess, "run", fail)
    with pytest.raises(sync.SyncError) as caught:
        sync.GitHub().request("mutation { fixture }")
    assert dummy not in str(caught.value)
    assert "GH_DEBUG" not in seen[0][1]["env"]
    assert seen[0][0][0][:4] == ["gh", "api", "--hostname", "github.com"]
