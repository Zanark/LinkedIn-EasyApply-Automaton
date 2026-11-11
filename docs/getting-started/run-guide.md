# INIT — How to Run LinkedIn Easy Apply Automaton

A copy‑paste friendly guide to **starting the tool** and **every command / option**, with ready‑to‑run examples for Windows PowerShell.

## Portable Windows app

Download and fully extract the Windows x64 ZIP from
[Releases](https://github.com/Zanark/LinkedIn-EasyApply-Automaton/releases/latest).
Double-click `EasyApplyAutomaton.exe`; keep `lea.exe` and `_internal` beside it.
Python is included, but use an installed Edge/Chrome. Private configs and
runtime data default to `%LOCALAPPDATA%\EasyApplyAutomaton`; `LEA_WORKSPACE`
overrides the workspace. Existing source data is not migrated automatically.

On first launch, edit Configuration and Answers, add your PDFs through the
workspace shown in Tools, sign in with Tools, then Scan and Dry run. The Run
page includes Search/Limits/Browser/Behavior settings, private per-run presets,
submission approval and an input row for prompts. **Stop is forceful**, not
graceful Ctrl+C. See [the full desktop guide](../guides/gui.md) for limitations:
unsigned EXEs, no bundled dashboard/OpenAI, and an external Python requirement
for dynamic resume building.

**Desktop v0.2.3 and source:** compact timestamps, colored severity/activity labels
and natural word wrapping. Toggle **Details** for original diagnostic prefixes.
**Hover help:** fields, toggles and labels explain their purpose and give a
practical example on the next line. Reopen the updated GUI to load these updates.
Older EXEs are unchanged; extract v0.2.4 into a separate folder.
The toolbar also removes the right-click **Main** hide checkbox;
[recover a hidden older toolbar](../guides/troubleshooting.md#the-top-toolbar-disappeared)
without resetting your setup.

**Current action and resume (v0.2.4 and source):** every stage has its own detailed,
outlined multicolor icon above a centered rounded Nunito action name, 23% smaller than before.
Current source enlarges the icons from 40 to 64 logical pixels, keeping the
112-by-108 tile and full labels unchanged; the v0.2.4 download retains 40px icons.
The border has a soft, steady glow matching the current stage's color, without
flashing or pulsing. There is no redundant action header. Blue indicates normal work, green/teal
resume or completion work, yellow a pause/caution, and red an error/discard.
These are operation cues, not application outcomes.
The Resume field keeps the last application
filename until a later application selects another; selection alone confirms
neither upload nor submission. Scans, tools and finished commands do not clear it.

**Live counters (v0.2.2 and source):** the Run page shows Scanned, Applied, Skipped,
Failed and HR sent during Apply/Scan/Reapply; Connect shows profile/invitation
outcomes. Drafts, dry runs and uncertain submissions stay separate from sends.
Target progress and elapsed time remain visible, and the last counts survive
Stop or Clear log. See [counter meanings](../guides/gui.md#live-run-counters-current-source).
**Retry list-only (current source):** the same layout shows Targets, Failed,
Aborted, Attempts and Repeated from the saved batch. These are historical
counts, not new failures or sends; no browser opens. Live Reapply keeps the
normal application and hiring-team counters. [Preview meanings](../guides/gui.md#retry-preview-current-source).
If a command is already running, finish it before manually restarting the GUI.

### Reuse an existing setup

From your already configured checkout, use its existing environment:

```powershell
$env:LEA_WORKSPACE = (Get-Location).Path
.\.venv\Scripts\python.exe apply.py gui
```

This keeps your current answers, resumes, history and browser profile; do not
repeat initialization or overwrite them with examples. The EXE can also use
that workspace, but its optional-feature limits still apply. In particular,
an enabled dynamic builder needs `resume.builder.python` set to an actual
external Python executable. See [the reuse guide](../guides/gui.md#reuse-an-existing-setup).
Keep any machine-local input bundle under the ignored `private-setup` folder;
it is private data, not a release asset or a standalone migration.

An existing `private-setup\Start-SourceSetup.cmd` keeps running this checkout's
Python and configured workspace. It does not download or select a release.
Keep using the same launcher after updating the source; finish active commands
and save editor changes before reopening. The packaged EXE is a separate option,
not a replacement for the source launcher or its installed extras.

### Guided tutorial

```powershell
.\.venv\Scripts\python.exe apply.py gui --tutorial
```

This opens only a read-only guide: no private configuration, database or browser
startup. Use its topic list and Back/Next to explore all options. In the
GUI, **Tutorial / F1** replays it; **?** beside the customization checkbox
opens that explanation. Checking customization only exposes changed-value
overrides; Start/Copy can create a private preset without changing saved YAML.
The [full guide](../guides/gui-tutorial.md) is also readable outside the app.
Windows v0.2.1 and later include the same guide. From the extracted folder:

```powershell
.\EasyApplyAutomaton.exe --tutorial
.\lea.exe gui --tutorial
```

Older v0.2.0 EXEs do not support these tutorial flags.

The commands below are for the source checkout. In the extracted release
folder, replace `.\.venv\Scripts\python.exe apply.py` with `.\lea.exe`.

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
   - [`version`](#version) · [`init`](#init) · [`login`](#login) · [`test-browser`](#test-browser) · [`scan`](#scan) · [`apply`](#apply) · [`reapply`](#reapply) · [`sync-answers`](#sync-answers) · [`test-form`](#test-form) · [`resume-test`](#resume-test) · [`stats`](#stats) · [`export`](#export) · [`dashboard`](#dashboard)
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
.\.venv\Scripts\python.exe apply.py apply --confirm-submit   # Enter = submit; auto-submits without this flag
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

Then edit `configs\config.yaml` (searches, scoring) and `configs\answers.yaml` (your data). Put a resume in `generated\resume\` whose filename matches `resume.default` in `config.yaml` (e.g. `Example_1page.pdf`), or generate a tailored set with the standalone [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder) (`render.py publish-variants --out-dir <this-repo>\generated\resume`).

> **Optional — a fresh résumé per job.** Download the [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder), set `resume.builder.enabled: true` and `resume.builder.path: C:\path\to\dynamic-resume-builder` in `config.yaml`, and the automaton renders a résumé **tailored to each job** right before applying (e.g. an AI-heavy posting → your AI skills first). Keyword clusters work offline; see [`docs/guides/configuration.md → resume.builder`](../guides/configuration.md#resumebuilder-dynamic-per-job-resumes).

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

# 8. When you're happy, go live (auto-submits; add --confirm-submit to approve each, Enter = submit)
.\.venv\Scripts\python.exe apply.py apply --confirm-submit
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
| `--confirm-submit` / `--no-confirm-submit` | Confirm before **each** submit (prompt defaults to **Yes**, so Enter submits) / submit automatically. | auto‑submit |
| `-n, --limit INT` | Max confirmed submissions this run, not scans or a consecutive-success streak. | config `jobs.max_per_run` |
| `--url TEXT` | Ignore configured searches; use this one search URL. | — |
| `-y, --yes` | Never prompt; use available answers and auto-submit. Unresolved questions are not guessed. | prompts on |
| `--message-hiring-team` / `--no-message-hiring-team` | After each successful apply, read every "Meet the hiring team" recruiter (name + LinkedIn profile URL), draft a message, and write a plain-text report at the end of the run for you to send by hand. Never clicks anything; runs even under `-y`. Overrides `outreach.enabled`. (Set `outreach.mode: send` to message on LinkedIn instead.) | config `outreach.enabled` (on) |

```powershell
# 🟢 Safest test: fill everything, submit nothing, no prompts, full logs
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# 🔴 Go live but confirm each submission yourself (Enter = submit)
.\.venv\Scripts\python.exe apply.py apply --confirm-submit
```

> ⚠️ Running `apply` **without** `--dry-run` submits **real** applications to LinkedIn. Start with `--dry-run`.

The tool reuses a matching uploaded resume before uploading; it re-reads the picker to verify selection,
including when LinkedIn replaces its controls.

For an exact batch, put ordered LinkedIn `/jobs/view/<numeric-id>/` URLs in
`search.job_urls`. `apply` uses only those jobs, with the same checks and limits;
`--dry-run` rehearses the list. An explicit `--url` switches back to that search.

Missing skill years are left unanswered, not replaced with total experience. Hybrid/commuting
questions need explicit approved answers; an unrelated city or degree never implies Yes.
After Submit it waits up to 20 seconds for positive LinkedIn confirmation or a rejection.
No confirmation means `unconfirmed`, not applied or failed: the run stops, exits with code 2,
and excludes that job from automatic search/reapply until it has been manually reviewed.

---

### `reapply`

Retry **every failed or aborted application** in one go — no search crawl. It reads the jobs whose Easy Apply run stalled (and that were never later submitted) straight from the database and re-runs the exact same pipeline against each, opening the job by its stored URL. Jobs that eventually succeeded are never retried.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `--list` | Print the failed/aborted jobs that *would* be retried, then exit (no browser). | off |
| `--dry-run` | Fill every form but **never submit**. | off (live!) |
| `--confirm-submit` / `--no-confirm-submit` | Confirm before each submit / submit automatically. | auto‑submit |
| `-n, --limit INT` | Cap how many failed jobs to retry. | all of them |
| `-y, --yes` | Never prompt; use available answers and auto-submit. Missing facts are not guessed. | prompts on |
| `--message-hiring-team` / `--no-message-hiring-team` | Draft hiring-team outreach after each success (see `apply`). | config `outreach.enabled` |

```powershell
# See which jobs would be retried (writes nothing, no browser)
.\.venv\Scripts\python.exe apply.py reapply --list

# Retry them all, confirming each submission yourself
.\.venv\Scripts\python.exe apply.py reapply --confirm-submit
```

> 💡 Run `sync-answers --apply` (or edit `answers.yaml`) **first** — many jobs failed on a question the bot couldn't answer, so fixing the answer is what lets the retry succeed. You can also trigger this from the dashboard's **⚠️ Needs attention** tab via the **🔁 Reapply all** button.

---

### `connect`

Send your pending hiring-team recruiters a **free LinkedIn connection invitation**, preferring their ≤300-character note — never the long message. It opens its **own fresh browser** (so you can run it after an apply run has closed its browser), goes to each recruiter's profile, clicks **Connect**, and uses the note box already open or **Add a note** when needed. It reads the same `outreach_messages` table the outreach drafts live in, de-dupes by profile URL, paces itself with a random human-like delay, and stops on LinkedIn's weekly invite limit.

Set `outreach.connect_without_note: true` to permit a plain invitation only when note entry is unavailable. Current source waits for usable controls and accepts **Send without a note**, or a final **Send/Connect** inside a positively identified invitation dialog; it never substitutes an unrelated message Send. The default is `false` (skip instead); an available note is still preferred. In the source GUI, use **Run → Customize settings for this run → Behavior → Connect without a note if unavailable**. Existing conflicting or unavailable drafts are left untouched, and note-send errors never trigger a plain retry.

Only a profile **Pending** indicator or new invitation-sent confirmation records delivery; clicking or closing a modal alone does not. Successful plain invitations leave the pending queue but do not mark or strike through the unsent note. Both draft texts stay available for follow-up. The **Connection invitations** summary includes **Without note** as a subset of **Sent**. This control-recognition repair is source-only; the published v0.2.4 download is unchanged.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `--dry-run` | Rehearse Connect; **click neither final Send nor Send without a note**. | off (live!) |
| `-n, --limit INT` | Cap how many invitations to send this pass. | config `connect_max_per_run` |
| `--run INT` | Only send notes drafted during a specific run id. | all pending |
| `-y, --yes` | Skip the confirmation prompt. | prompts on |

```powershell
# Rehearse — walk the flow on every pending recruiter but send nothing
.\.venv\Scripts\python.exe apply.py connect --dry-run

# Actually send up to 10 connection notes
.\.venv\Scripts\python.exe apply.py connect -n 10
```

> This is the standalone form of the same pass the `apply` run can trigger automatically when `outreach.send_connection_notes: true`. Sending real invitations is irreversible, so it is **off by default** and prompts before it starts unless you pass `-y` or `--dry-run`.

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

### `sync-answers`

Compare every answer the automation has recorded against your **master résumé**
(`master.yaml`) and, optionally, approve the fixes. Approved values are stored as
**overrides** that the fill workflow uses *first* — ahead of `answers.yaml` and the
learned bank — so the next application uses the corrected value. Only fields the
résumé can judge are graded (total & per-skill experience, identity); salary,
notice and other preferences are never flagged.

| Option | Meaning | Default |
| --- | --- | --- |
| `-c, --config PATH` | Config file. | `configs\config.yaml` |
| `--apply` | Store the recommended values as approved overrides (writes to the DB). | off (dry run) |
| `-y, --yes` | Skip the confirmation prompt when applying. | off |
| `--list` | List the approved overrides already in effect, then exit. | off |

```powershell
# Dry run — just print what differs from your résumé (writes nothing)
.\.venv\Scripts\python.exe apply.py sync-answers

# Approve & store every recommended fix (asks to confirm first)
.\.venv\Scripts\python.exe apply.py sync-answers --apply

# Approve without the prompt
.\.venv\Scripts\python.exe apply.py sync-answers --apply -y

# Show the overrides currently in effect
.\.venv\Scripts\python.exe apply.py sync-answers --list
```

> Prefer clicking? The dashboard's **🎯 Resume match** tab does the same thing
> visually: edit **Answer to save**, tick its adjacent **Save this answer**
> checkbox, then press **Save selected answers**. The previous answer and résumé
> reference are read-only comparisons; only the editable answer is saved.

---

### `dashboard`

The default appearance is **DeepSeaFoam**, matching the desktop app's dark palette.
Native Streamlit settings in `.streamlit/config.toml` theme widgets, tables and charts;
the dashboard adds warm headings and panel-filled KPI cards. Run from the repository
root, and restart an older dashboard process once after the theme update.

Launch the Streamlit web dashboard in your browser. The UI is organised into
Excel-style tabs — **📊 Overview** (KPIs, top companies, question frequency,
résumé usage), **✅ Submitted** (every successful application as a collapsible
**company — role** card; expand one to replay exactly what was asked and the
answer submitted, start to finish), **🔎 Application details** (drill into any
application — of any status — to see every
field asked and the value submitted), **⚠️ Needs attention** (questions with no
answer on record, the applications they blocked, and a **🔁 Reapply all** button
that retries every failed/aborted job in a new console window), **⏭️ Skipped**
(how many jobs were skipped and *why* — click a reason bar for its complete
matching event list, select a row for saved job/decision details, or download
the filtered CSV; a reason picker, **Show all**, trends and a legend are included),
**🎯 Resume match** (grade
answers against your résumé, a deviation-over-time chart, and one-click *sync* of
approved corrections), and **🤝 Outreach** (drafted hiring-team messages with
clickable profile links, **Applied on** dates, both the full message and a short
**≤300-char connection note** for the invitation, plus a **Message sent**
checkbox / **Remove message-sent outreach** button to delete finished outreach) — so
nothing is one long scroll.

Outreach prioritizes applications **more than seven days old with no connection
note sent** in a separate red-outlined **Prioritize first** table, oldest first,
under the same heading. Marking a note moves that contact to regular follow-up;
undo can return it. Those contacts also have red-highlighted collapsed titles
with an **Overdue outreach** label, using the same priority rule rather than an
expiration deadline. Dates use the matching submitted application's recorded
finish (start if missing), shown in local time. Missing/invalid dates show
**Unknown**, not an age guessed from message creation.

All table columns size to their content by default, including editable review
and outreach tables. Wide tables scroll horizontally; header edges and the
column menu's **Autosize** action remain available for manual adjustments.

Skipped lists include repeated encounters, not just unique jobs, and work in
the Overview drilldown too. Future skips retain observed posting metadata and
available decision-time scores/explanations. Legacy details are labeled as the
current saved job record; missing original scores are not reconstructed.
Inspection never opens LinkedIn or creates an application.

The five headline KPI numbers are also **clickable cards**: press a card's
**View details →** button and an inline drill-down opens under the header with
charts for that category (per-day trend line, top companies, résumé usage,
workplace type / experience level, Easy Apply vs external) and a filtered table
whose job column is a clickable **Open ↗** link. Press **✕ Close** to dismiss it.

For exported files, use **Reports → In browser**, choose an Analysis or Outreach
report, then preview or **Download report**. HTML, Markdown and UTF-8 text preview
inside the dashboard; PDF/XLSX are download-only. **Open folder** instead requests
a window on the computer running the dashboard, not necessarily your browser's
computer. Empty folders mean no supported report has been written there yet.

| Option | Meaning |
| --- | --- |
| `-c, --config PATH` | Config file. |

```powershell
# Requires the [dashboard] extra (Streamlit 1.60 or newer)
Set-Location "C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton"
.\.venv\Scripts\python.exe apply.py dashboard
```

---

## 7. `apply` — every option combination explained

Three flags decide **what the tool prompts you for and whether it submits**. Understand these and you understand everything:

| Flag | What it controls |
| --- | --- |
| `--dry-run` | If present, the tool **never submits** (fills, then discards). If absent, it **submits for real**. |
| `-y, --yes` | If present, **no prompts at all** — use available answers; leave unknowns unanswered. Submits are automatic. |
| `--confirm-submit` | If present (and not `-y`), asks **"Submit application to …?"** before every submission. The prompt **defaults to Yes**, so a bare Enter submits; type `n` to skip. Omit it to submit automatically. |

### The 8 core combinations

| # | Command | Submits? | Prompts for unknown Qs? | Asks before each submit? |
| --- | --- | :---: | :---: | :---: |
| 1 | `apply` | 🔴 Yes | Yes | No (auto) |
| 2 | `apply --confirm-submit` | 🔴 Yes | Yes | **Yes** (Enter = submit) |
| 3 | `apply -y` | 🔴 Yes | No | No |
| 4 | `apply -y --confirm-submit` | 🔴 Yes | No | No¹ |
| 5 | `apply --dry-run` | 🟢 No | Yes | — |
| 6 | `apply --dry-run --confirm-submit` | 🟢 No | Yes | — |
| 7 | `apply --dry-run -y` | 🟢 No | No | — |
| 8 | `apply --dry-run -y --confirm-submit` | 🟢 No | No | — |

¹ `-y` disables all prompting, so `--confirm-submit` has **no effect** when combined with `-y`.

```powershell
# 1) Live, auto‑submit, but pause to ask YOU any question it can't answer
.\.venv\Scripts\python.exe apply.py apply

# 2) Live, safest live mode — confirm every submission (Enter = submit, n = skip)
.\.venv\Scripts\python.exe apply.py apply --confirm-submit

# 3) Live, fully unattended — most aggressive, submits everything it can
.\.venv\Scripts\python.exe apply.py apply -y

# 4) Same as #3 (‑y wins; ‑‑confirm-submit ignored)
.\.venv\Scripts\python.exe apply.py apply -y --confirm-submit

# 5) Dry‑run, still asks you unknown questions (never submits)
.\.venv\Scripts\python.exe apply.py apply --dry-run

# 6) Dry‑run + confirm-submit — nothing submits, so it just fills & asks unknowns
.\.venv\Scripts\python.exe apply.py apply --dry-run --confirm-submit

# 7) 🟢 RECOMMENDED for testing: dry‑run, no prompts, unattended
.\.venv\Scripts\python.exe apply.py apply --dry-run -y

# 8) Same as #7 (‑‑confirm-submit has no effect with ‑y)
.\.venv\Scripts\python.exe apply.py apply --dry-run -y --confirm-submit
```

### Modifiers you can add to ANY of the above

These stack onto any combination:

```powershell
# --limit / -n : cap the number of REAL submissions
.\.venv\Scripts\python.exe apply.py apply -y -n 5              # submit at most 5, unattended
.\.venv\Scripts\python.exe apply.py apply --confirm-submit -n 3 # confirm each, stop after 3

# --url : run against ONE custom search instead of your config's searches
.\.venv\Scripts\python.exe apply.py apply --dry-run -y --url "https://www.linkedin.com/jobs/search/?keywords=full%20stack%20developer&location=India&f_AL=true&f_JT=F"

# -c / --config : use a different config file
.\.venv\Scripts\python.exe apply.py apply --dry-run -c configs\config.yaml

# -v (before the command) : full DEBUG narration of every field
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

# --no-confirm-submit : be explicit that submission should be automatic
.\.venv\Scripts\python.exe apply.py apply --no-confirm-submit

# --message-hiring-team : after each successful apply, read the "Meet the hiring
#   team" recruiters (name + profile URL), draft a message, and write a report
#   at the end of the run for you to send by hand (no clicking; works under -y)
.\.venv\Scripts\python.exe apply.py apply --message-hiring-team

# Everything at once: verbose dry‑run, single URL, capped, alternate config
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y -n 10 -c configs\config.yaml --url "https://www.linkedin.com/jobs/search/?keywords=python&location=India&f_AL=true"
```

> 🤝 **Message the hiring team:** by default (`outreach.enabled: true`, `mode: draft`), after a job is submitted the tool reads each *Meet the hiring team* recruiter's name and LinkedIn **profile URL** from the page, drafts **two** variants — the full message plus a short **connection note** (≤300 chars, for the free invitation) — and, at the end of the run, writes a plain-text **report** to `generated/outreach/` listing every contact, their profile URL, the résumé to attach, the full message, and the connection note, so you can open each profile and send by hand. It clicks nothing, so it runs even under `-y`; nothing is collected during `--dry-run` (no submit → the cards never appear). Prefer it to send for you? Set `outreach.mode: send` for the interactive draft-**approve**-and-send flow (Enter sends, `n` skips; needs an interactive run, degrades to `draft` under `-y`). Either mode never contacts the same person twice and stops after `outreach.max_per_run`. Toggle the whole feature with `--message-hiring-team` / `--no-message-hiring-team`. The connection note pulls your `portfolio`/`website` from `answers.yaml` and is auto-trimmed to stay ≤300 characters. Customise either template via `outreach.template` / `outreach.note_template`.

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
| `generated\coverletter\` | Auto-generated cover letters, a `.pdf` (for upload fields) and a `.txt` per job (git-ignored). |

Watch the log live in a second PowerShell window:

```powershell
Get-Content -Wait -Tail 40 logs\easy_apply_2026-07-13.log
```

---

## 9. Safety notes

- 🟢 **Always start with `--dry-run`.** It fills forms and reaches the Submit button, then discards — nothing is ever sent.
- 🔴 **`apply` without `--dry-run` submits real applications.** Use `--confirm-submit` your first few live runs so you approve each one (Enter = submit).
- 🧍 **Don't run two browser commands at once** (e.g. `login`, `apply`, and `reapply` — including the dashboard's **🔁 Reapply all** button, which launches `reapply` in a new console) — they share the `.browser-profile` and will collide.
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
.\.venv\Scripts\python.exe apply.py apply --confirm-submit     # approve each (Enter = submit)
.\.venv\Scripts\python.exe apply.py apply -y -n 10             # unattended, cap 10

# Review
.\.venv\Scripts\python.exe apply.py stats
.\.venv\Scripts\python.exe apply.py export -f xlsx -o exports\applications.xlsx
.\.venv\Scripts\python.exe apply.py dashboard

# Help anytime
.\.venv\Scripts\python.exe apply.py --help
.\.venv\Scripts\python.exe apply.py apply --help
```
