# Codebase Review & Roadmap — LinkedIn Easy Apply Automaton

**Scope:** full review of `linkedin_easy_apply/` (~8.5k LOC across 13 packages), the Streamlit
dashboard, the SQLite layer, and the CLI. **No code was changed** — this is an advisory report.

**Method:** four parallel deep-reads (pipeline · forms · answers/parser/scoring/AI · database/
dashboard/CLI), plus direct reads of the two hardest files (`orchestrator.py`, `forms/easy_apply.py`)
to ground the synthesis. Every High-severity item was re-verified by reading the exact source. Items
surfaced by the review agents but **not** personally re-read are flagged `(agent-reported)` and listed
in the Verification Notes appendix so you can see exactly what is confirmed vs. what is a lead.

**Legend:** severity is **High** (can submit wrong data / block a run), **Med** (robustness, coverage,
perf, maintainability), **Low** (tech debt, polish).

---

## Executive summary

The core is genuinely well built: a clean *functional-core / imperative-shell* split, deterministic
automation with AI strictly advisory, generous logging, and 187 passing tests. The findings below are
about **edge-correctness, browser robustness, and scaling the data/dashboard layer** — not
foundational rework.

The five things worth doing first:

1. **`START_DATE` resolves to the notice-period value** — a real "wrong answer submitted" bug
   (`resolver.py`). *High.*
2. **Job metadata extraction is unreliable/absent** (`workplace_type` rarely matches;
   `experience_level` is **never set anywhere**). This is the root cause of the two "unknown" charts you
   already hid, *and* it weakens seniority-based CTC tiering. *Med, high-leverage.*
3. **Configured browser retry/backoff is never used** — a transient profile lock is a hard stop even
   though `BrowserConfig.max_retries`/`retry_backoff_seconds` exist. *Med.*
4. **No schema-migration story** — only an ad-hoc `_ensure_columns()`. Future schema changes will be
   fragile. *Med.*
5. **A cluster of near-zero-effort quick wins** (redundant scoring recompute, dead `import time`, a
   dead-but-exported `retry` decorator, unvalidated AI JSON, no config range checks).

---

## Part 1 — Improvements

### A. Correctness & logic

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| C1 | `answers/resolver.py:35` (`_FIELD_MAP[START_DATE] = ("start_date", "notice_period")`) | **High** | A "when can you start / available from" question with no `start_date` configured falls back to the **notice-period** value, so a portal can receive `"45"`/`"45 days"` as a start date. Verified. Fix: drop the fallback, or convert notice → an actual future date. |
| C2 | `parser/question_parser.py:310` (`if skill and _EXPERIENCE_HINT.search(norm)`) | **Med** | A skill is only tagged `EXPERIENCE_SKILL` when an experience hint word (`years/experience/expertise/worked with/hands-on`) is present. "Are you proficient in Python?" / "Do you know Kubernetes?" fall through to UNKNOWN → prompt (or blank under `-y`). Reduces automation coverage. Verified. |
| C3 | `forms/detector.py:127-135` (`_clean_label` `rstrip("*")` before `_required`) | **Med** | `_clean_label()` strips the trailing `*` **before** `_required()` checks `label.endswith("*")`, so the `required` flag is effectively always `False`. Currently metadata-only, but any future "skip optional field / enforce required" logic would be silently wrong. Verified. Fix: compute `required` from the raw text. |
| C4 | `database/db.py:224-227` (`create_application … ON CONFLICT(job_id,run_id) DO UPDATE SET status=excluded.status`) | **Med** | The upsert conflict path updates only `status`; `resume_id` and `started_at` keep stale values. Latent (same job+run is rarely re-attempted), but surprising on any retry. Verified. |
| C5 | `forms/filler.py` (`_pick_option`) + `forms/matching.py` (`best_option`) | **Med** | Option matching prefers the top fuzzy score with no specificity tie-break, then can coerce qualitative answers to Yes/No (`_infer_yes_no`). On semantically-close dropdown options this can pick the wrong value for a sensitive question. *(agent-reported)* |
| C6 | `answers/resume_expectations.py` (`total_years`, boolean skill grading) | **Med** | Résumé total-years is earliest-start → latest-end, so overlapping roles overcount and partial months are ignored; boolean skill questions grade "Yes" whenever the skill exists, regardless of tense. Makes the answer-quality comparison noisier than it looks. *(agent-reported)* |

