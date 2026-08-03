# Configuration Guide

Everything the automaton does is driven by YAML configuration — there are no
hardcoded behaviours. This guide documents every file and key.

All config lives under `configs/`. Run `lea init` to copy the bundled
`*.example.yaml` files to their real names:

| Example                       | Real file (git-ignored)   | Purpose                          |
| ----------------------------- | ------------------------- | -------------------------------- |
| `config.example.yaml`         | `configs/config.yaml`     | Main application configuration   |
| `answers.example.yaml`        | `configs/answers.yaml`    | Your personal answers            |
| `searches.example.yaml`       | `configs/searches.yaml`   | Reusable search-URL library      |

## Environment-variable expansion

Any string value in `config.yaml` may reference environment variables:

```yaml
ai:
  api_key_env: OPENAI_API_KEY        # the *name* of the env var holding the key
browser:
  profile_path: ${LEA_PROFILE}       # expands to the env var's value
logging:
  level: ${LEA_LOG_LEVEL:-INFO}      # with a default if unset
```

`${VAR}` expands to the variable (empty string if unset) and `${VAR:-default}`
supplies a fallback. This keeps machine-specific paths and secrets out of the
file.

---

## `config.yaml`

The root document has one section per subsystem. Every section is optional; a
minimal file falls back to sensible defaults. Unknown top-level keys are
rejected so typos surface immediately.

### `browser`

| Key                     | Default            | Description                                             |
| ----------------------- | ------------------ | ------------------------------------------------------- |
| `engine`                | `edge`             | `edge`, `chrome`, or `chromium` (bundled).              |
| `profile_path`          | `.browser-profile` | User-data dir reused so your login persists.            |
| `headless`              | `false`            | Run without a visible window.                           |
| `viewport_width/height` | `1440` / `900`     | Browser viewport size.                                  |
| `slow_mo_ms`            | `0`                | Delay between actions (helps you watch / debug).        |
| `download_dir`          | `downloads`        | Where downloads land (only used when `accept_downloads` is true). |
| `accept_downloads`      | `false`            | Accept browser downloads. Off by default so LinkedIn's resume-preview PDF (re-served as an attachment) isn't saved as stray GUID files; turn on only if you actually need saved downloads. |
| `default_timeout_ms`    | `30000`            | Default action timeout.                                 |
| `navigation_timeout_ms` | `45000`            | Navigation timeout.                                     |
| `max_retries`           | `3`                | Retry budget for flaky steps.                           |
| `retry_backoff_seconds` | `2.0`              | Backoff between retries.                                |
| `record_har`            | `false`            | Record a HAR of the session for debugging.             |
| `har_dir`               | `logs/har`         | HAR output directory.                                   |

> **Login is never automated.** Sign in to LinkedIn once in the browser profile
> referenced by `profile_path`; the automaton reuses that session.

### `jobs`

Guard-rails applied to every run.

| Key                   | Default | Description                                             |
| --------------------- | ------- | ------------------------------------------------------- |
| `max_per_run`         | `25`    | Hard cap on applications submitted in a single run.     |
| `max_per_company`     | `5`     | Cap per company (checked live against the database).    |
| `max_daily`           | `50`    | Cap of submitted applications per calendar day.         |
| `pause_after`         | `0`     | Pause after N applications (`0` disables).              |
| `pause_seconds`       | `15.0`  | How long to pause.                                      |
| `blacklist_companies` | `[]`    | Never apply to these companies.                         |
| `whitelist_companies` | `[]`    | If non-empty, apply **only** to these companies.        |
| `include_keywords`    | `[]`    | Title/description must contain at least one.            |
| `exclude_keywords`    | `[]`    | Skip if any appears in the title/description.           |

### `search`

```yaml
search:
  searches:
    - name: backend
      url: "https://www.linkedin.com/jobs/search/?keywords=backend&f_AL=true"
      enabled: true
```

Build a URL by running a normal LinkedIn search, applying the **Easy Apply**
filter, and copying the address bar (`f_AL=true` is that filter). URLs must
point to `linkedin.com`. Disabled entries are skipped. You can keep a library in
`searches.yaml` and paste entries here.

### `answers`

| Key               | Default                 | Description                                    |
| ----------------- | ----------------------- | ---------------------------------------------- |
| `file`            | `configs/answers.yaml`  | Path to your answers file.                     |
| `fuzzy_threshold` | `80`                    | 0–100 similarity for fuzzy question matching.  |

