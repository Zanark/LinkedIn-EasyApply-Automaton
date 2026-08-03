This is exactly the kind of project where a **good specification** is worth far more than jumping straight into code.

I would ask the coding agent to build this like a **production-quality software project**, not just a Python script. The prompt below is written as if you were a senior engineer handing requirements to another senior engineer.

---

# Prompt

You are a Senior Python Automation Engineer and Software Architect.

Your task is to design and build a production-quality LinkedIn Easy Apply automation framework.

This is NOT a hackathon project or a simple Selenium script.

I expect clean architecture, maintainable code, documentation, configuration, extensibility and proper software engineering practices.

The application should be built so that new automation workflows can be added later.

---

# Overall Goal

The application should automate my own LinkedIn Easy Apply workflow.

Assume I am already logged into LinkedIn.

The application should open my logged-in browser profile, navigate to a LinkedIn Job Search page, inspect each job, determine whether it qualifies, and apply to it automatically while handling multi-step Easy Apply forms.

The project should minimize manual repetitive work while still allowing manual intervention whenever necessary.

---

# Important Constraints

DO NOT automate login.

DO NOT use bots that bypass authentication.

DO NOT scrape credentials.

DO NOT require storing LinkedIn username/password.

The browser should reuse my existing Chrome profile.

---

# Technology Stack

Python 3.12+

Playwright

SQLite

Pydantic

PyYAML

Loguru

Typer (CLI)

pytest

black

ruff

mypy

Jinja2 (if templates become useful)

fpdf2 (cover-letter PDF rendering)

Optional:

Streamlit dashboard

OpenAI integration

---

# High Level Architecture

Design the application using modular architecture.

Suggested layout:

```
linkedin_easy_apply/

    app/

        browser/

        jobs/

        parser/

        forms/

        answers/

        scoring/

        ai/

        database/

        dashboard/

        config/

        logging/

        cli/

        utils/

    configs/

    generated/

    logs/

    screenshots/

    database/

    tests/

    docs/

```

Every module should have a single responsibility.

No spaghetti code.

No giant main.py.

---

# Browser Module

Use Playwright.

Launch using a persistent browser profile.

Example:

```
launch_persistent_context(...)
```

Browser should support:

Chrome

Edge

Chromium

Headed mode

Headless mode

Configurable viewport

Configurable download directory

Automatic retries

Automatic waits

---

# Configuration

Everything must be configurable.

Use YAML.

Example:

```
browser:

  profile_path:

  headless:

jobs:

  max_per_run:

  max_per_company:

  max_daily:

search:

  url:

answers:

  file:

resume:

  default:

logging:

  level:
```

No hardcoded values.

---

# Job Discovery

The application should accept one or more LinkedIn Job Search URLs.

Example:

```
python apply.py \
--url "https://linkedin.com/jobs/search/..."
```

or

```
searches:

  backend:

      url:

  sre:

      url:

  architect:

      url:
```

The application should iterate over every search.

---

# Job Extraction

For every visible job gather:

Job title

Company

Location

Job URL

Easy Apply availability

Already applied?

Number of applicants

Posting age

Employment type

Experience level

Workplace type

Job description

Recruiter information if visible

Salary if available

Store all information inside SQLite.

---

# Duplicate Detection

Never apply twice.

Detect duplicates using:

Job URL

Company + Role

Application history

Database

---

# Resume Management

Support multiple resumes.

Example:

```
generated/resume/

Backend.pdf

Java.pdf

Azure.pdf

SRE.pdf
```

Allow mapping.

Example:

```
Backend Engineer

-> Backend.pdf

Site Reliability Engineer

-> SRE.pdf
```

---

# Resume Selection

Automatically choose the best resume.

Strategies:

Keyword matching

Weighted scoring

Optional LLM recommendation

Fallback to default resume

Log the chosen resume at INFO with its reason, then pause `run.resume_review_pause`
seconds (default 3) before applying so the pick is readable in the live log.

When attaching inside LinkedIn, first inspect the on-page resume cards and
select the one whose filename matches the target. Upload the PDF only when no
matching card exists, then select the uploaded card. Ask for manual upload only
when no programmatic file input is available.

**Per-job dynamic generation (optional).** When `resume.builder.enabled`, the
orchestrator invokes the external [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder)
just before applying to render a résumé tailored to the job (keyword clusters or
an LLM re-emphasis of the existing `master.yaml`). Falls back to the strategies
above on no match or any error. See `docs/configuration.md → resume.builder`.

---

# Job Scoring

Create a scoring engine.

Each job receives a score.

Example:

Backend +20

Azure +20

Distributed Systems +15

Kubernetes +10

Java +10

Principal -50

Staff -40

Rust -30

Go +5

Remote +5

User configurable.

Only jobs above threshold continue.

Emit an INFO scoring decision for every job as `[SCORE PASS] score/threshold |`
or `[SCORE FAIL] score/threshold |`, while keeping the full breakdown at DEBUG.

---

# Easy Apply Workflow

Detect Easy Apply button.

Ignore normal Apply buttons.

Click Easy Apply.

