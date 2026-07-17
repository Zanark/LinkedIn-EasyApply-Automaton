from __future__ import annotations

from pathlib import Path

import yaml

from linkedin_easy_apply.answers.dynamic_resume import DynamicResumeBuilder, _keyword_in
from linkedin_easy_apply.config.models import (
    ResumeBuilderConfig,
    ResumeBuilderMode,
    ResumeClusterConfig,
)
from linkedin_easy_apply.jobs.models import Job

_AI = ResumeClusterConfig(
    key="ai",
    keywords=["ai", "ml", "machine learning", "llm"],
    title="AI/ML Engineer",
    skills_order=["Data & AI", ".NET & Backend"],
    compact=True,
    condense_older=True,
    include_awards=False,
)
_BACKEND = ResumeClusterConfig(
    key="backend",
    keywords=["backend", ".net", "c#"],
    title="Backend Engineer",
    skills_order=[".NET & Backend", "Cloud & DevOps"],
)


def _fake_builder(dirpath: Path, categories=("Data & AI", ".NET & Backend")) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "render.py").write_text("# fake\n", encoding="utf-8")
    master = {
        "basics": {"name": "Test User", "title": "Engineer"},
        "skills": [{"category": c} for c in categories],
    }
    (dirpath / "master.example.yaml").write_text(yaml.safe_dump(master), encoding="utf-8")
    return dirpath


def _builder(tmp_path, **overrides) -> DynamicResumeBuilder:
    bpath = _fake_builder(tmp_path / "builder")
    rdir = tmp_path / "resumes"
    rdir.mkdir(parents=True, exist_ok=True)
    cfg = ResumeBuilderConfig(enabled=True, path=bpath, clusters=[_AI, _BACKEND], **overrides)
    return DynamicResumeBuilder(cfg, resume_dir=rdir, ai=None)


# -- keyword boundary matching -------------------------------------------------
def test_keyword_boundaries():
    assert _keyword_in("ai", "senior ai engineer")
    assert _keyword_in("ai", "ai/ml specialist")  # punctuation is a boundary
    assert not _keyword_in("ai", "email marketing")  # not inside a word
    assert not _keyword_in("ai", "training program")
    assert _keyword_in(".net", "strong .net backend")
    assert _keyword_in("c#", "c# developer")


# -- config parsing ------------------------------------------------------------
def test_config_parses_builder_block():
    cfg = ResumeBuilderConfig.model_validate(
        {
            "enabled": True,
            "path": "C:/tools/builder",
            "mode": "ai",
            "clusters": [
                {"key": "ai", "keywords": ["AI", "ML"], "title": "AI Eng"},
            ],
        }
    )
    assert cfg.enabled is True
    assert cfg.mode is ResumeBuilderMode.AI
    assert cfg.clusters[0].keywords == ["ai", "ml"]  # lower-cased by validator


# -- cluster detection ---------------------------------------------------------
def test_detect_cluster_title_weighted(tmp_path):
    drb = _builder(tmp_path)
    job = Job(url="u", title="Senior AI Engineer", description="build ml pipelines")
    match = drb._detect_cluster(job)
    assert match is not None
    cluster, score = match
    assert cluster.key == "ai"
    # "ai" in title -> title_weight(3); "ml" in desc -> 1; total 4
    assert score == 4


def test_detect_cluster_none_when_no_match(tmp_path):
    drb = _builder(tmp_path)
    job = Job(url="u", title="Marketing Manager", description="brand strategy")
    assert drb._detect_cluster(job) is None


def test_min_score_gate(tmp_path):
    drb = _builder(tmp_path, min_score=5)  # AI job scores 4 < 5
    job = Job(url="u", title="AI Engineer", description="ml")
    assert drb._detect_cluster(job) is None


# -- command construction ------------------------------------------------------
def test_build_command_maps_flags(tmp_path):
    drb = _builder(tmp_path)
    emphasis = drb._emphasis_from_cluster(_AI, reason="x")
    cmd = drb._build_command(emphasis)
    assert cmd[1].endswith("render.py")
    assert cmd[2] == "tailor"
    assert "--title" in cmd and "AI/ML Engineer" in cmd
    so = cmd.index("--skills-order")
    assert cmd[so + 1] == "Data & AI,.NET & Backend"
    assert "--compact" in cmd
    assert "--no-awards" in cmd  # include_awards False
    assert "--condense-older" in cmd
    assert "--out-dir" in cmd


def test_default_filename_from_master(tmp_path):
    drb = _builder(tmp_path)
    assert drb._default_filename("ai") == "Test_User_ai.pdf"


# -- end-to-end with a stubbed subprocess -------------------------------------
def test_tailor_for_and_cache(tmp_path, monkeypatch):
    drb = _builder(tmp_path)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> bool:
        calls.append(cmd)
        name = cmd[cmd.index("--name") + 1]
        (drb._resume_dir / name).write_bytes(b"%PDF-1.4 fake")
        return True

    monkeypatch.setattr(drb, "_run_builder", fake_run)

    job1 = Job(url="u1", title="AI Engineer", description="ml systems")
    job2 = Job(url="u2", title="Machine Learning Engineer", description="ai models")

    c1 = drb.tailor_for(job1)
    c2 = drb.tailor_for(job2)  # same 'ai' cluster -> cached, no second render

    assert c1 is not None and c1.name == "Test_User_ai.pdf"
    assert "tailored" in c1.reason
    assert c2 is c1  # cache returns the identical object
    assert len(calls) == 1  # rendered once for the whole run


def test_tailor_for_returns_none_on_render_failure(tmp_path, monkeypatch):
    drb = _builder(tmp_path)
    monkeypatch.setattr(drb, "_run_builder", lambda cmd: False)
    job = Job(url="u", title="AI Engineer", description="ml")
    assert drb.tailor_for(job) is None


def test_disabled_when_builder_missing(tmp_path):
    cfg = ResumeBuilderConfig(enabled=True, path=tmp_path / "nope", clusters=[_AI])
    drb = DynamicResumeBuilder(cfg, resume_dir=tmp_path / "resumes", ai=None)
    assert drb.enabled is False
    assert drb.tailor_for(Job(url="u", title="AI Engineer")) is None


def test_disabled_when_not_enabled(tmp_path):
    bpath = _fake_builder(tmp_path / "builder")
    cfg = ResumeBuilderConfig(enabled=False, path=bpath, clusters=[_AI])
    drb = DynamicResumeBuilder(cfg, resume_dir=tmp_path / "resumes", ai=None)
    assert drb.enabled is False
