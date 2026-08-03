"""Render a plain-text report of drafted 'Meet the hiring team' outreach.

In the default ``draft`` outreach mode the tool never messages anyone during a
run: it reads each recruiter's name and LinkedIn profile URL from the page,
drafts a personalised message, and records it. This module turns those records
into a human-readable report the user works through by hand -- opening each
profile URL and sending the drafted message.

The renderer is a pure function (records in, text out) so it can be unit tested
without a browser or database.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

_SEP = "=" * 72
_SUB = "-" * 60


def render_outreach_report(
    drafts: Sequence[dict[str, Any]],
    *,
    run_id: int | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Render *drafts* into a plain-text outreach report.

    Each draft is a mapping with (any missing key is tolerated): ``person_name``,
    ``profile_url``, ``message``, ``note``, ``job_title``, ``job_company``,
    ``resume_name`` and ``resume_path``.
    """
    when = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    run = f"Run #{run_id}  |  " if run_id is not None else ""
    lines: list[str] = [
        _SEP,
        "HIRING-TEAM OUTREACH - MESSAGES TO SEND",
        f"{run}Generated {when}  |  {len(drafts)} contact(s)",
        _SEP,
    ]

    if not drafts:
        lines += ["", "No hiring-team recruiters were found to contact this run.", ""]
        return "\n".join(lines)

    lines += [
        "",
        "For each contact: send the short CONNECTION NOTE with your invite, then",
        "the full MESSAGE once they accept (open the profile URL to do both).",
    ]
    for index, draft in enumerate(drafts, start=1):
        name = (draft.get("person_name") or "Unknown").strip()
        url = (draft.get("profile_url") or "").strip()
        company = (draft.get("job_company") or "").strip()
        title = (draft.get("job_title") or "").strip()
        message = (draft.get("message") or "").strip()
        note = (draft.get("note") or "").strip()
        resume = (draft.get("resume_name") or "").strip()
        resume_path = (draft.get("resume_path") or "").strip()

        role = " @ ".join(part for part in (title, company) if part)
        lines += ["", f"[{index}] {name}"]
        if role:
            lines.append(f"    Applied to : {role}")
        lines.append(f"    Profile    : {url or '(profile URL not found)'}")
        if resume:
            attach = f"{resume}  ({resume_path})" if resume_path else resume
            lines.append(f"    Resume     : {attach}")
        # 1) The full message — send it once they accept your invite / reply.
        lines.append(f"    {_SUB}")
        lines.append("    MESSAGE (send once connected):")
        lines += [f"    {ln}" if ln else "" for ln in (message.splitlines() or [""])]
        lines.append(f"    {_SUB}")
        # 2) The short note — attach it to the free connection invitation (<=300).
        if note:
            lines.append(f"    CONNECTION NOTE ({len(note)}/300 chars, attach to invite):")
            lines += [f"    {ln}" if ln else "" for ln in note.splitlines()]
            lines.append(f"    {_SUB}")

    lines.append("")
    return "\n".join(lines)