Navigate through every step.

Handle:

Next

Continue

Review

Submit

Cancel

Discard

Close

Detect progress.

Handle unexpected dialogs.

Skip filling any text, number, select, checkbox or radio field that already
contains the resolved value.

---

# Dynamic Form Engine

This is the most important module.

The application must NOT assume every company uses the same form.

Instead inspect the DOM.

Recognize fields dynamically.

Examples:

Text field

Textarea

Dropdown

Checkbox

Radio

Date picker

Resume upload

Cover letter upload

Numeric input

Phone number

Phone country code

Email

URL

Salary

Notice period

Experience

LinkedIn profile

Portfolio

GitHub

---

# Question Recognition

Create a generic parser.

Given:

```
How many years of Java experience do you have?
```

Recognize:

Category:

Experience

Skill:

Java

Answer source:

answers.yaml

---

Another example:

```
What is your expected annual salary?
```

Recognize:

Salary expectation

---

Another example:

```
Are you legally authorized to work in India?
```

Recognize:

Work authorization

---

Do NOT rely only on exact text matching.

Support fuzzy matching.

Treat phone country code as a distinct category from phone number. Default it to
`+91` / `India (+91)` and prompt only when the portal is pre-set to a different
country code.

Detect answer modifiers (tags) that change how a value is rendered: a salary
asked **monthly** vs **annual**, a currency hint (**INR**), and a notice period
asked **in days**. Current salary is stored annually and divided by 12 (rounded
to the nearest 10,000) for monthly questions. **Expected** salary is chosen per
job by the role's **seniority tier** (SDE 1/2/3, inferred from the job title;
default SDE 1); its monthly form uses an exact per-tier value when
`expected_ctc_monthly_sde1/2/3` is configured and otherwise divides by 12 and
rounds to the nearest 100,000. INR/number questions get a plain integer with no
commas; a computed *current*-salary value is persisted as a learned combo, while
*expected* salary (job-specific) is not.

---

# Answers Database

Maintain:

answers.yaml

Example:

```
phone:

phone_country_code:

email:

notice_period:

notice_period_days:

current_ctc:

expected_ctc_sde1:

expected_ctc_sde2:

expected_ctc_sde3:

expected_ctc:

linkedin:

github:

portfolio:

authorization:

visa:

relocation:

remote:

custom_questions:   # keyword -> canned answer for bespoke screening questions

skills:

    Java:

        years:

    Python:

        years:

    Kubernetes:

        years:

```

Support aliases.

Example:

Java

Core Java

Java Programming

Years of Java Experience

Should all resolve to the same answer.

Before prompting for an unconfigured answer, query previously learned question
answers in SQLite and reuse a match automatically.

---

# Unknown Questions

If a question cannot be recognized:

Pause.

Show:

Question text

Screenshot

HTML

Allow manual input.

Allow the user to type in the terminal, or fill the field directly in the
LinkedIn page and press Enter so the automaton reads the portal value back.

Store the final answer with source `manual` or `portal`.

Learn for future runs.

For questions that recur across postings but the parser cannot categorise (shift
timings, a location picker, a project-specific consent), a `custom_questions`
keyword map in `answers.yaml` pre-answers them so unattended (`-y`) runs never
stall. Custom answers are consulted only as a fallback, after built-in category
resolution, so smart handling (salary tiers, notice period, booleans) is never
shadowed.

---

# AI Integration (Optional but Recommended)

Support an LLM provider.

Given:

Resume

Job Description

Return:

Match %

Missing skills

Recommendation

Reasons

Suggested resume

Suggested cover letter

Should Apply?

The AI should NOT replace deterministic automation.

It should only advise.

---

# Cover Letters

Support templates.

Variables:

Company

Role

Tech stack

Automatically generate personalized cover letters if requested. Each letter is
rendered once and persisted as a **`.pdf`** (the artefact LinkedIn upload fields
expect) and a **`.txt`**; the letter text is also used to auto-fill inline
cover-letter **textareas**. PDF rendering uses the pure-Python `fpdf2` engine
(core Helvetica font, A4), so non-Latin-1 punctuation is sanitised down to ASCII
to keep rendering crash-free.

---

# Meet-the-Hiring-Team Outreach

After a successful application the job page often shows a **"Meet the hiring
team"** section with recruiter cards. When enabled (`outreach.enabled` or
`--message-hiring-team`, on by default), the orchestrator runs a post-submit
outreach pass with two modes:

- **`draft` (default)** — read each recruiter's name and LinkedIn **profile URL**
  straight from the card, draft a personalised message, and record it with status
  `drafted`. It clicks nothing (so it runs even under `--yes`) and does not need a
  free Message button. At the end of the run `orchestrator._emit_outreach_report`
  turns the run's drafts into a plain-text report under `generated/outreach/`.
- **`send` (opt-in)** — draft, call an **approval callback**, and only then dismiss
  the post-apply upsell modal, click **Message**, type into the contenteditable
  compose box (without emitting Enter), and click **Send**. Needs an interactive
  session; degrades to `draft` when none is available.

Pieces:

