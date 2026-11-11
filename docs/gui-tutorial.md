# Desktop guided tutorial

Open **Tutorial** in the desktop GUI, or press **F1**. Back/Next follows
the sequence; the topic list jumps directly to an option. The **?** beside
**Customize settings for this run** opens its explanation.

In the source GUI or Windows v0.2.2, hover a field, toggle, button or label for its
purpose followed by an **Example:** line. Tabs, saved searches and dropdown
choices have the same help; action/tool explanations follow the current
selection. Hovering does not save, change values or start a command.
Reopen the updated GUI to load this update; older v0.2.1 EXEs are unchanged.

For the guide alone, run `apply.py gui --tutorial`. No configuration or
database is loaded, and no browser or automation command is started.
Windows v0.2.1 and later bundle the same guide: use `EasyApplyAutomaton.exe --tutorial`
or `lea.exe gui --tutorial` from its extracted folder. Older v0.2.0 EXEs do not
contain this feature.

## Start here

**This is a read-only tour, not an automation rehearsal.** You can finish it,
close it, and replay it whenever needed. The tutorial's buttons only navigate
this guide; they do not operate controls in the main window.

- **Next / Back** move between topics. **Finish** closes the last topic.
- **Topic list** jumps to any page or option. Arrow keys move through the list.
- **Close tutorial / Escape** closes the guide without applying anything.
- **F1 / Tutorial** reopens it in the desktop when no command is running.
- **?** beside the customization checkbox jumps to that checkbox's explanation.

The ordinary desktop is a front end for the CLI, not a separate application
engine. Starting automation still operates your LinkedIn account. LinkedIn
prohibits automation in its terms; account restrictions remain a risk.

**Already have a working setup?** Keep its configuration, answers, resumes,
database and browser profile. You do not need to scaffold or sign in again
unless files are missing or the session has expired.

## Workspace, toolbar and themes

**Where:** the top toolbar and left sidebar.

In source and Windows v0.2.2, right-clicking the toolbar or Tutorial cannot hide the
bar through a **Main** checkbox. Text fields still offer normal editing menus.
If an older window has already hidden the bar, finish its run, save editor
changes and reopen it; your saved setup does not need resetting.

- **Config** selects the main YAML used by commands. A relative path is
  resolved from the workspace, not the YAML's own folder. Finishing a path edit
  reloads configuration and answers; save unsaved edits before changing it.
- **Browse** chooses a different YAML file. It does not import or copy inputs.
- **Run / Configuration / Answers / Data / Tools** select the five pages.
- **Light mode / Dark mode**, with sun/moon icons, switches DeepSeaFoam and
  Harbor Daylight. The normal desktop remembers this preference.
- **Tutorial (F1)** opens this guide. It is unavailable during a command so a
  modal tutorial cannot hide a live input prompt.
- **Open dashboard (Ctrl+D)** launches optional source-install analytics.
  It is disabled in the portable build.
- **Quit** closes the desktop; a running child command requires confirmation.

The source workspace is normally the checkout. The EXEs normally use
`%LOCALAPPDATA%\EasyApplyAutomaton`. `LEA_WORKSPACE` overrides either location.
Changing only Config does not move relative resumes, answers or history.
The standalone tutorial ignores Config and does not initialize a workspace.

## Scan and Apply

**Where:** Run > 1 Choose an action.

- **Action: Scan** discovers jobs, extracts details, scores them and records
  results. It does not fill forms or submit applications. It still opens the
  browser and writes discovery/history data; it is not an offline tutorial.
- **Action: Apply** discovers eligible jobs, checks duplicates and limits,
  scores them, selects a resume, fills Easy Apply, and may submit.
- **Run target** is a job count for Scan and a confirmed-submission target
  for Apply. **Command default** (zero) uses `jobs.max_per_run`.
- **Search URL** overrides configured searches for Scan/Apply. For Apply it
  also replaces an exact-job batch. Use an actual LinkedIn search URL.

Skips, failures and aborted jobs do not count toward an Apply submission
target. A target of five is not a promise of five consecutive successful
attempts. Exhausted searches or a company/daily cap can stop it sooner.

