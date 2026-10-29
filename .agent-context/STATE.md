> **Last updated:** 2026-10-28 (Asia/Kolkata) - Scan-discovery hardening, scoring-enforcement switch and the PySide6 desktop GUI are implemented and tested, all uncommitted on a worktree branch.
> **Last context offload:** 2026-10-28T18:05:00+05:30

# LinkedIn-EasyApply-Automaton state

> **Base identity:** `LinkedIn-EasyApply-Automaton` is the LinkedIn Easy Apply automation workspace at `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton`.
>
> **Persona-continuity contract:** Resume as the same honest, concise Easy Apply automation engineering partner after reading this store. Preserve verified context and recorded uncertainty; do not promote a defensive fix into a confirmed root cause.

## Current focus

Three workstreams are **implemented and unit-tested, uncommitted everywhere, and never run against
live LinkedIn**. They were written in a Copilot worktree on branch `mishrad_MC-urban-chainsaw`
(branched from `f9a49a9 GUID added`) at
`C:\Users\mishrad\AppData\Local\Microsoft\Copilot\User Data\CopilotCodingHome\8c4037f52828161422d06a386e9d7712\copilot-worktrees\LinkedIn-EasyApply-Automaton\mishrad_MC-urban-chainsaw`.
**That worktree is disposable.**

Where each workstream actually lives, verified by SHA-256 on 2026-10-28:

| Workstream | This checkout | Worktree |
| --- | --- | --- |
| Scan discovery (`forms/selectors.py`, `jobs/search.py`, `tests/test_job_discovery.py`) | **present, byte-identical** (uncommitted: ` M`/`??`) | same |
| `scoring.enforce` / `--ignore-score` (`config/models.py`, `orchestrator.py`, `cli/main.py`, docs, `tests/test_scoring.py`) | **absent** | only copy |
| Desktop GUI (`linkedin_easy_apply/gui/`, 3 test files, `docs/gui.md`, `pyproject.toml`, `README.md`) | **absent** - no `gui/` package here | only copy |

So the scan fix survives the worktree being deleted; the other two do not. Re-verify rather than
trusting this table if time has passed.

1. **Scan returned 0 jobs - discovery hardened.** A `scan` run collected 0 job ids from two searches
   whose URLs showed jobs in a normal browser. Root cause is **not confirmed**; the change makes the
   failure self-reporting instead of silent.
2. **`scoring.enforce` / `--ignore-score`.** The score can now be recorded without gating the run.
3. **PySide6 desktop GUI.** `apply.py gui` - a window over the same CLI commands, themed with
   DeepSeaFoam (dark) and Harbor Daylight (light).

## Threads

### Scan discovery (implemented, unverified against LinkedIn)

- `forms/selectors.py`: `JOB_CARD` widened to the current virtualised list (`li[data-occludable-job-id]`),
  the older `div.job-card-container`, `li.scaffold-layout__list-item:has(a[href*='/jobs/view/'])`,
  `[data-job-id][class*='job-card']` and the logged-out `div.base-card[data-entity-urn*='jobPosting']`.
  Added `JOB_CARD_LINK`, `AUTH_WALL`, `NO_RESULTS`; `JOB_LIST_CONTAINER` gained `div.scaffold-layout__list`.
- `jobs/search.py`: fixed 2.5 s sleep replaced by `_wait_for_results()` (20 s for a card to attach);
  `job_id_from_value()` parses canonical, slugged and `urn:li:jobPosting:` forms; a link-level fallback
  reads every `/jobs/view/` href when no card selector matches; `_scroll_results_pane()` scrolls the
  **inner** results column because the window scrollbar never loads more cards; `_report_empty_results()`
  logs URL, title, per-selector match counts and frame count, then dumps a screenshot + HTML to
  `logs/diagnostics/`.
- Next real run should make the cause obvious from the log: sign-in wall, genuine no-results, or
  unknown markup (in which case fix `JOB_CARD` from the saved HTML).

