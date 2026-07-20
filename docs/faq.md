# FAQ

### Does this store my LinkedIn password?

No. The tool **never** asks for, types, or stores credentials. You log in to
LinkedIn once in the browser profile referenced by `browser.profile_path`, and
the automaton reuses that already-authenticated session via Playwright's
persistent context.

### Will this get my account banned?

Automating LinkedIn is against their Terms of Service and carries real risk. The
tool ships with conservative defaults (`max_per_run`, `max_per_company`,
`max_daily`, optional pauses) to keep volume human-like, but **use it at your
own risk**. Start with `scan` and `--dry-run`. See the disclaimer in the README.

### How do I try it safely first?

1. `lea scan` — discovers and scores jobs, writes nothing to LinkedIn.
2. `lea apply --dry-run` — fills every field but never clicks the final submit.
3. `lea apply --interactive` — asks you to confirm before each submission.

### Is AI required?

No. AI is disabled by default and entirely optional. With `ai.enabled: false`
the flow is 100% deterministic. When enabled, AI only *advises* (match score,
missing skills, a recommendation); it can never submit an application.

### What happens when it hits a question it doesn't recognise?

By default (`run.pause_on_unknown_question: true`) it pauses and asks you for the
answer, then **remembers it** in the database for future runs. Before pausing on
a later run, it checks those learned answers and reuses the match automatically.
With `--yes` / non-interactive mode, unknown questions are skipped and the step
is recorded.

### It paused on a question — can I just fill it on the page instead of the terminal?

Yes. Either type the answer in the terminal and the tool fills LinkedIn for you,
or fill the field directly on the LinkedIn page and press Enter in the terminal.
It reads the final value back from the page, records whether it came from
`manual` input or the `portal`, and saves it for future runs.

### How do I see exactly what the tool is doing (and why)?

Add the global `-v` / `--verbose` flag **before** any command (or set
`logging.level: DEBUG`). Every run then narrates itself: the job it's on, each
form field, the question category it parsed, **which answer it resolved and from
which `answers.yaml` key**, and whether it filled the field or left it blank —
plus the submit/discard decision. Full logs land in `logs/easy_apply_<date>.log`
(git-ignored). For example:

    .\.venv\Scripts\python.exe apply.py -v apply --dry-run -y

To inspect a single question offline, `lea -v test-form "..."` shows the same
parse → resolve reasoning without opening a browser.

### How does it pick which resume to upload?

In order: an explicit `resume.mapping` match (role/keyword → filename), then
filename-keyword overlap with the job text, then `resume.default`. See
`docs/configuration.md`.

When the modal asks for a resume, the tool first reads the resume cards LinkedIn
already shows. If one matches the chosen filename, it selects that card and does
not upload again. If it is missing, it uploads the PDF through the file input and
then selects it. Manual upload is only requested when LinkedIn exposes no usable
file input — the goal is zero manual clicks.

If you enable `resume.builder`, a resume is **generated per job** first (see the
next question); the static order above is the fallback.

### Can it tailor a fresh resume to each job?

Yes — opt in with `resume.builder` (see `docs/configuration.md`). Download the
[dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder), point
`resume.builder.path` at it, and define keyword **clusters** (e.g. an `ai`
cluster). Just before applying, the automaton detects the job's cluster and asks
the builder to render a resume that surfaces the most relevant existing content
first (e.g. `Data & AI` skills under an AI headline). `mode: keyword` is offline
and deterministic; `mode: ai` asks your AI provider to choose the emphasis. Either
way it only **re-emphasises** your `master.yaml` — it never invents experience.
On no match or any error it falls back to static selection, and `scan` never
triggers a render.

### Where do the resume PDFs come from?

You can drop any PDF in `generated/resume/`, **or** generate one with the
standalone [dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder):
keep your content in one `master.yaml`, run
`python render.py publish --out-dir <this-repo>\generated\resume`, and it renders
a pixel-tuned one-page PDF straight into `generated/resume/`. See the
[resume-generation guide](resume-studio.md) for how it works.