**Dry run** is the separate switch that prevents Apply from submitting.
Choosing Apply alone is not permission to send anything.

## Reapply and Connect

**Where:** Run > Action; extra fields appear for the selected action.

- **Reapply (retry failed/aborted)** gets candidates from your database
  instead of searching. Submitted and uncertain submissions stay excluded.
- **Run target for Reapply** caps retry candidates; zero means the command's
  default of all retry candidates. Search URL is disabled.
- **List retry targets only (no browser)** prints candidates without opening
  LinkedIn or filling/submitting. This is different from a browser dry run.
- **Connect (send pending invitations)** opens pending recruiter profiles and
  prepares free connection invitations with their saved notes. It does not
  apply to jobs.
- **Draft run ID** filters notes to an earlier drafting run. Zero means all
  pending runs, not just the latest one.
- **Run target for Connect** limits invitations; zero uses the configured
  connection cap, `outreach.connect_max_per_run`.

Connect's **Dry run** can open Connect/Add a note but never clicks Send.
With Dry run off, Connect can send real invitations after confirmation.
Application-only controls are disabled for this action.

## Run safety switches

**Where:** Run > 2 Review run behavior.

- **Dry run - never submit or send** starts checked. Apply/Reapply can inspect
  and fill forms but do not submit; Connect does not send invitations.
  Dry run still uses a browser and can write logs, screenshots and history.
- **Ignore the minimum score** bypasses the score threshold for Apply/Reapply.
  Scores are still calculated. Duplicate checks, other filters and caps remain.
- **Confirm before every application** requests a separate approval at each
  Submit. It does not replace the initial live-action warning.
- **Answer unknown questions in this window** enables CLI prompt input.
  Turning it off requests `--yes` unless per-submit confirmation is selected.
  Unresolved answers are not invented.
- **Hiring-team outreach (mixed = config)** is tri-state: checked enables,
  unchecked disables, and mixed uses `outreach.enabled`. This is separate
  from outreach mode and end-of-run connection notes.
- **Verbose (DEBUG logging)** adds decision-level diagnostics. Logs may
  include applicant answers and other private values.

The GUI asks before starting live Apply, Reapply or Connect, with **No** as
the default. A Reapply list-only run does not need that live-action warning.
Unsupported switches are greyed out rather than passed to the wrong command.

## Prompts and confirmation

**Where:** the Run console and input row.

- **Input box** holds your response to the current CLI prompt.
- **Send**, or Enter while typing in the input box, sends the text and a newline.
- **Send Enter** sends an empty response, not the text currently in the box.
  It accepts the displayed prompt's default.
- **y / n** answer approval prompts. Read the current prompt before responding.
- Input buttons are disabled when no child command is running.

**Important:** the per-application confirmation defaults to **Yes**, so
Send Enter can submit a real application. The GUI's initial live-action dialog
defaults to **No**; these are two different confirmations.

For an unknown question, you may type a verified answer, or fill the field
manually in the browser and use Send Enter to let the tool read it back.
Pausing also depends on **Pause on unknown questions** in Behavior. Read what
the console actually asks; an empty response is not always an instruction to skip.

Per-submit confirmation takes precedence over `--yes`. If it is selected,
turning off the unknown-question checkbox does not force an unattended run.

## Customize this run

**Where:** Run > 3 Tune this run > Customize settings for this run.

**Unchecked:** the four settings tabs are hidden, and their values do not
override the saved configuration. You can run normally without enabling it.

**Checked:** Search, Limits, Browser and Behavior appear. They start from your
loaded settings. Only values changed from that baseline become overrides.

For example, temporarily changing **Daily cap** from 25 to 5 affects the
prepared run without saving 5 into your original main YAML.

- Checking this box does not start a run or save anything.
- Unchecking it stops applying these overrides; it does not rewrite YAML.
- **Start / Copy command** validate changed settings and create a private
  YAML preset under `logs\gui-runs`.
- The command then uses that preset. Your original saved YAML stays unchanged.
- Presets remain as private files; per-run does not mean memory-only.
- **Configuration > Save** is for permanent changes, not this checkbox.

The separate Dry run switch can also require a preset to override a saved
dry-run value, even with customization unchecked. The command preview shows
when Start or Copy will create a private preset.

