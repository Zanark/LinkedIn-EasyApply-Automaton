# Run lifecycle — what happens from start to finish

> A stage-by-stage walkthrough of one run: where it starts, how a job is
> discovered, what happens when a job is found, how the form is filled, and how
> it ends. Every stage points at the **real function** that does the work and the
> **log line** you'll see. For the diagrams and the "why", see
> [`architecture.md`](architecture.md); for the design of each piece, see
> [`data-structures.md`](data-structures.md) and [`algorithms.md`](algorithms.md).

## The whole run at a glance

```mermaid
flowchart TD
    A[CLI: apply / scan] --> B[Load config + logging]
    B --> C[Load answers.yaml + open SQLite]
    C --> D[Orchestrator.run: start_run row + RunSummary]
    D --> E[Launch browser - persistent Edge profile]
    E --> F{For each enabled search}
    F --> G[JobSearch.iterate: scroll, dedupe, yield Job]
    G --> H[_process_job: upsert job + score]
    H --> I{Hard gates pass?}
    I -- no --> S1[Skip reason] --> F
    I -- yes --> J{score >= threshold?}
    J -- no --> S2[Skip below_threshold] --> F
    J -- yes --> K[Select resume + optional AI advice]
    K --> L{mode == scan?}
    L -- yes --> S3[note scan_only] --> F
    L -- no --> M[_attempt_application: create application row]
    M --> N[EasyApplyWorkflow.apply: open modal]
    N --> O{Step loop: detect -> fill -> Next/Review}
    O --> P{Submit button reached}
    P -- dry_run --> Q1[Discard - DRY_RUN]
    P -- declined --> Q2[Discard - SKIPPED]
    P -- real apply --> Q3[Click Submit - SUBMITTED]
    Q1 --> R[persist result + learn answers]
    Q2 --> R
    Q3 --> R
    R --> F
    F --> Z[finish_run + close browser + print summary]
```

---

## Phase 0 — Startup (kahaan se shuru hota hai)

You run one command, e.g. a safe test run:

```powershell
.\.venv\Scripts\python.exe apply.py -v apply --dry-run -y
```

The CLI (`cli/main.py`) prepares everything before any browser opens:

1. **`_load()`** reads `configs/config.yaml`, validates it through the Pydantic
   models, and calls **`setup_logging()`** — the console + rotating file sinks
   start here. With `-v`, the level is forced to `DEBUG`.
2. **`_answer_store()`** loads `configs/answers.yaml` into an `AnswerStore` (your
   personal data: experience, skills, contact, booleans).
3. **`_database()`** opens the SQLite file and runs `initialize()` (creates the
   schema on first use).
4. **`_run_orchestrator()`** wires the interactive callbacks based on your flags
   (`on_unknown` to ask about unrecognised questions, `on_confirm` to confirm a
   submit), constructs the `Orchestrator`, and calls `orchestrator.run(...)`.

---

## Phase 1 — Run setup (`Orchestrator.run`)

5. Resolve the effective flags (`dry_run`, `interactive`, `max_per_run`) from the
   arguments, falling back to config.
6. Read `search.enabled_searches`; if none are enabled it raises immediately.
7. **`db.start_run(...)`** inserts a row in the `runs` table and returns a
   `run_id`; a `RunSummary` counter object is created.
8. Enter the browser context manager: **`with BrowserManager(...) as browser:`**
   launches Edge (or Chrome/Chromium) using your **persistent profile** so your
   existing LinkedIn login is reused — the tool never handles your password.

```
INFO  orchestrator:run - Run starting: mode=dry_run dry_run=True interactive=False max_per_run=… | 2 enabled search(es): ['software-engineer', 'full-stack-developer']
INFO  browser.manager:start - Launching edge (headless=False) with profile .browser-profile
```

---

## Phase 2 — Discovery (`_execute` → `JobSearch.iterate`)

9. Build a `JobSearch` driver and `WorkflowSettings`. Compute
   `scan_cap = max(max_per_run * 5, 30)` — an upper bound on how many jobs to
   look at per search.
10. **For each enabled search**, log `=== Search: <name> ===` and open the
    search URL.
