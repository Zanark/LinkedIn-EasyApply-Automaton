# Developer Guide

This project is a modular, testable automation framework. This guide explains
the architecture and how to extend it.

## Design principles

- **Single responsibility.** Each package does one thing; there is no god-object
  `main.py`. The `Orchestrator` only *coordinates* collaborators.
- **Configuration over code.** Behaviour is data-driven via Pydantic models; no
  magic strings or hardcoded limits.
- **Deterministic core, optional AI.** The apply flow is fully deterministic.
  AI is an optional *advisor* and can never submit on its own.
- **Never automate login.** The browser reuses an existing profile; credentials
  are never requested or stored.
- **Lazy Playwright.** Browser imports happen inside functions, so every
  pure-logic module (config, parser, scoring, answers, database) imports and
  unit-tests without a browser installed.

## Package layout

```
linkedin_easy_apply/
├── config/        Pydantic models + YAML loader (env expansion)
├── logging/       Loguru setup (console + rotating file)
├── database/      SQLite schema + repository (db.py, sql/schema.sql)
├── answers/       AnswerStore, AnswerResolver, ResumeSelector, DynamicResumeBuilder, CoverLetter
├── parser/        QuestionParser + QuestionCategory/AnswerType enums
├── scoring/       ScoringEngine (weighted keyword rules)
├── browser/       BrowserManager (persistent context)
├── forms/         detector, filler, matching, selectors, EasyApplyWorkflow
├── jobs/          Job model, JobExtractor, JobSearch
├── ai/            AIProvider ABC, Null/OpenAI providers, factory
├── dashboard/     optional Streamlit app
├── cli/           Typer CLI (main.py)
├── progress.py    strict Qt-free outcome snapshots and stream framing
├── utils/         text, retry, paths, screenshots
└── orchestrator.py  end-to-end flow
```

## The apply flow

`Orchestrator.run()` executes, per job:

```
discover → extract → upsert → pre-apply checks → score → select resume
        → (AI advise) → Easy Apply workflow → persist result → record answers
```

- **Pre-apply checks:** Easy Apply present, not already applied (URL + company/
  role dedupe), blacklist/whitelist, include/exclude keywords, per-company cap.
- **Scoring:** always recorded; gates the application on `scoring.threshold`.
- **AI advice:** a *soft* gate — only skips when the provider explicitly returns
  `should_apply = false`.
- **`scan` mode** stops before applying, so you can tune scoring/searches safely.

Limits enforced: `max_per_run` (in-memory counter), `max_per_company` and
`max_daily` (live database queries).

For a full stage-by-stage narrative (with the log lines emitted at each step and
the dry-run/scan stopping points), see [`run-lifecycle.md`](run-lifecycle.md).

## Logging conventions

Logging is centralised in `logging/setup.py` (Loguru; console → stderr, rotating
file → `logs/easy_apply_<date>.log`). Two levels carry meaning:

- **INFO** — the human-readable narrative: run/step headers, one line per field
  (`Field 'X' [kind] -> key: filled with '...' (source)` / `left blank`), and the
  submit vs dry-run/discard decision (`orchestrator`, `forms/easy_apply.py`).
- **DEBUG** — the internals: parse confidence (`parser`), which answer key each
  value resolved from (`answers/resolver.py`), every detected field + its options
  (`forms/detector.py`), option/match results (`forms/filler.py`) and job
  extraction (`jobs/extractor.py`).

The global `-v` / `--verbose` flag (see the `@app.callback` in `cli/main.py`)
forces `DEBUG` for a run. When adding behaviour, log a concise **INFO** line for
the decision and **DEBUG** for the "why" (inputs, candidates, chosen value).

## Extending the system

### Add a recognised question category

1. Add a member to `QuestionCategory` in `parser/categories.py` and its default
   type to `DEFAULT_ANSWER_TYPE`.
2. Add high-precision keyword rules in `QuestionParser._apply_rules` and/or
   representative phrases in `_PHRASES` for the fuzzy fallback.
3. Map it to answer-store keys in `answers/resolver.py` (`_FIELD_MAP` for text/
   number, `_BOOL_MAP` for yes/no).
4. Add a case to `tests/test_parser.py` and `tests/test_answers.py`.

### Add a scoring rule

