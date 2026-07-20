# Troubleshooting

## Browser won't launch

**`BrowserLaunchError: Playwright is not installed`**
Install Playwright and (for bundled Chromium) its browser binaries:
```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
```

**`Failed to launch browser 'edge'` / profile is locked**
The profile can only be used by one process at a time. Close every window of
that browser (and check Task Manager for stray processes), then retry. Or point
`browser.profile_path` at a **dedicated** profile directory used only by the
automaton.

**Edge/Chrome not found**
`engine: edge` needs Edge installed; `engine: chrome` needs Chrome. If you don't
have either, use `engine: chromium` and run `playwright install chromium`.

## "Not logged in" / redirected to the login page

The tool never logs in for you. Sign in once with the `login` command, which
opens the browser and waits while you authenticate:
```powershell
.\.venv\Scripts\python.exe apply.py login
```
Sign in, press Enter to save the session, then verify it with:
```powershell
.\.venv\Scripts\python.exe apply.py test-browser
```
Keep that profile path in `config.yaml` and stay logged in.

## No jobs are found

- Verify each `search.url` still returns results in a normal browser and that the
  **Easy Apply** filter (`f_AL=true`) is applied.
- Make sure at least one search has `enabled: true`.
- LinkedIn markup changes over time; if extraction returns nothing, update the
  selectors in `linkedin_easy_apply/forms/selectors.py`.

## Jobs are found but all get skipped

Check the run summary and logs for the skip reason:

| Reason                    | Fix                                                        |
| ------------------------- | ---------------------------------------------------------- |
| below scoring threshold   | Lower `scoring.threshold` or adjust `scoring.rules`.       |
| already applied           | Working as intended (URL / company-role dedupe).           |
| excluded / not included   | Review `jobs.include_keywords` / `exclude_keywords`.       |
| blacklisted / whitelist   | Review `jobs.blacklist_companies` / `whitelist_companies`. |
| per-company / daily limit | Raise `jobs.max_per_company` / `max_daily`.                |
| AI advised against         | Inspect the `ai_results` table; set `ai.enabled: false`.   |

Use `lea scan` to see scores without applying.

## I pressed Ctrl+C mid-run

That's safe. Ctrl+C exits cleanly even at an interactive prompt: the current
Easy Apply modal is discarded, the in-flight application is marked `aborted`,
the browser closes, orphan screenshots are cleaned up, and the normal summary
table is printed instead of a stack trace.

## A question was answered wrong (or skipped)

Diagnose a single question offline:
```powershell
.\.venv\Scripts\python.exe apply.py test-form "How many years of experience do you have with Java?"
```
This prints the recognised category, detected skill, answer type, confidence and
resolved answer. If it's wrong:
- Add or fix the value in `configs/answers.yaml` (remember skills + aliases).
- If the *category* is wrong, extend the parser (see `developer_guide.md`).
- Tune `answers.fuzzy_threshold` if fuzzy matching is too strict/loose.

## Wrong resume (or none) selected

```powershell
.\.venv\Scripts\python.exe apply.py resume-test "Senior Backend Engineer" -d "Java, AWS"
```
Ensure the files exist in `resume.directory`, that `resume.mapping` values are
real filenames, and set a `resume.default` as a safety net. During the form run,
the tool first checks the resume cards LinkedIn already lists in the modal,
selects a matching filename if present, and uploads only when that card is
missing. With `-v`, look for resume-card detection and upload/select log lines
to see whether LinkedIn showed the expected card or exposed a file input.

## The form filled but never submitted

That's the point of dry-run. If you want real submissions, drop `--dry-run` and
ensure `run.dry_run: false`. With `--interactive`, confirm at the prompt.

## It stops mid-application on an unknown question

Expected when `run.pause_on_unknown_question: true`. Either answer at the
prompt, or fill the field on the LinkedIn page and press Enter so the tool reads
that value back. The final answer is remembered for next time. Run
non-interactively with `--yes` to auto-skip instead.

## Reading the logs

Every line in `logs/easy_apply_<date>.log` has four pipe-delimited fields:

```
2026-07-13 21:09:16.805 | DEBUG    | linkedin_easy_apply.answers.resolver:resolve:131 - Resolve phone -> '+91-…' (from answers key 'phone')
└── timestamp (ms) ───┘   └ level ┘   └──── source: module:function:line ────┘   └───────────── message ─────────────┘
```

- **timestamp** — millisecond precision, so you can measure the gap between steps
  (e.g. a 30 000 ms gap before a click error = a Playwright timeout).
- **level** — `DEBUG` (the tool's internal "brain": every field parsed, resolved,
  filled), `INFO` (the readable narrative: job headers, skip/fill decisions, step
  transitions), `WARNING` (recoverable, e.g. résumé not found), `ERROR` (a failure).
  `-v` / `logging.level: DEBUG` turns on the DEBUG stream.
- **source** `module:function:line` — the exact code that emitted the line. This
  doubles as a **pipeline map**: `orchestrator:_process_job` (job header + skip),
  `forms.detector:detect` (what fields it saw), `answers.resolver:resolve` (where
  an answer came from), `forms.filler:*` (fill result), `forms.easy_apply:apply`
  (step transitions).
- **message** — the human/DEBUG text.

**Trace one field end-to-end** by reading top-to-bottom: *detected → understood
as (confidence) → resolved from (which `answers.yaml` key) → fill result*. The
full run walkthrough is in [`run-lifecycle.md`](run-lifecycle.md).

> **Records ≠ lines.** `ERROR` entries include a Playwright `Call log:` block that
> spans many raw lines, so filter by the `| ERROR |` prefix, not by line number.
> One dated file is **append-only across every run that day**.

Handy queries:

```powershell
# just the human narrative (skip DEBUG)
Select-String logs\easy_apply_2026-07-13.log -Pattern '\| (INFO|WARNING|ERROR)\s+\|'
# everything the resolver decided
Select-String logs\easy_apply_2026-07-13.log -Pattern 'resolver:resolve'
# the scoring math for every job
Select-String logs\easy_apply_2026-07-13.log -Pattern 'Scored'
# every job that passed or failed the score gate (aligned INFO column)
Select-String logs\easy_apply_2026-07-13.log -Pattern '\[SCORE PASS\]|\[SCORE FAIL\]'
# what got filled vs left blank
Select-String logs\easy_apply_2026-07-13.log -Pattern 'filled with|left blank'
```

## Logs and screenshots

- Logs: `logs/` (rotation/retention configurable under `logging`).
- Screenshots: `screenshots/` (per-step and on-error; toggle under
  `screenshots`). By default `screenshots.cleanup: true` deletes unreferenced
  step/unknown screenshots at the end of a run and keeps application evidence
  such as after-submit or aborted-state screenshots. Set it to `false` when you
  want every capture for debugging.
- The quickest way to see everything the tool is doing is the global `-v` /
  `--verbose` flag (before the command), e.g.
  `.\.venv\Scripts\python.exe apply.py -v apply --dry-run` — it forces `DEBUG`
  and narrates every field (parsed category, resolved answer + its source, and
  fill/skip outcome). Make it permanent with `logging.level: DEBUG`.
- For deep debugging also set `browser.headless: false` and a small
  `browser.slow_mo_ms` (e.g. `250`) to watch each action.

## Quality gates fail after my changes

```powershell
.\.venv\Scripts\ruff.exe check . --fix
.\.venv\Scripts\black.exe .
.\.venv\Scripts\mypy.exe linkedin_easy_apply
.\.venv\Scripts\python.exe -m pytest
```