- `answers/hiring_message.py` — `HiringTeamMessenger` renders the message from a
  Jinja2 template (built-in default, or a user `template` path), mirroring the
  cover-letter generator.
- `answers/hiring_report.py` — `render_outreach_report` turns drafted DB rows into
  the plain-text report (a pure function).
- `forms/outreach.py` — `HiringTeamOutreach` detects the section + cards and drives
  the mode. Both modes de-dupe against people already messaged
  (`database.has_messaged_person`), honour a per-run cap, and record every row
  (`drafted` / `sent` / `declined` / `failed`) via `database.record_outreach`.

Errors are swallowed with a warning so outreach can never fail an
otherwise-successful apply; nothing runs during `--dry-run` (no submit → no cards).

---

# Logging

Every action should be logged.

Include:

Timestamp

Action

Duration

Errors

Warnings

Navigation

Question detected

Answer selected

Resume chosen

Implemented with Loguru (`logging/setup.py`): **INFO** emits the readable
per-field narrative (navigation, question detected, answer selected **and its
source**, resume chosen, submit/discard), while **DEBUG** adds parse/resolve/
detect/fill internals. Pass the global `-v` / `--verbose` flag (before the
command) or set `logging.level: DEBUG` for the full trace.

Application status

---

# Screenshots

Take screenshots:

Job page

Every form page

Before Submit

After Submit

Errors

Store by timestamp.

At the end of a run, when screenshot capture and cleanup are enabled, delete
orphan step/unknown screenshots and keep screenshots referenced by application
records, such as after-submit evidence or aborted-state captures.

---

# Database

SQLite.

Tables:

Jobs

Applications

Questions

Answers

Runs

Errors

Resumes

Scoring

AI Results

---

# Dashboard

Build optional Streamlit dashboard.

Display:

Applications today

Success rate

Failures

Companies

Roles

Question frequency

Resume usage

Score distribution

Manual interventions

**Application details (drill-down):** pick any application and see exactly which
questions were asked and the value submitted for each (from
`application_answers`), plus the résumé that was submitted and a link to the job.

**Needs attention (unanswered questions & blocked applications):** an aggregate
view of the questions the automation had *no answer* for — surfaced only when a
question was left blank *and* was never given a value in any application (so
already-prefilled fields such as email or phone country code are excluded, not
mistaken for gaps). Each row shows how many applications it was blank in and how
many of those ended blocked (`failed`/`aborted`, usually "No progress between
steps"), so the highest-impact gaps to add to `answers.yaml` / `custom_questions`
sort to the top. A companion expander lists the blocked/aborted applications
themselves with a trimmed reason and the count of unanswered questions per
attempt. Backed by `database.unanswered_questions` and
`database.blocked_applications`.

**Hiring-team outreach (web view):** the drafted "messages to send" as a table
with clickable LinkedIn profile links (so you open each profile in one click) and
the résumé to attach, plus a per-contact expander with the copy-ready message.
Backed by `database.outreach_drafts`, which joins each draft to the résumé
submitted for that job.

---

# CLI

Commands:

```
apply

scan

dashboard

resume-test

test-form

test-browser

stats

export

```

---

# Error Handling

Recover from:

Browser crash

Network timeout

DOM changes

Missing elements

Slow loading

Unexpected popups

Resume upload failures

Ctrl+C / keyboard interrupt during any step or prompt

Rate limiting

Retry intelligently.

On Ctrl+C, discard any open Easy Apply modal, mark the current application as
aborted, close the browser, clean orphan screenshots, and return the normal run
summary instead of a stack trace.

---

# Testing

Write unit tests.

Integration tests.

Mock Playwright.

Test parser.

Test scoring.

Test answer resolution.

---

# Documentation

Create:

README

Architecture document

Configuration guide

Developer guide

FAQ

Troubleshooting

---

# Code Quality

Type hints everywhere.

Docstrings.

Dependency injection where appropriate.

SOLID principles.

No duplicated logic.

No magic strings.

No global variables.

Clean folder structure.

---

# Nice-to-Have Features

* Dry-run mode (navigate and inspect jobs without applying)
* Interactive approval mode (prompt before final submit)
* AI resume scoring and cover-letter generation
* Export applications to CSV/Excel
* Email summary after each run
* Slack/Discord notifications
* Automatic pause after configurable number of applications
* Per-company application limits
* Blacklist/whitelist for companies
* Keyword include/exclude filters
* Capture HAR files for debugging Playwright sessions
* Plugin system so support for other job boards (Indeed, Wellfound, Naukri, etc.) can be added later without changing the core engine

---

# Expected Deliverables

1. Complete source code.
2. Fully documented project.
3. Requirements file or `pyproject.toml`.
4. Installation instructions.
5. Configuration examples.
6. Example `answers.yaml`.
7. Example search configuration.
8. Sample SQLite database schema.
9. Tests with good coverage.
10. Clear instructions for extending the framework with new form handlers, scoring rules, AI providers, or job sources.

Build this as if it were an open-source project that other engineers could install, understand, and extend—not as a one-off automation script.
