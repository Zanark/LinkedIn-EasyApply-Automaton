# Tests

Run from the repository root with the existing development environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

| Group | Coverage |
| --- | --- |
| `core/` | Configuration, answers, database, parsing, scoring, resumes and progress protocol |
| `automation/` | Browser/form behavior, job discovery, orchestration, retry, outreach and invitations |
| `desktop/` | GUI commands, widgets, themes, tutorial and source/frozen workspace behavior |
| `dashboard/` | Report controls and table presentation |
| `tooling/` | Tracking synchronizer and Windows packaging resources/notices |

`conftest.py` remains here so every group inherits shared fixtures. Test filenames
and normal pytest discovery are unchanged; no test-package installation is needed.
For a focused run, use a group such as `python -m pytest tests\desktop`.

Use fictional, disposable workspaces and isolated Qt settings. Do not use real
applicant settings, browser profiles, databases or an independently running app
as fixtures. See the [developer guide](../docs/development/developer_guide.md)
for dependencies and the separate live-qualification boundaries.
