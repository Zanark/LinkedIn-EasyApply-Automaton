# Action icon glossary

[Desktop guide](gui.md#current-action-and-last-resume-source-and-windows-v024)
| [README](../README.md#action-icon-glossary)

The desktop action tile has **36 distinct icons: 29 engine operations and seven
command-lifecycle states**. Its label describes the current operation, not an
application result. These are the actual original GUI designs, exported in
**Harbor Daylight** colors on a light panel background, not generic substitutes
or screenshots of live applications. DeepSeaFoam recolors the same geometry.

Current source displays every icon at 64-by-64 logical pixels inside the
unchanged 112-by-108 tile, with full rounded labels beneath. The table artwork
is a padded documentation export, not the GUI's display size. Windows v0.2.4
retains its original 40px runtime icons.

## Colors and the border glow

The label, border and steady glow share the state's semantic color. Individual
icons also have multicolor details; a green detail inside an icon does not mean
the operation succeeded. The glow does not flash or pulse.

| Color | Role | What it communicates |
| --- | --- | --- |
| Blue | Information | Routine command, browser, job, form, outreach or invitation work. |
| Teal | Accent | Resume/content preparation, selection, saving, reporting or run wrap-up. |
| Green | Document/completion | The command process finished successfully; not every job was necessarily submitted. |
| Yellow | Warning | A skip, timed pause, input request, stopped command or unavailable status stream. |
| Red | Error | A command error or an attempt to discard an unfinished application. |

Colors adapt to the selected theme. Always read the distinct shape and action
name too; color alone is not the status.

## Command lifecycle

These seven states describe the GUI's child command rather than a specific
LinkedIn operation. Tools without operation updates can remain on **Running
command** until they exit.

| Icon | Action and state ID | Color | Meaning |
| --- | --- | --- | --- |
| ![Ready icon](images/action-icons/ready.svg) | **Ready**<br>`ready` | Blue | The window is ready to start a command. |
| ![Starting command icon](images/action-icons/starting.svg) | **Starting command**<br>`starting` | Blue | Launching the selected command's child process. |
| ![Running command icon](images/action-icons/running.svg) | **Running command**<br>`running` | Blue | The child process is running; no more-specific stage is displayed yet. |
| ![Command finished icon](images/action-icons/finished.svg) | **Command finished**<br>`finished` | Green | The command exited successfully, not necessarily every application. |
| ![Stopped icon](images/action-icons/stopped.svg) | **Stopped**<br>`stopped` | Yellow | The command was stopped through the GUI. |
| ![Command error icon](images/action-icons/error.svg) | **Command error**<br>`error` | Red | The command could not start or exited with an error. |
| ![Status unavailable icon](images/action-icons/unavailable.svg) | **Status unavailable**<br>`unavailable` | Yellow | Status updates could not be read reliably; check the console. |

## Jobs and resumes

| Icon | Action and state ID | Color | Meaning |
| --- | --- | --- | --- |
| ![Opening browser icon](images/action-icons/starting_browser.svg) | **Opening browser**<br>`starting_browser` | Blue | Opening the configured automation browser and profile. |
| ![Searching jobs icon](images/action-icons/searching_jobs.svg) | **Searching jobs**<br>`searching_jobs` | Blue | Reading job-search results for the current search. |
| ![Opening job icon](images/action-icons/opening_job.svg) | **Opening job**<br>`opening_job` | Blue | Opening a job posting's details. |
| ![Checking job icon](images/action-icons/checking_job.svg) | **Checking job**<br>`checking_job` | Blue | Recording, filtering and scoring the job before an application. |
| ![Skipping job icon](images/action-icons/skipping_job.svg) | **Skipping job**<br>`skipping_job` | Yellow | Recording why this job will not receive a live application in this pass. |
| ![Selecting resume icon](images/action-icons/selecting_resume.svg) | **Selecting resume**<br>`selecting_resume` | Teal | Choosing a mapped or fallback resume for the job. |
| ![Resume review pause icon](images/action-icons/reviewing_resume.svg) | **Resume review pause**<br>`reviewing_resume` | Yellow | Taking the configured timed pause after the resume choice. |
| ![AI job review icon](images/action-icons/ai_review.svg) | **AI job review**<br>`ai_review` | Blue | Asking the optional AI advisor to evaluate the job. |
| ![Building resume icon](images/action-icons/building_resume.svg) | **Building resume**<br>`building_resume` | Teal | Requesting a per-job tailored resume from the optional builder. |

**Resume review pause** is a configured timer, not a request for approval.
**Building resume** may reuse the builder's cache or fall back to a static
choice; its icon does not guarantee that a new PDF was produced.

The separate **Resume** filename changes only when an application supplies its
final selection, including a tailored replacement. It remains until another
application selects a resume while this window is open. Selection is not proof
that the file was attached or the application submitted.

## Application form

| Icon | Action and state ID | Color | Meaning |
| --- | --- | --- | --- |
| ![Preparing application icon](images/action-icons/preparing_application.svg) | **Preparing application**<br>`preparing_application` | Blue | Registering the final resume choice and preparing the application record. |
| ![Writing cover letter icon](images/action-icons/generating_cover_letter.svg) | **Writing cover letter**<br>`generating_cover_letter` | Teal | Preparing cover-letter content for this application. |
| ![Opening application icon](images/action-icons/opening_application.svg) | **Opening application**<br>`opening_application` | Blue | Opening the posting's Easy Apply dialog. |
| ![Filling application icon](images/action-icons/filling_application.svg) | **Filling application**<br>`filling_application` | Blue | Detecting questions and filling the current form step. |
| ![Selecting attachment icon](images/action-icons/selecting_attachment.svg) | **Selecting attachment**<br>`selecting_attachment` | Teal | Looking for or selecting the matching resume in the page's attachment picker. |
| ![Uploading document icon](images/action-icons/uploading_document.svg) | **Uploading document**<br>`uploading_document` | Blue | Attempting to upload a resume or cover-letter file. |
| ![Reviewing application icon](images/action-icons/reviewing_application.svg) | **Reviewing application**<br>`reviewing_application` | Blue | Advancing the form to its review step; this is not a manual approval pause. |
| ![Waiting for you icon](images/action-icons/awaiting_input.svg) | **Waiting for you**<br>`awaiting_input` | Yellow | Waiting for an answer, approval or requested manual attachment. |
| ![Submitting application icon](images/action-icons/submitting_application.svg) | **Submitting application**<br>`submitting_application` | Blue | Attempting the Submit action; success is not confirmed yet. |
| ![Checking submission icon](images/action-icons/verifying_submission.svg) | **Checking submission**<br>`verifying_submission` | Blue | Checking the page for submission confirmation or another outcome. |
| ![Discarding application icon](images/action-icons/discarding_application.svg) | **Discarding application**<br>`discarding_application` | Red | Attempting to dismiss and discard an unfinished application. |

**Selecting resume** chooses a local file; **Selecting attachment** works with
the page's resume picker. An existing uploaded match can avoid a new upload.
**Reviewing application** advances to review; **Waiting for you** means respond
to the current console prompt, possibly after the requested manual browser step.

**Submitting application** is only an attempt. **Checking submission** can lead
to confirmation, a limit or an unconfirmed outcome. Read the console and
confirmed-outcome counters; do not infer success from either icon.

## Outreach and invitations

| Icon | Action and state ID | Color | Meaning |
| --- | --- | --- | --- |
| ![Finding hiring team icon](images/action-icons/finding_contacts.svg) | **Finding hiring team**<br>`finding_contacts` | Blue | Reading the job's Meet the hiring team contacts. |
| ![Drafting outreach icon](images/action-icons/drafting_message.svg) | **Drafting outreach**<br>`drafting_message` | Teal | Preparing a hiring-team message and connection note. |
| ![Sending outreach icon](images/action-icons/sending_message.svg) | **Sending outreach**<br>`sending_message` | Blue | Attempting to send an approved hiring-team message. |
| ![Loading invitations icon](images/action-icons/loading_connections.svg) | **Loading invitations**<br>`loading_connections` | Blue | Loading and deduplicating saved pending connection targets, not incoming requests. |
| ![Processing invitation icon](images/action-icons/connecting.svg) | **Processing invitation**<br>`connecting` | Blue | Checking a target profile and processing its invitation, or previewing a dry run. |

Drafting does not send anything. Message sending and connection invitations are
separate operations, and a dry-run invitation does not send a request. The
**Processing invitation** icon is also used when the profile turns out to be
already connected, unavailable, skipped or blocked by a limit.

## Results, pauses and wrap-up

| Icon | Action and state ID | Color | Meaning |
| --- | --- | --- | --- |
| ![Saving results icon](images/action-icons/saving_results.svg) | **Saving results**<br>`saving_results` | Teal | Saving an application outcome or run summary to the database. |
| ![Writing report icon](images/action-icons/writing_report.svg) | **Writing report**<br>`writing_report` | Teal | Producing the run's outreach report. |
| ![Pacing pause icon](images/action-icons/pausing.svg) | **Pacing pause**<br>`pausing` | Yellow | Waiting for a configured pacing delay. |
| ![Finishing run icon](images/action-icons/finishing.svg) | **Finishing run**<br>`finishing` | Teal | Performing end-of-run work and cleanup; further outreach stages may still follow. |

**Pacing pause** resumes automatically; it is different from **Waiting for you**.
**Finishing run** is still an operation, not the terminal **Command finished**
state. Optional report or invitation work can change the icon again.

## Coverage and source of truth

The order above is a reference inventory, not a mandatory sequence. Stages
depend on the command, options, job and page; they may repeat, pass quickly or
never appear. Scan, dry runs and tools do not traverse every application stage.
An operation indicator is not an ETA or an independently verified live result.

- [State labels and semantic tones](../linkedin_easy_apply/gui/activity.py):
  `_STATES` and `RunActivity`.
- [Original vector artwork](../linkedin_easy_apply/gui/activity_icons.py):
  `_ARTWORK` and `activity_icon`; the documentation copies preserve that geometry.
- [Theme colors](../linkedin_easy_apply/gui/theme.py): `HARBOR_DAYLIGHT` and
  `DEEP_SEA_FOAM`.
- [Command lifecycle](../linkedin_easy_apply/gui/main_window.py):
  `_run`, `_connect_runner` and `_on_finished`.
- [Job, resume and run stages](../linkedin_easy_apply/orchestrator.py),
  [form stages](../linkedin_easy_apply/forms/easy_apply.py),
  [outreach stages](../linkedin_easy_apply/forms/outreach.py) and
  [invitation stages](../linkedin_easy_apply/connect/service.py):
  explicit `ProgressReporter.activity` calls, not guessed log-text matches.

The detailed designs are available in Windows v0.2.4 and matching source.
This reference does not modify older immutable downloads.
