# Development tools

Run these scripts from the repository root using the existing virtual environment.

| Script | Purpose |
| --- | --- |
| `windows/build_windows.py` | Build an allowlisted portable Windows distribution and integrity files |
| `windows/smoke_windows.py` | Exercise an existing frozen bundle offline with a temporary workspace |
| `media/capture_screenshots.py` | Regenerate fictional GUI screenshots and walkthroughs in `docs/assets/images` |
| `media/build_banner.py` | Regenerate the retained legacy vector banner, not the current README PNG |
| `todo_sync.py` | Preview or explicitly apply scoped workstream/issue/Project synchronization |

```powershell
.\.venv\Scripts\python.exe tools\windows\build_windows.py --help
.\.venv\Scripts\python.exe tools\windows\smoke_windows.py --help
.\.venv\Scripts\python.exe tools\media\capture_screenshots.py --help
```

Media generators can overwrite their named documentation outputs; do not run
them just to check the layout. Building, publishing and live actions have
separate authority. For credential handling and scoped tracking invocation,
follow the [tracking contract](../docs/development/github-tracking.md).
