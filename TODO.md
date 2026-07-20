# LinkedIn-EasyApply-Automaton — Improvements TODO

Post-live-test automation improvements.

- **Date:** 2026-07-20
- **Commit:** `a60b1f9` (24 files, +958/-70)
- **Status:** committed, **not yet pushed**
- **Tests:** full suite 109 tests green · `ruff`/`black` clean · PII kept out of git

## new todo — Cover letter: PDF + inline textarea + logging (2026-07-21) — DONE (uncommitted)

After the submit fix, the G-P form had **no** cover-letter field, but letters were
only ever written as `.txt` (LinkedIn upload fields want PDF/DOC) and inline
cover-letter textareas were never auto-filled. Fixed all three:

- [x] **Render a PDF.** `CoverLetterGenerator` now writes a `.pdf` (pure-Python
  `fpdf2`, A4, Helvetica) alongside the `.txt`. Non-Latin-1 punctuation is
  sanitised to ASCII so core-font rendering never crashes. New `render_pdf_to_file`
  + `render_all` (returns text + both paths via `RenderedCoverLetter`).
- [x] **Auto-fill inline textareas.** A COVER_LETTER text/textarea field is now
  filled with the generated letter text (`_fill_cover_textarea`), bypassing the
  generic resolver/prompt. File-upload cover fields still get the PDF.
- [x] **Clear logging.** INFO on generation (`Generated cover letter for '<company>'
  -> <path>`), on inline fill (`filled inline (N chars)`), and on PDF upload.
  - **Files:** `answers/cover_letter.py` (PDF + `RenderedCoverLetter` + sanitiser),
    `orchestrator.py` (`_maybe_cover_letter` -> `render_all`, INFO log, passes text),
    `forms/easy_apply.py` (thread `cover_letter_text` through `apply`/`_fill_step`/
    `_fill_field`, new `_fill_cover_textarea`), `pyproject.toml` (`fpdf2>=2.7`).
- [x] Tests: `tests/test_cover_letter.py` +5 (PDF header, both artifacts, unicode,
  textarea auto-fill, file-field routing). Full suite **174** green; ruff/black/mypy
  clean. Docs synced (README, INIT.MD, ARCHITECTURE, run-lifecycle, architecture,
  coverletter README).

## new todo — Auto-submit by default + default-Yes confirm flag (2026-07-21) — DONE (uncommitted)

