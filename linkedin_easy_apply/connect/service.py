"""Open a fresh browser and send every pending free connection invitation.

:class:`ConnectionInviteService` is the orchestration half of the connection-note
microservice. It:

1. loads the pending invites from the database (rows that have a profile URL and a
   note but whose ``note_sent_at`` is still NULL),
2. de-duplicates them by profile URL,
3. opens a **fresh** :class:`BrowserManager` (the apply run's browser has already
   closed by the time this runs, which is exactly the "close the window, open it
   again" behaviour we want - a clean session just for connecting),
4. paces itself with a randomised human-like delay between invites, and
5. marks each successfully sent note via ``mark_outreach_note_sent`` so it is
   never sent twice and the dashboard strikes it through.

Everything the browser touches lives in :mod:`connect.connector`, so this class is
fully unit-testable with a fake connector + browser factory.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from linkedin_easy_apply.browser import BrowserLaunchError, BrowserManager
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.connect.connector import ConnectOutcome, InviteTarget, ProfileConnector
from linkedin_easy_apply.database import Database


@dataclass(slots=True)
class ConnectSummary:
    """Tally of a connection-note pass."""

    total: int = 0  # pending invites considered (after de-dup + cap)
    sent: int = 0  # notes sent (or, in dry-run, would-be sent)
    already: int = 0  # already connected / pending
    skipped: int = 0  # no Connect button or no note field
    failed: int = 0  # errors
    limit_reached: bool = False  # LinkedIn weekly invite limit hit -> stopped early
    dry_run: bool = False


class ConnectionInviteService:
    """Send pending connection notes, one fresh browser session for the whole pass."""

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        *,
        dry_run: bool | None = None,
        connector: ProfileConnector | None = None,
        sleeper: Callable[[float], None] | None = None,
        browser_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._config = config
        self._db = db
        cfg = config.outreach
        self._dry_run = cfg.connect_dry_run if dry_run is None else dry_run
        self._max = max(0, cfg.connect_max_per_run)
        self._min_delay = max(0.0, cfg.connect_min_delay_seconds)
        self._max_delay = max(self._min_delay, cfg.connect_max_delay_seconds)
        self._connector = connector or ProfileConnector(dry_run=self._dry_run)
        self._sleep = sleeper or time.sleep
        self._browser_factory = browser_factory or (lambda: BrowserManager(config.browser))
        # Rows sharing one profile URL (same recruiter reached via two jobs) are
        # invited once but ALL of them are marked sent, so none stays stuck pending.
        self._ids_by_key: dict[str, list[int]] = {}

    def run(self, run_id: int | None = None, *, limit: int | None = None) -> ConnectSummary:
        """Send every pending connection note (optionally scoped to *run_id*)."""
        cap = limit if limit is not None else (self._max or None)
        targets = self._load_targets(run_id, cap)
        summary = ConnectSummary(total=len(targets), dry_run=self._dry_run)
        if not targets:
            logger.info("Connect: no pending connection notes to send")
            return summary
        logger.info(
            "Connect: sending {} connection note(s){}",
            len(targets),
            " [dry-run]" if self._dry_run else "",
        )
        try:
            with self._browser_factory() as browser:
                self._process(browser, targets, summary)
        except BrowserLaunchError as exc:
            logger.error("Connect: could not launch browser: {}", exc)
        return summary

    # -- internals ------------------------------------------------------------
    @staticmethod
    def _dedup_key(url: str) -> str:
        return url.split("?")[0].rstrip("/").lower()

    def _load_targets(self, run_id: int | None, cap: int | None) -> list[InviteTarget]:
        rows = self._db.pending_connection_invites(run_id, limit=cap)
        targets: list[InviteTarget] = []
        ids_by_key: dict[str, list[int]] = {}
        seen: set[str] = set()
        for row in rows:
            url = (row.get("profile_url") or "").strip()
            note = (row.get("note") or "").strip()
            if not url or not note:
                continue
            key = self._dedup_key(url)
            ids_by_key.setdefault(key, []).append(int(row["id"]))
            if key in seen:  # same person surfaced by two jobs - invite once
                continue
            seen.add(key)
            targets.append(
                InviteTarget(
                    id=int(row["id"]),
                    person_name=row.get("person_name"),
                    profile_url=url,
                    note=note,
                )
            )
        self._ids_by_key = ids_by_key
        return targets

    def _process(self, browser: Any, targets: list[InviteTarget], summary: ConnectSummary) -> None:
        for index, target in enumerate(targets):
            if index:  # human-like pause between invites (not before the first)
                self._pace()
            outcome = self._connector.send_invite(browser.page, target)
            self._tally(outcome, target, summary)
            if outcome is ConnectOutcome.LIMIT_REACHED:
                summary.limit_reached = True
                logger.warning("Connect: stopping early - weekly invitation limit reached")
                break

    def _tally(
        self, outcome: ConnectOutcome, target: InviteTarget, summary: ConnectSummary
    ) -> None:
        if outcome is ConnectOutcome.SENT:
            summary.sent += 1
            ids = self._ids_by_key.get(self._dedup_key(target.profile_url), [target.id])
            self._db.mark_outreach_note_sent(ids)
        elif outcome is ConnectOutcome.DRY_RUN:
            summary.sent += 1  # would-be sent; DB is deliberately left untouched
        elif outcome is ConnectOutcome.ALREADY:
            summary.already += 1
        elif outcome in (ConnectOutcome.NO_BUTTON, ConnectOutcome.NOTE_UNAVAILABLE):
            summary.skipped += 1
        elif outcome is ConnectOutcome.LIMIT_REACHED:
            pass  # not counted as a failure; the run just stops
        else:  # FAILED
            summary.failed += 1

    def _pace(self) -> None:
        if self._max_delay <= 0:
            return
        delay = random.uniform(self._min_delay, self._max_delay)
        logger.debug("Connect: pausing {:.1f}s before next invite", delay)
        self._sleep(delay)
