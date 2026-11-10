"""Open a fresh browser and send every pending free connection invitation.

:class:`ConnectionInviteService` is the orchestration half of the connection-note
microservice. It:

1. loads the pending invites from the database (rows that have a profile URL and a
   note but neither an invitation nor a note marked sent),
2. de-duplicates them by profile URL,
3. opens a **fresh** :class:`BrowserManager` (the apply run's browser has already
   closed by the time this runs, which is exactly the "close the window, open it
   again" behaviour we want - a clean session just for connecting),
4. paces itself with a randomised human-like delay between invites, and
5. records invitation delivery separately from actual note delivery so a plain
   invitation is not retried or falsely displayed as a delivered note.

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
from linkedin_easy_apply.progress import Metric, ProgressReporter


@dataclass(slots=True)
class ConnectSummary:
    """Tally of a connection-invitation pass."""

    total: int = 0  # pending invites considered (after de-dup + cap)
    sent: int = 0  # invitations sent (or, in dry-run, would-be sent)
    already: int = 0  # already connected / pending
    skipped: int = 0  # no Connect button or no note field
    failed: int = 0  # errors
    limit_reached: bool = False  # LinkedIn weekly invite limit hit -> stopped early
    dry_run: bool = False
    sent_without_note: int = 0  # subset of sent, including would-send in dry-run


class ConnectionInviteService:
    """Send pending invitations, one fresh browser session for the whole pass."""

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        *,
        dry_run: bool | None = None,
        connector: ProfileConnector | None = None,
        sleeper: Callable[[float], None] | None = None,
        browser_factory: Callable[[], Any] | None = None,
        progress: ProgressReporter | None = None,
    ) -> None:
        self._config = config
        self._db = db
        self._progress = progress or ProgressReporter()
        cfg = config.outreach
        self._dry_run = cfg.connect_dry_run if dry_run is None else dry_run
        self._max = max(0, cfg.connect_max_per_run)
        self._min_delay = max(0.0, cfg.connect_min_delay_seconds)
        self._max_delay = max(self._min_delay, cfg.connect_max_delay_seconds)
        self._connector = connector or ProfileConnector(
            dry_run=self._dry_run, allow_without_note=cfg.connect_without_note
        )
        self._sleep = sleeper or time.sleep
        self._browser_factory = browser_factory or (lambda: BrowserManager(config.browser))
        # Rows sharing one profile URL (same recruiter reached via two jobs) are
        # invited once but ALL of them are marked sent, so none stays stuck pending.
        self._ids_by_key: dict[str, list[int]] = {}

    def run(self, run_id: int | None = None, *, limit: int | None = None) -> ConnectSummary:
        """Send pending invitations (optionally scoped to *run_id*)."""
        self._progress.activity("loading_connections")
        cap = limit if limit is not None else (self._max or None)
        targets = self._load_targets(run_id, cap)
        summary = ConnectSummary(total=len(targets), dry_run=self._dry_run)
        self._progress.connections(len(targets), dry_run=self._dry_run)
        if not targets:
            logger.info("Connect: no pending connection invitations to send")
            return summary
        logger.info(
            "Connect: sending {} connection invitation(s){}",
            len(targets),
            " [dry-run]" if self._dry_run else "",
        )
        try:
            self._progress.activity("starting_browser")
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
            self._progress.activity("connecting")
            outcome = self._connector.send_invite(browser.page, target)
            self._tally(outcome, target, summary)
            if outcome is ConnectOutcome.LIMIT_REACHED:
                summary.limit_reached = True
                logger.warning("Connect: stopping early - weekly invitation limit reached")
                break

    def _tally(
        self, outcome: ConnectOutcome, target: InviteTarget, summary: ConnectSummary
    ) -> None:
        metrics: dict[ConnectOutcome, Metric] = {
            ConnectOutcome.SENT: "connect_sent",
            ConnectOutcome.SENT_WITHOUT_NOTE: "connect_sent",
            ConnectOutcome.DRY_RUN: "connect_dry_runs",
            ConnectOutcome.DRY_RUN_WITHOUT_NOTE: "connect_dry_runs",
            ConnectOutcome.ALREADY: "connect_already",
            ConnectOutcome.NO_BUTTON: "connect_skipped",
            ConnectOutcome.NOTE_UNAVAILABLE: "connect_skipped",
            ConnectOutcome.FAILED: "connect_failed",
        }
        increments: dict[Metric, int] = {"connect_processed": 1}
        if outcome in metrics:
            increments[metrics[outcome]] = 1
        self._progress.increment(increments)
        if outcome in (
            ConnectOutcome.SENT,
            ConnectOutcome.SENT_WITHOUT_NOTE,
            ConnectOutcome.DRY_RUN,
            ConnectOutcome.DRY_RUN_WITHOUT_NOTE,
        ):
            summary.sent += 1
            without_note = outcome in (
                ConnectOutcome.SENT_WITHOUT_NOTE,
                ConnectOutcome.DRY_RUN_WITHOUT_NOTE,
            )
            summary.sent_without_note += int(without_note)
            if outcome in (ConnectOutcome.SENT, ConnectOutcome.SENT_WITHOUT_NOTE):
                ids = self._ids_by_key.get(self._dedup_key(target.profile_url), [target.id])
                self._db.mark_outreach_invitation_sent(ids, with_note=not without_note)
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
        self._progress.activity("pausing")
        logger.debug("Connect: pausing {:.1f}s before next invite", delay)
        self._sleep(delay)
