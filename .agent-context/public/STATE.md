# Public source state

This is a curated source snapshot, not private session continuity. Use this
checkout's commit identity and the [workstream index](../../todo/00_INDEX.todo)
to establish the current revision.

## Delivered source

- The desktop action tile has 36 detailed multicolor icons, rounded centered
  labels and semantic border glow. Icons are 64 by 64 logical pixels inside
  the unchanged 112-by-108 tile; high-density rendering retains sharp vectors.
- The [complete action glossary](../../docs/gui-action-icons.md) and expandable
  README reference explain all icons, stage names, tones and outcome caveats.
  Documentation screenshots and walkthroughs use fictional data.
- Connection controls use bounded polling and invitation-scoped recognition.
  A usable note is preferred; sending without a note requires the explicit
  option. Existing conflicting drafts are preserved.
- An invitation is recorded as delivered only after Pending or a new explicit
  invitation-sent confirmation. A click or closed modal is not sufficient.
  Dry runs never click a final send action or persist delivery.

These source changes are documented by workstreams lea-34, lea-35 and lea-36.
Their evidence distinguishes local unit/GUI/fictional-browser qualification
from current live-site acceptance.

## Release and qualification boundaries

The published Windows release remains **v0.2.4**. Its original 40-pixel icon
size and older exact-only note-free fallback are not updated by a source push.
No new tag, release, installation or installed-app update is part of this handoff.

The reported live modal markup has not been established by the fictional
fixtures. Direct top-card one-click Connect delivery without a modal is also
not established. Do not treat either case as confirmed support or retry an
unconfirmed live send automatically.

The original live qualification gaps in repository issues #2 and #9 remain
separate work. Do not close them because offline tests or source publication pass.

## Resuming development

Read [MEMORY.md](MEMORY.md) and the [developer guide](../../docs/developer_guide.md).
Inspect current code, dirty work and the relevant numbered workstream before
editing. Use fictional disposable state, not personal inputs or a logged-in
profile. Live actions, independent application control and publication require
their own explicit authority.