### B. Robustness & error handling (browser / DOM / timing)

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| B1 | `browser/manager.py:start()` vs `config/models.py:37-38` | **Med** | `BrowserConfig.max_retries=3` / `retry_backoff_seconds=2.0` are defined but **never referenced** — `launch_persistent_context` runs once and a transient profile lock / flaky start is a hard failure. Verified. |
| B2 | `forms/easy_apply.py:184-208` (`_step_signature` = `label:kind` join) | **Med** | Stall detection compares only field label+kind between steps. A step that changes content but keeps labels can be read as "No progress" and abort; conversely a re-rendered same-label step won't be detected. Verified by read. |
| B3 | `forms/easy_apply.py` apply loop (`wait_for_timeout(600)`/`(800)`) and `jobs/search.py` | **Med** | The form flow and job discovery are driven by **fixed sleeps** rather than waiting for element/network state. Brittle under slow pages or transient overlays. Verified in the apply loop. |
| B4 | `forms/easy_apply.py:613-641` (`if "cover" in label`) & `:542-571` (`_upload_via_file_chooser`) | **Med** | File-upload routing is a substring heuristic (mis-routes labels like "Cover photo"); after `set_input_files()` there is no verification the correct file actually attached, and upload recovery assumes fixed 5s/2s windows. *(agent-reported)* |
| B5 | `forms/easy_apply.py:682-725` (`_discard` / confirmation) | **Med** | Discard is best-effort (dismiss → loop selector → Escape) with **no final assertion** that the modal/overlay is gone before returning, which is exactly the class of bug that caused the earlier "discard modal intercepts pointer events" incident. *(agent-reported)* |
| B6 | `jobs/extractor.py` (`_has_easy_apply` treats exceptions as True) | **Med** | Extraction is heuristic and reportedly biases toward false-positive Easy-Apply detection on error, which is risky for gating. *(agent-reported — not personally re-verified.)* |

### C. Data model, schema & queries

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| D1 | `database/db.py` (`_ensure_columns`) + `database/sql/schema.sql` | **Med** | No `schema_version` table and no ordered migrations — only `CREATE IF NOT EXISTS` plus a one-off column add. Any non-additive change (index/constraint/backfill) will be fragile to roll out. *(agent-reported.)* |
| D2 | `extractor.py:parse_metadata` + everywhere | **Med** | `workplace_type` regex rarely matches the scraped text and `experience_level` is **never assigned anywhere in the codebase** (grep-confirmed) → those `jobs` columns are ~100% NULL. This is the root cause of the hidden "unknown" charts **and** means seniority tiering (`_apply_expected_ctc_tier`) relies on the job title alone. Verified. |
| D3 | `database/db.py` — `date(started_at)`, `GROUP BY lower(j.company)`, status counts | **Med** | Several hot queries filter/group on **expressions**, which cannot use the column-only indexes in `schema.sql`; they degrade to scans as history grows. Add expression indexes or store normalized columns. *(agent-reported.)* |
| D4 | `database/db.py` — `answer_comparison`, `blocked_applications`, `reapply_targets` | **Med** | Correlated per-row subqueries ("latest value", "unanswered count") are SQL-level N+1 that scale poorly with question/application volume. *(agent-reported.)* |

### D. Performance

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| P1 | `orchestrator.py:354, 597, 713` (`self._scoring.score(...)`) | **Low** | The same job is scored up to **three times** per submitted job (score gate, outreach `tech_stack`, cover-letter `tech_stack`). Compute once, reuse. Verified. |
| P2 | `dashboard/app.py:32-40` (only the `Database` object is cached) | **Med** | Query **results** aren't cached, so every Streamlit rerun rebuilds KPIs, focus data, and tab tables; `stats()` alone fires ~10 `COUNT(*)` queries per rerun. Add `st.cache_data` keyed on `max(updated_at)`/latest run id. *(agent-reported.)* |
| P3 | `dashboard/app.py` (`st.data_editor` on the resume-sync table) | **Low** | Large question-history tables render with no pagination/cap — will get heavy as the DB grows. *(agent-reported.)* |

### E. Architecture & tech debt

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| T1 | `utils/retry.py:19` + `utils/__init__.py:6` | **Low** | The `retry` decorator is implemented and exported but **never applied** anywhere (no `@retry`). Dead code — or, better, wire it into B1/B3. Verified. |
| T2 | `orchestrator.py:739` (`import time` inside `_maybe_pause`) | **Low** | Redundant local import; `time` is already imported at module top (line 15). Verified. |
| T3 | `config/models.py` (numeric knobs) | **Med** | `max_per_run`, `max_per_company`, `max_daily`, `pause_*`, `fuzzy_threshold`, retry settings have **no range validation** — a negative/zero value fails weirdly at runtime instead of at config load. *(agent-reported.)* |
| T4 | `config/models.py:85-88` (`SearchEntry.url`) | **Low** | Only checks `"linkedin.com" in value`; a non-search LinkedIn URL passes validation and later makes discovery silently do nothing. *(agent-reported.)* |

### F. Testing gaps

- **Screenshot cleanup** (`orchestrator._cleanup_screenshots`) and **retry/backoff** have no visible
  tests *(agent-reported)*.
- The **form state machine** stall/abort transitions (B2) and **upload verification** (B4) are exactly
  the flaky, live-DOM-dependent paths that would benefit most from fake-page unit tests (the outreach
  module already models this well with its fake-page harness — extend that pattern).

### G. Safety / ToS

