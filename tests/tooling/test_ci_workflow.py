"""Every relocated test group and required result must reach the release gate."""

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.load(
    (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8"),
    Loader=yaml.BaseLoader,
)


def test_matrix_covers_every_test_file_on_each_supported_python():
    matrix = WORKFLOW["jobs"]["tests"]["strategy"]["matrix"]
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    supported = {
        item.removeprefix("Programming Language :: Python :: ")
        for item in metadata["project"]["classifiers"]
        if item.startswith("Programming Language :: Python :: ")
    }
    assert set(matrix["python"]) == supported
    groups = matrix["suite"]
    assert len(groups) == len(set(groups))
    for group in groups:
        assert list((ROOT / "tests" / group).glob("test_*.py")), f"Empty lane: {group}"
    for test in (ROOT / "tests").rglob("test_*.py"):
        assert test.relative_to(ROOT / "tests").parts[0] in groups, f"Unscheduled test: {test}"


def test_release_cannot_bypass_any_qualification_job():
    jobs = WORKFLOW["jobs"]
    assert set(jobs["qualify"]["needs"]) == set(jobs) - {"qualify", "publish"}
    assert jobs["qualify"]["if"] == "always()"
    assert jobs["publish"]["needs"] == "qualify"
    assert jobs["publish"]["if"] == (
        "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"
    )
    assert not jobs["quality"].get("continue-on-error")
    assert not jobs["tests"].get("continue-on-error")
    assert not jobs["build"].get("continue-on-error")


@pytest.mark.parametrize("lane", ["quality", "tests", "build"])
@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped"])
def test_actual_release_barrier_rejects_nonpassing_dependency(monkeypatch, lane, result):
    results = {name: {"result": "success"} for name in WORKFLOW["jobs"]["qualify"]["needs"]}
    results[lane]["result"] = result
    monkeypatch.setenv("NEEDS_JSON", json.dumps(results))
    script = WORKFLOW["jobs"]["qualify"]["steps"][0]["run"]
    with pytest.raises(SystemExit, match=f"{lane}: {result}"):
        exec(compile(script, "qualification-barrier", "exec"), {})


@pytest.mark.parametrize(
    "results",
    [
        {},
        {"quality": {"result": "failure"}},
        {"quality": {"result": "success"}},
        {name: {"result": "success"} for name in ("quality", "tests", "build", "unexpected")},
    ],
)
def test_actual_release_barrier_rejects_missing_or_unexpected_results(monkeypatch, results):
    monkeypatch.setenv("NEEDS_JSON", json.dumps(results))
    script = WORKFLOW["jobs"]["qualify"]["steps"][0]["run"]
    with pytest.raises(SystemExit):
        exec(compile(script, "qualification-barrier", "exec"), {})


def test_actual_release_barrier_accepts_all_passing_dependencies(monkeypatch, capsys):
    results = {name: {"result": "success"} for name in WORKFLOW["jobs"]["qualify"]["needs"]}
    monkeypatch.setenv("NEEDS_JSON", json.dumps(results))
    script = WORKFLOW["jobs"]["qualify"]["steps"][0]["run"]
    exec(compile(script, "qualification-barrier", "exec"), {})
    assert "Every quality, test and frozen-build lane passed." in capsys.readouterr().out


def test_external_actions_are_immutable_and_release_writes_are_isolated():
    assert WORKFLOW["permissions"] == {"contents": "read"}
    for name, job in WORKFLOW["jobs"].items():
        if name != "publish":
            assert job.get("permissions", WORKFLOW["permissions"]) == {"contents": "read"}
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", step["uses"])
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
    assert WORKFLOW["jobs"]["publish"]["permissions"] == {"contents": "write"}
