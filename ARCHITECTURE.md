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

    resumes/

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
resumes/

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

---

# Answers Database

Maintain:

answers.yaml

Example:

```
phone:

email:

notice_period:

current_ctc:

expected_ctc:

linkedin:

github:

portfolio:

authorization:

visa:

relocation:

remote:

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

---

# Unknown Questions

If a question cannot be recognized:

Pause.

Show:

Question text

Screenshot

HTML

Allow manual input.

Store answer.

Learn for future runs.

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

Automatically generate personalized cover letters if requested.

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

Rate limiting

Retry intelligently.

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
