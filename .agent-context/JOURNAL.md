# LinkedIn-EasyApply-Automaton journal

> Newest at top.

## 2026-10-29 - Root cause found and discovery repaired: LinkedIn rebuilt the jobs UI

Ran the CLI live. The failure was NOT the one guessed earlier. LinkedIn shipped a rebuilt jobs UI:
`/jobs/search/` redirects to `/jobs/search-results/?currentJobId=<id>`; class names are now
build-generated hashes (`ajrhc3`, `ajrk8d`); **no** `data-job-id`/`data-occludable-job-id`/
`data-entity-urn` anywhere; cards are `<button>` not `<a>`; and the detail pane has **no `h1`**.
Only the selected job has a `/jobs/view/` link, which is why the link fallback returned exactly one
id and the extractor produced `? @ ? (?)` and `[SCORE FAIL] 0/10` on everything.

Not a block and not a logout - the page renders 25 jobs; probes proved the content is reachable
through ARIA. Repaired by adding an accessible-name strategy alongside the id strategy (whichever
finds more cards wins, so both builds work): cards = buttons matching `Dismiss .+ job` whose own
`aria-label` does not start with "Dismiss"; ids read from `currentJobId` after clicking;
title/company from `document.title` ("<title> | <company> | LinkedIn"); description from the
"About the job" heading's container; location parsed from the card text before it is clicked.

Verified live: 25 cards collected, `Full Stack Engineer @ Deloitte (Hyderabad)` scoring 80/10 with a
real keyword breakdown and a matched resume. 497 tests pass (18 new). The Easy Apply **modal** has
not been examined and is likely broken the same way - that is the next piece.

## 2026-10-28 - Work location reconciled against this checkout

While verifying the new store, `git status` in this checkout showed ` M forms/selectors.py`,
` M jobs/search.py` and `?? tests/test_job_discovery.py`. SHA-256 comparison confirms all three are
**byte-identical** to the worktree versions - the scan-discovery fix is already here, uncommitted.
The scoring switch and the GUI are **not**: `config/models.py` and `cli/main.py` differ and there is
no `linkedin_easy_apply/gui/` package. STATE.md corrected to record exactly which workstream survives
the worktree and which does not, rather than the blanket "all three are only in the worktree" it
originally claimed.

## 2026-10-28 - Base registered with Context Mesh

User asked whether the context refresh had picked up the day's work. It had not, and the re-run
confirmed it: identical output (28 contexts / 421 nodes / 424 edges, byte-identical files). Two
concrete causes found in `context-network\config.json` - this project is in none of the 17 `roots`,
and `sessionStateRoot` points at the Copilot **CLI** store (`C:\Users\mishrad\.copilot\session-state`,
425 sessions) while this chat lives under `...\CopilotCodingHome\<hash>\session-state\` (22 sessions),
which is never scanned. Verified the session id is absent from `artifact-cache.json`. User chose to
register this base here in the durable checkout, explicitly **without** a `.gitignore` entry (sibling
bases ignore theirs). Store created and root registered; the `sessionStateRoot` decision is still open.

## 2026-10-28 - Desktop GUI delivered with both themes

Built `linkedin_easy_apply/gui/` and wired `apply.py gui`. Five pages (Run, Configuration, Answers,
Data, Tools) over a sidebar; every control resolves to an `apply.py` command that is echoed before it
runs. Live log streaming through `QProcess` with a working Stop, tri-state outreach checkbox, guarded
live-apply confirmation, YAML editors that validate through `AppConfig` before saving, and a detached
launcher for the Streamlit dashboard so it survives the window closing. DeepSeaFoam and Harbor
Daylight transcribed as semantic roles into `gui/theme.py`.

Verification: 479 tests passing (74 new Qt-free GUI tests, 8 Qt widget tests); an offscreen smoke run
that walked all five pages, applied both themes and executed a **real** child process end to end; and
a pixel audit of rendered screenshots showing exactly the published palette values. The audit also
caught a genuine bug - log lines kept their original ink across a theme switch, leaving DeepSeaFoam's
`#93A1A1` on Harbor Daylight paper at about 2.2:1. Fixed by storing `(text, role)` pairs and
repainting the backlog; re-measured leak 0.000%, with a regression test. PySide6 6.12.0 installed into
`.venv` with explicit approval. The window has still never been shown on a real display.

## 2026-10-28 - Score-enforcement switch added

Added `ScoringConfig.enforce` (default `True`) plus `--ignore-score` on `apply` and `reapply`, so the
keyword score can be computed, logged and stored without gating the run. Hard gates are untouched and
still run first. Documented in `docs/configuration.md` ("Ignoring the score"), `docs/faq.md` and
`configs/config.example.yaml`; four tests cover enforced-skip, non-enforced pass-through, the score
still being recorded, and the default.

Also answered how scoring works: a linear weighted-keyword model summed over title + description and
compared to an inclusive threshold, with negative weights acting as vetoes. Noted that `threshold: 0`
is not equivalent to disabling scoring while penalties exist.

## 2026-10-28 - Zero-result scan diagnosed and discovery hardened

A `scan` run reported "Collected 0 job id(s)" for two searches that visibly return jobs in a browser.
Traced the exact bail-out: `_collect_ids` → `_current_ids` → `first_group(page, JOB_CARD)` matched
nothing, then three stagnant scroll rounds ended the crawl after roughly six seconds of in-page
waiting. Every DOM helper swallows exceptions, so the run could not distinguish stale selectors from a
sign-in wall from a page that had not rendered.

Hardened discovery (wait-for-results, four id shapes, link-level fallback, inner-pane scrolling) and
made the zero path self-reporting: page URL/title, per-selector match counts, frame count, and a
screenshot + HTML dump to `logs/diagnostics/`. 16 new tests. **The root cause remains unconfirmed** -
the next real run is what identifies it.

## 2026-10-28 - Base created

Registered `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton` as a Context Mesh base and seeded this
four-file store from the session's verified work. No prior store existed, so nothing was reconciled or
carried over; all history above was established in this session.
