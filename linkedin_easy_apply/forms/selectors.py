"""Centralised LinkedIn selectors.

Keeping selectors in one module makes the automation resilient: when LinkedIn
changes its DOM only this file needs updating. Each entry is a list of
candidate selectors tried in order.
"""

from __future__ import annotations

# The Easy Apply entry button on a job page.
EASY_APPLY_BUTTON = [
    "button.jobs-apply-button",
    "button[aria-label*='Easy Apply']",
    "button:has-text('Easy Apply')",
]

# The modal dialog that hosts the multi-step form.
MODAL = [
    "div.jobs-easy-apply-modal",
    "div[data-test-modal][role='dialog']",
    "div[role='dialog']:has(.jobs-easy-apply-content)",
]
# On the rebuilt UI the form is NOT a dialog - confirmed live, `role=dialog` and
# `aria-modal` both return zero. What it does have is a level-2 heading reading
# "Apply to <company>" and a `contentinfo` footer holding Next/Review/Submit.
MODAL_HEADING_NAME = r"^Apply to "
MODAL_FOOTER_ROLE = "contentinfo"
# Controls that close the form without submitting.
DISMISS_BUTTON_NAME = r"^Dismiss$"
DISCARD_BUTTON_NAME = r"^Discard"

# Individual field containers within a step.
FIELD_CONTAINER = [
    "div.fb-dash-form-element",
    "div[data-test-form-element]",
    "div.jobs-easy-apply-form-element",
    "div.jobs-easy-apply-form-section__grouping",
]

# Footer action buttons.
BTN_NEXT = [
    "button[aria-label='Continue to next step']",
    "button[data-easy-apply-next-button]",
    "footer button:has-text('Next')",
]
BTN_REVIEW = [
    "button[aria-label='Review your application']",
    "footer button:has-text('Review')",
]
BTN_SUBMIT = [
    "button[aria-label='Submit application']",
    "footer button:has-text('Submit application')",
    "footer button:has-text('Submit')",
]

# LinkedIn's platform-side daily Easy Apply cap. Instead of the "application
# sent" confirmation, a submit can be rejected with a notice like: "We limit
# daily submissions to maintain quality and prevent bots ... Save this job and
# apply tomorrow." Detected so the run stops cleanly instead of falsely recording
# a submit and then hammering the cap on every subsequent job (which looks bot-like).
SUBMIT_LIMIT_MODAL = [
    "div[role='dialog']:has-text('apply tomorrow')",
    "div[role='alertdialog']:has-text('apply tomorrow')",
    "div[role='dialog']:has-text('limit daily submissions')",
    ".artdeco-modal:has-text('Save this job and apply tomorrow')",
]
BTN_BACK = [
    "button[aria-label='Back to previous step']",
    "footer button:has-text('Back')",
]

# Dialogs that appear when closing/discarding an in-progress application.
DISCARD_CONFIRMATION = [
    "[data-test-modal-id='data-test-easy-apply-discard-confirmation']",
    "div[role='alertdialog']",
]
BTN_DISCARD = [
    "[data-test-modal-id='data-test-easy-apply-discard-confirmation'] "
    "button[data-test-dialog-secondary-btn]",
    "[data-test-modal-id='data-test-easy-apply-discard-confirmation'] "
    "button:has-text('Discard')",
    "button.artdeco-modal__confirm-dialog-btn:has-text('Discard')",
    "button:has-text('Discard')",
]
BTN_DISMISS = [
    "button[aria-label='Dismiss']",
    "button[aria-label='Cancel']",
]

# Confirmation that an application was submitted.
POST_SUBMIT_MARKERS = [
    "text=Your application was sent",
    "text=Application sent",
    "h3:has-text('Your application was sent')",
]

# --- Resume step -------------------------------------------------------------
# The resume step shows previously uploaded resumes as selectable cards plus an
# "Upload resume" control. Selectors below cover the current redesign and the
# older markup; each is a list of candidates tried in order.
RESUME_CARD = [
    "div.jobs-document-upload-redesign-card__container",
    "div.jobs-resume-picker__resume",
    "div.ui-attachment--pdf",
    "div[class*='jobs-document-upload'][class*='card']",
]
RESUME_CARD_NAME = [
    "h3.jobs-document-upload-redesign-card__file-name",
    ".jobs-document-upload-redesign-card__file-name",
    ".jobs-resume-picker__resume-name",
    "[class*='file-name']",
]
# Class fragment (not a full selector) marking a card as currently selected.
RESUME_CARD_SELECTED_FRAGMENT = "--selected"
# Control that selects a given resume card.
RESUME_SELECT_BUTTON = [
    "button[aria-label*='Select']",
    "input[type='radio']",
    "label",
]
# The <input type=file> used to upload a new resume (often visually hidden).
RESUME_UPLOAD_INPUT = [
    "input[type='file'][name='file']",
    "input.js-jobs-document-upload__input",
    "input[type='file'][id*='upload-resume']",
    "input[type='file']",
]
# The "Upload resume" button/label that opens a file chooser (used only when no
# <input type=file> is present in the DOM to set files on directly).
RESUME_UPLOAD_BUTTON = [
    "label.jobs-document-upload__upload-button",
    "button[aria-label*='Upload resume']",
    "label[aria-label*='Upload resume']",
    "button:has-text('Upload resume')",
    "label:has-text('Upload resume')",
]

