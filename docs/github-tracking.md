# Workstream and GitHub tracking adoption

This is the repository-specific contract, not an always-on service.
The initial adoption is technically complete and independently reconciled;
the verified receipt and remaining qualification boundaries are recorded below.

## Canonical identity and visibility

| Resource | Pinned identity |
| --- | --- |
| Repository | `Zanark/LinkedIn-EasyApply-Automaton` |
| Repository URL | https://github.com/Zanark/LinkedIn-EasyApply-Automaton |
| Repository database / node ID | `1299191007` / `R_kgDOTXAU3w` |
| Repository visibility / source branch | Public / `main` |
| Authenticated account and Project owner | `Zanark` |
| Owner Project | https://github.com/users/Zanark/projects/10 |
| Project node ID / visibility | `PVT_kwHOAe2wCs4BqfEB` / private |
| Status field ID | `PVTSSF_lAHOAe2wCs4BqfEBzho1_j8` |

Discovery paginated all repository issues and the owner's Projects before
creation: no issues and no appropriate existing Project were found. Existing
Projects associated with other repositories were left alone. Project 10 was
created under the actual owner, linked to this repository and kept private.
Its default Todo, In Progress and Done options were retained; missing stages
were added. Other fields, items and views are not managed by this synchronizer.
Public issues remain public even though the Project is private.

| Local stage | Exact Project option name | Option ID |
| --- | --- | --- |
| Backlog | Backlog | `c95c2e06` |
| Ready | Ready | `b3987357` |
| In progress | In Progress | `47fc9ee4` |
| In review | In review | `c29b798f` |
| Done | Done | `98236657` |

The original `Todo` option `f75ad846` is preserved but not a sync destination.
All configured option names/IDs are verified against live metadata before writes.

## Saved Kanban view

The existing first view is now named **Kanban**, with saved `BOARD_LAYOUT`:
https://github.com/users/Zanark/projects/10/views/1.
Its original view ID, `PVTV_lAHOAe2wCs4BqfEBzgMb6Sc`, is retained; no second
Project or duplicate view was created.

The board's column field was separately verified through
`verticalGroupByFields`: it resolves to the pinned **Status** field above.
`groupByFields` is empty; it is not the board's column-field read-back.

The user-requested 2026-11-06 layout change was independently read back through
the API. All ten issue-backed items, exact issue content/lifecycle, issue/item
timestamps and Status option identities/order/descriptions remained unchanged:
eight Done and two In review. The Project remains private and the view unfiltered.
This confirms the saved board layout, not a browser-rendering qualification.

The synchronizer does not manage view configuration. Moving cards in GitHub
changes remote field values, not the local workstreams; those files still own
completion and managed Status. Reconcile such edits explicitly before a sync
rather than deleting its conflict baseline.

## Local sources and approval boundary

Keep the existing lowercase `todo` directory rather than a case-only rename.
[`00_INDEX.todo`](../todo/00_INDEX.todo) navigates the explicit inventory.
Each actual workstream has Status, Milestone, Dependencies, Purpose, Tasks,
Acceptance criteria, Completion evidence and Completion log.

Ten numbered files are reviewed **public-safe projections**, not verbatim
copies of the older records. Their `Source-record` field is local provenance;
it and the identity/backlink metadata are intentionally outside the managed
description. The issue's managed preamble explicitly discloses this projection.
Historical test counts and dates are attributed, not newly executed validation.
No date is fabricated for the undated dashboard source.

Configuration explicitly excludes these five files:

| File | Reason |
| --- | --- |
| `00_INDEX.todo` | Navigation, not an actual workstream |
| `99_DEVELOPMENT_LEDGER.todo` | Perpetual engineering history |
| `TODO.md` | Mixed historical source including applicant-specific values and quotations |
| `dashboard.todo` | Original source already projected once as `lea-09` |
| `resume.todo` | Empty placeholder |

Private continuity, real configuration, credentials, browser state, databases,
logs, generated applicant documents, screenshots and exports are never input
directories. Original legacy files are preserved unchanged, not republished by
this adoption. Their presence does not authorize quoting their contents.

For a new actual workstream, semantically review its complete title, eight
fields, examples and links before declaring `Publication: PUBLIC_SAFE_PROJECTION`
and adding a new stable ID/file to the allowlist. Automated token/contact/path
guards are defense in depth, **not** personal-data detection or publication approval.
Relative public links are deliberately projected to repository source URLs;
source links can lag local uncommitted changes. Unadopted files are reported
but receive no issue. Review safe dependencies explicitly; do not manufacture
workstreams for navigation or create duplicate issues for individual checkboxes.