## Search overrides

**Where:** Customize settings for this run > Search.

- **Enabled saved searches** selects which loaded search entries to use.
  It is not an editor for creating or renaming search entries.
- **Exact job URLs (Apply only, one per line)** supplies a bounded batch of
  `https://www.linkedin.com/jobs/view/<numeric-id>/` URLs. Blank lines are
  ignored; invalid URLs fail validation.
- Exact jobs replace Apply discovery; Scan uses searches, and Reapply uses
  database candidates.
- The top **Search URL** field takes precedence over configured Apply targets,
  including an exact-job batch.

Each exact job still goes through duplicate/uncertain-submission checks,
filters, scoring and application limits. A URL does not bypass those guards.
Use Configuration to add permanent `search.searches` entries.

## Limits and scoring

**Where:** Customize settings for this run > Limits.

- **Per company** (`jobs.max_per_company`) caps applications for one company
  using recorded history.
- **Daily cap** (`jobs.max_daily`) is the daily submission ceiling. Run target
  does not override it.
- **Search pages** (`jobs.max_search_pages`) bounds pages per saved search.
- **Results per page** (`jobs.search_page_size`) controls the pagination step.
  LinkedIn normally serves 25; changing this is not a guarantee of more results.
- **Pause every N** (`jobs.pause_after`) enables periodic application pauses;
  zero disables them.
- **Pause seconds** (`jobs.pause_seconds`) sets their duration.
- **Score threshold** (`scoring.threshold`) sets the minimum acceptable score
  when score enforcement is enabled.

Scoring rules/weights and enforcement are saved Configuration options, not
controls in this tab. **Ignore the minimum score** is the per-run bypass.
Raise search pages only deliberately; a bigger run target does not remove
the daily cap or invent additional eligible jobs.

## Browser and resume overrides

**Where:** Customize settings for this run > Browser.

- **Browser** chooses installed Edge, installed Chrome, or Playwright Chromium.
  Chromium needs its browser download; Edge/Chrome use the installed browser.
- **Profile folder** holds the browser session you signed into manually.
  Do not run two automation browsers against that profile simultaneously.
- **Headless browser** hides the browser window. Keep it off for manual login,
  manual field corrections, and observing a rehearsal.
- **Slow motion (ms)** adds a delay between browser actions.
- **Timeout (ms)** sets the default action timeout.
- **Navigation (ms)** sets the navigation timeout.
- **Resume folder** points to PDFs used by static resume selection.
- **Default PDF** is a fallback filename; mapping matches can take priority.

All relative folders resolve from the workspace. A path is not a file upload.
On the active LinkedIn resume step, the tool checks matching existing uploaded
resumes before uploading. Failure to select an existing match is not permission
to upload a duplicate.

The external builder can create a differently named tailored PDF. Configure its
paths/design and the static mapping in Configuration; this tab does not edit
resume content.

## Behavior and screenshots

**Where:** Customize settings for this run > Behavior.

- **Pause on unknown questions** controls whether unresolved questions pause
  for help; GUI prompt input must also be enabled. A missing required answer
  can still prevent a successful application.
- **Resume review** adds a delay after logging the selected resume. Zero
  disables the delay. It is not a resume-approval dialog.
- **Capture screenshots** enables runtime screenshots.
- **Capture each step** stores `screenshots.each_step`, but the current
  workflow does not enforce it separately: step captures follow **Capture
  screenshots** even when this option is unchecked.
- **Clean unreferenced screenshots** removes unreferenced runtime captures
  during normal cleanup while retaining referenced evidence.

Screenshots can contain private applicant data. Cleanup is not a privacy
guarantee or a promise that forceful Stop runs cleanup. Keep screenshots and
logs out of public issues/releases unless separately reviewed.

Outreach and the dynamic builder also appear on Behavior and are explained
in the next topic.

## Outreach and dynamic resumes

**Where:** Customize settings for this run > Behavior.

- **Outreach: draft** prepares hiring-team outreach reports instead of sending
  the long messages. **send** can send free messages under the approval flow
  after successful applications.
- **Send connection notes after run** separately enables an end-of-run
  invitation pass. Draft mode alone does not switch off this pass.
