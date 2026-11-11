# Tests

Run from the repository root with the existing development environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
# Two isolated workers; keep each file's Qt/session fixtures in one process
.\.venv\Scripts\python.exe -m pytest -n 2 --dist loadfile
```

| Group | Coverage |
| --- | --- |
| `core/` | Configuration, answers, database, parsing, scoring, resumes and progress protocol |
| `automation/` | Browser/form behavior, job discovery, orchestration, retry, outreach and invitations |
| `desktop/` | GUI commands, widgets, themes, tutorial and source/frozen workspace behavior |
| `dashboard/` | Report controls and table presentation |
| `tooling/` | Tracking, relocated document links, CI coverage/release gates, Windows resources/notices and archive integrity |

`conftest.py` remains here so every group inherits shared fixtures. Test filenames
and normal pytest discovery are unchanged; no test-package installation is needed.
For a focused run, use a group such as `python -m pytest tests\desktop`.

Use fictional, disposable workspaces and isolated Qt settings. Do not use real
applicant settings, browser profiles, databases or an independently running app
as fixtures. See the [developer guide](../docs/development/developer_guide.md)
for dependencies and the separate live-qualification boundaries.

The Windows workflow schedules all five groups independently on Python 3.12
and 3.13: ten test lanes, each with two process-isolated workers. Lint/format,
types and the pinned frozen build/smoke run independently too. `qualify` waits
for every lane; a failed, skipped or cancelled dependency blocks publication.
Per-lane JUnit and coverage XML reports are retained as Actions artifacts,
including on test failure. Automation lanes install Chromium and require the
fictional invitation browser cases rather than permitting missing-browser skips.

Layout regressions exercise the source tutorial and packaged SQL schema from
an unrelated working directory, frozen example loading and upgrade retention,
relative documentation resources, moved build-tool roots, ZIP/manifest checksums
and rejection of fictional private/excluded bundle inputs. These are offline
checks, not a live LinkedIn or installed-application qualification.