## Ownership and exact status mapping

Local workstream -> one repository issue -> one issue-backed Project item.
No duplicate Project draft is created. Local files own the managed description
and completion decision. No board-to-file synchronization exists.

| Exact local Status | Issue state / reason | Project stage |
| --- | --- | --- |
| `NOT_STARTED`, `DEFERRED` | Open | Backlog |
| `READY` | Open | Ready |
| `IN_PROGRESS` | Open | In progress |
| `IN_REVIEW` | Open | In review |
| `DONE` | Closed / COMPLETED | Done |
| `CANCELLED`, `SUPERSEDED` | Closed / NOT_PLANNED | Backlog, explicitly not completed |
| `BLOCKED` | Open | Required `Blocked-stage`, plus a nonempty `Blocker` |

`Blocked-stage` must explicitly name Backlog, Ready, In progress or In review.
Reopening uses an open local status and reopens the existing issue. Unknown
compound phrases are rejected rather than matched by substring. DONE requires
nonempty evidence and no unchecked tasks/acceptance; the author must still
judge whether the evidence actually meets the scope.

Original automation/upload qualification (`lea-01`) and outreach selector
qualification (`lea-08`) remain IN_REVIEW. Fixture success does not close their
explicit live gaps. Other historical DONE records represent their bounded
technical batches, not proof of target qualification, human acceptance or
publication. GitHub creation/closure metadata is current import activity.

## Executable, configuration and durable mapping

| Role | Repository path |
| --- | --- |
| Standard-library Python/gh synchronizer | `tools/todo_sync.py` |
| Reviewed allowlist, repository/Project/options | `.github/todo-sync.json` |
| Persistent issue/node/item identities and baselines | `.github/todo-sync-state.json` |
| Offline fixtures | `tests/test_todo_sync.py` |
| Short contributor/agent entry point | `AGENTS.md` |

The implementation reuses the reviewed standard-library/gh recovery approach
from the sibling EntropyTag integration, adapted to this repository's identity,
public projection boundary, title checks, renamed-repository backlinks and
partial-operation origins. It does not import or execute a sibling script.
There are no new dependencies or remote secret requirements.

Stable `lea-NN` identity is independent of the title and filename. It appears
in the configuration, local file, issue managed markers and mapping. The mapping
also pins repository and Project node IDs and stores actual issue/item node IDs.
Do not regenerate IDs after a rename. Update the reviewed filename mapping.
For a repository rename, retain the pinned repository ID, review the canonical
new name, and explicitly add the old name to `repository_aliases` to migrate
backlinks. No rename is inferred from a title or a failed lookup.

Keep the mapping durable with the tracking sources when a future commit is
authorized. It contains public identifiers and managed-content fingerprints,
not credential contents. Do not ignore/delete it to bypass a conflict.

## Exact local invocation

Run from `C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton`.
The shared trusted credential runner is:
`C:\devdesk\homedesk\skill-library\skills\development-documentation-manual\scripts\with_github_token.py`.

The runner internally uses the canonical ignored/untracked credential file;
only if absent does it consider process/current-Windows-user variables. A
present malformed, tracked or unignored file blocks use. Never open, print,
search, copy or hash that real credential file. The child receives credentials
only in its process environment; no global auth/account or secret provisioning.
Review changed executable code before granting the credential-bearing child access.

**Preview all allowlisted workstreams; no issue, Project, mapping or backlink writes:**

```powershell
.\.venv\Scripts\python.exe -B "C:\devdesk\homedesk\skill-library\skills\development-documentation-manual\scripts\with_github_token.py" -- .\.venv\Scripts\python.exe -B .\tools\todo_sync.py
```

**Explicit apply, only when authorized by the current task:**

```powershell
.\.venv\Scripts\python.exe -B "C:\devdesk\homedesk\skill-library\skills\development-documentation-manual\scripts\with_github_token.py" -- .\.venv\Scripts\python.exe -B .\tools\todo_sync.py --apply
```

**Select the pilot or a bounded update; repeat `--only` for multiple IDs:**

```powershell
.\.venv\Scripts\python.exe -B "C:\devdesk\homedesk\skill-library\skills\development-documentation-manual\scripts\with_github_token.py" -- .\.venv\Scripts\python.exe -B .\tools\todo_sync.py --only lea-09
.\.venv\Scripts\python.exe -B "C:\devdesk\homedesk\skill-library\skills\development-documentation-manual\scripts\with_github_token.py" -- .\.venv\Scripts\python.exe -B .\tools\todo_sync.py --apply --only lea-09
```