No code needed — add to `scoring.rules` in `config.yaml`. Weights may be
negative to penalise unwanted roles. See
[`configuration.md` → scoring](configuration.md#scoring) for the full scoring
algorithm (matching modes, breakdown, worked examples).

### Add a new AI provider

1. Subclass `AIProvider` (`ai/provider.py`) and implement `advise(...)` returning
   an `AIResult`.
2. Register it in `ai/factory.build_provider` and extend `AIProviderName`.
Providers must remain advisory — never submit.
To let a provider drive **résumé tailoring** too, override `suggest_tailoring(...)`
to return a `TailoringSuggestion` (title + a reorder of the *given* categories);
it must never add content outside `available_categories`.

### Tailor a résumé per job (dynamic builder)

- **No code** for a new job type: add a `key`/`keywords`/`title`/`skills_order`
  entry under `resume.builder.clusters` in `config.yaml`
  ([config reference](configuration.md#resumebuilder-dynamic-per-job-resumes)).
  Keywords match at word boundaries; `skills_order` names must equal the builder
  `master.yaml` categories.
- **Detection logic** lives in `answers/dynamic_resume.py` (`_detect_cluster`
  weights title hits over description hits). It shells out to the builder's
  `tailor` command via `_run_builder` (isolated for tests) and caches one render
  per cluster per run. Unit-test pure bits in `tests/test_dynamic_resume.py`.

### Support a new form control

1. Add detection logic in `forms/detector.py` and a `FieldKind` in
   `forms/field.py`.
2. Handle filling in `forms/filler.py`, reusing the pure helpers in
   `forms/matching.py` (`best_option`, `boolean_option`).
3. Unit-test the pure matching logic in `tests/test_matching.py`.

### Add a job source

Implement discovery returning `jobs.models.Job` objects and wire it into the
orchestrator's discovery step. The rest of the pipeline is source-agnostic.

## LinkedIn selectors

All DOM selectors are centralised in `forms/selectors.py`. LinkedIn changes its
markup periodically; when automation breaks, update selectors there first — no
other module hardcodes them.

## Database

`database/db.py` is a thin repository over `sqlite3` with short-lived, per-call
connections (`PRAGMA foreign_keys=ON`, `Row` factory, commit-on-success). The
schema (`database/sql/schema.sql`) has tables for runs, jobs, scores, resumes,
applications, questions, answers, application_answers, ai_results and errors.
Answers learned interactively are reused on future runs.

## Development workflow

Read [`../AGENTS.md`](../AGENTS.md) and the
[repository tracking contract](github-tracking.md). Actual workstreams live in
[`../todo/00_INDEX.todo`](../todo/00_INDEX.todo); preserve its numbered `.todo`
files, eight-field schema and separate perpetual ledger. Review public-safe
payloads, preview authorized tracking changes, then explicitly apply and read
back issue/Project/backlink results. This is local invocation, not an activated
workflow; commits, pushes and live applications require separate authority.

```powershell
# Install dependencies for the complete test suite
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,gui,dashboard,export]"

# Quality gates (all must pass)
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\black.exe --check linkedin_easy_apply tests tools\build_windows.py tools\smoke_windows.py tools\capture_screenshots.py tools\todo_sync.py packaging\windows
.\.venv\Scripts\mypy.exe linkedin_easy_apply
.\.venv\Scripts\python.exe -m pytest
```

Optional extras: `.[ai]` (OpenAI), `.[dashboard]` (Streamlit), `.[export]`
(XLSX export). The full suite imports dashboard helpers, so its environment
needs the dashboard extra even though the portable build excludes it.

Report-control tests use disposable fictional files and stub native openers.
AppTest exercises corner-button events and standalone dialog widget reruns;
it does not reproduce browser dialog-fragment reruns. Qualify actual iframe
rendering and downloads through an isolated loopback fixture with a fresh browser,
never private reports, a user's running dashboard or real file-browser windows.
Keep the Reports popover keyed and stateful, close it in the browser-button
callback, and render the dialog outside it. An open popover can intercept dialog
clicks even when AppTest passes; the browser check must use ordinary clicks.

`tests/test_dashboard_tables.py` exercises every dataframe/editor renderer with
a fictional database. Keep `width="content"` and leave column widths unspecified
so native content sizing is not replaced by stretching or fixed presets.
AppTest covers configuration, control types and unchanged data, not actual canvas
measurements or frontend editor gestures. Verify initial widths against native
Autosize subject to the grid's automatic width cap; manual Autosize can be wider.
Check narrow-view scrolling and real edit/save clicks in an isolated browser,
waiting for actual backend reruns between edits and saves.

The resume editor retains its internal column keys and question identity while
displaying **Answer to save** beside **Save this answer**. Keep both reference
columns disabled and explicitly labeled read-only. Qualification must edit the
saved value to something different from both references, select only that row,
and verify that only its final edited value persists. Empty selected values are
skipped; unselected rows stay unchanged.

Outreach dates must come from the submitted application matched by job and run,
not the draft's creation or another run's application. Prefer its recorded finish
and document the legacy start fallback. Normal application writes are naive
local ISO timestamps; normalize them and offset-aware records to local aware
times before the strict seven-day comparison. Unknown/invalid dates must remain
visible and unaged. Only untouched contacts enter the oldest-first priority
table; note-sent follow-ups remain regular.

Collapsed contact titles reuse that same priority membership, with an explicit
Overdue outreach label and semantic-red header emphasis. Scope styling to keyed
native expanders and their summary only; do not color the message body or create
a second age rule. Note marking and undo must remove/restore the correct title's
emphasis. Qualify actual collapsed headers, keyboard expansion and dark/light/
narrow layouts in a fictional browser; AppTest alone does not prove CSS rendering.

Both outreach editors must preserve `width="content"` and actual outreach IDs.
Streamlit's fixed-row editor can retain positional edits across equal-sized data
changes. Key each editor by its ordered outreach IDs so both frontend and backend
selection reset when IDs/order change; clearing server state alone is insufficient.
Qualify equal-sized
queue swaps, note marking/undo, completion from both tables, the real themed red
outline and narrow scrolling in an isolated fictional browser. Neither a note
mark nor a priority classification sends anything; these checks do not qualify
live invitations, messages or the original outreach workstream's acceptance.

Both skip entry points reuse `_skipped_section` with independent widget prefixes
and `skip_events(limit=None)`: bar counts, row membership and CSV must cover the
same complete event history, not a capped sample or deduplicated job list. Keep
the native reason picker and explicit clear action alongside chart selection.
Reset chart identity after picker/clear actions, and key row selection by reason
and ordered event IDs so equal-sized list changes cannot reuse positional state.
Retain content-sized columns. Qualify actual bar clicks, keyboard filtering,
double-click clearing, repeated rows, CSV downloads and narrow scrolling in an
isolated fictional browser, not just AppTest.

`record_skip` stores optional observed job, exact score/threshold/breakdown and
detail as nullable JSON context. Add the column idempotently; never rewrite
legacy events. Explicit observed `None` values must not borrow a different
observation's metadata. Do not join a later score to explain a prior decision.
Captured posting fields must survive later job updates/deletion; legacy current-
job fallback and unavailable context need explicit UI provenance. Preserve
form-result reasons and available targeted-open identity even without a saved
job. Reading this dashboard must neither scrape LinkedIn nor write applications.

## Desktop and Windows release

The GUI builds CLI argv; it does not duplicate the automation engine.
`gui/settings_panel.py` collects common run overrides and `gui/settings.py`
merges only changed values, validates through `config/loader.parse_config`,
and writes private presets. `gui/process.py` streams UTF-8 output through
QProcess and forwards input. Stop terminates the child; it is not Ctrl+C.
Desktop startup destroys its owned window before releasing `QApplication`,
explicitly delivering deferred deletion after the event loop stops. Qt tests
share one session application, destroy owned widgets and isolate preferences
with an explicit temporary INI backend rather than touching native settings.

`MainWindow.createPopupMenu()` returns `None` so Qt cannot offer a visibility
checkbox for the essential top toolbar. Keep ordinary text-control context
menus intact. Layout visibility is not persisted; reopening restores an older
hidden toolbar without clearing configuration or the saved theme.

`gui/widgets.py::Console` inserts plain `QTextCursor` spans, not HTML:
spaces/indentation remain literal and long messages wrap at word boundaries.
Only recognized dated Loguru prefixes become compact severity/activity badges;
unknown output stays intact. Original ANSI-stripped lines and semantic roles
remain in the bounded backlog, allowing theme changes and the Details checkbox
to repaint without changing child/file logs. Submission-attempt, confirmation,
dry-run, cancellation and process-exit labels retain distinct meanings.

`progress.py` supplies a strict version-1, status-only snapshot protocol.
`CommandRunner` opts its own child in with `LEA_GUI_PROGRESS=1`, separates frames
from human output and forwards snapshots to `gui/metrics.py::RunMetrics`.
Hook authoritative outcomes, not log strings: confirmation before outreach
approval; exact outreach statuses before recording; invitation results distinct
from dry-run would-send. Preserve the existing persistence/final-summary
sequence. Bad/truncated frames warn without leaking payloads or clearing valid
counts. Ordinary CLI/file logs emit no telemetry. Real-child tests verify
updates before exit, prompt forwarding, stop/reset and rejection recovery.

`gui/widgets.py::tooltip` formats option help as purpose plus a second
`Example:` line. Explicit inventories cover settings, actions, targets and tool
arguments; field labels share their control's help, and dependent descriptions
update on selection changes. Use native Qt tooltips rather than layout-expanding
help controls, and preserve the console's diagnostic span tooltips. Coverage
checks include labels/items and actual help events on disabled controls,
spinbox editors and text viewports, without executing commands or saving state.

`gui/tutorial.py` reads the reviewed `docs/gui-tutorial.md` chapters into a
read-only dialog, shared by toolbar/F1 and contextual settings help. Standalone
`gui --tutorial` avoids MainWindow construction, configuration loading and
database initialization. The tutorial is blocked during child commands. The Windows
entry bypasses first-run workspace preparation for tutorial mode, and its spec
explicitly includes the same guide in Windows v0.2.1. Frozen offline smoke
renders the contextual guide alongside the normal window and sibling CLI;
actual standalone native startup remains a separate qualification.
Older v0.2.0 binaries are not retrofitted.

### Refresh README media

Use the existing `.[dev,gui]` environment; Pillow is a development-only encoder,
not a new desktop/runtime dependency:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -B tools\capture_screenshots.py
```

For a Run-only presentation change, add `--run-only` to refresh seven affected
Run PNGs and its GIF without replacing unrelated page/tutorial media.

The tool writes thirteen desktop PNGs and two looping GIFs to `docs\images`.
The README intentionally uses a curated subset: the run GIF comes before setup,
with distinct still views rather than the entire capture inventory. Retain the
other source images for guides and future curation; a front-page edit does not
require regenerating unchanged media.
It renders only owned Qt widgets, exercises real action/settings controls and
read-only tutorial navigation, and captions illustrative output explicitly.
Configuration, database and INI preferences live in a temporary demo workspace;
location labels and command executable paths are fictionalized before capture.
Start, Copy command, Save, browser and dashboard launchers are not exercised.
Font checks reject missing-glyph boxes. Owned windows are explicitly destroyed
before temporary workspace cleanup, including when GIF encoding fails.
The Limits still requests a real help event and composites only the owned
window and native tooltip. A missing or clipped popup fails explicitly;
never use a desktop/screen grab on a shared workstation. Targeted updates
can reuse `_save_screenshot(..., tooltip_target=field)` without regenerating
unchanged media. Display-path fictionalization preserves option-help text.
Review the rendered media and captions before any separately authorized push;
these captures do not qualify a live run, installed release or human acceptance.
The Run captures inject explicit **Offline demo** counter and activity snapshots
using the same reporter and typed activity signal. The walkthrough demonstrates
an input pause, a replacement tailored filename and retention across later
actions; neither a process nor an elapsed timer starts. Geometry tests register
the same usable fonts before judging digits, wrapping and compact header fit.

Desktop preferences use the explicit `QSettings.defaultFormat()` / UserScope
constructor. The two-string constructor uses native storage on Windows even
after setting IniFormat globally, which would bypass temporary test/capture
paths. Ordinary launches still default to the existing native preferences.

`runtime.py` separates source/frozen resources from writable workspace data.
Frozen startup copies missing examples into `%LOCALAPPDATA%\EasyApplyAutomaton`
(or `LEA_WORKSPACE`), without migrating personal source data. The shared
`packaging/windows/entry.py` dispatches the GUI and `lea.exe`. The spec builds
two executables sharing a one-folder runtime and explicitly excludes browsers,
Streamlit/OpenAI, development helpers and unused Qt PDF/QML/WebEngine features.
The Qt shared libraries remain replaceable; original notices and LGPL/GPL
texts are shipped alongside dependency versions and integrity manifests.

On Windows x64, with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r packaging\windows\requirements.txt
.\.venv\Scripts\python.exe -B tools\build_windows.py
.\.venv\Scripts\python.exe -B tools\smoke_windows.py dist\windows\EasyApplyAutomaton
```

`.github/workflows/windows-release.yml` qualifies PRs/main/manual builds.
Only a pushed `v<pyproject-version>` tag publishes after qualification, using
the job-scoped GitHub token. The pipeline checks Ruff, Black over product,
tests and release/tracking tools, mypy, the full test suite and the actual
frozen GUI/CLI offline. It produces a ZIP, SHA256SUMS and a per-file manifest
with the exact source SHA. It is not a tracking daemon or a cloud deployment.
Unsigned binaries, fresh-machine behavior and live browser/applications are
separate qualification boundaries, not inferred from passing offline checks.

## Testing strategy

Pure-logic modules are unit-tested without a browser: config, database, answer
store + resolver, parser, scoring, resume selector, cover letter, option
matching, and job-metadata parsing. Playwright-dependent modules (browser,
forms, jobs discovery) are exercised manually via the CLI `test-browser` /
`test-form` / `--dry-run` commands against the live site.
