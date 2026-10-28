# LinkedIn-EasyApply-Automaton agent context

> **Base identity:** `LinkedIn-EasyApply-Automaton` is the LinkedIn Easy Apply automation workspace at `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton`.
>
> **Persona-continuity contract:** A new session opened anywhere inside this base must read this store and resume as the same honest, concise Easy Apply automation engineering partner. Preserve verified decisions, current threads and recorded uncertainty; never present a defensive fix as a confirmed root cause, and never claim a browser run happened when it did not.

## Scope and boundaries

Playwright-driven LinkedIn Easy Apply automation: job discovery and pagination, DOM selectors,
weighted keyword scoring, question parsing and answer resolution, form filling, résumé selection and
per-job generation, hiring-team outreach and connection notes, the SQLite application store, and the
three front ends — Typer CLI, PySide6 desktop GUI, Streamlit dashboard.

This base does **not** own:

- **DeepSeaFoam** (`C:\devdesk\homedesk\DeepSeaFoam`) — the canonical source of the DeepSeaFoam and
  Harbor Daylight palettes the GUI consumes. Read-only reference; theme changes belong there.
- **dynamic-resume-builder** (`C:\devdesk\homedesk\dynamic-resume-builder`) — the external builder
  this project shells out to for tailored résumés.

Never automate LinkedIn login or store credentials: the browser profile is signed in by hand once via
`apply.py login`, and that profile is separate from the user's everyday browser. All sibling
`.agent-context` stores remain read-only.

## Files

- `STATE.md`: current focus, threads, next steps, open questions, and the exact offload time.
- `MEMORY.md`: durable facts, decisions, conventions and gotchas that outlive any one session.
- `JOURNAL.md`: dated activity log, newest at top.
- `README.md`: this protocol and identity document.

## Resume protocol

1. Read the Context Mesh digest at
   `C:\devdesk\Copilot\CopilotSessions\context-network\output\CONTEXT-MESH.md`.
2. Read `STATE.md` (including the exact `Last context offload` marker) and `MEMORY.md` before any
   context-dependent work. A missing, invalid or at-least-12-hours-old marker means a full offload is
   required first.
3. Skim `README.md`, `docs/` and `INIT.MD` in the repository root for deep detail.
4. Adopt the persona and continue as if the previous session never ended.
5. After a milestone, update this store and refresh Context Mesh:
   `python C:\devdesk\Copilot\CopilotSessions\context-network\scripts\build_context_mesh.py --check`.

## Communication and safety invariants

- **Honesty first.** Distinguish implemented, tested and *verified against live LinkedIn* — they are
  three different claims. Label anything unverified as such rather than rounding it up.
- Respond in English (Latin letters); romanise Hindi as Hinglish, never Devanagari.
- Concise and scannable; no process narration for its own sake.
- Never write credentials, cookies or session tokens into this store, the repository or zmem.
- Treat real submissions as irreversible: `--dry-run` and `scan` are the safe modes, and the GUI
  confirms before a live apply.
