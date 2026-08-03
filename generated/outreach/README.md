# generated/outreach — hiring-team outreach reports

When post-apply outreach runs in the default `draft` mode, the automaton reads
each **Meet the hiring team** recruiter's name and LinkedIn profile URL from the
page, drafts two message variants, and — at the end of the run — writes a
plain-text report here named `outreach_run<run-id>_<timestamp>.txt`.

Each entry lists the recruiter's name, the job you applied to, their profile
URL, the résumé to attach, and **two** drafts: the full **MESSAGE** to send once
they connect, and a short **CONNECTION NOTE** (≤300 characters, with its live
character count) to attach to the free connection invitation. Open each profile,
send the note with your invite, then send the full message once they accept.
Nothing is ever sent automatically in `draft` mode.

Reports are **git-ignored** (they contain recruiter names and profile URLs);
this folder and README are kept so a fresh clone has the structure.

See `docs/configuration.md` (the `outreach` section) and
`linkedin_easy_apply/orchestrator.py` (`_emit_outreach_report`) for how this
path is wired.
