# Setup & Commands

Everything needed to install the automaton and drive it — from either the
terminal or the desktop app. For a narrative, copy-paste run guide see
**[INIT.MD](../INIT.MD)**; for the window itself see **[docs/gui.md](gui.md)**.

---

## 1. Requirements

- Python **3.12+**
- Microsoft Edge (default), Google Chrome, or bundled Chromium
- A LinkedIn account you sign into **by hand**, once, inside the automation's
  browser profile. The tool never stores a password and never automates login.

## 2. Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# Only if you use bundled Chromium (not needed for Edge/Chrome):
.\.venv\Scripts\python.exe -m playwright install chromium
```

### Optional extras

| Extra | Adds | Needed for |
| --- | --- | --- |
| `.[gui]` | PySide6 | the desktop app (`apply.py gui`) |
| `.[dashboard]` | Streamlit, pandas | the analytics dashboard (`apply.py dashboard`) |
| `.[export]` | openpyxl | `export --format xlsx` |
| `.[ai]` | openai | the optional AI advisor |
| `.[dev]` | pytest, ruff, black, mypy | development |

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[gui,dashboard,export]"
```

Installing the package also exposes a `lea` console script, so with the venv
active `lea scan`, `lea apply --dry-run`, `lea gui` all work.

## 3. First run

```powershell
# 1. Scaffold config files + runtime folders
.\.venv\Scripts\python.exe apply.py init

# 2. Edit configs/config.yaml  (searches, scoring, limits)
#    Edit configs/answers.yaml (your details & skills)
#    Put your résumé PDF(s) in generated/resume/ and reference them in config.yaml

# 3. Sign in to LinkedIn once - a browser opens, you log in, the session is saved
.\.venv\Scripts\python.exe apply.py login

# 4. Confirm the saved session works
.\.venv\Scripts\python.exe apply.py test-browser

# 5. Discover and score jobs without applying to anything
.\.venv\Scripts\python.exe apply.py scan

# 6. Practice run - fills every field, never submits
.\.venv\Scripts\python.exe apply.py apply --dry-run

# 7. For real, one application
.\.venv\Scripts\python.exe apply.py apply --limit 1
```

> The automation profile (`.browser-profile`) is **separate** from your everyday
> browser. Being signed in normally does not sign the automation in — step 3 is
> what does that.

---

## 4. Starting the tool

### Desktop app

```powershell
.\.venv\Scripts\python.exe apply.py gui
.\.venv\Scripts\python.exe apply.py gui --theme harbor-daylight    # light theme
.\.venv\Scripts\python.exe apply.py gui --config configs/other.yaml
```

### Command line

```powershell
.\.venv\Scripts\python.exe apply.py --help
.\.venv\Scripts\python.exe apply.py apply --help
```

### Dashboard

```powershell
.\.venv\Scripts\python.exe apply.py dashboard      # http://localhost:8501
```

Also reachable from the GUI's **Data → Open dashboard** button, or
<kbd>Ctrl</kbd>+<kbd>D</kbd> anywhere in the window.

---

## 5. Command reference

Add `-v` / `--verbose` **before** the sub-command for DEBUG-level,
decision-by-decision logging: `apply.py -v apply --dry-run`.

| Command | What it does |
| --- | --- |
| `init` | Scaffold example configs and runtime directories. `--force` overwrites. |
| `login` | Open the browser so you can sign in to LinkedIn once; the session is reused. |
| `gui` | Open the desktop app. `--theme deepseafoam\|harbor-daylight`, `--config`. |
| `apply` | Run the Easy Apply automation. |
| `reapply` | Retry every failed/aborted application, by stored URL (no search). |
| `scan` | Discover and score jobs without applying. |
| `connect` | Send pending recruiters a free connection invitation carrying their ≤300-char note. Opens its own browser. |
| `dashboard` | Launch the Streamlit dashboard. |
| `stats` | Print database statistics. |
| `export` | Export applications (joined with jobs) to CSV/XLSX. |
| `sync-answers` | Compare recorded answers with your résumé and approve corrections. |
| `resume-test <title>` | Show which résumé would be chosen for a job. |
| `test-form "<question>"` | Recognise and resolve a single question, offline. |
| `test-browser` | Launch the browser and verify the logged-in session. |
| `version` | Print the version. |

