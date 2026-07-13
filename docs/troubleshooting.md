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
real filenames, and set a `resume.default` as a safety net.

## The form filled but never submitted

That's the point of dry-run. If you want real submissions, drop `--dry-run` and
ensure `run.dry_run: false`. With `--interactive`, confirm at the prompt.

## It stops mid-application on an unknown question

Expected when `run.pause_on_unknown_question: true`. Answer at the prompt (it's
remembered for next time), or run non-interactively with `--yes` to auto-skip.

## Logs and screenshots

- Logs: `logs/` (rotation/retention configurable under `logging`).
- Screenshots: `screenshots/` (per-step and on-error; toggle under
  `screenshots`). These are the fastest way to see what the page looked like when
  something failed.
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
