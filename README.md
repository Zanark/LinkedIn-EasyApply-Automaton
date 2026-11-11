<p align="center">
  <img src="docs/readme-banner.svg" width="640" alt="Easy Apply Automaton — Automate your LinkedIn applications.">
</p>
<p align="center">
  <a href="https://github.com/Zanark/LinkedIn-EasyApply-Automaton/releases/tag/v0.2.4">Download for Windows</a> &nbsp; · &nbsp;
  <a href="docs/setup-and-commands.md">Setup &amp; commands</a> &nbsp; · &nbsp;
  <a href="docs/gui-tutorial.md">Tutorial</a>
</p>

<div align="center">

**Find jobs, score them, fill Easy Apply from your own answers, and track the results.
Desktop app or CLI — same engine.**

<img src="docs/images/gui-run-walkthrough.gif" alt="Animated run walkthrough: detailed multicolor action icons, retained resume filenames, live counters, Scan, dry-run Apply, settings, Reapply and Connect" width="900">

<sub>18-second offline walkthrough: detailed icons, rounded action labels and state-colored glow, changing resume selections and live counters, using fictional data. No command runs or application is submitted.
<a href="docs/images/gui-run-walkthrough.gif">Open the GIF</a>.</sub>

</div>

> **Account risk:** LinkedIn prohibits automation and may restrict your account.
> Educational use only; not affiliated with LinkedIn. Use at your own risk.
> Sign-in is manual; this app does not store your password.

## Get started

**Windows:** [Download v0.2.4](https://github.com/Zanark/LinkedIn-EasyApply-Automaton/releases/tag/v0.2.4),
extract the **entire ZIP**, then open `EasyApplyAutomaton.exe`.
Keep `lea.exe` and `_internal` beside it. No Python installation needed; installed
Edge/Chrome is required. Browser binaries are not bundled, and the EXEs are unsigned.

First launch creates example files in `%LOCALAPPDATA%\EasyApplyAutomaton`.
Add your config, answers and resume PDFs, then use **Tools → Sign in**.
Start with **Scan**, then **dry-run Apply**, before enabling live actions.
[Full executable setup](docs/gui.md#windows-executable).

**Already configured?** [Reuse your existing workspace](docs/gui.md#reuse-an-existing-setup)
instead of initializing again. Set `LEA_WORKSPACE` when launching the EXE against
that setup. Private config snapshots belong in ignored `private-setup`, never a release.

<details>
<summary>Install from source</summary>

For a new source installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[gui,dashboard]"
.\.venv\Scripts\python.exe apply.py init
.\.venv\Scripts\python.exe apply.py gui
```

Edit the example config/answers and sign in manually through Tools before running.
[Every command and option](docs/setup-and-commands.md).

</details>

**Optional:** Streamlit [dashboard](INIT.MD#dashboard) (auto-sized tables, clear answer approval,
overdue outreach queues, clickable skip reasons and report downloads)
and AI need source extras; they are not in the
Windows ZIP. Dynamic resumes need the separate
[resume builder](https://github.com/Zanark/dynamic-resume-builder) and its external Python.

## Screenshots

<img src="docs/images/gui-settings-deepseafoam.png" alt="DeepSeaFoam limits with two-line help, current-action icon, counters and selected resume filename" width="900">

<sub><b>Tune each run:</b> limits and pauses without editing YAML; hover a field for its purpose and example.</sub>

<img src="docs/images/gui-small-harbor-daylight.png" alt="Compact Harbor Daylight Run page with current-action icon, retained resume filename, counters, colored logs and prompt input" width="900">

<sub><b>Light theme, smaller window:</b> detailed action icon, rounded centered name and color-matched border glow, last-selected resume, counters and color-coded logs.
Both themes come from <a href="https://github.com/Zanark/DeepSeaFoam">DeepSeaFoam</a>.
v0.2.4 adds distinct artwork for every stage without a redundant action header; previews use fictional offline data.</sub>

## Documentation

| Need | Guides |
| --- | --- |
| Use the app | [Desktop GUI](docs/gui.md) · [21-topic tutorial](docs/gui-tutorial.md) · [Run guide](INIT.MD) |
| Configure | [Configuration](docs/configuration.md) · [Resume generation](generated/resume/README.md) · [FAQ](docs/faq.md) · [Troubleshooting](docs/troubleshooting.md) |
| Learn the code | [Architecture](docs/architecture.md) · [Run lifecycle](docs/run-lifecycle.md) · [Data structures](docs/data-structures.md) · [Algorithms](docs/algorithms.md) · [Builder integration](docs/resume-studio.md) |
| Contribute | [Developer guide](docs/developer_guide.md) · [GitHub tracking](docs/github-tracking.md) |