### `apply`

| Option | Meaning |
| --- | --- |
| `--dry-run` | Fill everything, never submit. |
| `--limit`, `-n` | Target number of **successful submissions**. Skipped/failed jobs do not consume it, so the crawler paginates until this many are actually sent. Defaults to `jobs.max_per_run`. |
| `--url` | Override the configured searches with a single LinkedIn URL. |
| `--confirm-submit` / `--no-confirm-submit` | Ask in the terminal before each submit (Enter = submit). Omit to submit automatically. |
| `--ignore-score` | Apply regardless of `scoring.threshold`. The score is still computed, logged and stored. |
| `--message-hiring-team` / `--no-message-hiring-team` | Draft hiring-team outreach after each successful apply. Defaults to `outreach.enabled`. |
| `--yes`, `-y` | Never prompt; auto-answer. |
| `--config`, `-c` | Config file to use. |

### `reapply`

Same submission flags as `apply` (`--dry-run`, `--limit`, `--confirm-submit`,
`--ignore-score`, `--message-hiring-team`, `--yes`), plus:

| Option | Meaning |
| --- | --- |
| `--list` | Print the failed/aborted jobs that would be retried, then exit. |

There is no `--url`: reapply opens each job by its stored URL.

### `scan`

| Option | Meaning |
| --- | --- |
| `--limit`, `-n` | Maximum jobs to scan. |
| `--url` | Override searches with a single URL. |

Scan never submits, so it takes no submission flags.

### `connect`

| Option | Meaning |
| --- | --- |
| `--dry-run` | Open Connect + Add a note, but never click Send. |
| `--limit`, `-n` | Maximum invitations this pass. |
| `--run` | Only send notes drafted in one run id. |
| `--yes`, `-y` | Skip the confirmation prompt. |

### `export`

| Option | Meaning |
| --- | --- |
| `--output`, `-o` | Destination file (default `applications.csv`). |
| `--format`, `-f` | `csv` or `xlsx` (xlsx needs `.[export]`). |

### `sync-answers`

| Option | Meaning |
| --- | --- |
| `--apply` | Store the recommended values as approved overrides (used before anything else next run). |
| `--list` | List overrides already in effect, then exit. |
| `--yes`, `-y` | Skip the confirmation prompt when applying. |

---

## 6. Safety rails

- **`scan` and `--dry-run` never submit.** Use them first, always.
- `jobs.max_per_run`, `max_per_company` and `max_daily` cap a run, a company and
  a day. LinkedIn's own daily Easy Apply cap is detected and stops the run
  cleanly rather than hammering it.
- URL and company+role dedupe mean the same posting is never applied to twice.
- `blacklist_companies` / `whitelist_companies` and
  `include_keywords` / `exclude_keywords` gate jobs **before** scoring.
- Ctrl+C shuts down gracefully and records the run as aborted.

---

## 7. Development

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,gui,dashboard]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\black.exe --check .
.\.venv\Scripts\mypy.exe linkedin_easy_apply
.\.venv\Scripts\python.exe -m pytest
```

GUI tests that need Qt skip automatically when PySide6 is absent; the theme and
command-builder tests always run.

## 8. Project structure

```
linkedin_easy_apply/   the package (config, parser, scoring, answers, forms,
                       browser, jobs, ai, database, cli, gui, dashboard, utils,
                       orchestrator.py)
configs/               *.example.yaml templates (init copies these)
generated/resume/      résumé PDFs the automaton attaches (git-ignored)
generated/coverletter/ generated cover letters, .pdf + .txt per job (git-ignored)
docs/                  configuration, GUI, developer guide, FAQ, troubleshooting
tests/                 unit tests for the pure-logic modules
apply.py               CLI entry point
INIT.MD                run guide: every command & option with examples
```

## 9. More documentation

- [Configuration](configuration.md) — every file and key explained.
- [Desktop GUI](gui.md) — the window, its themes, and how it maps onto these commands.
- [Troubleshooting](troubleshooting.md) — fixes for common problems.
- [FAQ](faq.md) — safety, AI, résumés, data storage.
- [Developer Guide](developer_guide.md) — architecture and how to extend it.