Use preview/apply after authorized new workstreams, task/description/evidence
updates, completion, reopening and cancellation/supersession. Run again for
final verification; a settled rerun must report no-op without remote mutations.
Updating these instructions does not update already-running sessions.

## Conflicts, partial failure and concurrency

The issue description has one `lea-todo:<ID>:begin/end` managed section.
Comments, labels, assignees and body text outside it remain untouched.
Stored baselines detect unexpected title, managed-body, lifecycle or Project
status edits. Human edits within managed ownership block that item; independent
safe workstreams continue. Resolve the real difference with the author. Never
delete markers, erase a baseline or blindly rerun until it overwrites the human.

Issue creation and Project addition persist intent before mutation. An uncertain
response is not automatically retried. The next complete inventory looks up the
stable marker or issue-backed membership; visible results are reused. If an
uncertain result is still invisible, stop and inspect before any new create/add.
Do not clear the intent merely because it was not immediately visible.

Successful partial writes remain. Pending target and observed-origin fingerprints
allow recovery when one operation succeeds and a later one fails, including a
new local target during partial recovery. A backlink failure is retryable without
recreating the issue/item. Missing local files, removed/archived Project items,
duplicate identity/membership and inaccessible reads block, never authorize
replacement or deletion. Unmapped existing markers require explicit reviewed
adoption/restoration of the verified mapping; there is no blind auto-adopt switch.

GitHub reads have bounded retries; permission failures and GraphQL partial
errors fail explicitly, never become empty inventories. Mutation timeouts are
never replayed automatically. Final read-back compares exact managed content,
state/reason and item/status, with bounded consistency rereads. Local content is
checked again before the backlink. Review a nonzero exit even when earlier
items succeeded.

`.todo-sync.lock` serializes writers in this checkout only. Inspect the recorded
PID before manually removing a genuinely stale lock. Do not steal a live lock.
It is not a distributed lock or server compare-and-swap; another clone and human
edits after the last read are residual races. Use one operator/writer and reconcile
before resuming elsewhere. GitHub issue/item connections are fully paginated.
Metadata connections over 100 fields/repository links block rather than assume
complete coverage. Future expansion must implement corresponding pagination.

## Attribution and publication

Repository-local configuration is `user.name=Zanark` and
`user.email=32354314+Zanark@users.noreply.github.com`; global Git identity is unchanged.
Before a separately authorized commit, check effective overrides too:

```powershell
git config --local --get user.name
git config --local --get user.email
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

Verify both effective identities, not just the configuration. Preserve required
session trailers. Stage only reviewed task files; never sweep the unrelated
dirty worktree into a commit. Backlinks and mappings remain local/uncommitted
until publication is separately authorized. No commit/push is performed by sync.

There is no tracking schedule, daemon, Actions workflow or activated unattended service.
The separately authorized Windows release workflow does not synchronize tracking.
The credential's available workflow scope does not authorize workflow activation,
dispatch, deployments, remote secrets or untrusted code execution.

## Adoption receipt

The 2026-11-06 adoption created ten issues and adopted zero pre-existing issues.
Final independent API reconciliation verified ten unique repository issues,
ten issue-backed Project items and ten persistent local backlinks: eight
CLOSED/COMPLETED in Done and two OPEN/In review. There were no blocked,
conflicting, duplicate or partial results.

Preview, real pilot, exact pilot rerun, nine-workstream backfill and complete
reconciliation passed before closing adoption issue #10. Its meaningful
completion update reused the existing issue/item. The final full rerun then
created zero, reused ten and reported ten no-ops. Independent before/after
receipts matched identities, exact managed content, issue/item timestamps and
local mapping/workstream bytes and modification times.

Issue #2 retains the original upload/country-code qualification gap; issue #9
retains the outreach selector qualification gap. Fixture success and later
resume reuse do not qualify those original live behaviors. Their review status
was preserved rather than implementing old product work during this adoption.

Focused executable validation: 57 offline tracking fixtures, Ruff, Black and
targeted `mypy tools/todo_sync.py` passed. This is not a new product/browser test
run or hosted Actions qualification. No dependencies were installed.

The five exclusions above and the original legacy records remain unchanged.
Credential exclusion was verified through Git metadata, not credential contents.
Source, configuration, mapping, backlinks and contributor guidance remain
local/uncommitted; public source links can lag until separately authorized
publication. No commit, push, workflow activation/dispatch, unattended service,
deployment, remote-secret provisioning or new application was performed.
