"""Downloads are declined by default; opt in via browser.accept_downloads.

LinkedIn re-serves the resume as a PDF "attachment" when it renders the Easy
Apply preview pane. With downloads accepted, Chromium saved those as stray
GUID files under ``download_dir``. We now decline downloads unless the user
explicitly enables them.
"""

from __future__ import annotations

import types

from linkedin_easy_apply.browser.manager import BrowserManager
from linkedin_easy_apply.config.models import BrowserConfig


def test_accept_downloads_defaults_false():
    assert BrowserConfig().accept_downloads is False


class _FakeContext:
    def __init__(self) -> None:
        self.pages = [object()]

    def set_default_timeout(self, *_):  # noqa: D401 - stub
        pass

    def set_default_navigation_timeout(self, *_):
        pass

    def close(self):
        pass


class _FakeLauncher:
    def __init__(self, recorder: dict) -> None:
        self._recorder = recorder

    def launch_persistent_context(self, **kwargs):
        self._recorder.update(kwargs)
        return _FakeContext()


class _FakePlaywright:
    def __init__(self, recorder: dict) -> None:
        self.chromium = _FakeLauncher(recorder)

    def stop(self):
        pass


def _install_fake_playwright(monkeypatch, recorder: dict) -> None:
    fake_pw = _FakePlaywright(recorder)
    starter = types.SimpleNamespace(start=lambda: fake_pw)
    import playwright.sync_api as sapi

    monkeypatch.setattr(sapi, "sync_playwright", lambda: starter)


def test_downloads_declined_by_default(monkeypatch, tmp_path):
    recorder: dict = {}
    _install_fake_playwright(monkeypatch, recorder)
    cfg = BrowserConfig(profile_path=tmp_path / "profile", download_dir=tmp_path / "dl")
    BrowserManager(cfg).start()
    assert recorder["accept_downloads"] is False
    assert recorder["downloads_path"] is None
    # The download directory is not created when downloads are declined.
    assert not (tmp_path / "dl").exists()


def test_downloads_accepted_when_opted_in(monkeypatch, tmp_path):
    recorder: dict = {}
    _install_fake_playwright(monkeypatch, recorder)
    dl = tmp_path / "dl"
    cfg = BrowserConfig(profile_path=tmp_path / "profile", download_dir=dl, accept_downloads=True)
    BrowserManager(cfg).start()
    assert recorder["accept_downloads"] is True
    assert recorder["downloads_path"] == str(dl)
    assert dl.exists()  # prepared eagerly when accepting downloads
