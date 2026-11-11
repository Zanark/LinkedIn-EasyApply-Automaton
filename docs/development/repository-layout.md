# Repository layout

The root keeps the application entry point, package metadata and contributor
entry points. The existing Python package and workspace paths are unchanged.

| Location | Responsibility |
| --- | --- |
| `apply.py`, `linkedin_easy_apply/` | CLI entry point and importable application package |
| `configs/` | Public example YAML; real settings stay ignored |
| `docs/getting-started/` | Installation, launch commands and the complete run guide |
| `docs/guides/` | Desktop tutorial, configuration, FAQ and troubleshooting |
| `docs/architecture/` | Architecture, lifecycle, algorithms, data structures and original specification |
| `docs/development/` | Contributor guidance, tracking contract and historical review |
| `docs/assets/branding/` | Current README PNG, application marks and retained legacy SVG banner |
| `docs/assets/images/` | Fictional screenshots, walkthrough GIFs and all 36 action SVGs |
| `docs/releases/` | Version-specific release notes |
| `tests/` | Shared fixtures and responsibility-based test groups |
| `tools/windows/` | Windows build and frozen offline checks |
| `tools/media/` | Documentation screenshot and legacy vector-banner generators |
| `tools/todo_sync.py` | Stable, explicitly invoked tracking entry point |
| `packaging/windows/` | Freezer specification, pinned requirements and redistribution notices |
| `todo/` | Canonical numbered workstreams, index and development ledger |
| `generated/` | Ignored resumes, cover letters and outreach outputs, with public folder guidance |

## Compatibility and private files

Run commands from the repository root. `apply.py`, the installed `lea` command
and existing private launch helpers keep their locations. Package imports and
editable-install metadata do not change.

Existing `database`, `downloads`, `logs`, `screenshots`, `reports`, browser
profiles and private setup stay in place. They can contain active or personal
data: directory cleanup is not permission to move, delete or publish them.
Build outputs, virtual environments and caches also remain local and ignored;
moving an existing environment or release bundle can invalidate stored paths.

Earlier workstream evidence and the reviewed public handoff retain their
historical paths and bytes. Use [the documentation index](../README.md) for
current navigation. The tracked historical codebase review now lives with
development documentation rather than alongside runtime report output.

See [test groups](../../tests/README.md) and [tool commands](../../tools/README.md).
