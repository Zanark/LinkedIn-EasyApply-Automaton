<p align="center">
  <img src="docs/assets/branding/readme-banner.png" width="900" alt="Easy Apply Automaton: teal robot logo and blue lettering on a feathered grid background">
</p>
<p align="center">
  <a href="https://github.com/Zanark/LinkedIn-EasyApply-Automaton/releases/tag/v0.2.4">Download for Windows</a> &nbsp; · &nbsp;
  <a href="docs/getting-started/setup-and-commands.md">Setup &amp; commands</a> &nbsp; · &nbsp;
  <a href="docs/guides/gui-tutorial.md">Tutorial</a>
</p>

<div align="center">

**Find jobs, score them, fill Easy Apply from your own answers, and track results.**

<img src="docs/assets/images/gui-run-walkthrough.gif" alt="Offline walkthrough: action icons, resume selection, live counters, retry-history preview and Connect" width="900">

<sub>Current source, fictional data: Scan, dry-run Apply, retry preview and Connect.
No browser or sends. <a href="docs/assets/images/gui-run-walkthrough.gif">Open the walkthrough</a>.</sub>

</div>

> **Account risk:** LinkedIn prohibits automation and may restrict your account.
> Educational use only; not affiliated with LinkedIn. Use at your own risk.
> Sign-in is manual; this app does not store your password.

## Get started