Live test showed every job ended `You declined submission - discarding` — the old
`--interactive` confirm defaulted to **No**, so a bare Enter discarded and nothing
was ever submitted (that's why the "Your application was sent!" modal never showed).

- [x] **Default = auto-submit.** Submission now happens automatically; the confirm
  gate is decoupled from unknown-question prompting and from `settings.interactive`
  (`_finalize_submit` submits unless an `on_confirm` handler is wired).
- [x] **New `--confirm-submit / --no-confirm-submit` flag** (replaces `--interactive`).
  Its terminal prompt now **defaults to Yes**, so pressing Enter submits; `n` skips.
- [x] Unknown-question prompting still on by default (only `--yes` silences it).
  - **Files:** `forms/easy_apply.py` (guard now `if self._on_confirm and not self._on_confirm()`),
    `cli/main.py` (flag rename, `typer.confirm(default=True)`, resolve vs `run.interactive`),
    `config/models.py` + `configs/config.example.yaml` (comment), README/INIT.MD/docs synced.
- [x] New `tests/test_submit_confirmation.py` (5 cases: auto-submit, accept, decline,
  interactive-independent, dry-run). Full suite **169** green; ruff/black/mypy clean.

## ✅ Completed — your original asks (verbatim), all DONE

- [x] update the code to clean up the screenshots folder towards the end of the work so that no orphan screenshots remain.
  - **Done.** New config `screenshots.cleanup` (default true). At run end, deletes unreferenced step/unknown screenshots; keeps captures referenced by an application record (after-submit, aborted-state). Gated on `screenshots.enabled`.
  - **Files:** `config/models.py`, `orchestrator.py` (`_cleanup_screenshots`).

- [x] do you select a resume from the list by searching for it or do you upload a resume from local, you shoudl always first check the list of resumes shown on the portal, if you dont see the name of the resume that should be updated then you should upload the file of the resume which should have been present and once uploaded you should select that. MAKE SURE THIS THING IS TESTED EXTENSIVELY CUZ THE WHOLE DEAL OF CREATING THIS AUTOMATION IS TO NOT HAVE ME CLICK ANYTHING AND I WANT YOU TO DO THE FILE UPLOAD IF POSSIBLE. IF ITS NOT POSSIBLE ONLY THEN TELL ME TO UPLOAD THE FILE FOR YOU.
  - **Done (code).** Now checks the on-page resume cards FIRST; selects a card whose filename matches the target. If missing, uploads the PDF via the file input and then selects it. Asks for a manual upload ONLY when no programmatic file input exists.
  - **Files:** `forms/easy_apply.py` (`_ensure_resume_selected` / `_resume_cards` / `_card_selected` / `_select_card` / `_ask_manual_upload` / `_resume_matches`), `forms/selectors.py`.
  - **⚠️ Still needs the extensive live test you asked for:** the resume-card + upload selectors are heuristic and unvalidated against the real LinkedIn DOM. See **Remaining / next steps** below.

- [x] need to add flags in logging when a particular job passes the score. need to have a seperate column for that in the logs
  - **Done.** Per-job INFO line `[SCORE PASS] N/T | summary` or `[SCORE FAIL] N/T | summary` at the score gate (both tags same width so it reads as an aligned, greppable column). DEBUG breakdown kept.
  - **Files:** `orchestrator.py` (`_process_job`).

- [x] phone country code should be left default cuz its always (+91) if you see anything else only then flag or request for user input
  - **Done.** Recognized as its own category (distinct from the phone-number field). Defaults to +91; only pauses/flags when the portal is pre-set to a DIFFERENT country code. Answer key `phone_country_code` (e.g. "India (+91)") overrides the default.
  - **Files:** `parser/categories.py`, `parser/question_parser.py`, `answers/resolver.py`, `forms/matching.py`, `forms/easy_apply.py` (`_handle_country_code`).

- [x] are you recoridng a database of all possible questions that are asked so that the user input is minimized to the most
  - **Yes + improved.** The DB already recorded every asked question + answer; now the resolver also REUSES them — it looks up a previously learned answer before pausing on an unconfigured question.
  - **Files:** `orchestrator.py` (`answer_lookup=db.get_known_answer`), `forms/easy_apply.py`.

- [x] there will be times when you would ask me for the answer to a question, what if i fill it directly on the website form, will you be able to take info from there? I want you to be able to take it from either of the locations, if I fill in on the portal I can just press enter in terminal, If I fill in on terminal then you need to fill it on the portal. in the end you should always register the question that came up on the portal in your database and you should also always register the corresponding anwer I filed.
  - **Done.** When paused you can either type the answer in the terminal (tool fills LinkedIn) OR fill the field on the page and press Enter (tool reads it back). Either way the question + final answer are saved to the DB (source recorded "manual" or "portal") and reused next time.
  - **Files:** `forms/easy_apply.py` (`_resolve_interactively`), `forms/values.py` (`current_value_of`), `cli/main.py`, `orchestrator.py`.

- [x] if you see a field prefilled with some data, and it matches with your answers in the db, then just skip that field, you dont need to overwrite that same field with the same value again
  - **Done.** If a field already holds the value the tool would fill, it leaves it as-is (logs "already filled ... leaving as is") instead of rewriting. Text/number/select/checkbox/radio.
  - **Files:** `forms/filler.py` (`matches_current`), `forms/detector.py`, `forms/field.py`, `forms/values.py`.

- [x] (from the same message) "maybe add something that will gracefuly end the porgram if I do a ctrl+c"
  - **Done.** Ctrl+C anywhere (including at a prompt) exits cleanly: discards the open modal, marks the in-flight application "aborted", closes the browser, cleans screenshots, prints the summary table — no stack trace.
  - **Files:** `cli/main.py` (`Abort`/`EOF` → `KeyboardInterrupt`), `orchestrator.py`, `forms/easy_apply.py` (`discard_open`).

## ✅ Completed — supporting work

- [x] New module `forms/values.py` (`current_value_of`) — reads what a control currently holds.
- [x] New tests: `tests/test_form_improvements.py` + `tests/test_orchestrator_improvements.py` (31 tests).
- [x] Full suite 109 green; `ruff` + `black` clean; all changed modules import clean.
- [x] Config examples updated (`configs/config.example.yaml`, `configs/answers.example.yaml`); real git-ignored configs updated locally too.
- [x] Docs synced (7): `README.md`, `INIT.MD`, `ARCHITECTURE.md`, `docs/{configuration,faq,troubleshooting,run-lifecycle}.md`.
- [x] Committed `a60b1f9` with required trailers; PII (`config.yaml` / `answers.yaml` / `generated` / `screenshots`) excluded.

## ⏳ Remaining / next steps

- [ ] **Live-test validation** (you run; I read logs at `logs\easy_apply_<today>.log`):

  ```powershell
  python apply.py -v apply --dry-run --limit 1       # score column, country-code, resume-card detection
  python apply.py -v apply --limit 1 --interactive   # real resume upload + bidirectional Q&A + submit
  ```

  (Press **Ctrl+C** at a prompt to confirm graceful shutdown.)

  Grep hints:

  ```powershell
  Select-String logs\easy_apply_*.log -Pattern '\[SCORE PASS\]|\[SCORE FAIL\]'
  Select-String logs\easy_apply_*.log -Pattern 'resume|Uploading|card'
  Select-String logs\easy_apply_*.log -Pattern 'country code'
  ```

- [ ] **Tune resume-card / country-code `SELECT` selectors** against the real DOM if the live test reveals mismatches.
- [ ] **git push** (held until the live test confirms resume upload + country-code work against live LinkedIn).



# new todo — Salary / notice period / resume-log (2026-07-20) — DONE (uncommitted)

This batch is implemented and green (full suite **121 tests** · `ruff`/`black`/`mypy` clean)
but **not yet committed** — awaiting your review + live test, then it ships alongside the
earlier `a60b1f9` on push.

- [x] for question like what is your notice period in days, just mention the numerical value 45. This is a fixed value that should be provided in the config.
  - **Done.** `notice_period` (free text, e.g. `45 days`) still answers most phrasings; new `notice_period_days: 45` is returned as the plain number when a question asks for the notice period **in days**. Falls back to the digits inside `notice_period` if the numeric key is absent.
  - **Files:** `parser/question_parser.py` (days/weeks/months tags), `answers/resolver.py` (`_resolve_notice_period`), `configs/answers.yaml` + `answers.example.yaml`.

- [x] current yearly ctc in INR will be mentioned in the config. if a question comes up that asks for current net salary in INR monthly, then the tool needs to calculate and enter the value and the save that as one of the question answers combos. My current yearly CTC is 30 LPA INR
  - **Done.** `current_ctc: 3000000` (30 LPA, annual). A **monthly** question divides by 12 → enters `250000`, and saves the question/answer combo (source `computed`, learned so it isn't recomputed/asked next time).
  - **Files:** `answers/resolver.py` (`_resolve_salary`), `parser/question_parser.py` (monthly/annual/inr tags), `orchestrator.py` (learn `computed`), `configs/answers*.yaml`.

- [x] expected salary should be configured in config. for me it is 40LPA CTC INR. if question asks for monthly expected then the tool needs to calculate and then save again
  - **Done.** `expected_ctc: 4000000` (40 LPA, annual). Monthly → annual ÷ 12 = 333,333 **rounded to the nearest 10,000 → `330000`**, entered and saved as a learned combo. (Yearly answer stays `4000000`.)
  - **Files:** same as the current-CTC item above.

- [x] when quetsion asks for value in INR, just mention the number (no commas)
  - **Done.** Salary answers always render as a plain integer — no commas, no currency (e.g. `4000000`, never `40,00,000`). Stored values that contain commas are parsed and re-rendered clean.
  - **Files:** `answers/resolver.py` (`_parse_amount` / `_format_number`).

- [x] in the resume section in the logs first mention what would be the best resume to pick for that scneario and then wait for 3seconds for the user to read the logs whcih resume you picked.
  - **Done.** The resume pick is now logged at INFO — `Best resume for '<job>': '<file>' (<reason>)` — then the tool pauses `run.resume_review_pause` seconds (default **3**, configurable, `0` disables) before the form opens so you can read which resume was chosen. (Skipped during `scan`.)
  - **Files:** `orchestrator.py` (`_pause_for_resume_review`), `config/models.py` (`RunConfig.resume_review_pause`), `configs/config.yaml` + `config.example.yaml`.

## Supporting work (this batch)

- [x] New tests `tests/test_salary_notice.py` (12 cases: monthly math, notice-days, INR-no-commas, tags).
- [x] Monthly salary rounds to the nearest **10,000** (40 LPA → `330000`/mo); yearly unchanged.
- [x] Fixed a pre-existing **timezone bug**: `count_applications_today()` and the daily-cap query compared local `started_at` against SQLite `date('now')` (UTC), so between 00:00–05:30 IST "today" counts read 0. Now use `date('now','localtime')`. (`database/db.py`)
- [x] Full suite **121 green**; `ruff` + `black` + `mypy` clean.
- [x] Real + example configs updated (`notice_period_days`, CTC values, `resume_review_pause`).
- [x] Docs synced: `docs/{configuration,faq,run-lifecycle}.md`, `ARCHITECTURE.md`.
- [ ] **Commit this batch** (awaiting your OK) and push together with `a60b1f9` after the live test.
# new todo — Tiered expected salary by seniority (2026-07-21) — DONE (uncommitted)

Full suite **163 tests** green · `ruff`/`black`/`mypy` clean. Not committed — ships with the batches above.

- [x] 40 LPA is the ceiling; expected CTC is chosen per job by seniority tier: **SDE 3 = 40 LPA, SDE 2 = 35 LPA, SDE 1 = 32 LPA**.
  - Tier inferred from the job **title** (fallback: LinkedIn experience level); **default SDE 1 (32 LPA)** when the level can't be determined.
  - **Files:** new `jobs/seniority.py` (`detect_seniority`), `orchestrator.py` (`_apply_expected_ctc_tier` sets a per-job resolver override + INFO log `Seniority tier ... -> expected CTC ... (NN LPA)`), `answers/resolver.py` (`set_expected_ctc`), `configs/answers*.yaml` (`expected_ctc_sde1/2/3`).
- [x] Monthly **expected** salary: when `expected_ctc_monthly_sde1/2/3` is configured the tool enters that **exact** value; otherwise it falls back to annual/12 rounded to the nearest 100,000.
  - Monthly **current** salary keeps the finer nearest-10,000 rounding (250000/mo) so it stays accurate.
  - Expected salary is tagged source `tier` and is **never learned** (job-specific); current-salary monthly stays `computed` (learned).

## new todo — Hand-set per-tier monthly expected salary (2026-07-21) — DONE (uncommitted)

- [x] Enter a specific monthly figure per tier instead of a rounding rule: **SDE 3 → 340000/mo, SDE 2 → 320000/mo, SDE 1 → 300000/mo** (annual stays 40/35/32 LPA).
  - **Files:** `answers/resolver.py` (`set_expected_ctc(annual, monthly)` + monthly-override branch in `_resolve_salary`), `orchestrator.py` (`_apply_expected_ctc_tier` looks up `expected_ctc_monthly_<tier>`, INFO log now includes the monthly), `configs/answers*.yaml` (`expected_ctc_monthly_sde1/2/3`).
  - Falls back to the annual/12 nearest-100,000 computation when no monthly key is set; expected monthly stays source `tier` (never learned).
- [x] Verified end-to-end: Senior/Staff→340000, SDE II→320000, SWE/Backend/default→300000; current/mo stays 250000; annual answers stay 4000000/3500000/3200000.
- [x] Tests updated (`tests/test_salary_notice.py`: configured-monthly per tier, division fallback); full suite **164** green; ruff/black/mypy clean; all 4 YAMLs parse.

## Supporting work (this batch)

- [x] New `tests/test_seniority.py` (39 cases) + expanded `tests/test_salary_notice.py` (tier override, 100k rounding).
- [x] Docs synced: `docs/{configuration,faq,run-lifecycle}.md`, `ARCHITECTURE.md`.
- [x] All 4 config YAMLs parse; tier keys load (3200000/3500000/4000000, default 3200000).
- [ ] **Commit** (awaiting your OK) and push after the live test.

## new todo — Notice period as a plain number (2026-07-21) — DONE (committed `9635c68`)

- [x] Always answer notice-period questions with a plain integer — `45`, never `"45 days"`.
  `notice_period_days` now wins for **every** notice phrasing (not just "…in days"); a
  free-text `notice_period` has its first integer parsed out; a genuinely non-numeric value
  (e.g. `Immediate`) is only kept for a non-"days" question.
  - **Files:** `answers/resolver.py` (`_resolve_notice_period`), `tests/test_salary_notice.py`
    (updated/added notice tests), `configs/answers*.yaml` comments, `docs/{configuration,faq}.md`.
  - Full suite **176** green; ruff/black/mypy clean. Committed `9635c68` (not pushed).

## new todo — Meet-the-hiring-team outreach (opt-in) (2026-07-21) — DONE (uncommitted)

After a successful application, optionally message the **"Meet the hiring team"** recruiters —
**draft-and-approve** so nothing is ever sent without your OK.

- [x] **Opt-in config + flag.** `outreach:` block (`enabled` off by default, `max_per_run: 5`,
  optional `template`, `skip_if_messaged`) + `--message-hiring-team / --no-message-hiring-team`
  CLI override. Runs only in an interactive session (never under `-y`) and only after a real
  submit (never during `--dry-run`).
- [x] **Personalised draft.** `answers/hiring_message.py` `HiringTeamMessenger` renders a short
  Jinja2 message (role / company / your background / recruiter first name); optional user template.
- [x] **Detect + send.** `forms/outreach.py` `HiringTeamOutreach` finds the section + recruiter
  cards, reads name / profile URL / Message button, drafts, **pauses for approval**, then types
  into the contenteditable compose box (no premature Enter) and clicks Send; closes the overlay.
- [x] **Dedupe + audit.** New `outreach_messages` table + `Database.has_messaged_person` /
  `record_outreach`; dedupes by profile URL (else name), skips InMail-only cards, caps per run,
  records every draft as `sent` / `declined` / `failed`.
  - **Files:** `config/models.py` (`OutreachConfig`), `answers/hiring_message.py`,
    `forms/outreach.py`, `forms/selectors.py` (HIRING_TEAM_* / MSG_*), `database/db.py` +
    `database/sql/schema.sql`, `orchestrator.py` (`_make_outreach`, `_reach_out_to_hiring_team`,
    call site after `_persist_result` on `SUBMITTED`), `cli/main.py` (flag + approval callback),
    `configs/config*.yaml`.
- [x] Tests: new `tests/test_outreach.py` (9: message render + defaults, DB dedup, sent/declined,
  already-messaged skip, InMail-only skip, per-run cap, no-section). Full suite **185** green;
  ruff/black/mypy clean; all 4 YAMLs parse.
- [x] Docs synced: `README.md`, `INIT.MD`, `ARCHITECTURE.md`, `docs/{configuration,faq,run-lifecycle,architecture}.md`.
- [ ] **Live-test the selectors** — `forms/selectors.py` HIRING_TEAM_* / MSG_* are screenshot-derived
  and unvalidated against the live DOM. Needs a job that shows a "Meet the hiring team" card.
- [ ] **Commit** (awaiting your OK) and push after the live test.