### `resume`

| Key         | Default   | Description                                          |
| ----------- | --------- | --------------------------------------------------- |
| `directory` | `generated/resume` | Folder holding your resume files.           |
| `default`   | `null`    | Fallback resume filename.                           |
| `mapping`   | `{}`      | `role/keyword -> filename`; best match wins.        |
| `master_path` | `null`  | Path to your `master.yaml` (résumé source of truth) used by the **Resume match** tab and `sync-answers`. Auto-located at `<builder.path>/master.yaml` then `configs/master.yaml` when unset. |

Selection order: **mapping match** (score ≥ 60) → **filename-keyword overlap**
with the job text → **default**.

> 💡 The PDFs in `generated/resume/` are built from one master content file by
> the standalone **[dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder)** —
> run `python render.py publish-variants --out-dir <this-repo>\generated\resume`
> there and it drops resumes whose filenames match your `mapping`/`default` here.

#### `resume.builder`: dynamic per-job resumes

Off by default. When enabled, the automaton asks the **downloaded**
[dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder) to
render a resume **tailored to each job right before applying** — e.g. an AI-heavy
posting surfaces your `Data & AI` skills first under an AI headline. It only
**re-emphasises / reorders / hides** content that already exists in the builder's
`master.yaml`; it never invents experience. On no match or any error it falls
back to the static `mapping`/`default` above. Rendering runs only when actually
applying (never during `scan`) and each cluster renders at most once per run.

```yaml
resume:
  builder:
    enabled: true
    path: C:\path\to\dynamic-resume-builder   # folder with render.py + master.yaml
    # python: C:\path\to\python.exe           # optional; defaults to this tool's own
    mode: keyword            # keyword (offline) | ai (needs ai.enabled + OPENAI_API_KEY)
    clusters:
      - key: ai
        keywords: [ai, ml, machine learning, llm, genai]
        title: AI / ML Engineer
        skills_order: [Data & AI, .NET & Backend, Cloud & DevOps]
        compact: true
        condense_older: true
        include_awards: false
```

| Key                   | Default   | Description                                                                 |
| --------------------- | --------- | --------------------------------------------------------------------------- |
| `enabled`             | `false`   | Master switch for dynamic generation.                                       |
| `path`                | `null`    | Folder holding the builder's `render.py` + `master.yaml`.                   |
| `python`              | `null`    | Interpreter to run it; defaults to the automaton's own (has the deps).      |
| `design`              | `SeafoamTide-Light` | Builder HTML design used for tailored resumes (e.g. `SeafoamTide-Light`, `SeafoamBubbles-Light`, `focus`). |
| `mode`                | `keyword` | `keyword` (deterministic, offline) or `ai` (asks `ai.*` provider).          |
| `ai_fallback_keyword` | `true`    | In `ai` mode, fall back to keyword clusters if the model abstains.          |
| `cache`               | `true`    | Render each cluster at most once per run.                                   |
| `timeout`             | `180`     | Seconds to wait for one render.                                             |
| `title_weight`        | `3`       | A keyword hit in the job **title** counts this much (vs `1` in the body).   |
| `min_score`           | `1`       | Minimum weighted keyword hits before tailoring overrides the static pick.   |
| `clusters`            | `[]`      | Job-keyword → emphasis rules (below).                                       |

Each **cluster** maps job keywords to one emphasis. `skills_order` names must
match the `category:` names in the builder's `master.yaml` **exactly**; keywords
match at word boundaries (so `ai` matches `ai/ml` but not `email`).

| Cluster key       | Meaning                                                              |
| ----------------- | ------------------------------------------------------------------- |
| `key`             | Short id; also names the output PDF + the per-run cache slot.        |
| `keywords`        | Lower-cased list matched against the job title + description.        |
| `title`           | Headline override for this cluster.                                  |
| `skills_order`    | Skill categories to list first (rest keep their master order).       |
| `compact`/`roomy` | Denser / airier layout.                                              |
| `include_awards`  | `false` hides Awards, `true` forces them, omitted keeps master's.    |
| `condense_older`  | Recency 1-pager: newest role full, older roles collapsed.           |
| `filename`        | Optional explicit output name (default `<Name>_<key>.pdf`).          |

> **AI mode** reuses the `ai:` provider (see below). The model may only reorder
> the categories you already have and pick a headline — it is constrained to the
> real `master.yaml` categories and cannot fabricate content.

