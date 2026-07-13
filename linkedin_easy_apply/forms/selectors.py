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
