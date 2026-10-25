"""Free LinkedIn connection-invitation microservice.

A small, self-contained subsystem (its own module, sharing the project's browser,
config and database) that opens a fresh browser after a run and sends each pending
recruiter a **free connection invitation** carrying their <=300-char note - never
the long message. Exposed both as an end-of-run hook the apply run can call and as
the standalone ``connect`` CLI command.
"""

from __future__ import annotations

from linkedin_easy_apply.connect.connector import (
    NOTE_CHAR_LIMIT,
    ConnectOutcome,
    InviteTarget,
    ProfileConnector,
)
from linkedin_easy_apply.connect.service import ConnectionInviteService, ConnectSummary

__all__ = [
    "NOTE_CHAR_LIMIT",
    "ConnectOutcome",
    "InviteTarget",
    "ProfileConnector",
    "ConnectionInviteService",
    "ConnectSummary",
]