- **Connect without a note if unavailable** is off by default. When enabled,
  Connect and the end-of-run pass still prefer the note. Updated source waits
  for usable controls and permits explicit no-note actions or a final Send/Connect
  only inside an identified invitation dialog when note entry is unavailable.
  Turning it off skips that contact instead. Existing drafts and send errors do
  not authorize a plain retry; it never sends the long message. Dry run clicks no
  final send action. This repair is not in the unchanged v0.2.4 download.
- **Connection cap** limits pending invitation rows selected for that pass and
  supplies Connect's default.
- **Dynamic resume builder** enables the separately installed builder when
  properly configured. It re-emphasizes existing master content for a job;
  it must not fabricate experience.

The top tri-state **Hiring-team outreach** controls whether hiring-team
outreach is enabled. Mode, connection-note sending and invitation cap are
separate settings; review all of them before a live run.
Dry run skips both final invitation-send actions and leaves delivery unmarked.
The no-note fallback is included in source and Windows v0.2.4, not v0.2.3.

For no outreach, explicitly disable hiring-team outreach and leave
**Send connection notes after run** off. For resume building, configure the
builder folder, master input, design and interpreter in Configuration.
The packaged EXE is not a Python interpreter; an enabled external builder
needs its own real Python environment.

## Start, Copy command and console

**Where:** the right side of Run.

- **Command preview** updates as controls change; it does not execute a
  command or create presets.
- **Start scan / applications / retry / connections** validates configuration
  and changed overrides, then starts the CLI child. Live actions also ask for
  permission before the child starts.
- **Copy command** copies a PowerShell command. It does not run it, but can
  create a validated private preset, just like Start.
- **READY / RUNNING** and the status bar describe command state.
- **Current action** (source and Windows v0.2.4) shows an icon above the operation
  name beside the counters. Searching, building, filling, uploading, checking
  submission and outreach have distinct labels; **Waiting for you** means
  answer the current prompt. Completion/Stop/error describe the child command,
  not whether an application succeeded. Tools without detailed stages show
  their command lifecycle. Each stage has distinct outlined, detailed multicolor
  artwork. The smaller rounded Nunito action name is centered below it, without a separate
  **CURRENT ACTION** header. Blue is normal work, green/teal resume or completion,
  yellow pause/caution and red error/discard. The border glows steadily in the
  matching color without flashing; none proves a successful submission.
- **Resume** (source and Windows v0.2.3) beside the run buttons shows the final
  application choice, including a replacement tailored PDF. It moves below
  the buttons when narrow. Hover a shortened name to inspect the full filename.
  It changes only on a later explicit application choice, not a scan, missing
  choice, tool, finished run, theme change or Clear log. Closing the window
  forgets it. Selection alone confirms neither attachment nor submission.
  Older v0.2.2 EXEs do not include these two indicators.
- **Live counters** (source and v0.2.2) update above the console for this command:
  Scanned, Applied, Skipped, Failed and HR sent. Applied requires workflow
  confirmation; HR sent excludes drafts and invitations. Scan-only jobs and
  completed dry runs are also Skipped, as in the final summary. The footer
  keeps drafts, dry runs and unconfirmed submissions separate from sends.
  Connect instead shows Profiles, Invites, Already, Skipped and Failed.
  Target progress counts inspected jobs for Scan, completed forms for
  Apply/Reapply, and checked profiles during a connection pass.
  The header shows the actual child action/run and elapsed time, not an ETA.
  Counts remain after Stop, Clear log or selector/theme changes; only an
  accepted new command resets them. Before data arrives, `--` is unavailable,
  not zero. A stream warning preserves the last good totals. List-only and
  unsupported tools hide the strip. Older v0.2.1 EXEs do not include the counters.
- **Console** streams output and prompts, including prompts without a newline.
  Source and v0.2.2 use compact times and colored severity/activity badges;
  messages wrap at word boundaries. Amber SKIP/DRY-RUN are not errors,
  SUBMIT is an attempt, and green SUBMITTED requires confirmed submission.
  DONE means only that the child exited successfully; STOPPED is cancellation.
  Scrolling up pauses automatic tail following until you return to the bottom.