#### Resume match & `sync-answers` (correcting submitted answers)

Independent of dynamic generation, the tool can grade every answer it has already
submitted against your `master.yaml` and let you approve corrections. It reads the
résumé from `resume.master_path` (or auto-locates `<builder.path>/master.yaml`,
then `configs/master.yaml`). Only fields the résumé can judge are graded — total &
per-skill years of experience and identity (name/email/phone/city/country);
salary, notice period, relocation and other **preferences** are reported *not
derivable* and never counted as a deviation.

Two front-ends, one effect:

- the dashboard's **🎯 Resume match** tab (metrics, a deviation-over-time chart, a
  differences-by-category bar, and an editable *approve → Sync* table); and
- the **`lea sync-answers`** CLI (`--apply` to store, `--list` to review, `-y` to
  skip the prompt).

Approved values are stored as **overrides** in the `answer_overrides` table and
take top priority in the answer-resolution order at fill time:

1. **approved override** (this feature) →
2. `answers.yaml` (the resolver) →
3. learned answer (SQLite) →
4. prompt the user.

So a synced correction is used the next time that question is asked — ahead of
`answers.yaml` and the learned bank. Use `answers.yaml` for values you set once;
use sync to fix what the bot already submitted (e.g. a stale total-experience of
`3` when your résumé shows `6`).

### `scoring`

```yaml
scoring:
  threshold: 20
  case_sensitive: false
  rules:
    - {keyword: backend, weight: 25}
    - {keyword: "c++",   weight: 15}
    - {keyword: intern,  weight: -50}
```

| Key             | Default | Description                                             |
| --------------- | ------- | ------------------------------------------------------- |
| `threshold`     | `0`     | Minimum score to be eligible; job passes if `score >= threshold`. |
| `case_sensitive`| `false` | When `false`, matching is case-insensitive.             |
| `rules`         | `[]`    | List of `{keyword, weight}` pairs (weights may be negative). |

#### How the score is computed

For each job the engine builds one haystack — the **title and description
joined** — and adds a rule's `weight` **once** if its `keyword` is found there:

```
score  = Σ rule.weight   for every rule whose keyword appears in (title + description)
passed = score >= threshold
```

Key details:

- **Presence, not frequency.** A keyword contributes its weight once whether it
  appears one time or ten. It's a set-of-signals model, not a word count.
- **Two matching modes.** A keyword made only of letters/digits/spaces
  (`^[a-z0-9 ]+$`) matches by **whole word** — `\bgo\b`, so `go` never matches
  `google`. A keyword containing punctuation (`c++`, `.net`, `node.js`) matches
  by **substring** (word boundaries misbehave around symbols).
- **Case handling.** With `case_sensitive: false` (default) both sides are
  lower-cased; keyword values are *also* lower-cased when the config loads, so
  `Python` and `python` behave identically.
- **Negative weights are penalties** used to push undesirable roles below the
  threshold (`architect: -30`, `principal: -50`, `us citizen: -80`).
- **Threshold is inclusive.** A job scoring exactly `threshold` passes.
- **Duplicate keywords accumulate.** Two rules with the same keyword each add
  their weight (they share one entry in the breakdown).

#### The breakdown (your audit trail)

`score()` returns a `breakdown` map of `{keyword: weight}` for every rule that
fired. It is stored in the database (`scores` table) **and** logged at `DEBUG`:

```
Scored 'Senior Software Engineer': 12 vs threshold 20 -> FAIL
    (breakdown: {'python': 20, 'javascript': 12, 'software engineer': 10, 'architect': -30})
```

Run with `-v` (or `logging.level: DEBUG`) and grep the log to see the math for
any job: `Select-String logs\easy_apply_<date>.log -Pattern 'Scored'`.

#### Worked examples

| Job (title) | Keywords hit | Score | Result (threshold 20) |
| --- | --- | --- | --- |
| Senior Software Engineer | python 20 + javascript 12 + software engineer 10 **− architect 30** | **12** | FAIL — a penalty sank a strong match |
| Lead Back End Engineer | sql 8 + backend 8 | **16** | FAIL |
| Software Engineer | azure 10 + software engineer 10 | **20** | PASS (exactly at threshold) |
| Software Engineer | python+javascript+react+node+azure+sql+software engineer | **82** | PASS |

#### Scoring is only half of the skip decision

