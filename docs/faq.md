# FAQ

### Does this store my LinkedIn password?

No. The tool **never** asks for, types, or stores credentials. You log in to
LinkedIn once in the browser profile referenced by `browser.profile_path`, and
the automaton reuses that already-authenticated session via Playwright's
persistent context.

### Will this get my account banned?

Automating LinkedIn is against their Terms of Service and carries real risk. The
tool ships with conservative defaults (`max_per_run`, `max_per_company`,
`max_daily`, optional pauses) to keep volume human-like, but **use it at your
own risk**. Start with `scan` and `--dry-run`. See the disclaimer in the README.

### How do I try it safely first?

1. `lea scan` — discovers and scores jobs, writes nothing to LinkedIn.
2. `lea apply --dry-run` — fills every field but never clicks the final submit.
3. `lea apply --interactive` — asks you to confirm before each submission.

### Is AI required?

No. AI is disabled by default and entirely optional. With `ai.enabled: false`
the flow is 100% deterministic. When enabled, AI only *advises* (match score,
missing skills, a recommendation); it can never submit an application.

### What happens when it hits a question it doesn't recognise?

By default (`run.pause_on_unknown_question: true`) it pauses and asks you for the
answer, then **remembers it** in the database for future runs. With `--yes` /
non-interactive mode, unknown questions are skipped and the step is recorded.

### How does it pick which resume to upload?

In order: an explicit `resume.mapping` match (role/keyword → filename), then
filename-keyword overlap with the job text, then `resume.default`. See
`docs/configuration.md`.

### How do I control which jobs it applies to?

Combine `scoring.rules` + `scoring.threshold` with the `jobs` filters
(`include_keywords`, `exclude_keywords`, `blacklist_companies`,
`whitelist_companies`). Use `lea scan` to see scores before applying.

### Where is my data stored?

Locally only. A SQLite database (`database.path`) records jobs, applications,
questions/answers, AI results and errors. Nothing is sent anywhere except
LinkedIn itself (and your AI provider, if you explicitly enable one).

### Can I run it headless?

Yes — set `browser.headless: true`. Keep it headed the first few runs so you can
watch what it does and intervene if needed.

### Which browsers are supported?

Chrome, Edge, and bundled Chromium (`browser.engine`). For Chrome/Edge the
matching browser must be installed; for `chromium`, run
`playwright install chromium` once.

### How do I see stats / export results?

`lea stats` prints a summary table. `lea export --format csv` (or `xlsx`, which
needs the `.[export]` extra) writes applications joined with jobs. `lea
dashboard` launches an optional Streamlit UI (needs the `.[dashboard]` extra).

See [`troubleshooting.md`](troubleshooting.md) if something isn't working.