| ID | Location | Sev | Finding |
|----|----------|-----|---------|
| S1 | `answers/dynamic_resume.py:184-213` | **Med** | AI tailoring constrains `skills_order` but accepts the `title` **verbatim** from the model. The stated design is "re-emphasis only, never fabricate," so an invented headline could slip into a tailored résumé. Constrain `title` to the master profile. *(agent-reported.)* |
| S2 | `ai/openai_provider.py:163-168` (`_parse`) | **Low** | `should_apply`/`match_percent` are passed through unvalidated — a non-bool or out-of-range value can leak into the advisory result. Clamp/validate. *(agent-reported.)* |
| S3 | `forms/easy_apply.py:347-384` + `resolver.py` `_DEFAULT_PHONE_COUNTRY_CODE = "+91"` | **Med** | A hardcoded `+91` default is correct for your India-first use but would mis-fill other locales. The code already only uses it when nothing is stored **and** nothing is pre-selected, so impact is bounded — flag it if the tool is ever shared. Verified. |

---

## Part 2 — Feature ideas (prioritized)

**P1 — highest leverage**
1. **Reliable job-metadata extraction (D2).** Read `workplace_type`/`employment_type`/`experience_level`
   from LinkedIn's structured job-insight pills (and JSON-LD when present) instead of a loose regex.
   Unlocks the two hidden charts and gives seniority tiering a real signal beyond the title.
2. **Wire the retry policy (B1/B3/T1).** Use the existing `retry` decorator + `BrowserConfig` knobs on
   browser launch and transient Playwright actions (navigate/click/card-open), logging the attempt count.
3. **Schema-migration framework (D1).** A `schema_version` table + ordered migration steps so indexes,
   constraints, and backfills evolve safely.
4. **"Strict match" mode for sensitive questions (C5).** Disable fuzzy Yes/No coercion for
   eligibility/work-authorization/salary/country-code fields; require an exact or high-confidence match
   or prompt.

**P2**
5. **Dashboard query caching + saved filters (P2).** `st.cache_data` invalidated on latest run id, plus
   status/company/date filters across Submitted/Failed/Skipped.
6. **Skill-question synonym layer (C2).** Recognize "proficient in / familiar with / experience with /
   worked on" so more real LinkedIn phrasings map to `EXPERIENCE_SKILL`.
7. **Richer step fingerprint + discovery-confidence summary (B2/B3).** Add field values + button set to
   the stall signature; report cards found / failed-to-open / scrolls so you can tell when LinkedIn
   pagination reduced coverage.
8. **Post-upload verification (B4).** Re-read the field after `set_input_files()` to confirm the right
   file attached.
9. **Filtered/JSON export + an `audit` command.** `export --status/--from/--to/--company`; an `audit`
   that reports orphaned rows, missing indexes, and unanswered-question hotspots.

**P3**
10. **Selector versioning + telemetry** (record which selector matched) to monitor DOM brittleness.
11. **Locale-aware phone/country/date fallbacks** (C-series) instead of a single hardcoded code.
12. **Graded skill-years scoring** in `resume_expectations` (exact / plausible / inflated) to cut
    dashboard false alarms.
13. **Weekly/monthly trend views** in the KPI drill-down.

---

## Part 3 — Quick-wins table (low effort, clear value)

| Change | File | Effort | Payoff |
|--------|------|--------|--------|
| Score each job once, reuse the result | `orchestrator.py:354/597/713` | XS | Removes 2 redundant scoring passes/job |
| Delete redundant `import time` | `orchestrator.py:739` | XS | Tidiness |
| Compute `required` from raw label text | `forms/detector.py:127-135` | XS | Fixes an always-False flag |
| Validate/clamp AI JSON | `ai/openai_provider.py:163-168` | S | Safer advisory layer |
| Add `Field(ge=…)` range checks | `config/models.py` | S | Fail-fast on bad config |
| Drop/repair the `START_DATE → notice_period` fallback | `answers/resolver.py:35` | S | Stops a wrong-answer submission |
| Wire `@retry` onto browser launch | `browser/manager.py` + `utils/retry.py` | S | Uses config already present |

---

## Appendix — Verification notes (honesty ledger)

**Verified by direct source read (High confidence):** C1, C2, C3, C4, B1, B2, B3, D2, P1, T1, T2, S3,
and the grep-confirmed fact that `experience_level` is never assigned anywhere.

**Surfaced by the review agents, not personally re-read** (`agent-reported`; treat as strong leads to
confirm before acting): C5, C6, B4, B5, B6, D1, D3, D4, P2, P3, T3, T4, S1, S2.

**Not fully verifiable within this pass:** the exact ≤300-char note guarantee lives outside the forms
flow (in `answers/hiring_message.py`, which already has tests and graceful truncation), and
`utils/text.py` `normalize()`/`tokenize()` internals were not read here — a couple of C-series
punctuation edge cases depend on them.

*Prepared as an advisory review only — no source files were modified.*
