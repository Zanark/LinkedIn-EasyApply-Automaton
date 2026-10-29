# LinkedIn-EasyApply-Automaton memory

> Durable facts, decisions, conventions and gotchas. Add to this the moment something becomes
> invariably true; keep transient status in `STATE.md`.

## People

- **Debashish Mishra (mishrad)** - owner and sole user. SRE on Azure BCDR/MAB; this is a personal
  project. Prefers concise, scannable answers and explicit uncertainty over confident guessing.
- Standing preference, stated 2026-10-28: run tests with the repository's **own** `.venv`
  (`C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\.venv`) rather than building throwaway
  environments, and do not create new binaries inside a Copilot worktree.

## Conventions

- **The CLI is the single execution path.** The GUI builds `apply.py <command>` argv through
  `gui/commands.py`, echoes it, and runs it. Never add behaviour to the GUI that the CLI lacks.
- **Selectors live in one file.** `forms/selectors.py` holds ordered candidate lists; `dom_utils.first`
  / `first_group` take the first that matches. When LinkedIn changes, only that file should need edits.
- **Defensive DOM helpers swallow exceptions** and return `None`/`[]`. That makes the automation
  resilient but means a zero result is ambiguous, so any new zero-path must log *why* (see
  `_report_empty_results`).
- Pure logic is kept Qt-free and browser-free so it can be unit tested: `gui/theme.py`,
  `gui/commands.py`, `scoring/engine.py`, `parser/`, `jobs/extractor.parse_metadata`.
- Tests mirror features one file per concern under `tests/`; Qt-dependent tests use
  `pytest.importorskip("PySide6")` plus `QT_QPA_PLATFORM=offscreen`.
- Documentation is part of a change: `docs/configuration.md` for config keys, `docs/gui.md` for the
  desktop app, `docs/faq.md` for skip reasons, `README.md` for the command table.

## Gotchas

### CLI surface

- `init` and `version` accept **no** `--config`; passing one is a Typer usage error.
- `--verbose` is a callback option and must come **before** the sub-command.
- `scan` has no `--dry-run`, `--yes` or `--ignore-score`; `reapply` has no `--url`.
- `sync-answers --apply` prompts for confirmation, so a non-interactive caller must pair it with
  `--yes`.
- Rich parses `[...]` as markup: print text containing `pip install .[gui]` with `markup=False`.

### Scoring

- Hard gates run **before** the score and can skip a job regardless of it, so disabling scoring does
  not make the bot apply to everything.
- The threshold is inclusive (`score >= threshold`), keywords are lower-cased at config load, matching
  is presence-based (once per keyword), and plain alphanumeric keywords match on word boundaries while
  punctuation-bearing ones (`c++`, `.net`) match as substrings.
- `threshold: 0` is **not** "scoring off" while negative rules exist - one penalty drops a job below
  zero. Use `enforce: false` (or `--ignore-score`).

### The 2026 LinkedIn rebuild (confirmed live 2026-10-29)

**Class-based selectors are permanently dead on the jobs UI.** Verified against the live site:

- `/jobs/search/` redirects to `/jobs/search-results/?currentJobId=<id>`.
- Class names are build-generated hashes (`ajrhc3`, `ajrk8d`, `ajrayf`) - they change every deploy,
  so never key off them again.
- There is **no** `data-job-id`, `data-occludable-job-id` or `data-entity-urn` anywhere, and **no
  `h1`** on the detail pane.
- Result cards are `<button>` elements, not links. Only the *selected* job has a `/jobs/view/` link,
  which is why a link-based fallback returns exactly one id.

What is stable, and what the code now uses instead:

| Need | Source |
| --- | --- |
| The 25 cards | buttons whose accessible name matches `Dismiss .+ job`, minus those whose own `aria-label` starts with "Dismiss" (that is the nested dismiss control) |
| Job id | click the card, then read `currentJobId` from `page.url` |
| Title + company | `document.title` = `"<job title> \| <company> \| LinkedIn"` |
| Description | the `About the job` heading's first ancestor with >400 chars of text |
| Location | the card's own text, before the `(Hybrid)`/`(On-site)`/`(Remote)` marker |