- **Details** (source and v0.2.2) restores original dates and module/function/line
  prefixes for the same retained history. Compact entries expose them on hover.
  This does not change logging verbosity or saved files.
- **Clear log**, also available on the console's context menu, clears the
  window's displayed backlog. It does not delete saved log files or history.
- **Splitter / setup scroll** let you resize the console and reach options
  in a smaller window.

Start and Copy refuse to use unsaved Configuration/Answers edits: save or
reload them first. Per-run presets are separate from those saved inputs.
Only one child command can run in the desktop at a time.
Successful child exit is not by itself proof that an application was sent;
look for confirmed submission results.
Counters report observed outcomes before potentially delayed persistence.
After a hard stop, verify LinkedIn/history before retrying; live totals can be
ahead of database records or the final summary.

## Stop and recovery

**Where:** Run > Stop, or Quit while a child is running.

**Stop is forceful.** It terminates the child and can escalate to a kill
after four seconds. It is not the CLI's graceful Ctrl+C.

- Cleanup, browser closure and a final summary are not guaranteed.
- Browser descendants may remain; do not start another run against the same
  profile until the old browser has stopped.
- If interruption happened near Submit, check LinkedIn and the recorded
  application status before deciding to retry.
- Unconfirmed submissions are deliberately excluded from automatic Reapply.
  They are not ordinary failed attempts.
- Closing the desktop asks whether to stop an active child; No keeps it open.
- A separately launched analytics dashboard can keep running after GUI close.

The tutorial is blocked while a child is running so it cannot cover a prompt.
Stop a run because you intend to stop it, not merely to open help.

## Configuration editor

**Where:** Configuration.

- **Editor** changes the main YAML on screen, not immediately on disk.
- **Validate** parses YAML, expands environment references, and validates the
  same application model used by the CLI. It does not test live login,
  external dependencies or whether your personal answers are true.
- **Save** writes the main configuration only after validation. It reloads
  per-run baseline settings. Save/reload Answers edits first, because changing
  the configured answers path can otherwise discard them.
- **Reload** replaces the editor with the saved file and resets per-run
  settings; unsaved editor changes are discarded.
- **Status text** shows loaded, valid, saved, or the reported problem.

Use this page for permanent searches, scoring weights, filters, resume
mapping, builder settings, answer paths and other advanced configuration.
Save is a real persistent change; closing this tutorial is not.

## Answers editor

**Where:** Answers.

- **Editor** opens the file configured by `answers.file`, resolved from the
  workspace. It need not be beside the main YAML.
- **Validate** checks that the document is a YAML mapping. It does not
  establish answer truth, resume consistency, or a live form match.
- **Save** writes those answers persistently after YAML validation.
- **Reload** discards unsaved edits and rereads the saved answers.
- **Run sync-answers** compares recorded answers with the configured resume
  master and prints a drift report in Run. This GUI button is the report-only
  command; it does not approve or apply suggested overrides.

Enter verified answers only. Do not substitute total career experience for
experience with an unknown skill, or reuse a generic city/remote preference
as consent to a particular commute or hybrid arrangement.
Learned answers and approved overrides can also affect resolution; inspect
the console/report when a filled value differs from YAML.

## Data, exports and dashboard

**Where:** Data.

- **Metric / Value table** shows recorded database statistics, not live
  LinkedIn account totals. It is not editable.
- **Refresh** rereads the database statistics. Database startup/refresh can
  initialize or migrate schema; it is not a read-only file viewer.
- **Format: csv / xlsx** chooses the export format.
- **Export applications** asks for an output path and runs the export command.
  Cancel leaves it unstarted. Review overwrite prompts and keep exports private.
- **Open dashboard** starts the optional Streamlit process and opens its local
  page. It remains separate from the automation child and may outlive the GUI.
- **Open in browser** only opens `http://localhost:8501`; it does not start
  a missing server.

Streamlit/OpenAI are not bundled in the portable EXE. The source installation
needs the dashboard extra for analytics. The built-in table and CSV/XLSX
export remain available in the package. A zero count or exported file is not
evidence of a fresh live application.

## One-shot tools

**Where:** Tools > Command.