# Job list / card selectors on a search results page.
# LinkedIn has shipped several result-list redesigns and still serves older
# markup to some accounts, so every known variant is listed. ``first_group``
# uses the first selector that matches at least once, hence most-specific first.
JOB_CARD = [
    "li[data-occludable-job-id]",  # current virtualised results list
    "div.job-card-container",  # previous redesign
    "li.jobs-search-results__list-item",  # legacy
    "li.scaffold-layout__list-item:has(a[href*='/jobs/view/'])",
    "[data-job-id][class*='job-card']",
    "div.base-card[data-entity-urn*='jobPosting']",  # logged-out / guest page
]
# Last-resort discovery when no card selector matches: every link to a job.
JOB_CARD_LINK = "a[href*='/jobs/view/']"

# --- accessible-name strategy (LinkedIn's hashed-class rebuild) --------------
# The 2026 jobs UI ships build-generated class names (``ajrhc3``...), no
# ``data-job-id`` and no ``h1``, so nothing above can match it. The content is
# still exposed through ARIA, which is what these describe.
#
# Every result card is a button whose accessible name ends with the nested
# "Dismiss <title> job" control. That nested button matches the same pattern,
# so cards are the matches whose own aria-label does NOT start with "Dismiss".
CARD_ACCESSIBLE_NAME = r"Dismiss .+ job"
DISMISS_LABEL_PREFIX = "Dismiss"
# The job description lives under this heading; the id is only in the URL.
JOB_DESCRIPTION_HEADING = "About the job"
# ``document.title`` is "<job title> | <company> | LinkedIn".
DOCUMENT_TITLE_SUFFIX = "LinkedIn"
JOB_LIST_CONTAINER = [
    "div.scaffold-layout__list",  # current results column
    "div.jobs-search-results-list",  # previous redesign
    "div.jobs-search-results-list__list",
    "ul.jobs-search__results-list",  # logged-out / guest page
]
# Shown when LinkedIn is serving a sign-in wall instead of the results page.
AUTH_WALL = [
    "input[name='session_key']",
    "form.login__form",
    "section.authwall",
    "div.authwall-join-form",
]
# Shown when the search itself legitimately matched nothing.
NO_RESULTS = [
    ".jobs-search-no-results-banner",
    "text=No matching jobs found",
    "text=We couldn't find any jobs",
]

# Job detail (right-hand pane) selectors.
JOB_TITLE = [
    "h1.job-details-jobs-unified-top-card__job-title",
    ".job-details-jobs-unified-top-card__job-title",
    "h1.t-24",
    "h1",
]
JOB_COMPANY = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    "a.ember-view.t-black.t-normal",
]
JOB_PRIMARY_DESC = [
    ".job-details-jobs-unified-top-card__primary-description-container",
    ".job-details-jobs-unified-top-card__tertiary-description-container",
    ".jobs-unified-top-card__subtitle-primary-grouping",
]
JOB_DESCRIPTION = [
    "#job-details",
    ".jobs-description__content",
    ".jobs-box__html-content",
]
JOB_APPLIED_MARKER = [
    "span.artdeco-inline-feedback__message:has-text('Applied')",
    ".jobs-s-apply--applied",
]
JOB_INSIGHT_TEXT = [
    ".job-details-jobs-unified-top-card__job-insight",
    ".jobs-unified-top-card__job-insight",
]

# --- "Meet the hiring team" post-apply outreach ------------------------------
# The section on a job page listing hiring-team members you can message.
HIRING_TEAM_SECTION = [
    "section:has(h2:has-text('Meet the hiring team'))",
    "div:has(> h2:has-text('Meet the hiring team'))",
    ".job-details-people-who-can-help__section",
    "section.hirer-card__container",
]
# A single recruiter card within the section.
HIRING_TEAM_CARD = [
    ".hirer-card__container",
    ".job-details-people-who-can-help__list-item",
    "li:has(a[href*='/in/']):has(button)",
    "div:has(> a[href*='/in/']):has(button)",
]
# The recruiter's display name inside a card.
HIRING_TEAM_NAME = [
    ".hirer-card__hirer-information a span[aria-hidden='true']",
    "a[href*='/in/'] span[aria-hidden='true']",
    ".hirer-card__hirer-information a",
    "a[href*='/in/']",
]
# The link to the recruiter's profile (used as a stable dedup key).
HIRING_TEAM_PROFILE_LINK = [
    ".hirer-card__hirer-information a[href*='/in/']",
    "a[href*='/in/']",
]
# The free "Message" button (skip cards that only offer paid InMail).
HIRING_TEAM_MESSAGE_BUTTON = [
    "button[aria-label*='Message']",
    "button:has-text('Message')",
    "a[aria-label*='Message']",
    "a:has-text('Message')",
]