Both strategies are kept and whichever finds more cards wins, so the crawler still works if an
account is served the older build. `page.accessibility` no longer exists in current Playwright - use
`locator.aria_snapshot()`, which also reveals content inside shadow roots.

### Job discovery

- LinkedIn **virtualises** the results column: the window scrollbar does not load more cards, and
  off-screen list items are emptied. Scroll the inner scrollable ancestor of a card instead.
- Job ids appear in at least four shapes: `data-job-id`, `data-occludable-job-id`,
  `urn:li:jobPosting:<id>` and a slugged URL (`/jobs/view/senior-engineer-at-acme-4123456789`). The
  original canonical-URL-only regex missed the last two entirely.
- The automation browser profile is **separate** from the everyday browser. Being logged in normally
  says nothing about whether the automation is signed in.

### Qt and theming

- **CSS puts alpha last (`#RRGGBBAA`); Qt's hex form puts it first (`#AARRGGBB`).** Pasting a palette
  token straight into QSS silently shifts every channel. `theme.qt_color()` converts to
  `rgba(r, g, b, a)`; a test asserts no 8-digit hex survives into the generated stylesheet.
- DeepSeaFoam has **no second accent fill**. Its `text` role is documented as "primary text *and
  primary-action hover*", so that is the dark theme's hovered primary button, with the near-black base
  as the ink on top. Harbor Daylight has a real `accentHover` and uses paper ink.
- Qt only re-evaluates a stylesheet after a dynamic property changes if you `unpolish`/`polish` the
  widget.
- A log line written under one theme keeps its inline colour forever unless the backlog is re-rendered.
  The console stores `(text, role)` pairs and repaints on theme switch - do not regress this; the
  original bug put DeepSeaFoam's near-white ink on Harbor Daylight paper at roughly 2.2:1.

### Environment

- pytest's end-of-session tmpdir cleanup raises `OSError WinError 448` ("untrusted mount point") in
  sandboxed temp directories and suppresses the terminal summary. Tests still run; print the tally
  from a `tryfirst` `pytest_sessionfinish` hook.
- Running a script by absolute path puts *the script's* directory on `sys.path`, not the working
  directory - set `PYTHONPATH` when the repository copy must win over an editable install.

## Theme source of truth

Both palettes belong to the **DeepSeaFoam** base (`C:\devdesk\homedesk\DeepSeaFoam`), read-only from
here. Canonical files: `palette/deepseafoam.json`, `palette/harbor-daylight.json` (+ a generated
`harbor-daylight.css`). Porting rules in `docs/GUIDE.md` require mapping *semantic roles* rather than
similarly named fields, preserving alpha, keeping user content separate from application chrome, and
following the interaction safeguards in `docs/HARBOR-DAYLIGHT.md`. Applying them here is an
application of the published palettes - **not** a native DeepSeaFoam target and not a contrast
certification.

## Context-offload protocol

- This store is the source of truth over ephemeral session context. Read `STATE.md` + `MEMORY.md`
  before context-dependent work; a `Last context offload` marker that is missing, invalid or at least
  12 hours old requires a full offload first.
- Update `STATE.md` at every milestone, add durable facts here as they are established, and append
  `JOURNAL.md` (newest at top) per significant action.
- After changing this store, refresh Context Mesh:
  `python C:\devdesk\Copilot\CopilotSessions\context-network\scripts\build_context_mesh.py --check`.
- This base was registered on 2026-10-28 and its root added to the Context Mesh `config.json`. At the
  user's explicit instruction `.agent-context/` is **not** added to `.gitignore` here, unlike sibling
  bases such as DeepSeaFoam and CareerHQ which ignore it.