**Windows:** [Download v0.2.4](https://github.com/Zanark/LinkedIn-EasyApply-Automaton/releases/tag/v0.2.4),
extract the **entire ZIP**, then open `EasyApplyAutomaton.exe`.
No Python needed; use installed Edge/Chrome. [Full setup](docs/guides/gui.md#windows-executable).

**First run:** add your config, answers and resume PDFs; use **Tools → Sign in**.
Start with **Scan**, then **dry-run Apply** before enabling live actions.

**Source / CLI:** [Install and commands](docs/getting-started/setup-and-commands.md).
**Already configured?** [Reuse your workspace](docs/guides/gui.md#reuse-an-existing-setup); do not initialize again.

Previews show current source, including larger icons and the five-card retry
preview. The **v0.2.4 download is unchanged**.

## Screenshots

<img src="docs/assets/images/gui-settings-deepseafoam.png" alt="DeepSeaFoam limits with two-line help, current-action icon, counters and selected resume filename" width="900">

<sub><b>Tune each run:</b> limits and pauses, with purpose-and-example hover help.</sub>

<img src="docs/assets/images/gui-small-harbor-daylight.png" alt="Compact Harbor Daylight Run page with current-action icon, retained resume filename, counters, colored logs and prompt input" width="900">

<sub><b>Compact light theme:</b> action, retained resume, counters and colored logs.
Fictional data; themes from <a href="https://github.com/Zanark/DeepSeaFoam">DeepSeaFoam</a>.</sub>

## Action icon glossary

[All 36 icons and their meanings](docs/guides/gui-action-icons.md), including the
color/glow legend. Stages describe operations, **not confirmed outcomes**.

<details>
<summary>View the complete icon set</summary>

| Action | Action | Action | Action |
| --- | --- | --- | --- |
| ![Ready](docs/assets/images/action-icons/ready.svg)<br>Ready | ![Starting command](docs/assets/images/action-icons/starting.svg)<br>Starting command | ![Running command](docs/assets/images/action-icons/running.svg)<br>Running command | ![Command finished](docs/assets/images/action-icons/finished.svg)<br>Command finished |
| ![Stopped](docs/assets/images/action-icons/stopped.svg)<br>Stopped | ![Command error](docs/assets/images/action-icons/error.svg)<br>Command error | ![Status unavailable](docs/assets/images/action-icons/unavailable.svg)<br>Status unavailable | ![Opening browser](docs/assets/images/action-icons/starting_browser.svg)<br>Opening browser |
| ![Searching jobs](docs/assets/images/action-icons/searching_jobs.svg)<br>Searching jobs | ![Opening job](docs/assets/images/action-icons/opening_job.svg)<br>Opening job | ![Checking job](docs/assets/images/action-icons/checking_job.svg)<br>Checking job | ![Skipping job](docs/assets/images/action-icons/skipping_job.svg)<br>Skipping job |
| ![Selecting resume](docs/assets/images/action-icons/selecting_resume.svg)<br>Selecting resume | ![Resume review pause](docs/assets/images/action-icons/reviewing_resume.svg)<br>Resume review pause | ![AI job review](docs/assets/images/action-icons/ai_review.svg)<br>AI job review | ![Building resume](docs/assets/images/action-icons/building_resume.svg)<br>Building resume |
| ![Preparing application](docs/assets/images/action-icons/preparing_application.svg)<br>Preparing application | ![Writing cover letter](docs/assets/images/action-icons/generating_cover_letter.svg)<br>Writing cover letter | ![Opening application](docs/assets/images/action-icons/opening_application.svg)<br>Opening application | ![Filling application](docs/assets/images/action-icons/filling_application.svg)<br>Filling application |
| ![Selecting attachment](docs/assets/images/action-icons/selecting_attachment.svg)<br>Selecting attachment | ![Uploading document](docs/assets/images/action-icons/uploading_document.svg)<br>Uploading document | ![Reviewing application](docs/assets/images/action-icons/reviewing_application.svg)<br>Reviewing application | ![Waiting for you](docs/assets/images/action-icons/awaiting_input.svg)<br>Waiting for you |
| ![Submitting application](docs/assets/images/action-icons/submitting_application.svg)<br>Submitting application | ![Checking submission](docs/assets/images/action-icons/verifying_submission.svg)<br>Checking submission | ![Discarding application](docs/assets/images/action-icons/discarding_application.svg)<br>Discarding application | ![Finding hiring team](docs/assets/images/action-icons/finding_contacts.svg)<br>Finding hiring team |
| ![Drafting outreach](docs/assets/images/action-icons/drafting_message.svg)<br>Drafting outreach | ![Sending outreach](docs/assets/images/action-icons/sending_message.svg)<br>Sending outreach | ![Loading invitations](docs/assets/images/action-icons/loading_connections.svg)<br>Loading invitations | ![Processing invitation](docs/assets/images/action-icons/connecting.svg)<br>Processing invitation |
| ![Saving results](docs/assets/images/action-icons/saving_results.svg)<br>Saving results | ![Writing report](docs/assets/images/action-icons/writing_report.svg)<br>Writing report | ![Pacing pause](docs/assets/images/action-icons/pausing.svg)<br>Pacing pause | ![Finishing run](docs/assets/images/action-icons/finishing.svg)<br>Finishing run |

</details>

## Documentation

[Browse all guides](docs/README.md) · [Repository layout](docs/development/repository-layout.md)

| Need | Guides |
| --- | --- |
| Use the app | [Desktop GUI](docs/guides/gui.md) · [21-topic tutorial](docs/guides/gui-tutorial.md) · [Action icon glossary](docs/guides/gui-action-icons.md) · [Run guide](docs/getting-started/run-guide.md) |
| Configure | [Configuration](docs/guides/configuration.md) · [Resume generation](generated/resume/README.md) · [FAQ](docs/guides/faq.md) · [Troubleshooting](docs/guides/troubleshooting.md) |
| Learn the code | [Architecture](docs/architecture/overview.md) · [Run lifecycle](docs/architecture/run-lifecycle.md) · [Data structures](docs/architecture/data-structures.md) · [Algorithms](docs/architecture/algorithms.md) · [Builder integration](docs/guides/resume-studio.md) |
| Contribute | [Developer guide](docs/development/developer_guide.md) · [GitHub tracking](docs/development/github-tracking.md) · [Public project handoff](.agent-context/public/README.md) |