### How do I control which jobs it applies to?

Combine `scoring.rules` + `scoring.threshold` with the `jobs` filters
(`include_keywords`, `exclude_keywords`, `blacklist_companies`,
`whitelist_companies`). Use `lea scan` to see scores before applying.

### How exactly does job scoring work?

Each job gets one number. The engine joins the **title and description** into a
single haystack and adds a rule's `weight` **once** for every `keyword` that
appears there; the job is eligible when `score >= threshold`.

- **Presence, not frequency** — a keyword counts once no matter how often it
  occurs.
- **Whole-word vs substring** — plain alphanumeric keywords match on word
  boundaries (`go` never matches `google`); punctuation keywords like `c++` or
  `.net` match by substring.
- **Negative weights are penalties** (`architect: -30`) that push roles below
  the bar. **Threshold is inclusive** (exactly `threshold` passes).
- The per-keyword `breakdown` is saved to the DB and logged at `DEBUG`:
  `Scored '…': 12 vs threshold 20 -> FAIL (breakdown: {'python': 20, 'architect': -30, ...})`.

Full reference + worked examples:
[`configuration.md` → scoring](configuration.md#scoring). Algorithm write-up:
[`algorithms.md`](algorithms.md#5-weighted-keyword-scoring--threshold).

### Why was a job skipped?

Skips happen in **two phases** (`orchestrator._process_job`). Hard **gates** are
checked first and win over any score; then the **score threshold** applies:

**Phase 1 — hard gates (`_pre_apply_checks`), first match wins:**

| Reason logged | Trips when… |
| --- | --- |
| `not_easy_apply` | the posting has no Easy Apply button (external apply) |
| `already_applied` | you already applied to this URL (recorded in the DB) |
| `duplicate_company_role` | you already applied to that company + title |
| `not_whitelisted` | `whitelist_companies` is set and the company isn't on it |
| `blacklisted` | the company is in `blacklist_companies` |
| `excluded_keyword` | an `exclude_keywords` term appears in title/description |
| `missing_include_keyword` | `include_keywords` is set and none appear |
| `company_limit` | you've hit `max_per_company` for that company |

**Phase 2 — score:** if it clears the gates but `score < threshold`, it's
skipped as `below_threshold`.

**Two later, silent skips:** `ai_advised_against` (only when AI is enabled) and
`scan_only` (`scan` mode never applies). Every decision is in the log — the
`INFO` line reads `Skip (<reason>) - <job>`, and the preceding `DEBUG` `Scored …`
line shows the exact keyword math.

### Does it overwrite fields LinkedIn already filled correctly?

No. If a text, number, select, checkbox, or radio field already contains the
same value the tool would use, it logs that the field is already filled and
leaves it as-is instead of rewriting it.

### Where is my data stored?

Locally only. A SQLite database (`database.path`) records jobs, applications,
questions/answers, AI results and errors. Nothing is sent anywhere except
LinkedIn itself (and your AI provider, if you explicitly enable one).

### Can I run it headless?

Yes — set `browser.headless: true`. Keep it headed the first few runs so you can
watch what it does and intervene if needed.

### Which browsers are supported?

Microsoft Edge (default), Google Chrome, and bundled Chromium
(`browser.engine`). For Edge/Chrome the
matching browser must be installed; for `chromium`, run
`playwright install chromium` once.

### How do I see stats / export results?

`lea stats` prints a summary table. `lea export --format csv` (or `xlsx`, which
needs the `.[export]` extra) writes applications joined with jobs to
`applications.csv` (git-ignored, so your exported data isn't committed). `lea
dashboard` launches an optional Streamlit UI (needs the `.[dashboard]` extra).

See [`troubleshooting.md`](troubleshooting.md) if something isn't working.
