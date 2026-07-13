# Algorithms — what this project uses, with real-world examples

> Each algorithm below is used in **this repo** (file · function cited) with a
> plain explanation, its complexity, and a real-world/industry example so the
> technique transfers beyond this codebase.

## Contents

1. [Unicode text normalization](#1-unicode-text-normalization)
2. [Rule-based classification (decision list)](#2-rule-based-classification-decision-list)
3. [Fuzzy string matching](#3-fuzzy-string-matching)
4. [Greedy longest-match (maximal munch)](#4-greedy-longest-match-maximal-munch)
5. [Weighted keyword scoring + threshold](#5-weighted-keyword-scoring--threshold)
6. [Cascading option matcher (exact → numeric → fuzzy)](#6-cascading-option-matcher)
7. [1-D nearest-neighbour / range matching](#7-1-d-nearest-neighbour--range-matching)
8. [Multi-strategy resume selection](#8-multi-strategy-resume-selection)
9. [Streaming dedupe with stagnation termination](#9-streaming-dedupe-with-stagnation-termination)
10. [Exponential backoff retry](#10-exponential-backoff-retry)
11. [Guard-clause validation chain](#11-guard-clause-validation-chain)
12. [Form state machine](#12-form-state-machine)
13. [Idempotent upsert + durable memoization](#13-idempotent-upsert--durable-memoization)
14. [Cheat-sheet](#14-cheat-sheet)

---

## 1. Unicode text normalization

**Where:** `utils/text.py` · `normalize()`

```python
text = unicodedata.normalize("NFKD", text)                 # decompose accents
text = "".join(ch for ch in text if not unicodedata.combining(ch))  # drop marks
text = text.lower()
text = _NON_WORD_RE.sub(" ", text)                         # punctuation -> space
return _WHITESPACE_RE.sub(" ", text).strip()               # collapse whitespace
```

**What it does:** collapses many surface forms of a string ("Señor", "SEÑOR ",
"senor") into one canonical form so later comparisons are apples-to-apples.
**NFKD** is Unicode *compatibility decomposition* — it splits a character like
`é` into `e` + combining-accent, which we then discard.

**Complexity:** O(n) in the string length.

**Real world:** this is the **analyzer** stage of every search engine
(Elasticsearch/Lucene lowercase + ASCII-folding filters), the canonicalization
in username/email dedupe, and the preprocessing in NLP pipelines. Getting
normalization right (or wrong) is why "café" does or doesn't match "cafe" in
your search box.

---

## 2. Rule-based classification (decision list)

**Where:** `parser/question_parser.py` · `parse()` and its ordered `_rule_*`
checks, with data in `_PHRASES` / `categories.py`.

**What it does:** classify a free-text application question into one of ~29
`QuestionCategory` values by testing **high-precision rules in priority order**
and taking the first that fires. A **decision list** = ordered `if/elif` rules;
order matters because earlier, more specific rules pre-empt later ones (e.g.
"years with GitHub" must be caught as *experience*, not as a *GitHub URL*).

**Complexity:** O(r) in the number of rules per question (r is small/constant).

**Real world:** spam filters and email routers began as ordered rule lists;
firewall/ACL rules ("first match wins"); feature-flag targeting; medical triage
protocols. Rule lists are the interpretable ancestor of ML classifiers — still
preferred where you need **explainability** and determinism.

---

## 3. Fuzzy string matching

**Where:** `parser/question_parser.py` · `_fuzzy()` (default threshold **80**),
`forms/matching.py` · `best_option()`, `answers/resume_selector.py` — all via
`rapidfuzz.fuzz`.

```python
# parser/question_parser.py
score = fuzz.token_set_ratio(norm, phrase)
...
if best_category is not None and best_score >= self._threshold:
    return best_category, ...
```

**What it does:** when exact rules miss, measure *similarity* between the
question and known phrases and accept the best match **only if it clears a
threshold**. `token_set_ratio` is order- and duplicate-insensitive
(so "salary expected" ≈ "expected salary"); `partial_ratio` finds the best
substring alignment. Both are built on **edit-distance / Indel** similarity
(a Levenshtein relative) computed with dynamic programming.

**Complexity:** roughly O(m·k) per comparison (string lengths); RapidFuzz is a
fast C++ implementation.

**Real world:** **record linkage / entity resolution** (matching "Bob's Diner"
to "Bob's Diner LLC" across databases), Postgres `pg_trgm` similarity,
Elasticsearch fuzzy queries, spell-check/"did you mean", and deduplicating
customer records. The **accept-only-above-threshold** guard is the key idea —
it turns a similarity score into a decision while controlling false positives.

---

## 4. Greedy longest-match (maximal munch)

**Where:** `parser/question_parser.py` — skills are sorted **longest-first** in
`__init__`, and skill detection walks that order and takes the first hit.

**What it does:** when scanning for a known skill, prefer the *longest* phrase
that matches ("spring boot" over "spring", "core java" over "java"). Sorting the
vocabulary by descending length once, up front, makes the scan naturally greedy.

**Complexity:** O(v log v) one-time sort + O(v) per question scan.

**Real world:** this is exactly how **lexers/tokenizers** work — a compiler
reading `>=` consumes both characters as one token rather than `>` then `=`
(**maximal munch**). Also dictionary-based word segmentation for Chinese/Thai
NLP, and longest-prefix matching in IP routers.

---

## 5. Weighted keyword scoring + threshold

**Where:** `scoring/engine.py` · `ScoringEngine.score()`

```python
for rule in self._config.rules:
    if self._contains(keyword, haystack):
        breakdown[rule.keyword] += rule.weight
        total += rule.weight
return ScoreResult(score=total, passed=total >= self._threshold, ...)
```

Note the **two matching modes** in `_contains`: plain alphanumeric keywords use
**word-boundary regex** (`\bgo\b`, so "go" ≠ "google"); punctuation-heavy ones
like `c++`/`.net` fall back to **substring** (word boundaries don't behave for
symbols). That's a small but important correctness detail.

**What it does:** a **linear scoring model** — sum the weights of matched
signals, then compare to a threshold to make a yes/no decision. Weights can be
negative (penalties). The `breakdown` dict keeps the decision **explainable**.

**Complexity:** O(rules × text) with tiny constants.

**Real world:** **credit scorecards** and insurance underwriting (sum of
weighted factors vs a cutoff), lead scoring in CRMs, **ATS résumé keyword
scoring** (the very systems this project is submitting into!), and naive-Bayes
spam scoring. It's a hand-tuned linear classifier — the same shape as a single
neuron/logistic-regression, minus the learned weights.

**Worked example (real breakdown from a run):** a job matching
`python 20 + javascript 12 + software engineer 10` looks strong at **42**, but
the posting also contains "architect" (`architect: -30`), so the final score is
**12** and it fails a threshold of 20. Two ideas to notice: (1) matching is
**presence-based** — a keyword adds its weight once regardless of how many times
it occurs; (2) **negative weights** let one disqualifier veto several positives,
which is exactly how risk scorecards encode hard "knock-out" factors. This score
only decides *eligibility*; hard gates (`_pre_apply_checks`, see §11) run first
and can skip a job regardless of score. Full config reference:
[`configuration.md` → scoring](configuration.md#scoring).

---

## 6. Cascading option matcher

**Where:** `forms/matching.py` · `best_option()`

**What it does:** to pick a `<select>`/radio option for a resolved value, try
strategies from **most to least precise** and stop at the first success:

1. exact normalized equality,
2. numeric proximity (if the field is numeric — see §7),
3. fuzzy match above `fuzzy_threshold=70`, else give up (return `None` → leave
   blank rather than guess wrong).

**Why it's a good pattern:** cheap/precise checks first, expensive/approximate
last, with a **safe default of "no answer"**. Returning `None` instead of a bad
guess is a deliberate correctness-over-coverage choice.

**Real world:** this "waterfall" is everywhere — payment routing (try primary
processor → fallback), CDN/cache tiers (memory → disk → origin), address
geocoding (exact → fuzzy), and de-dupe pipelines (deterministic key → fuzzy).

---

## 7. 1-D nearest-neighbour / range matching

**Where:** `forms/matching.py` · `_numeric_option()`

```python
if len(nums) >= 2 and nums[0] <= value <= nums[1]:   # inside a range "3-5 years"
    return option
distance = min(abs(value - n) for n in nums)          # else nearest endpoint
if distance < best_distance: best_distance, best = distance, option
```

**What it does:** map a number (e.g. 4 years) onto the best textual bucket:
if an option encodes a **range** that contains the value, take it; otherwise pick
the option whose number is **closest** (1-D nearest neighbour by absolute
distance).

**Complexity:** O(options).

**Real world:** bucketing a value into histogram bins, tax brackets, shipping
weight tiers, and the 1-D case of **k-NN** classification. "Snap to nearest" is
the core of quantization and nearest-neighbour search generally.

---

## 8. Multi-strategy resume selection

**Where:** `answers/resume_selector.py` · `select()`

**What it does:** choose a résumé file with a **fallback chain**:

1. **Explicit mapping** — fuzzy-match a configured role→file mapping; accept if
   `score ≥ 60` (`fuzz.partial_ratio`, with a substring shortcut scoring 100).
2. **Keyword overlap** — otherwise score each résumé by the fraction of its
   filename tokens present in the job text: `overlap / len(tokens) * 100`.
   That ratio is a **containment/overlap coefficient**.
3. **Default** — fall back to a configured default résumé.

**Complexity:** O(mappings + resumes × tokens).

**Real world:** this is a **recommender fallback ladder** — personalized rule →
content-based similarity → popular default — exactly how product recommenders and
ad-targeting degrade gracefully when signal is missing. The overlap coefficient
is a cousin of **Jaccard similarity** used in near-duplicate detection.

---

## 9. Streaming dedupe with stagnation termination

**Where:** `jobs/search.py` · `_collect_ids()`

```python
seen: set[str] = set()
stagnant = 0
for _ in range(max_scrolls):            # hard cap (15) - safety bound
    for job_id in self._current_ids():
        if job_id not in seen:          # O(1) visited check
            seen.add(job_id); ordered.append(job_id)
    grew = self._scroll_list(len(ordered))
    stagnant = 0 if grew else stagnant + 1
    if stagnant >= 3:                   # 3 scrolls with no new ids -> stop
        break
```

**What it does:** an **incremental crawler** over an infinite-scroll list. It
combines three ideas: a **visited set** for O(1) dedupe, a **convergence /
stagnation check** (stop after 3 consecutive scrolls that add nothing — you've
hit the bottom), and a **hard iteration cap** (`max_scrolls=15`) so a
misbehaving page can't loop forever.

**Complexity:** O(total ids seen); memory O(unique ids).

**Real world:** every **web crawler** and infinite-scroll scraper uses a
visited-set frontier + a termination heuristic. "Stop when no progress for N
rounds" is the same **convergence criterion** used to end iterative optimizers,
fixpoint computations, and simulation loops. The hard cap is a **circuit-breaker
by iteration count** — cheap insurance against runaway loops.

---

## 10. Exponential backoff retry

**Where:** `utils/retry.py` · `retry()` decorator

```python
delay = backoff_seconds                 # 1.0s
for attempt in range(1, attempts + 1):
    try: return func(...)
    except catch as exc:
        if attempt >= attempts: break
        time.sleep(delay)
        delay *= backoff_factor          # 1s -> 2s -> 4s ...
raise RetryError(...) from last_exc
```

**What it does:** on a transient failure, wait and retry, **doubling** the wait
each time (`backoff_factor=2.0`). Fail loudly with a chained `RetryError` after
`attempts` tries so the original cause is preserved.

**Complexity:** O(attempts); total wait ≈ geometric series.

**Real world:** the canonical resiliency pattern in **AWS/Google/Stripe** SDKs
and any network client — backing off gives an overloaded dependency room to
recover instead of hammering it (avoiding "retry storms").

> **Learning callout — missing jitter.** Production backoff usually adds
> **randomized jitter** (e.g. AWS's "Exponential Backoff and Jitter") so that
> many clients that failed at the same instant don't retry in lockstep (the
> *thundering herd*). This implementation is pure exponential with **no jitter** —
> fine for a single-user CLI, but the first thing you'd add to make it
> multi-client-safe. Great example of "correct for the context, not yet
> web-scale."

---

## 11. Guard-clause validation chain

**Where:** `orchestrator.py` · `_pre_apply_checks()` (and early-returns
throughout)

**What it does:** validate preconditions with a series of early exits — "already
applied? bail. not Easy Apply? bail. below score threshold? bail." — before
doing expensive work. Each check is a **guard clause** that fails fast and keeps
the happy path un-nested.

**Complexity:** O(checks), all cheap.

**Real world:** input-validation **middleware** (auth → rate-limit → schema →
handler), the **fail-fast** principle, and "**return early**" style that keeps
functions flat. Ordering cheap/likely rejections first is a performance idiom
(short-circuiting).

---

## 12. Form state machine

**Where:** `forms/easy_apply.py` (the multi-step Easy Apply workflow)

**What it does:** drive LinkedIn's multi-page modal as a **finite state
machine**: on each step, detect fields → fill → decide the transition
(**Next** → **Review** → **Submit**), looping until a terminal state
(submitted / dry-run-discard / failed). Bounded step iteration prevents infinite
loops if the DOM never advances.

**Real world:** **checkout funnels**, multi-step signup wizards, TCP's
connection states, and workflow/orchestration engines are all FSMs. Modeling a
process as explicit states + transitions makes it testable and prevents
"impossible" sequences.

---

## 13. Idempotent upsert + durable memoization

**Where:** `database/db.py` · `upsert_job`, `create_application`, `learn_answer`
(all `INSERT ... ON CONFLICT ... DO UPDATE`), and `get_known_answer`.

**What it does:** two related ideas.

- **Upsert / idempotency** — re-running a scan doesn't create duplicate job rows;
  `ON CONFLICT(url)` updates in place. Running the pipeline twice converges to the
  same state (**idempotent**), which is what makes retries and re-scans safe.
- **Durable memoization** — when a human answers an unknown question, `learn_answer`
  stores it keyed by the question's `normalized` form; future runs read it back
  with `get_known_answer`. That's a **cache that survives restarts**, turning a
  one-time human decision into permanent knowledge.

**Real world:** idempotent writes are foundational to **ETL/data sync** (SQL
`MERGE`), event processing ("process-once" semantics), and REST `PUT`. Durable
memoization is the **human-in-the-loop** pattern behind labeling tools and
support-macro suggestion systems.

---

## 14. Cheat-sheet

| Algorithm | Repo location | Complexity | Learn-it-because |
| --- | --- | --- | --- |
| Unicode normalize | `utils/text.normalize` | O(n) | search analyzers |
| Decision list | `parser…parse` | O(rules) | explainable classifiers |
| Fuzzy match + threshold | `_fuzzy`, `best_option` | O(m·k) | record linkage, fuzzy search |
| Longest-match (greedy) | parser skills | O(v log v) | lexers, tokenizers |
| Weighted scoring | `scoring.engine` | O(rules·text) | credit scorecards, ATS |
| Cascading matcher | `best_option` | O(options) | payment/cache fallbacks |
| Nearest-neighbour (1-D) | `_numeric_option` | O(options) | bucketing, k-NN |
| Fallback ladder | `resume_selector.select` | O(n·tokens) | recommenders |
| Streaming dedupe + stop | `search._collect_ids` | O(ids) | web crawlers |
| Exponential backoff | `utils.retry` | O(attempts) | resilient clients (add jitter!) |
| Guard clauses | `_pre_apply_checks` | O(checks) | validation middleware |
| State machine | `forms.easy_apply` | — | checkout funnels |
| Upsert / memoize | `database.db` | O(log n) | ETL, human-in-the-loop |

See also: [`data-structures.md`](data-structures.md) · [`architecture.md`](architecture.md).