The score decides *eligibility*, but a job is first run through hard **gates**
(`_pre_apply_checks`) that can skip it **regardless of score** — see
[FAQ → *Why was a job skipped?*](faq.md#why-was-a-job-skipped). The algorithmic
write-up lives in [`algorithms.md`](algorithms.md#5-weighted-keyword-scoring--threshold).

#### Tuning

- Too many good jobs skipped? Lower `threshold`, raise a keyword's weight, or
  soften a penalty (e.g. `architect: -10`).
- Applying to jobs you don't want? Add a negative rule or an
  `exclude_keywords`/`blacklist_companies` entry under `jobs`.
- Always preview with `lea scan` (scores jobs, writes nothing) before applying.

### `ai` (optional, advisory only)

| Key           | Default          | Description                                    |
| ------------- | ---------------- | ---------------------------------------------- |
| `enabled`     | `false`          | Turn AI advice on.                             |
| `provider`    | `none`           | `none` or `openai`.                            |
| `model`       | `gpt-4o-mini`    | Model name.                                    |
| `api_key_env` | `OPENAI_API_KEY` | Env var holding the API key.                   |
| `temperature` | `0.2`            | Sampling temperature.                          |
| `max_tokens`  | `800`            | Response cap.                                  |

The AI **only advises** (match %, missing skills, a recommendation). It never
auto-submits and can only *soft-skip* a job — it cannot force an application.

### `database`

| Key    | Default                    | Description               |
| ------ | -------------------------- | ------------------------- |
| `path` | `database/easy_apply.db`   | SQLite database location. |

### `screenshots`

| Key          | Default       | Description                                |
| ------------ | ------------- | ------------------------------------------ |
| `enabled`    | `true`        | Master switch.                             |
| `directory`  | `screenshots` | Output directory.                          |
| `on_error`   | `true`        | Capture on failures.                       |
| `each_step`  | `true`        | Capture each Easy Apply step.              |
| `cleanup`    | `true`        | Delete unreferenced captures at run end.     |

With `cleanup: true`, step/unknown screenshots that are not referenced by an
application record are deleted at the end of the run. After-submit evidence and
aborted-state screenshots are kept. Set `cleanup: false` when you want to keep
every screenshot for debugging. Cleanup is gated by `enabled` too.

### `logging`

| Key         | Default    | Description                              |
| ----------- | ---------- | ---------------------------------------- |
| `level`     | `INFO`     | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. `DEBUG` traces every field (parse → resolve → fill). |
| `directory` | `logs`     | Log-file directory.                      |
| `rotation`  | `10 MB`    | Rotate when the file reaches this size.  |
| `retention` | `14 days`  | How long to keep rotated logs.           |
| `serialize` | `false`    | JSON logs when `true`.                   |
| `console`   | `true`     | Also log to the console.                 |

> **Verbose "brain" logging.** `INFO` prints a readable per-field narrative plus
> step and submit/discard decisions. It also emits one aligned score gate line
> per job: `[SCORE PASS] N/T | …` or `[SCORE FAIL] N/T | …`, so PowerShell can
> grep decisions with `Select-String logs\easy_apply_<date>.log -Pattern
> '\[SCORE PASS\]'`. `DEBUG` adds the internals: parse confidence, which
> `answers.yaml` key each value came from, every detected form field with its
> options, and why a value did or didn't fit. You don't have to edit this file —
> pass `-v` / `--verbose` **before** any command to force `DEBUG` for that run
> (e.g. `apply.py -v apply --dry-run`). Logs are written to
> `logs/easy_apply_<date>.log` (git-ignored).

### `run`

| Key                          | Default | Description                                        |
| ---------------------------- | ------- | -------------------------------------------------- |
| `dry_run`                    | `false` | Fill everything but never click final submit.      |
| `interactive`                | `false` | Confirm before each final submit (prompt defaults to Yes). `false` submits automatically. |
| `pause_on_unknown_question`  | `true`  | Prompt you when a question can't be recognised.    |
| `resume_review_pause`        | `3.0`   | Seconds to pause after logging the resume pick (0 disables). |

CLI flags (`--dry-run`, `--confirm-submit`, `--yes`, `--limit`, `--url`) override
these per invocation. `--confirm-submit` turns on the terminal confirmation (its
prompt defaults to **Yes**, so pressing Enter submits); omit it to submit
automatically. The global `-v` / `--verbose` flag (placed **before** the
command) forces `DEBUG` logging for that run.

### `outreach`

Post-apply handling of the **"Meet the hiring team"** recruiters shown on a job
page. Enabled by default in the **`draft`** mode: after an application is
submitted, the tool reads each recruiter's name and LinkedIn **profile URL**
straight from the page, drafts **two** variants — the full message plus a short
**connection note** (≤300 characters, for the free invitation note) — and
records both. At the end of the run it writes a **plain-text report**
(`report_dir`) listing every contact, their profile URL, the résumé submitted
for that job (to attach), the full message, and the connection note so you can
send them by hand.
It clicks nothing, so it runs fully unattended (even under `--yes`).

Set `mode: send` to instead restore the interactive flow that pauses for your
approval and types + sends each message on LinkedIn.

| Key                | Default              | Description                                                        |
| ------------------ | -------------------- | ------------------------------------------------------------------ |
| `enabled`          | `true`               | Master switch. Overridden per-run by `--message-hiring-team` / `--no-message-hiring-team`. |
| `mode`             | `draft`              | `draft` = collect contacts + draft messages + write the report (no clicking). `send` = draft, approve, and message on LinkedIn (needs an interactive run; falls back to `draft` under `--yes`). |
| `max_per_run`      | `5`                  | Safety cap on the number of contacts handled in a single run.      |
| `template`         | *(none)*             | Optional path to a custom Jinja2 **message** template. Falls back to the built-in template. |
| `note_template`    | *(none)*             | Optional path to a custom Jinja2 **connection-note** template. The rendered note is always trimmed to ≤300 characters. Falls back to the built-in note template. |
| `skip_if_messaged` | `true`               | Never contact the same person twice (deduped by profile URL, else name). |
| `report_dir`       | `generated/outreach` | Where the plain-text `draft`-mode report is written.               |

```yaml
outreach:
  enabled: true
  mode: draft             # draft (report only) | send (message on LinkedIn)
  max_per_run: 5
  # template: configs/hiring_message.j2       # optional custom full-message template
  # note_template: configs/hiring_note.j2     # optional custom ≤300-char note template
  skip_if_messaged: true
  report_dir: generated/outreach
```

Behaviour:

- **`draft` (default) never clicks anything.** It only reads the recruiter's name
  and profile URL, so it works under `-y`/`--yes`. Nothing is collected during
  `--dry-run` (no submit → the hiring-team cards never appear). The report lands
  at `generated/outreach/outreach_run<id>_<timestamp>.txt` and its path is printed
  in the run summary. Because you send by hand, **InMail-only cards are included**
  too (you contact them from their profile).
- **`send` is draft-and-approve.** A message is shown for your approval (Enter
  sends, `n` skips), so it needs an **interactive** run and only contacts
  recruiters with a free Message button. Under `--yes` it degrades to `draft`.
- Every record (drafted, sent, declined, or failed) is written to the
  `outreach_messages` table for auditing and dedupe.
- The message context includes the role, company, your name, years of experience
  and the job's matched skills; the recruiter's first name personalises the
  greeting. The **connection note** uses the same context plus your
  `portfolio` (falling back to `website`) from `answers.yaml`, and is
  automatically trimmed to stay within LinkedIn's **300-character** invitation
  limit — the tech-stack list is shortened first, then the portfolio link, so the
  introduction and reason for reaching out always survive.

> ⚠️ Reaching out at volume can look like spam and put your account at risk. Keep
> `max_per_run` small and review every draft before you send.

---

## `answers.yaml`

Holds the values used to auto-fill questions. Three kinds of data:

```yaml
# 1) Flat fields — personal & preference values.
phone: "+91-9000000000"
phone_country_code: India (+91)
email: jane@example.com
years_experience: 8
current_ctc: 3000000         # ANNUAL, plain integer (e.g. 30 LPA INR)
expected_ctc_sde1: 3200000   # expected CTC by seniority tier — SDE 1 / junior
expected_ctc_sde2: 3500000   # SDE 2 / mid
expected_ctc_sde3: 4000000   # SDE 3 / senior+ (the ceiling)
expected_ctc: 3200000        # fallback / default tier (SDE 1)
expected_ctc_monthly_sde1: 300000  # exact monthly per tier (overrides annual/12)
expected_ctc_monthly_sde2: 320000
expected_ctc_monthly_sde3: 340000
notice_period: 45 days       # fallback only (non-numeric answers like "Immediate")
notice_period_days: 45       # numeric days used for ALL notice questions (submitted as a plain number)
authorization: true          # yes/no questions accept true/false or yes/no
visa: false
relocation: true

# 2) Skills — years of experience, with optional aliases.
skills:
  Java:
    years: 6
    aliases: [Core Java, J2EE]
  Python: 5                   # shorthand: just the years

# 3) Aliases — map an alternate label to a canonical field.
aliases:
  mobile: phone
  expected compensation: expected_ctc

# Defaults for anything not explicitly answered.
defaults:
  onsite: true
```

Lookups are **alias-aware and normalised**, so `"Java"`, `"Core Java"`, and
`"Years of Java experience"` all resolve to the same skill. Use
`phone_country_code` for LinkedIn's separate country-code picker; match the
visible option label (for example `India (+91)`). If it is omitted, the tool
silently uses `+91` and only prompts when the portal is already set to a
*different* country code.

**Salary, INR and monthly questions.** Store `current_ctc` as the **annual**
amount (plain integer, no commas or currency). **Expected** salary is chosen per
job by the role's **seniority tier** — inferred from the job title (falling back
to LinkedIn's experience level) — via `expected_ctc_sde1` / `expected_ctc_sde2` /
`expected_ctc_sde3` (SDE 1 / 2 / 3). When the level can't be inferred it defaults
to the **SDE 1** band, and `expected_ctc` is the catch-all fallback. Answers are
always just the number (so an "amount in INR" field gets `4000000`, never
`40,00,000`). If a question asks for a **monthly** figure, the tool prefers an
**exact per-tier monthly** value when configured — `expected_ctc_monthly_sde1` /
`_sde2` / `_sde3` (e.g. `300000` / `320000` / `340000`) — so each tier reports a
hand-picked take-home rather than a division artefact. When no monthly key is set
it divides the annual amount by 12 instead: **expected** salary rounds to the
nearest **100,000** while **current** salary rounds to the nearest **10,000**
(30 LPA → `250000`/month) so it stays accurate. Expected values are recomputed per
job and never persisted; a computed current-salary value is saved so it is reused
without recomputing.

**Notice period.** Notice-period answers are **always submitted as a plain
number** (e.g. `45`), never `45 days` — even for a generic "What is your notice
period?" field. `notice_period_days` (e.g. `45`) is the numeric value used for
every notice question; if it is absent, the tool pulls the first integer out of
the free-text `notice_period`. `notice_period` is only kept as a literal answer
when it is genuinely non-numeric (e.g. `Immediate`) and the question is not
asking for a number of days.

**Custom screening questions.** Some postings ask bespoke questions the category
parser cannot recognise (shift timings, a location picker, a project-specific
consent). Left unanswered these get skipped, and under `-y` an unanswered
required question aborts the application. A `custom_questions` list is the escape
hatch — it maps keyword patterns to a canned answer:

```yaml
custom_questions:
  - match: ["shift timing", "night shift", "rotational shift"]
    answer: "Yes"                       # Yes/No fills selects, radios & checkboxes
  - match: ["which location are you applying", "preferred location"]
    answer: ["Bengaluru", "Hyderabad"]  # ordered dropdown fallbacks
  - match: "notice period negotiable"
    answer: "Yes"
```

An entry matches when **any** of its `match` keywords (normalised — case- and
space-insensitive) appears anywhere in the question text; the first matching
entry wins. The `answer` may be:

- **`"Yes"`/`"No"`** — filled as a boolean, so it satisfies Yes/No selects,
  radio groups and checkboxes.
- **a plain string** — typed into a text field or matched against a dropdown.
- **a list** — ordered dropdown fallbacks: the tool tries each value against the
  actual options and picks the **first one that exists** (so `["Bengaluru",
  "Hyderabad"]` prefers Bengaluru but takes Hyderabad when Bengaluru isn't
  offered).

Custom answers are consulted **only as a fallback** — built-in category handling
(salary tiers, notice period, work-authorization booleans, contact fields…)
always takes priority and is never shadowed by a `custom_questions` entry.

Questions the resolver can map are documented in `docs/developer_guide.md` (the
`QuestionCategory` table).

---

## `searches.yaml`

An optional standalone library of named searches with the same shape as
`search.searches` in `config.yaml`. Copy the entries you want into `config.yaml`.

See also: [`developer_guide.md`](developer_guide.md),
[`faq.md`](faq.md), [`troubleshooting.md`](troubleshooting.md).