### Scoring enforcement (implemented)

- `ScoringConfig.enforce: bool = True`. When false the score is still computed, logged and written to
  the `scores` table, but a below-threshold job is no longer skipped.
- `apply --ignore-score` / `reapply --ignore-score` set it for one run.
- Hard gates (`_pre_apply_checks`) are unaffected and still run first.

### Desktop GUI (implemented, smoke-tested offscreen)

- `linkedin_easy_apply/gui/`: `theme.py` and `commands.py` are Qt-free and unit-tested;
  `process.py` (QProcess), `widgets.py` and `main_window.py` need PySide6.
- Five pages: Run, Configuration, Answers, Data, Tools. Every button builds an `apply.py` command,
  echoes it to the log and runs it - there is no second implementation of any behaviour.
- The Streamlit dashboard is unchanged and reachable from both `apply.py dashboard` and the GUI's
  Data page (started detached, so it outlives the window).
- PySide6 6.12.0 was installed into `.venv` on 2026-10-28 with the user's explicit approval.

## Next steps

1. Decide how to commit the three workstreams (one commit or three) and whether to open a PR.
2. Run a real `scan` and read `logs/diagnostics/` - that is what actually identifies why discovery
   returned zero. Until then the fix is defensive, not proven.
3. Decide the Context Mesh `sessionStateRoot` question (see Open questions).

## Open questions

- ~~Why did the scan return 0 jobs?~~ **ANSWERED 2026-10-29 by a live run.** LinkedIn rebuilt the
  jobs UI with hashed class names, no id attributes and no `h1`; discovery was repaired with an
  accessible-name strategy. See the JOURNAL entry and `MEMORY.md` → "The 2026 LinkedIn rebuild".
- **Is the Easy Apply modal broken the same way?** Almost certainly - it relies on the same kind of
  class selectors - but it has **not** been examined. Checking it means opening a real application
  form. Nothing about submitting has been re-verified since the rebuild.
- **Commit shape** for the uncommitted branch is undecided.
- **Chat indexing gap.** Context Mesh `config.json` sets
  `sessionStateRoot = C:\Users\mishrad\.copilot\session-state` (the Copilot CLI store, 425 sessions).
  Sessions from the Copilot app live under
  `...\CopilotCodingHome\<hash>\session-state\` and are never scanned, so this work is absent from the
  Artifact Finder. The key holds a single string: repointing it would drop the 425 CLI sessions, and
  supporting both would mean editing the shared `build_context_mesh.py`. Awaiting a decision.
- **Persona registry row.** `context-offload/SKILL.md` says a new base should be added to its registry
  table. Not done - that file is a shared skill repo and the edit was not authorised.
- **GUI never shown on a real display.** It was built and exercised with `QT_QPA_PLATFORM=offscreen`
  only. No human has looked at the actual window.

## Environment reminders

- Interpreter: `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\.venv\Scripts\python.exe`
  (Python 3.13.14; pytest 9.1.1, playwright, streamlit 1.60, pandas 3.0.5, altair 6.2.2,
  PySide6 6.12.0).
- Run tests with `-B` and `PYTHONDONTWRITEBYTECODE=1` to avoid leaving `.pyc` files behind.
- **pytest's end-of-session tmpdir cleanup raises `OSError WinError 448` in sandboxed temp dirs**,
  which kills the terminal summary. Use a `tryfirst` `pytest_sessionfinish` plugin to print the tally,
  or read the progress dots. The tests themselves are unaffected.
- Full suite as of 2026-10-28: **479 passing, 0 failing**.
- `zmem` is installed but broken (`Cannot find module ...\node_modules\zmem\bin\zmem.js`), so
  `zmem read` cannot hydrate and Context Mesh indexes 0 memories.
- `.browser-profile` holds the signed-in LinkedIn session and must never be committed.
