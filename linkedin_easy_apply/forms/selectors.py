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

# Job list / card selectors on a search results page.
JOB_CARD = [
    "div.job-card-container",
    "li.jobs-search-results__list-item",
    "div[data-job-id]",
]
JOB_LIST_CONTAINER = [
    "div.jobs-search-results-list",
    "ul.jobs-search__results-list",
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
