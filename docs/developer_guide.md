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
├── answers/       AnswerStore, AnswerResolver, ResumeSelector, CoverLetter
├── parser/        QuestionParser + QuestionCategory/AnswerType enums
├── scoring/       ScoringEngine (weighted keyword rules)
├── browser/       BrowserManager (persistent context)
├── forms/         detector, filler, matching, selectors, EasyApplyWorkflow
├── jobs/          Job model, JobExtractor, JobSearch
├── ai/            AIProvider ABC, Null/OpenAI providers, factory
├── dashboard/     optional Streamlit app
├── cli/           Typer CLI (main.py)
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
negative to penalise unwanted roles.

### Add a new AI provider

1. Subclass `AIProvider` (`ai/provider.py`) and implement `advise(...)` returning
   an `AIResult`.
2. Register it in `ai/factory.build_provider` and extend `AIProviderName`.
Providers must remain advisory — never submit.

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

```powershell
# Install with dev extras
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Quality gates (all must pass)
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\black.exe --check .
.\.venv\Scripts\mypy.exe linkedin_easy_apply
.\.venv\Scripts\python.exe -m pytest
```

Optional extras: `.[ai]` (OpenAI), `.[dashboard]` (Streamlit), `.[export]`
(XLSX export).

## Testing strategy

Pure-logic modules are unit-tested without a browser: config, database, answer
store + resolver, parser, scoring, resume selector, cover letter, option
matching, and job-metadata parsing. Playwright-dependent modules (browser,
forms, jobs discovery) are exercised manually via the CLI `test-browser` /
`test-form` / `--dry-run` commands against the live site.
