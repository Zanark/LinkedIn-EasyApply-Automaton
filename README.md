# LinkedIn-EasyApply-Automaton

A production-quality, **modular** framework that automates the LinkedIn **Easy
Apply** workflow: it discovers jobs from your saved searches, scores them against
your criteria, picks the right resume, fills every question from your own answer
file, and applies — with dry-run, interactive approval, dedupe and daily limits
built in.

> ⚠️ **Read this first.** Automating LinkedIn violates their Terms of Service and
> can get your account restricted. This project is provided for educational
> purposes; **use it at your own risk**. It **never** stores your password —
> you stay logged in through your own browser profile.

## Highlights

- **Reuses your logged-in browser profile** (Playwright persistent context) —
  no credentials, no automated login.
- **Dynamic question recognition** — a hybrid keyword + fuzzy parser maps
  free-form Easy Apply questions to your answers; unknown questions pause for
  input and are **remembered** for next time.
- **Config-driven everything** — searches, scoring, filters, limits, resume
  selection, logging and AI are all YAML. No hardcoded values.
- **Weighted job scoring** with whole-word matching (so `go` ≠ `google`) and
  punctuation keywords (`c++`, `.net`).
- **Automatic resume selection** (mapping → keyword overlap → default).
- **Safety rails**: per-run / per-company / daily caps, blacklist/whitelist,
  include/exclude keywords, URL + company-role dedupe.
- **Dry-run & interactive** modes; per-step and on-error screenshots.
- **Verbose, decision-level logging** — a global `-v/--verbose` flag (or
  `logging.level: DEBUG`) narrates every field: what was parsed, which answer it
  resolved and *from where*, and whether it filled or skipped — so you see
  exactly what the tool is "thinking."
- **SQLite persistence** of jobs, applications, questions/answers, scores,
  errors — with `stats`, CSV/XLSX `export`, and an optional Streamlit dashboard.
- **Optional AI advisor** (OpenAI) that only *advises* — it can never submit.
- Clean, typed, tested codebase (ruff + black + mypy + pytest).

## Requirements

- Python **3.12+**
- Microsoft Edge (default), Google Chrome, or bundled Chromium
- A LinkedIn account you are logged into within the chosen browser profile

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# First time only, if you use bundled Chromium (not needed for Edge/Chrome):
.\.venv\Scripts\python.exe -m playwright install chromium
```

Optional extras: `.[ai]`, `.[dashboard]`, `.[export]`, `.[dev]` (e.g.
`pip install -e ".[dev]"`).

## Quickstart

```powershell
# 1. Scaffold config files + runtime folders
.\.venv\Scripts\python.exe apply.py init

# 2. Edit configs/config.yaml (searches, scoring, limits)
#    and configs/answers.yaml (your details & skills).
#    Drop your resume(s) in resumes/ and reference them in config.yaml.

# 3. Sign in to LinkedIn once (opens Edge; session is saved to the profile)
.\.venv\Scripts\python.exe apply.py login

# 4. Confirm the saved session works
.\.venv\Scripts\python.exe apply.py test-browser

# 5. Discover & score jobs without applying
.\.venv\Scripts\python.exe apply.py scan

# 6. Practice run — fills everything, never submits
.\.venv\Scripts\python.exe apply.py apply --dry-run

# 7. For real, confirming each submission
.\.venv\Scripts\python.exe apply.py apply --interactive
```

> 💡 Add `-v` **before** any command for full DEBUG narration of every decision,
> e.g. `.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y`. See
> **[INIT.MD](INIT.MD)** for a copy-paste run guide covering every option.

Installing the package also exposes a `lea` console script, so `lea init`,
`lea scan`, `lea apply --dry-run`, etc. work once the venv is active.

## Commands

| Command                       | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `init`                        | Scaffold example configs and runtime directories.       |
| `login`                       | Open the browser to sign in to LinkedIn once (reused).  |
| `apply`                       | Run the Easy Apply automation (`--dry-run`, `--interactive`, `--yes`, `--limit`, `--url`). |
| `scan`                        | Discover & score jobs without applying.                 |
| `stats`                       | Print database statistics.                              |
| `export`                      | Export applications (joined with jobs) to CSV/XLSX.     |
| `dashboard`                   | Launch the Streamlit dashboard.                         |
| `resume-test <title>`         | Show which resume would be chosen for a job.            |
| `test-form "<question>"`      | Recognise & resolve a single question (offline).        |
| `test-browser`                | Launch the browser and verify your logged-in session.   |
| `version`                     | Print the version.                                      |

> **Global option:** add `-v` / `--verbose` **before** any command for
> DEBUG-level, decision-by-decision logging. For every command's full option list
> with copy-paste examples, see **[INIT.MD](INIT.MD)**.

## How it works

```
discover → extract → dedupe → filter → score → select resume
        → (AI advise) → Easy Apply workflow → persist → learn answers
```

The `Orchestrator` coordinates focused modules (`config`, `parser`, `scoring`,
`answers`, `forms`, `browser`, `jobs`, `ai`, `database`). Playwright is imported
lazily, so the pure-logic modules run and unit-test without a browser.

## Project structure

```
linkedin_easy_apply/   the package (config, parser, scoring, answers, forms,
                       browser, jobs, ai, database, cli, dashboard, utils,
                       orchestrator.py)
configs/               *.example.yaml templates (init copies these)
resumes/               your resume files (git-ignored)
docs/                  configuration, developer guide, FAQ, troubleshooting
tests/                 unit tests for the pure-logic modules
apply.py               CLI entry point
INIT.MD                run guide: every command & option with examples
```

## Documentation

- **[Run Guide (INIT.MD)](INIT.MD)** — how to start the tool and **every**
  command/option with copy-paste examples.
- [Configuration](docs/configuration.md) — every file and key explained.
- [Developer Guide](docs/developer_guide.md) — architecture & how to extend.
- [FAQ](docs/faq.md) — safety, AI, resumes, data storage.
- [Troubleshooting](docs/troubleshooting.md) — fixes for common problems.

### Learning the internals

Deep-dive guides that teach the computer-science behind this codebase — written
for engineers who want to understand *why* it's built this way and map it to
patterns used at bigger companies:

- [Architecture & Design Patterns](docs/architecture.md) — component/sequence
  diagrams, the Functional-Core/Imperative-Shell style, and every design pattern
  used here (Facade, Strategy, Factory, Repository, Null Object…) with real code.
- [Data Structures](docs/data-structures.md) — the maps, sets, enums, DTOs and
  relational schema used, each with complexity and where industry uses it.
- [Algorithms](docs/algorithms.md) — normalization, fuzzy matching, weighted
  scoring, backoff and more, each with a real-world example.

## Development

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\black.exe --check .
.\.venv\Scripts\mypy.exe linkedin_easy_apply
.\.venv\Scripts\python.exe -m pytest
```

## Disclaimer

This software is not affiliated with, endorsed by, or connected to LinkedIn.
Automating the platform may violate LinkedIn's User Agreement and could lead to
account restrictions. You are solely responsible for how you use it.

