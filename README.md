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

<sub>18-second offline walkthrough of current source: larger icons in the same box, rounded action labels and state-colored glow, changing resume selections and live counters, using fictional data. No command runs or application is submitted.
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

**Source Connect repair:** the optional no-note fallback now waits for usable controls
and recognizes final Send/Connect only inside an identified invitation dialog.
Notes stay preferred; dry-run never sends. [Behavior and safeguards](docs/configuration.md#outreach).
The v0.2.4 download is unchanged.

## Screenshots

<img src="docs/images/gui-settings-deepseafoam.png" alt="DeepSeaFoam limits with two-line help, current-action icon, counters and selected resume filename" width="900">

<sub><b>Tune each run:</b> limits and pauses without editing YAML; hover a field for its purpose and example.</sub>

<img src="docs/images/gui-small-harbor-daylight.png" alt="Compact Harbor Daylight Run page with current-action icon, retained resume filename, counters, colored logs and prompt input" width="900">

<sub><b>Light theme, smaller window:</b> larger action icon, rounded centered name and color-matched border glow, last-selected resume, counters and color-coded logs.
Both themes come from <a href="https://github.com/Zanark/DeepSeaFoam">DeepSeaFoam</a>.
Current source uses 64px icons inside the unchanged 112×108px box; the v0.2.4 download is unchanged. Previews use fictional offline data.</sub>

## Action icon glossary

The action tile shows **what the command is doing**, not whether it succeeded.
Its border/glow follows the action's color: **blue** for routine work, **teal**
for content/selection/saving, **green** for command completion, **yellow** for
pauses/skips/warnings, and **red** for errors/discarding.

<details>
<summary>Show all 36 icons and their meanings</summary>

The actual GUI artwork is shown in Harbor Daylight colors. DeepSeaFoam uses
the same designs with its own palette. The
[detailed glossary](docs/gui-action-icons.md) also lists each state ID and color.

| Icon | Action | Meaning |
| --- | --- | --- |
| ![Ready icon](docs/images/action-icons/ready.svg) | **Ready** | The window is ready to start a command. |
| ![Starting command icon](docs/images/action-icons/starting.svg) | **Starting command** | Launching the selected command's child process. |
| ![Running command icon](docs/images/action-icons/running.svg) | **Running command** | The child process is running; no more-specific stage is displayed yet. |
| ![Command finished icon](docs/images/action-icons/finished.svg) | **Command finished** | The command exited successfully, not necessarily every application. |
| ![Stopped icon](docs/images/action-icons/stopped.svg) | **Stopped** | The command was stopped through the GUI. |
| ![Command error icon](docs/images/action-icons/error.svg) | **Command error** | The command could not start or exited with an error. |
| ![Status unavailable icon](docs/images/action-icons/unavailable.svg) | **Status unavailable** | Status updates could not be read reliably; check the console. |
| ![Opening browser icon](docs/images/action-icons/starting_browser.svg) | **Opening browser** | Opening the configured automation browser and profile. |
| ![Searching jobs icon](docs/images/action-icons/searching_jobs.svg) | **Searching jobs** | Reading job-search results for the current search. |
| ![Opening job icon](docs/images/action-icons/opening_job.svg) | **Opening job** | Opening a job posting's details. |
| ![Checking job icon](docs/images/action-icons/checking_job.svg) | **Checking job** | Recording, filtering and scoring the job before an application. |
| ![Skipping job icon](docs/images/action-icons/skipping_job.svg) | **Skipping job** | Recording why this job will not receive a live application in this pass. |
| ![Selecting resume icon](docs/images/action-icons/selecting_resume.svg) | **Selecting resume** | Choosing a mapped or fallback resume for the job. |
| ![Resume review pause icon](docs/images/action-icons/reviewing_resume.svg) | **Resume review pause** | Taking the configured timed pause after the resume choice. |
| ![AI job review icon](docs/images/action-icons/ai_review.svg) | **AI job review** | Asking the optional AI advisor to evaluate the job. |
| ![Building resume icon](docs/images/action-icons/building_resume.svg) | **Building resume** | Requesting a per-job tailored resume from the optional builder. |
| ![Preparing application icon](docs/images/action-icons/preparing_application.svg) | **Preparing application** | Registering the final resume choice and preparing the application record. |
| ![Writing cover letter icon](docs/images/action-icons/generating_cover_letter.svg) | **Writing cover letter** | Preparing cover-letter content for this application. |
| ![Opening application icon](docs/images/action-icons/opening_application.svg) | **Opening application** | Opening the posting's Easy Apply dialog. |
| ![Filling application icon](docs/images/action-icons/filling_application.svg) | **Filling application** | Detecting questions and filling the current form step. |
| ![Selecting attachment icon](docs/images/action-icons/selecting_attachment.svg) | **Selecting attachment** | Looking for or selecting the matching resume in the page's attachment picker. |
| ![Uploading document icon](docs/images/action-icons/uploading_document.svg) | **Uploading document** | Attempting to upload a resume or cover-letter file. |
| ![Reviewing application icon](docs/images/action-icons/reviewing_application.svg) | **Reviewing application** | Advancing the form to its review step; this is not a manual approval pause. |
| ![Waiting for you icon](docs/images/action-icons/awaiting_input.svg) | **Waiting for you** | Waiting for an answer, approval or requested manual attachment. |
| ![Submitting application icon](docs/images/action-icons/submitting_application.svg) | **Submitting application** | Attempting the Submit action; success is not confirmed yet. |
| ![Checking submission icon](docs/images/action-icons/verifying_submission.svg) | **Checking submission** | Checking the page for submission confirmation or another outcome. |
| ![Discarding application icon](docs/images/action-icons/discarding_application.svg) | **Discarding application** | Attempting to dismiss and discard an unfinished application. |
| ![Finding hiring team icon](docs/images/action-icons/finding_contacts.svg) | **Finding hiring team** | Reading the job's Meet the hiring team contacts. |
| ![Drafting outreach icon](docs/images/action-icons/drafting_message.svg) | **Drafting outreach** | Preparing a hiring-team message and connection note. |
| ![Sending outreach icon](docs/images/action-icons/sending_message.svg) | **Sending outreach** | Attempting to send an approved hiring-team message. |
| ![Loading invitations icon](docs/images/action-icons/loading_connections.svg) | **Loading invitations** | Loading and deduplicating saved pending connection targets, not incoming requests. |
| ![Processing invitation icon](docs/images/action-icons/connecting.svg) | **Processing invitation** | Checking a target profile and processing its invitation, or previewing a dry run. |
| ![Saving results icon](docs/images/action-icons/saving_results.svg) | **Saving results** | Saving an application outcome or run summary to the database. |
| ![Writing report icon](docs/images/action-icons/writing_report.svg) | **Writing report** | Producing the run's outreach report. |
| ![Pacing pause icon](docs/images/action-icons/pausing.svg) | **Pacing pause** | Waiting for a configured pacing delay. |
| ![Finishing run icon](docs/images/action-icons/finishing.svg) | **Finishing run** | Performing end-of-run work and cleanup; further outreach stages may still follow. |

Stages depend on the command and enabled options; they can repeat or be skipped.
**Waiting for you** needs your response; **Resume review pause** and **Pacing pause**
are timed waits. Use the console and confirmed-outcome counters to check results.

</details>

## Documentation

| Need | Guides |
| --- | --- |
| Use the app | [Desktop GUI](docs/gui.md) · [21-topic tutorial](docs/gui-tutorial.md) · [Action icon glossary](docs/gui-action-icons.md) · [Run guide](INIT.MD) |
| Configure | [Configuration](docs/configuration.md) · [Resume generation](generated/resume/README.md) · [FAQ](docs/faq.md) · [Troubleshooting](docs/troubleshooting.md) |
| Learn the code | [Architecture](docs/architecture.md) · [Run lifecycle](docs/run-lifecycle.md) · [Data structures](docs/data-structures.md) · [Algorithms](docs/algorithms.md) · [Builder integration](docs/resume-studio.md) |
| Contribute | [Developer guide](docs/developer_guide.md) · [GitHub tracking](docs/github-tracking.md) · [Public project handoff](.agent-context/public/README.md) |
