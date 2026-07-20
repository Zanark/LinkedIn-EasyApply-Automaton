# INIT — How to Run LinkedIn Easy Apply Automaton

A copy‑paste friendly guide to **starting the tool** and **every command / option**, with ready‑to‑run examples for Windows PowerShell.

> Every example below can be pasted **as‑is** into your terminal from the project folder:
> `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton`

---

## Table of Contents

1. [TL;DR — the 3 commands you'll use most](#1-tldr--the-3-commands-youll-use-most)
2. [Prerequisites & one‑time setup](#2-prerequisites--one-time-setup)
3. [Two ways to run the tool](#3-two-ways-to-run-the-tool)
4. [The global `-v` / `--verbose` flag](#4-the-global--v--verbose-flag)
5. [First‑time walkthrough (in order)](#5-first-time-walkthrough-in-order)
6. [Command reference (every command, every option)](#6-command-reference-every-command-every-option)
   - [`version`](#version) · [`init`](#init) · [`login`](#login) · [`test-browser`](#test-browser) · [`scan`](#scan) · [`apply`](#apply) · [`test-form`](#test-form) · [`resume-test`](#resume-test) · [`stats`](#stats) · [`export`](#export) · [`dashboard`](#dashboard)
7. [`apply` — every option combination explained](#7-apply--every-option-combination-explained)
8. [Where everything lives (logs, DB, screenshots)](#8-where-everything-lives)
9. [Safety notes](#9-safety-notes)
10. [Troubleshooting](#10-troubleshooting)
11. [Cheat sheet](#11-cheat-sheet)

---

## 1. TL;DR — the 3 commands you'll use most

```powershell
# 1) Sign in to LinkedIn once (a browser window opens; log in, then press Enter)
.\.venv\Scripts\python.exe apply.py login

# 2) Safe practice run — fills forms but NEVER submits, fully unattended, full logs
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# 3) Go live — actually submit applications (see the safety notes first!)
.\.venv\Scripts\python.exe apply.py apply --interactive
```

> 🟢 `--dry-run` = safe (never submits). 🔴 no `--dry-run` = real applications are submitted.
> Press Ctrl+C anytime for a clean abort + summary table.

---

## 2. Prerequisites & one‑time setup

You only do this **once**. If you already have a working `.venv` (you do), you can skip to section 3.

```powershell
# From the project root:
cd C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton

# Create the virtual environment
python -m venv .venv

# Install the tool + optional extras (dashboard + xlsx export)
.\.venv\Scripts\python.exe -m pip install -e ".[dashboard,export]"
```

**Browser:** the default engine is **Edge** (`browser.engine: edge` in `configs/config.yaml`), which uses the copy of Microsoft Edge already on Windows — nothing to download.

```powershell
# ONLY needed if you switch browser.engine to "chromium" in config.yaml:
.\.venv\Scripts\python.exe -m playwright install chromium
```

**Config files:** create your personal config + answers from the examples:

```powershell
.\.venv\Scripts\python.exe apply.py init
```

Then edit `configs\config.yaml` (searches, scoring) and `configs\answers.yaml` (your data). Put a resume in `generated\resume\` whose filename matches `resume.default` in `config.yaml` (e.g. `Debashish_Mishra_1page.pdf`), or generate a tailored set with the standalone [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder) (`render.py publish-variants --out-dir <this-repo>\generated\resume`).

> **Optional — a fresh résumé per job.** Download the [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder), set `resume.builder.enabled: true` and `resume.builder.path: C:\path\to\dynamic-resume-builder` in `config.yaml`, and the automaton renders a résumé **tailored to each job** right before applying (e.g. an AI-heavy posting → your AI skills first). Keyword clusters work offline; see [`docs/configuration.md → resume.builder`](docs/configuration.md#resumebuilder-dynamic-per-job-resumes).

---

## 3. Two ways to run the tool

Both are identical — pick whichever you like. **All examples in this doc use the first form** because it always works.

```powershell
# Form A — explicit (recommended, always works):
.\.venv\Scripts\python.exe apply.py <command> [options]

# Form B — short console script (installed by pip):
.\.venv\Scripts\lea.exe <command> [options]
```

> 💡 Tip: to type just `lea` for the whole session, add an alias:
> ```powershell
> Set-Alias lea "C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\.venv\Scripts\lea.exe"
> lea stats
> ```

See the full list of commands any time:

```powershell
.\.venv\Scripts\python.exe apply.py --help
.\.venv\Scripts\python.exe apply.py apply --help   # help for one command
```

---

## 4. The global `-v` / `--verbose` flag

`-v` turns on **DEBUG logging** — the tool narrates *every* decision, data lookup and outcome (parse → resolve → detect → fill). Works with **any** command.

> ⚠️ **`-v` must come BEFORE the command**, not after.

```powershell
# ✅ Correct — flag before the command
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# ❌ Wrong — this errors with "No such option: -v"
.\.venv\Scripts\python.exe apply.py apply --dry-run -y -v
```

You can also make verbose the permanent default by setting `logging.level: DEBUG` in `configs\config.yaml` (already set for you). With that, `-v` is optional.

---

## 5. First‑time walkthrough (in order)

Run these top to bottom the first time:

```powershell
# 1. Scaffold config files + folders
.\.venv\Scripts\python.exe apply.py init

# 2. (edit configs\config.yaml and configs\answers.yaml in your editor now)

# 3. Sign in to LinkedIn once — a browser opens, log in, come back, press Enter
.\.venv\Scripts\python.exe apply.py login

# 4. Confirm the tool sees you as logged in
.\.venv\Scripts\python.exe apply.py test-browser

# 5. Sanity‑check a single question offline (no browser)
.\.venv\Scripts\python.exe apply.py -v test-form "How many years of experience do you have with Python?"

# 6. Discover & score jobs WITHOUT applying
.\.venv\Scripts\python.exe apply.py scan

# 7. Full dry‑run: fill every form but never submit, with full logs
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# 8. When you're happy, go live (confirm each submit)
.\.venv\Scripts\python.exe apply.py apply --interactive
```

---

## 6. Command reference (every command, every option)

Global option available on all commands: `-v, --verbose` (see §4).
`-c, --config PATH` defaults to `configs\config.yaml` everywhere it appears.

---

### `version`

Print the tool version. No options.

```powershell
.\.venv\Scripts\python.exe apply.py version
```

---

### `init`

Scaffold example config files into `configs\` and create the working folders (`configs`, `resumes`, `logs`, `screenshots`, `database`).

| Option | Meaning |
| --- | --- |
| `--force` | Overwrite `config.yaml` / `answers.yaml` / `searches.yaml` if they already exist. |

```powershell
# Create configs only if they don't exist yet (safe)
.\.venv\Scripts\python.exe apply.py init

# Force‑overwrite existing configs with fresh copies of the examples
.\.venv\Scripts\python.exe apply.py init --force
```

---

### `login`

Open a browser at LinkedIn's login page so you can sign in **once**. Your session is saved to the browser profile (`.browser-profile`) and reused by every future run. The tool never stores your password.

| Option | Meaning |
| --- | --- |
| `-c, --config PATH` | Use a different config file. |

```powershell
# Standard login
.\.venv\Scripts\python.exe apply.py login

# Login using an alternate config
.\.venv\Scripts\python.exe apply.py login -c configs\config.yaml
```

> The command waits with a prompt — sign in inside the browser, then return to the terminal and **press Enter**.

---

### `test-browser`

Launch the browser with your saved profile and confirm the session works. Prints the page title and saves a screenshot.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `--url TEXT` | Page to open for the check. | `https://www.linkedin.com/feed/` |

```powershell
# Open the LinkedIn feed and verify you're logged in
.\.venv\Scripts\python.exe apply.py test-browser

# Point the check at a specific page
.\.venv\Scripts\python.exe apply.py test-browser --url "https://www.linkedin.com/jobs/"

# Verbose (see the browser launch details)
.\.venv\Scripts\python.exe apply.py -v test-browser
```

---

### `scan`

Discover and **score** jobs from your configured searches **without applying**. Great for seeing what the tool would target and why.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `-n, --limit INT` | Max jobs to scan. | all |
| `--url TEXT` | Ignore configured searches; scan this one search URL. | — |

```powershell
# Scan every enabled search in your config
.\.venv\Scripts\python.exe apply.py scan

# Scan but stop after 20 jobs
.\.venv\Scripts\python.exe apply.py scan -n 20

# Scan a single custom search URL
.\.venv\Scripts\python.exe apply.py scan --url "https://www.linkedin.com/jobs/search/?keywords=backend%20developer&location=India&f_AL=true"

# Everything together, verbose
.\.venv\Scripts\python.exe apply.py -v scan --url "https://www.linkedin.com/jobs/search/?keywords=python&location=India&f_AL=true" -n 15
```

---

### `apply`

Run the actual Easy Apply automation. **This is the main command** — see §7 for every option combination.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `--dry-run` | Fill every form but **never submit** (reaches Submit, then discards). | off (live!) |
| `--interactive` / `--no-interactive` | Ask you to confirm before **each** submit / don't ask. | don't ask |
| `-n, --limit INT` | Max applications (submissions) this run. | config `jobs.max_per_run` |
| `--url TEXT` | Ignore configured searches; use this one search URL. | — |
| `-y, --yes` | Never prompt — auto‑answer unknown questions and auto‑submit. | prompts on |

```powershell
# 🟢 Safest test: fill everything, submit nothing, no prompts, full logs
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# 🔴 Go live but confirm each submission yourself
.\.venv\Scripts\python.exe apply.py apply --interactive
```

> ⚠️ Running `apply` **without** `--dry-run` submits **real** applications to LinkedIn. Start with `--dry-run`.

---

### `test-form`

Offline (no browser). Give it a question in quotes; it shows how the tool categorises the question and what answer it resolves from your `answers.yaml`. Perfect with `-v` to see the "brain."

| Argument / Option | Meaning |
| --- | --- |
| `QUESTION` (required) | The question text, in quotes. |
| `-c, --config PATH` | Config file. |

```powershell
# Years‑of‑experience question
.\.venv\Scripts\python.exe apply.py test-form "How many years of experience do you have with Python?"

# See exactly where the answer comes from (DEBUG)
.\.venv\Scripts\python.exe apply.py -v test-form "What is your expected CTC?"

# A yes/no question
.\.venv\Scripts\python.exe apply.py test-form "Are you legally authorized to work in India?"
```

---

### `resume-test`

Show which resume the tool would attach for a given job title/description.

| Argument / Option | Meaning |
| --- | --- |
| `TITLE` (required) | Job title, in quotes. |
| `-d, --description TEXT` | Optional job description text to refine the match. |
| `-c, --config PATH` | Config file. |

```powershell
# By title only
.\.venv\Scripts\python.exe apply.py resume-test "Full Stack Developer"

# With a description snippet
.\.venv\Scripts\python.exe apply.py resume-test "Software Engineer" -d "Python, Django, PostgreSQL, AWS"
```

---

### `stats`

Print database statistics (jobs seen, applications, runs, top companies, etc.).

| Option | Meaning |
| --- | --- |
| `-c, --config PATH` | Config file. |

```powershell
.\.venv\Scripts\python.exe apply.py stats
```

---

### `export`

Export your applications (joined with job details) to CSV or XLSX.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `-o, --output PATH` | Output file path. | `applications.csv` |
| `-f, --format TEXT` | `csv` or `xlsx`. | `csv` |

```powershell
# Default CSV -> applications.csv
.\.venv\Scripts\python.exe apply.py export

# CSV to a custom path
.\.venv\Scripts\python.exe apply.py export -o exports\my_applications.csv

# Excel workbook (requires the [export] extra installed)
.\.venv\Scripts\python.exe apply.py export -f xlsx -o exports\applications.xlsx
```

---

### `dashboard`

Launch the Streamlit web dashboard in your browser.

| Option | Meaning |
| --- | --- |
| `-c, --config PATH` | Config file. |

```powershell
# Requires the [dashboard] extra installed
.\.venv\Scripts\python.exe apply.py dashboard
```

---

## 7. `apply` — every option combination explained

Three flags decide **what the tool prompts you for and whether it submits**. Understand these and you understand everything:

| Flag | What it controls |
| --- | --- |
| `--dry-run` | If present, the tool **never submits** (fills, then discards). If absent, it **submits for real**. |
| `-y, --yes` | If present, **no prompts at all** — unknown questions are auto‑handled and submits are automatic. |
| `--interactive` | If present (and not `-y`), asks **"Submit this application?"** before every submission. |

### The 8 core combinations

| # | Command | Submits? | Prompts for unknown Qs? | Asks before each submit? |
| --- | --- | :---: | :---: | :---: |
| 1 | `apply` | 🔴 Yes | Yes | No |
| 2 | `apply --interactive` | 🔴 Yes | Yes | **Yes** |
| 3 | `apply -y` | 🔴 Yes | No | No |
| 4 | `apply -y --interactive` | 🔴 Yes | No | No¹ |
| 5 | `apply --dry-run` | 🟢 No | Yes | — |
| 6 | `apply --dry-run --interactive` | 🟢 No | Yes | — |
| 7 | `apply --dry-run -y` | 🟢 No | No | — |
| 8 | `apply --dry-run -y --interactive` | 🟢 No | No | — |

¹ `-y` disables all prompting, so `--interactive` has **no effect** when combined with `-y`.

```powershell
# 1) Live, auto‑submit, but pause to ask YOU any question it can't answer
.\.venv\Scripts\python.exe apply.py apply

# 2) Live, safest live mode — confirm every single submission yourself
.\.venv\Scripts\python.exe apply.py apply --interactive

# 3) Live, fully unattended — most aggressive, submits everything it can
.\.venv\Scripts\python.exe apply.py apply -y

# 4) Same as #3 (‑y wins; ‑‑interactive ignored)
.\.venv\Scripts\python.exe apply.py apply -y --interactive

# 5) Dry‑run, still asks you unknown questions (never submits)
.\.venv\Scripts\python.exe apply.py apply --dry-run

# 6) Dry‑run + interactive — nothing submits, so it just fills & asks unknowns
.\.venv\Scripts\python.exe apply.py apply --dry-run --interactive

# 7) 🟢 RECOMMENDED for testing: dry‑run, no prompts, unattended
.\.venv\Scripts\python.exe apply.py apply --dry-run -y

# 8) Same as #7 (‑‑interactive has no effect with ‑y)
.\.venv\Scripts\python.exe apply.py apply --dry-run -y --interactive
```

### Modifiers you can add to ANY of the above

These stack onto any combination:

```powershell
# --limit / -n : cap the number of REAL submissions
.\.venv\Scripts\python.exe apply.py apply -y -n 5            # submit at most 5, unattended
.\.venv\Scripts\python.exe apply.py apply --interactive -n 3 # confirm each, stop after 3

# --url : run against ONE custom search instead of your config's searches
.\.venv\Scripts\python.exe apply.py apply --dry-run -y --url "https://www.linkedin.com/jobs/search/?keywords=full%20stack%20developer&location=India&f_AL=true&f_JT=F"

# -c / --config : use a different config file
.\.venv\Scripts\python.exe apply.py apply --dry-run -c configs\config.yaml

# -v (before the command) : full DEBUG narration of every field
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# --no-interactive : be explicit that no per‑submit confirmation is wanted
.\.venv\Scripts\python.exe apply.py apply -y --no-interactive

# Everything at once: verbose dry‑run, single URL, capped, alternate config
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y -n 10 -c configs\config.yaml --url "https://www.linkedin.com/jobs/search/?keywords=python&location=India&f_AL=true"
```

> 📝 Note on `--limit` during `--dry-run`: the limit counts **submissions**, and a dry‑run never submits, so `-n` will **not** cut a dry‑run short — it still walks through a batch of jobs (roughly 30 per search). `-n` is meant to cap **real** runs.

---

## 8. Where everything lives

| Path | What it is |
| --- | --- |
| `configs\config.yaml` | Your settings (searches, scoring, browser, logging). Personal — git‑ignored. |
| `configs\answers.yaml` | Your data used to fill forms. Personal — git‑ignored. |
| `logs\easy_apply_<date>.log` | Full run log (very detailed at DEBUG). Git‑ignored. |
| `screenshots\` | Screenshots captured during runs / `test-browser`. |
| `database\easy_apply.db` | SQLite DB of jobs, applications, questions. Used by `stats`/`export`. |
| `.browser-profile\` | Your saved LinkedIn browser session. Never commit this. |
| `generated\resume\` | Resume PDF(s) the automaton attaches (git-ignored). Build them with the external dynamic-resume-builder. |
| `generated\coverletter\` | Auto-generated cover letters, one `.txt` per job (git-ignored). |

Watch the log live in a second PowerShell window:

```powershell
Get-Content -Wait -Tail 40 logs\easy_apply_2026-07-13.log
```

---

## 9. Safety notes

- 🟢 **Always start with `--dry-run`.** It fills forms and reaches the Submit button, then discards — nothing is ever sent.
- 🔴 **`apply` without `--dry-run` submits real applications.** Use `--interactive` your first few live runs so you approve each one.
- 🧍 **Don't run two browser commands at once** (e.g. `login` and `apply`) — they share the `.browser-profile` and will collide.
- 🔐 The tool **never** stores your LinkedIn password. You log in yourself via `login`; only the browser session cookie is reused.
- 🧾 Logs may contain your personal data (name, phone, CTC) by design — that's why `logs\` is git‑ignored. Don't paste raw logs publicly.
- 🧹 `screenshots.cleanup` is on by default: end-of-run cleanup keeps application evidence but tidies unreferenced step/unknown screenshots.
- ⛔ Ctrl+C is graceful at any point: it discards an open modal, marks the current application aborted, closes the browser and prints the normal summary.

---

## 10. Troubleshooting

**"Browser launch failed … Chromium distribution 'chrome' is not found"**
Your config's `browser.engine` points at a browser you don't have. Set `engine: edge` in `configs\config.yaml` (uses system Edge), or run `.\.venv\Scripts\python.exe -m playwright install chromium` and set `engine: chromium`.

**"No such option: -v"**
You put `-v` after the command. It must come **before**: `apply.py -v apply …`.

**"Answers file not found"**
Run `.\.venv\Scripts\python.exe apply.py init`, then edit `configs\answers.yaml`.

**"openpyxl not installed" (on `export -f xlsx`)**
`.\.venv\Scripts\python.exe -m pip install -e ".[export]"`

**"Streamlit not installed" (on `dashboard`)**
`.\.venv\Scripts\python.exe -m pip install -e ".[dashboard]"`

**A field was left blank in the logs**
Read the DEBUG line — it tells you why (e.g. the resolved value didn't match any dropdown option). Fix the value in `configs\answers.yaml`.

**Not logged in / session expired**
Re‑run `.\.venv\Scripts\python.exe apply.py login`.

---

## 11. Cheat sheet

```powershell
# Setup (once)
.\.venv\Scripts\python.exe apply.py init
.\.venv\Scripts\python.exe apply.py login

# Verify
.\.venv\Scripts\python.exe apply.py test-browser
.\.venv\Scripts\python.exe apply.py -v test-form "Expected CTC?"

# Look, don't apply
.\.venv\Scripts\python.exe apply.py scan
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# Go live
.\.venv\Scripts\python.exe apply.py apply --interactive        # confirm each
.\.venv\Scripts\python.exe apply.py apply -y -n 10             # unattended, cap 10

# Review
.\.venv\Scripts\python.exe apply.py stats
.\.venv\Scripts\python.exe apply.py export -f xlsx -o exports\applications.xlsx
.\.venv\Scripts\python.exe apply.py dashboard

# Help anytime
.\.venv\Scripts\python.exe apply.py --help
.\.venv\Scripts\python.exe apply.py apply --help
```