**Tool** selects a command; **Value** and **Optional** are enabled only when
that tool accepts them. **Run** executes the selected command and shows output
in the Run console. Run-page dry-run switches do not govern these tools.

- **Sign in to LinkedIn:** opens your configured browser profile for manual
  sign-in. Use the console's Send Enter only after finishing.
- **Verify browser session:** opens the configured browser and checks a page.
  Optional is a URL; blank uses the LinkedIn feed. It can write a screenshot.
- **Database statistics:** prints stored counts; it can initialize schema.
- **Scaffold example configs:** creates missing example inputs/runtime folders
  in the workspace. It does not use the top Config field. Do not scaffold over
  an already working setup merely to follow a tutorial.
- **Show version:** prints the application version; no input is needed.
- **Install optional Chromium:** downloads a Playwright browser. This is a
  network download, not a login check; installed Edge/Chrome do not need it.
- **Preview resume choice:** Value is the required job title; Optional is a
  description. It previews static selection, not a new tailored render/upload.
- **Recognise a question:** Value is the required question. It previews parsing
  and answer resolution from your local answers, without opening LinkedIn.

Missing required Values are reported rather than silently running another tool.
Close this guide before intentionally running a tool.

## Locations and private files

**Where:** Tools > Locations.

Each path is selectable/copyable. **Open** creates the directory if necessary
and opens it in Explorer; it is not a read-only inspection operation.

- **Workspace** is the root for relative inputs and runtime data.
- **Logs** holds saved logs and private GUI run presets.
- **Screenshots** holds runtime captures, not the public fictional UI previews.
- **Generated resumes** holds PDFs for static/generated application resumes.
- **Outreach reports** holds prepared messages and connection notes.
- **Search diagnostics** holds discovery troubleshooting artifacts.

These shortcuts are standard workspace locations; custom configuration can
point a particular output elsewhere. Follow the configured path when it differs.
The ignored `private-setup` folder contains local handoff inputs/helpers, not
public examples. Git ignore is not encryption or an access-control boundary.

The EXE helper's main configuration and the source helper's main configuration
are separate. Their relative answers/history can still refer to the same
workspace. Backups are not automatically restored or synchronized.

## Advanced saved settings

**Where:** Configuration; the dedicated tabs expose only common run options.

The full reference is `docs\configuration.md`. Its saved sections cover:

- **browser:** viewport, downloads, retries and diagnostic capture beyond the
  common timing/profile controls.
- **jobs / search:** company lists, include/exclude keywords and saved URLs.
- **answers:** answer-file path and fuzzy recognition threshold.
- **resume:** default/mapping/master input and the external builder's full
  keyword clusters, design, interpreter, cache and timeout.
- **scoring:** enforcement, matching modes and weighted rules.
- **run:** submission approval, unresolved-question behavior and workflow limits.
- **screenshots / logging / database:** private artifact locations, cleanup,
  log levels and persistent history.
- **cover_letter / outreach:** document/message templates and sending policies.
- **ai:** optional advisor/provider configuration, separate from the deterministic
  automation core. The portable build excludes the OpenAI extra.

Environment-variable references are expanded by the shared loader. Keep
credential values out of public files, screenshots, copied logs and issues.
Enabling an optional feature does not install its dependencies or qualify it
against LinkedIn.

## First-run checklist

**After closing this tutorial**, use this sequence deliberately:

1. Select the correct workspace/configuration. Reuse existing inputs rather
   than initializing again.
2. Review Configuration and Answers; validate and save intentional changes.
3. Confirm the static resume paths and any external builder/interpreter.
4. Use Sign in only if needed, then Verify browser session when you intend a
   real browser check.
5. Start a bounded Scan to inspect discovery and scoring.
6. Choose Apply, keep Dry run checked, and use a small, known target batch to
   inspect form filling. Review the selected resume and unresolved answers.
7. Only when intentionally ready for real applications, review caps/outreach,
   disable Dry run and decide whether to require each submission's approval.
8. Check confirmed outcomes in the console/database; recover uncertain
   submissions manually before retrying.

Nothing on this list was executed by reading the tutorial. The tutorial is
not a live qualification, a promise of successful submissions, or approval
to send applications/invitations.
