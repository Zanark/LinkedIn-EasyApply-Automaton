from __future__ import annotations

import pytest

from linkedin_easy_apply.config import ConfigError, load_config
from linkedin_easy_apply.config.models import AppConfig, BrowserEngine


def _write(tmp_path, text: str):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_minimal_config_uses_defaults(tmp_path):
    path = _write(tmp_path, "jobs:\n  max_per_run: 3\n")
    config = load_config(path)
    assert isinstance(config, AppConfig)
    assert config.jobs.max_per_run == 3
    assert config.browser.engine is BrowserEngine.CHROME
    assert config.logging.level == "INFO"


def test_env_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_PROFILE", "/tmp/profile")
    path = _write(tmp_path, "browser:\n  profile_path: ${MY_PROFILE}\n")
    config = load_config(path)
    assert str(config.browser.profile_path).replace("\\", "/").endswith("/tmp/profile")


def test_env_expansion_default(tmp_path):
    path = _write(tmp_path, "logging:\n  level: ${LEA_LEVEL:-DEBUG}\n")
    config = load_config(path)
    assert config.logging.level == "DEBUG"


def test_invalid_search_url_raises(tmp_path):
    path = _write(
        tmp_path, "search:\n  searches:\n    - name: x\n      url: https://example.com/jobs\n"
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_raises():
    with pytest.raises(ConfigError):
        load_config("does-not-exist.yaml")


def test_unknown_top_level_key_forbidden(tmp_path):
    path = _write(tmp_path, "unexpected: 1\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_scoring_rules_lowercased(tmp_path):
    path = _write(
        tmp_path,
        "scoring:\n  threshold: 10\n  rules:\n    - {keyword: BackEnd, weight: 20}\n",
    )
    config = load_config(path)
    assert config.scoring.rules[0].keyword == "backend"
