# Public engineering memory

These contributor-wide rules summarize reviewed repository contracts.
They contain no applicant values or private session history.

## Architecture

- Python 3.12+, Playwright, Pydantic configuration and SQLite persistence form
  a deterministic automation core. Optional AI advises and may re-emphasize
  existing resume content; it must not fabricate applicant facts.
- The orchestrator coordinates discovery, filtering/scoring, resume selection,
  form handling and persistence. Prefer the existing module boundaries; see
  [architecture](../../docs/architecture.md) and [run lifecycle](../../docs/run-lifecycle.md).
- Browser imports are lazy. Reuse an explicitly configured authenticated profile
  for authorized use; never automate login or store credentials.
- Desktop activity comes from authoritative typed engine stages, not parsed
  console text. Human logs and confirmed-outcome metrics remain separate.
- Icon states and labels live in `gui/activity.py`; original vector artwork and
  density-aware rendering live in `gui/activity_icons.py`. Maintain the complete
  glossary when states, labels, artwork or semantic meanings change.

## Invitation invariants

- Prefer a usable note, including an already-open editable note field.
- Plain invitations are opt-in and limited to positively identified invitation
  context. Never reuse an unrelated message composer's generic Send control.
- Preserve existing drafts. Arbitrary note-send/fill failures are not permission
  to fall back to a plain invitation.
- Dry runs never click final send controls. Positive delivery evidence is
  required before persisting success; invitation and note timestamps differ.
- Current selectors may need new live qualification when the site changes.
  A fictional browser fixture does not establish current live markup.

## Contributor workflow

- Preserve unrelated dirty work and use the lowercase `todo` directory.
  Each actual numbered workstream has a stable `lea-NN` identity and all eight
  fields in [the tracking contract](../../docs/github-tracking.md).
- Preview authorized tracking changes, then verify the exact issue description,
  lifecycle, single Project membership/status and persistent local backlink.
  Human edits are conflicts, not permission to reset stored baselines.
- Keep implementation, offline qualification, live qualification, human
  acceptance and publication distinct. There is no background tracking service.
- Update directly affected user/developer/learning guides with behavior changes.
  Existing media provenance can be reused when the actual media is unchanged.
- Commit and push only with authority. Verify the repository-local effective
  Zanark author/committer identity and retain required session trailers.
- Do not restart, reload or drive an independently running app during development.
  Use temporary settings, fictional workspaces and owned browser contexts.

## Focused qualification

Use the existing environment and commands in the
[developer guide](../../docs/developer_guide.md#development-workflow).
Do not install dependencies unless required by a manifest change or an actual
missing-dependency failure.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:LEA_REQUIRE_INVITATION_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -B -m pytest tests\test_connection_invites.py tests\test_gui_window.py
```

The invitation browser cases use intercepted fictional HTTPS pages and a fresh
headless context. Required-browser mode fails rather than silently skipping a
missing browser. GUI fixtures isolate their INI settings and application data.
