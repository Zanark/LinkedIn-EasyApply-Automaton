"""DeepSeaFoam presentation details beyond Streamlit's native theme settings."""

from __future__ import annotations

from linkedin_easy_apply.gui.theme import DEEP_SEA_FOAM, HARBOR_DAYLIGHT


def build_stylesheet() -> str:
    """Keep scoped emphasis compatible with native dark and light color schemes."""
    dark, light = DEEP_SEA_FOAM, HARBOR_DAYLIGHT
    return f"""
<style>
[data-testid="stApp"] {{
    --dsf-heading: light-dark({light["heading"]}, {dark["heading"]});
    --dsf-card: light-dark({light["raised"]}, {dark["surface"]});
    --dsf-accent: light-dark({light["accent"]}, {dark["accent"]});
    --dsf-danger: light-dark({light["error"]}, {dark["error"]});
    --dsf-hover: light-dark({light["hover"]}, {dark["hover"]});
    --dsf-selection: light-dark({light["selection"]}, {dark["selection"]});
}}
[data-testid="stApp"] :is(h1, h2, h3, h4, h5, h6),
[data-testid="stApp"] [data-testid="stMetricValue"] {{
    color: var(--dsf-heading);
}}
[data-testid="stApp"] [class*="st-key-kpi_card_"] {{
    background-color: var(--dsf-card);
    border-radius: 0.75rem;
}}
[data-testid="stApp"] .st-key-outreach_priority {{
    outline: 2px solid var(--dsf-danger);
    border-radius: 0.75rem;
}}
[data-testid="stApp"] .st-key-outreach_priority h4 {{
    color: var(--dsf-danger);
}}
[data-testid="stApp"] [class*="st-key-outreach_overdue_"] summary {{
    background-color: color-mix(in srgb, var(--dsf-danger) 12%, transparent);
    border: 1px solid var(--dsf-danger);
    border-left-width: 4px;
    border-radius: 0.5rem;
    color: var(--dsf-danger);
}}
[data-testid="stApp"] [class*="st-key-outreach_overdue_"] summary p {{
    color: var(--dsf-danger);
    font-weight: 600;
}}
[data-testid="stApp"] [role="tab"][aria-selected="true"] {{
    color: var(--dsf-heading);
}}
[data-testid="stApp"] [data-testid="stBaseButton-secondary"]:hover {{
    background-color: var(--dsf-hover);
    border-color: var(--dsf-accent);
    color: var(--dsf-heading);
}}
[data-testid="stApp"] ::selection {{
    background-color: var(--dsf-selection);
    color: var(--dsf-heading);
}}
</style>
"""