11. **`JobSearch.iterate(...)` is a generator.** It scrolls the results list,
    collects job IDs into a **visited `set`** (no duplicates), and **stops
    scrolling after 3 scrolls that add nothing** (you've hit the bottom) or after
    a hard cap of 15 scrolls. It then **`yield`s one `Job` at a time**, each built
    by `JobExtractor` (title, company, description, easy-apply flag, …).

```
INFO  jobs.search:open    - Opening search https://www.linkedin.com/jobs/search/?keywords=software%20engineer&…
INFO  jobs.search:iterate - Collected 7 job id(s) from 'software-engineer'
```

Each yielded job increments `summary.scanned` and flows into `_process_job`. The
loop stops early when `summary.applied >= max_per_run` (except in scan mode) or
the daily limit is hit.

---

## Phase 3 — When a job is found (`_process_job`) — *jab job milta hai toh kya hota*

For **every** job, in order:

12. **`db.upsert_job(...)`** inserts/updates the `jobs` row (idempotent on URL)
    and returns `job_id`. Logs `Job: <title> @ <company> (<posted>)`.
13. **`gate = _pre_apply_checks(job)`** runs the hard filters (Easy-Apply?
    already applied? duplicate company+role? whitelist/blacklist? include/exclude
    keywords? per-company limit?).
14. **`score = _scoring.score(title, description)`** is computed and **always
    recorded** via `db.record_score(...)`, whether or not the job proceeds.
15. **Decision:**
    - if a gate tripped → `Skip (<reason>)` and return;
    - else if `score < threshold` → `Skip (score N < T)` and return;
    - else continue.
16. **`_resume_selector.select(...)`** picks the best résumé (mapping → keyword
    overlap → default).
17. **`_advise(...)`** runs the optional AI advisor; if it says *no*, skip as
    `ai_advised_against` (no-op when AI is disabled).
18. If **`mode == "scan"`** → note `scan_only` and return — **scan never opens
    the application form.** Otherwise → `_attempt_application(...)`.

```
INFO  orchestrator:_process_job - Job: Lead Back End Engineer @ HDFC Bank (1 day ago)
DEBUG orchestrator:_process_job - Scored 'Lead Back End Engineer': 16 vs threshold 20 -> FAIL (breakdown: {'sql': 8, 'backend': 8})
INFO  orchestrator:_process_job - Skip (score 16 < 20) - Lead Back End Engineer @ HDFC Bank (1 day ago)
```

(See [`configuration.md` → scoring](configuration.md#scoring) and
[FAQ → *Why was a job skipped?*](faq.md#why-was-a-job-skipped) for the full
gate + score logic.)

---

## Phase 4 — Application attempt (`_attempt_application`)

19. **`db.create_application(...)`** inserts an `applications` row with status
    `pending` and returns `application_id` (so a crash still leaves a record).
20. Optionally render a cover letter (`_maybe_cover_letter`).
21. Build an **`EasyApplyWorkflow`**, injecting the collaborators: parser,
    resolver, field detector, filler, screenshot manager, settings, and the
    unknown/confirm callbacks.
22. Call `workflow.apply(resume_path, cover_letter_path)` (Phase 5). If it throws,
    log the error, mark the application `failed`, bump `summary.failed`, return.
    On success → `_persist_result(...)` (Phase 7).

---

## Phase 5 — The Easy Apply modal loop (`EasyApplyWorkflow.apply`) — the heart

23. **`_open_modal()`** finds and clicks the **Easy Apply** button. If it's
    missing (external application) or already says *Applied*, return `SKIPPED`.
24. Then loop over steps (`for step in 1..max_steps`). Each step:
    - wait a beat, **capture a screenshot** `step-N.png`, log `--- Easy Apply step N ---`;
    - **`_fill_step()`** → **`FormFieldDetector.detect()`** finds every field in
      the current step, then for each field **`_fill_field()`** does the
      parse → resolve → fill pipeline:
      1. **parser** turns the label into a `QuestionCategory` (with a confidence),
      2. **resolver** looks up the value from `answers.yaml` (or learned answers),
      3. if it's an **unknown** question and prompting is on, **`_handle_unknown()`**
         asks *you* (that answer is tagged `manual` and later learned),
      4. **filler** fills the text/select/radio; logs `filled with '…'` or
         `could not fill - left blank` (it never guesses a wrong option);
    - **`_detect_action()`** looks for the step's button → `submit` / `review` /
      `next` / `none`;
    - on **`next`/`review`**: record a "signature" of the step, click the button,
      and if the next step's signature is **identical** (no progress) → `_abort`;
    - on **`none`** or exceeding `max_steps` → `_abort` (safety against loops).

```
DEBUG forms.detector:detect        -   field: 'Mobile phone number' kind=number required=False options=-
DEBUG forms.easy_apply:_fill_field - Reading field 'Mobile phone number' [number] -> understood as 'phone' (confidence 97%, keyword rule)
DEBUG answers.resolver:resolve     - Resolve phone -> '+91-…' (from answers key 'phone')
INFO  forms.easy_apply:_fill_field - Field 'Mobile phone number' [number] -> phone: filled with '+91-…' (source: yaml)
DEBUG forms.easy_apply:apply       - Step 1: next action = next
```

---

## Phase 6 — The terminal decision (`_finalize_submit`)

When the **Submit** button is reached, the mode decides the ending:

| Situation | What happens | Result status |
| --- | --- | --- |
| **`--dry-run`** (a test run) | Logs `DRY-RUN: reached the Submit button … discarding WITHOUT submitting`, then **`_discard()`** clicks *Discard* and confirms the discard dialog | `DRY_RUN` |
| **`--interactive`** and you decline the confirm prompt | `_discard()` | `SKIPPED` |
| **Real apply** (no dry-run, confirmed) | Clicks **Submit** | `SUBMITTED` |
| Loop couldn't progress / no button | `_abort()` → `_discard()` | `ABORTED` |

> **This is the safety guarantee of a test run:** in `--dry-run` the tool walks
> the entire form to the very last step and then **throws it away** — nothing is
> ever sent to LinkedIn.

```
INFO  forms.easy_apply:_finalize_submit - DRY-RUN: reached the Submit button at step 3 - discarding WITHOUT submitting
```

---

## Phase 7 — Persistence & learning (`_persist_result`)

25. **`db.update_application(...)`** writes the final status, reason, step count
    and screenshot path, and marks it finished.
26. **`_record_answers(...)`** stores every question the run encountered:
    `upsert_question` + `record_application_answer`, and for any **manually**
    supplied answer, **`learn_answer(...)`** — so the **next run resolves it
    automatically** (durable memoization / human-in-the-loop learning).
27. If `SUBMITTED`: bump `summary.applied`, log a success line, and
    **`_maybe_pause()`** throttles (a human-like pause every N applications). If
    `FAILED`: bump `summary.failed`. Otherwise: `note_skip(status)`.

---

## Phase 8 — Finishing the run (`run` → `finally`)

28. After all searches finish (or a limit is hit), **`db.finish_run(run_id,
    "completed", scanned, applied, skipped, failed)`** closes out the `runs` row.
    If anything threw, it's logged, the run is marked `failed`, and re-raised.
29. Leaving the `with BrowserManager` block calls **`stop()`** → the browser
    closes.
30. `run()` returns the `RunSummary`; the CLI prints the summary table
    (scanned / applied / skipped / failed + skip-reason breakdown).

---

## What a *test run* does specifically

Two safe ways to test, and exactly where each stops:

| Command | Opens the form? | Submits? | Stops at |
| --- | --- | --- | --- |
| `apply.py scan` | ❌ no | ❌ never | Phase 3 step 18 (`scan_only`) — only discovers + scores |
| `apply.py apply --dry-run -y` | ✅ yes, fills everything | ❌ never | Phase 6 — discards at the Submit button (`DRY_RUN`) |
| `apply.py apply --interactive` | ✅ yes | only if you confirm | Phase 6 — asks you per submit |

- **`scan`** is the fastest sanity check: "which jobs would it target, and what
  score did each get?" Nothing touches the application form.
- **`apply --dry-run -y`** is the full rehearsal: it exercises the *entire*
  parse → resolve → fill pipeline on real postings and shows you exactly what it
  would submit — then throws it away. `-y` makes it unattended (no prompts).
- Turn on `-v` for either to see the complete brain trace (see
  [*Reading the logs*](troubleshooting.md#reading-the-logs) for the log line
  format and handy queries).

See also: [`architecture.md`](architecture.md) ·
[`configuration.md`](configuration.md) · [`faq.md`](faq.md).