# The messaging compose overlay that opens after clicking "Message".
MSG_OVERLAY = [
    ".msg-overlay-conversation-bubble",
    ".msg-overlay-installed",
    "div[role='dialog']:has(.msg-form__contenteditable)",
]
# The contenteditable compose box (NOT a textarea).
MSG_COMPOSE_BOX = [
    ".msg-form__contenteditable",
    "div[contenteditable='true'][role='textbox']",
    "div[aria-label*='Write a message']",
]
MSG_SEND_BUTTON = [
    "button.msg-form__send-button",
    "button[type='submit']:has-text('Send')",
    "button:has-text('Send')",
]
MSG_OVERLAY_CLOSE = [
    "button[aria-label*='Close your conversation']",
    ".msg-overlay-bubble-header__control--close-btn",
    "button[aria-label='Dismiss']",
]

# LinkedIn's post-apply "next best action" upsell (e.g. "Turn your resume into a
# profile that recruiters notice") pops over the confirmation and intercepts
# clicks on the hiring-team Message button. Clicking "Not now" dismisses only the
# upsell and leaves the "Meet the hiring team" cards on the page.
POST_APPLY_UPSELL_DISMISS = [
    "button:has-text('Not now')",
    "div[role='dialog']:has-text('recruiters notice') button[aria-label*='Dismiss']",
    "div[role='dialog']:has(button:has-text('Update profile')) button[aria-label*='Dismiss']",
]

# --- Profile "Connect" + custom-note invitation ------------------------------
# Used by the connection-note microservice (linkedin_easy_apply/connect). It opens
# a recruiter's profile and sends a FREE connection invitation carrying the
# <=300-char note. The primary Connect button in the profile top-card action bar.
PROFILE_CONNECT_BUTTON = [
    "main button[aria-label*='Invite'][aria-label*='to connect']",
    "main button[aria-label*='to connect']",
]
# The "More" overflow button that hides Connect on most profiles. The live button
# is just text "More" with NO aria-label (LinkedIn pushes Follow as primary and
# tucks Connect inside this menu), and it is NOT an ``artdeco-dropdown__trigger``,
# so a plain visible-text match is what actually works; the first hit in DOM order
# is the top-card menu (About/Experience "...more" expanders come later).
PROFILE_MORE_BUTTON = [
    "main button:has-text('More')",
    "main button[aria-label*='More actions']",
]
# The Connect entry inside the opened "More" overflow menu. Live, it is a
# ``[role='menuitem']`` whose visible text is exactly "Connect" (no aria-label, and
# it is NOT under ``.artdeco-dropdown__content``). We match by text here, but the
# connector additionally verifies the entry's text is exactly "Connect" before
# clicking - a substring match would also catch "Remove Connection" on an
# already-connected profile and disconnect them, which must never happen.
PROFILE_MORE_CONNECT = [
    "[role='menuitem']:has-text('Connect')",
    "div[role='button']:has-text('Connect')",
]
# "Pending" indicator = an invitation to this person is already outstanding.
PROFILE_PENDING = [
    "main button:has-text('Pending')",
    "main span.artdeco-button__text:has-text('Pending')",
]
# The "Add a note" button in the invitation modal.
INVITE_ADD_NOTE_BUTTON = [
    "button[aria-label='Add a note']",
    "button:has-text('Add a note')",
]
# The custom-note textarea revealed after clicking "Add a note".
INVITE_NOTE_TEXTAREA = [
    "textarea[name='message']",
    "textarea#custom-message",
    "textarea[id*='custom-message']",
    "div[role='dialog'] textarea",
]
# The "Send" / "Send invitation" button in the invitation modal.
INVITE_SEND_BUTTON = [
    "button[aria-label='Send invitation']",
    "button[aria-label*='Send now']",
    "div[role='dialog'] button:has-text('Send')",
]
# The modal LinkedIn shows once the weekly invitation limit is hit (stop signal).
INVITE_LIMIT_MODAL = [
    "div[role='dialog']:has-text('weekly invitation limit')",
    "div[role='dialog']:has-text('reached the weekly')",
]
# Dismiss/cancel in the invitation modal (used to back out cleanly on dry-run or
# when the note field never appears).
INVITE_DISMISS_BUTTON = [
    "div[role='dialog'] button[aria-label='Dismiss']",
    "div[role='dialog'] button[aria-label*='Cancel']",
    "button[aria-label='Dismiss']",
]
