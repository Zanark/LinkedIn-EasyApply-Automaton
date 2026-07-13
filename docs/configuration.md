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
| `download_dir`          | `downloads`        | Where downloads land.                                   |
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
| `directory` | `resumes` | Folder holding your resume files.                   |
| `default`   | `null`    | Fallback resume filename.                           |
| `mapping`   | `{}`      | `role/keyword -> filename`; best match wins.        |

Selection order: **mapping match** (score ≥ 60) → **filename-keyword overlap**
with the job text → **default**.

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

Each rule adds its weight when the keyword appears in the title/description.
Plain alphanumeric keywords use **whole-word** matching (so `go` never matches
`google`); punctuation-heavy keywords like `c++` or `.net` match by substring.
Only jobs scoring `>= threshold` are eligible.

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
> step and submit/discard decisions. `DEBUG` adds the internals: parse
> confidence, which `answers.yaml` key each value came from, every detected form
> field with its options, and why a value did or didn't fit. You don't have to
> edit this file — pass `-v` / `--verbose` **before** any command to force
> `DEBUG` for that run (e.g. `apply.py -v apply --dry-run`). Logs are written to
> `logs/easy_apply_<date>.log` (git-ignored).

### `run`

| Key                          | Default | Description                                        |
| ---------------------------- | ------- | -------------------------------------------------- |
| `dry_run`                    | `false` | Fill everything but never click final submit.      |
| `interactive`                | `false` | Ask for confirmation before each final submit.     |
| `pause_on_unknown_question`  | `true`  | Prompt you when a question can't be recognised.    |

CLI flags (`--dry-run`, `--interactive`, `--yes`, `--limit`, `--url`) override
these per invocation. The global `-v` / `--verbose` flag (placed **before** the
command) forces `DEBUG` logging for that run.

---

## `answers.yaml`

Holds the values used to auto-fill questions. Three kinds of data:

```yaml
# 1) Flat fields — personal & preference values.
phone: "+91-9000000000"
email: jane@example.com
years_experience: 8
expected_ctc: 5000000
notice_period: 30 days
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
`"Years of Java experience"` all resolve to the same skill. Questions the
resolver can map are documented in `docs/developer_guide.md`
(the `QuestionCategory` table).

---

## `searches.yaml`

An optional standalone library of named searches with the same shape as
`search.searches` in `config.yaml`. Copy the entries you want into `config.yaml`.

See also: [`developer_guide.md`](developer_guide.md),
[`faq.md`](faq.md), [`troubleshooting.md`](troubleshooting.md).
