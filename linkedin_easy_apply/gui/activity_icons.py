"""Original outlined, multicolor artwork for explicit run operations."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from linkedin_easy_apply.gui.theme import Palette

_ARTWORK = {
    "ready": """
        <circle cx="20" cy="20" r="13" fill="{information}" fill-opacity=".10"/>
        <path d="M20 5v4m15 11h-4M20 35v-4M5 20h4"/>
        <path d="m25 14-3 9-9 3 3-9Z" stroke="{document}" fill="{document}" fill-opacity=".18"/>
        <circle cx="20" cy="20" r="1.5" fill="{heading}" stroke="none"/>
    """,
    "starting": """
        <path d="M12 9a14 14 0 1 0 16 0" stroke="{information}"/>
        <path d="M20 4v14" stroke="{document}" stroke-width="3"/>
        <path d="m30 4 1 4 4 1-4 1-1 4-1-4-4-1 4-1Z"
              fill="{warning}" stroke="{warning}" stroke-width="1"/>
    """,
    "running": """
        <path d="m16 5 1-2h6l1 5 4 2 4-2 3 5-3 3v5l3 3-3 5-4-2-4 2-1 5h-6l-1-5-4-2-4 2-3-5 3-3v-5l-3-3 3-5 4 2Z"
              fill="{information}" fill-opacity=".10"/>
        <circle cx="20" cy="19" r="8" stroke="{accent}"/>
        <path d="m18 14 7 5-7 5Z" fill="{document}" stroke="{document}"/>
    """,
    "finished": """
        <path d="m12 26-2 10 7-4 3 3 2-9m4-1 4 10-7-3" stroke="{warning}"/>
        <circle cx="20" cy="16" r="12" stroke="{document}"
                fill="{document}" fill-opacity=".12"/>
        <path d="m14 16 4 4 8-8" stroke="{document}" stroke-width="2.8"/>
        <path d="M3 8h3m28 0h3M5 28l2-2m26 0 2 2" stroke="{information}"/>
    """,
    "stopped": """
        <circle cx="20" cy="20" r="14" stroke="{warning}"
                fill="{warning}" fill-opacity=".10"/>
        <rect x="14" y="14" width="12" height="12" rx="2" stroke="{error}"
              fill="{error}" fill-opacity=".22"/>
        <path d="M20 3v3m14 14h3" stroke="{warning}"/>
    """,
    "error": """
        <path d="M14 5h12l9 9v12l-9 9H14l-9-9V14Z" stroke="{error}"
              fill="{error}" fill-opacity=".12"/>
        <path d="m15 15 10 10m0-10L15 25" stroke="{error}" stroke-width="2.8"/>
        <path d="M4 3v4m-2-2h4m29 29v4m-2-2h4" stroke="{warning}"/>
    """,
    "unavailable": """
        <path d="M6 22v11h5V22m5-7v18h5V15m5-8v13" stroke="{information}"/>
        <path d="M4 5 35 36" stroke="{warning}" stroke-width="2.5"/>
        <path d="M28 27a4 4 0 0 1 8 0c0 3-4 3-4 5m0 4h.01" stroke="{warning}"/>
    """,
    "starting_browser": """
        <rect x="4" y="7" width="32" height="26" rx="4"
              fill="{information}" fill-opacity=".10"/>
        <path d="M4 14h32M9 10.5h.01m4 0h.01m4 0h.01" stroke="{accent}"/>
        <circle cx="20" cy="23" r="7" stroke="{information}"/>
        <path d="M13 23h14m-7-7c-5 4-5 10 0 14 5-4 5-10 0-14" stroke="{information}"/>
        <path d="m31 2 1 3 3 1-3 1-1 3-1-3-3-1 3-1Z"
              stroke="{warning}" fill="{warning}" stroke-width="1"/>
    """,
    "searching_jobs": """
        <rect x="4" y="7" width="23" height="25" rx="3"
              fill="{information}" fill-opacity=".10"/>
        <path d="M9 13h12m-12 5h7m-7 7h6" stroke="{accent}"/>
        <circle cx="25" cy="24" r="8" stroke="{information}" fill="{surface}"/>
        <path d="m31 30 5 6" stroke="{document}" stroke-width="3"/>
        <path d="M21 21h7m-7 5h4" stroke="{information}"/>
    """,
    "opening_job": """
        <path d="M6 12h26v21H6Zm8 0V7h12v5M6 21h17"
              fill="{information}" fill-opacity=".10"/>
        <path d="M17 19v5h5v-5" stroke="{accent}"/>
        <path d="M24 28h12m-5-5 5 5-5 5" stroke="{document}" stroke-width="2.5"/>
        <path d="M10 28h5" stroke="{information}"/>
    """,
    "checking_job": """
        <path d="M12 7H6v28h22V7h-6M13 4h8v6h-8Z"
              fill="{information}" fill-opacity=".10"/>
        <path d="m10 17 2 2 3-4m-5 11 2 2 3-4m3-6h5m-5 9h3" stroke="{document}"/>
        <circle cx="28" cy="25" r="6" stroke="{information}" fill="{surface}"/>
        <path d="m32 30 4 5" stroke="{warning}" stroke-width="2.5"/>
    """,
    "skipping_job": """
        <path d="M5 7h17v27H5Z" fill="{information}" fill-opacity=".10"/>
        <path d="M9 13h8m-8 5h5m-5 11h4" stroke="{information}"/>
        <path d="m19 17 7 7-7 7m9-14 7 7-7 7m7-16v18"
              stroke="{warning}" stroke-width="2.5"/>
    """,
    "selecting_resume": """
        <path d="M7 4h17l7 7v24H7Zm17 0v8h7"
              fill="{information}" fill-opacity=".10"/>
        <circle cx="17" cy="17" r="3" stroke="{accent}"/>
        <path d="M12 26v-2c0-4 10-4 10 0v2m-11 5h7" stroke="{information}"/>
        <path d="m25 22 11 7-5 1-2 6Z" stroke="{document}"
              fill="{surface}" stroke-width="2"/>
    """,
    "reviewing_resume": """
        <path d="M7 4h17l7 7v13M7 4v31h8m9-31v8h7"
              fill="{information}" fill-opacity=".10"/>
        <circle cx="16" cy="17" r="3" stroke="{information}"/>
        <path d="M11 24c1-5 9-5 10 0" stroke="{information}"/>
        <circle cx="20" cy="29" r="5" stroke="{warning}"/>
        <circle cx="32" cy="29" r="5" stroke="{warning}"/>
        <path d="M25 29h2m-12-2-2-4m24 4 1-4" stroke="{warning}"/>
    """,
    "ai_review": """
        <rect x="9" y="9" width="22" height="22" rx="4"
              fill="{information}" fill-opacity=".12"/>
        <path d="M14 4v5m6-5v5m6-5v5M14 31v5m6-5v5m6-5v5M4 14h5m-5 6h5m-5 6h5m22-12h5m-5 6h5m-5 6h5"
              stroke="{accent}"/>
        <path d="m20 13 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z"
              stroke="{information}" fill="{information}" fill-opacity=".22"/>
        <path d="m33 2 1 3 3 1-3 1-1 3-1-3-3-1 3-1Z"
              stroke="{warning}" fill="{warning}" stroke-width="1"/>
    """,
    "building_resume": """
        <path d="M6 4h16l7 7v23H6Zm16 0v8h7M11 17h9m-9 5h5m-5 6h3"
              fill="{information}" fill-opacity=".10"/>
        <path d="m24 21-9 11 4 4 10-11a7 7 0 0 0 8-8l-4 4-4-4 4-4a7 7 0 0 0-9 8Z"
              stroke="{document}" fill="{surface}"/>
        <circle cx="19" cy="32" r="1" stroke="{information}"/>
    """,
    "preparing_application": """
        <path d="M12 7H6v28h25V7h-7M13 4h10v6H13Z"
              fill="{information}" fill-opacity=".10"/>
        <path d="M11 16h13m-13 6h9m-9 6h5" stroke="{information}"/>
        <circle cx="29" cy="28" r="8" stroke="{accent}" fill="{surface}"/>
        <path d="M25 28h8m-4-4v8" stroke="{accent}"/>
    """,
    "generating_cover_letter": """
        <path d="M4 17h25v18H4Zm0 0 12 10 13-10M4 35l8-10m17 10-8-10"
              fill="{information}" fill-opacity=".10"/>
        <path d="M16 21 29 5c3-4 8-2 7 2-2 6-7 9-14 10m-3 0 10-7"
              stroke="{warning}" fill="{warning}" fill-opacity=".14"/>
        <path d="M9 12h6m-4-5h7" stroke="{accent}"/>
    """,
    "opening_application": """
        <rect x="4" y="5" width="32" height="30" rx="3"
              fill="{information}" fill-opacity=".10"/>
        <path d="M4 12h32m-27-4h.01m4 0h.01m4 0h.01" stroke="{accent}"/>
        <path d="M23 18h8v13h-8V18Zm4 7h.01" stroke="{information}"/>
        <path d="M9 24h11m-5-5 5 5-5 5" stroke="{document}" stroke-width="2.5"/>
    """,
    "filling_application": """
        <path d="M6 4h24v31H6Z" fill="{information}" fill-opacity=".10"/>
        <path d="M11 11h3m4 0h7m-14 7h3m4 0h4m-11 7h3m-3 5h7"
              stroke="{information}"/>
        <path d="m21 25 12-12 4 4-12 12-6 2Zm9-9 4 4"
              stroke="{warning}" fill="{surface}"/>
    """,
    "selecting_attachment": """
        <path d="M6 6h12l5 5v23H6Zm12 0v6h5M10 18h6m-6 5h4"
              fill="{information}" fill-opacity=".10"/>
        <path d="m23 29 11-11a6 6 0 0 0-8-8L15 21a4 4 0 0 0 6 6l10-10a2 2 0 0 0-3-3l-9 9"
              stroke="{information}"/>
        <path d="m27 33 3 3 7-7" stroke="{document}" stroke-width="2.5"/>
    """,
    "uploading_document": """
        <path d="M11 29H9a7 7 0 0 1-1-14 10 10 0 0 1 19-4 9 9 0 0 1 4 18h-2"
              fill="{information}" fill-opacity=".10"/>
        <path d="M20 36V17m-6 6 6-6 6 6" stroke="{document}" stroke-width="2.5"/>
        <path d="M9 33H5m28 0h3" stroke="{accent}"/>
    """,
    "reviewing_application": """
        <path d="M7 4h26v32H7Zm5 6h9m-9 20h4m5 0h6"
              fill="{information}" fill-opacity=".10"/>
        <path d="M3 21c8-11 21-11 29 0-8 11-21 11-29 0Z"
              stroke="{accent}" fill="{surface}"/>
        <circle cx="18" cy="21" r="5" stroke="{information}"/>
        <circle cx="18" cy="21" r="1" fill="{document}" stroke="{document}"/>
    """,
    "awaiting_input": """
        <path d="M5 5h30v23H18L9 35v-7H5Z" stroke="{warning}"
              fill="{warning}" fill-opacity=".10"/>
        <path d="M16 13a4 4 0 0 1 8 0c0 4-4 3-4 7m0 4h.01"
              stroke="{warning}" stroke-width="2.5"/>
        <path d="m29 25 8 7-4 1-1 5Z" stroke="{information}" fill="{surface}"/>
    """,
    "submitting_application": """
        <path d="M6 4h15l6 6v12H6Zm15 0v7h6M10 16h9"
              fill="{information}" fill-opacity=".10"/>
        <path d="M5 28v8h30v-8m-30 0h8l2 4h10l2-4h8" stroke="{accent}"/>
        <path d="M20 20h15m-5-5 5 5-5 5" stroke="{information}" stroke-width="2.5"/>
    """,
    "verifying_submission": """
        <path d="m20 4 13 5v10c0 9-13 16-13 16S7 28 7 19V9Z"
              fill="{information}" fill-opacity=".10"/>
        <path d="m14 18 4 4 8-8" stroke="{document}" stroke-width="2.5"/>
        <path d="M35 21a16 16 0 0 1-8 14m6-1-6 1 1-5" stroke="{accent}"/>
    """,
    "discarding_application": """
        <path d="m10 13 2 22h17l2-22M7 12h27M15 12V7h11v5"
              stroke="{error}" fill="{error}" fill-opacity=".10"/>
        <path d="M17 18v11m7-11v11" stroke="{error}"/>
        <path d="m26 3 8 3-3 8-8-3Z" stroke="{warning}" fill="{surface}"/>
    """,
    "finding_contacts": """
        <circle cx="14" cy="12" r="5" stroke="{information}"
                fill="{information}" fill-opacity=".12"/>
        <path d="M4 31v-5c0-9 20-9 20 0v5Zm19-23a5 5 0 0 1 3 9"
              stroke="{information}"/>
        <circle cx="29" cy="25" r="6" stroke="{accent}" fill="{surface}"/>
        <path d="m33 30 4 5" stroke="{document}" stroke-width="2.5"/>
        <path d="M27 25h4m-2-2v4" stroke="{accent}"/>
    """,
    "drafting_message": """
        <path d="M4 6h29v21H16l-8 7v-7H4Z"
              fill="{information}" fill-opacity=".10"/>
        <path d="M10 12h15m-15 6h9" stroke="{information}"/>
        <path d="m22 27 11-11 4 4-11 11-6 2Zm8-8 4 4"
              stroke="{warning}" fill="{surface}"/>
    """,
    "sending_message": """
        <path d="M7 17 36 5 25 35l-6-12Zm12 6L36 5m-17 18-1 9 5-4"
              fill="{information}" fill-opacity=".12"/>
        <path d="M3 25h8m-5 6h7m-1 6h5" stroke="{document}"/>
        <path d="m12 17 15-6" stroke="{accent}"/>
    """,
    "loading_connections": """
        <path d="M11 5h21v22H11Z" fill="{information}" fill-opacity=".10"/>
        <path d="M7 10v17m-3-6v15h32V21m-32 6h10l2 5h8l2-5h10"
              stroke="{accent}"/>
        <circle cx="21" cy="12" r="3" stroke="{information}"/>
        <path d="M16 21c0-6 10-6 10 0m3-14h.01" stroke="{information}"/>
        <path d="M20 27v-3m-3 1 3 3 3-3" stroke="{warning}"/>
    """,
    "connecting": """
        <path d="m15 26-3 3a6 6 0 0 1-8-8l9-9a6 6 0 0 1 9 1"
              stroke="{information}"/>
        <path d="m23 14 3-3a6 6 0 0 1 8 8l-9 9a6 6 0 0 1-9-1"
              stroke="{accent}"/>
        <path d="m13 24 11-11" stroke="{information}"/>
        <circle cx="31" cy="31" r="6" stroke="{information}" fill="{surface}"/>
        <path d="M28 31h6m-3-3v6" stroke="{document}"/>
    """,
    "saving_results": """
        <path d="M5 5h25l5 5v25H5Z" fill="{information}" fill-opacity=".10"/>
        <path d="M11 5v11h17V5M11 35V23h18v12m-5-12v12"
              stroke="{information}"/>
        <path d="M23 8v5" stroke="{accent}" stroke-width="3"/>
        <path d="m8 19 3 3 6-6" stroke="{document}" stroke-width="2.5"/>
    """,
    "writing_report": """
        <path d="M6 4h20l7 7v25H6Zm20 0v8h7"
              fill="{information}" fill-opacity=".10"/>
        <path d="M11 30V20h4v10m4 0V16h4v14" stroke="{document}"/>
        <path d="M27 30V22h3v8" stroke="{warning}"/>
        <path d="M11 10h8m-8 24h19" stroke="{information}"/>
    """,
    "pausing": """
        <path d="M10 5h20m-20 30h20M12 5v8c0 4 8 7 8 7s8 3 8 7v8M28 5v8c0 4-8 7-8 7s-8 3-8 7v8"
              stroke="{information}"/>
        <path d="m15 11 5 5 5-5Zm-1 20 6-6 6 6Z"
              stroke="{warning}" fill="{warning}" fill-opacity=".24"/>
        <path d="M20 19v3" stroke="{warning}"/>
    """,
    "finishing": """
        <path d="M8 36V5m0 2c8-7 16 6 25-1v20c-9 7-17-6-25 1Z"
              stroke="{document}" fill="{document}" fill-opacity=".10"/>
        <path d="M16 7v19m9-17v19M8 16c8-7 16 6 25-1" stroke="{information}"/>
        <path d="M10 9h4v5h-4Zm8 10h5v6h-5Zm9-8h4v5h-4Z"
              stroke="none" fill="{information}" fill-opacity=".65"/>
        <path d="M4 36h10m20-5 1 3 3 1" stroke="{warning}"/>
    """,
}


def activity_icon(state: str, palette: Palette, *, pixel_ratio: float = 1.0) -> QPixmap:
    """Render the stage's own vectors at the current display's pixel density."""
    drawing = _ARTWORK[state].format_map(palette.tokens)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" '
        f'viewBox="0 0 40 40" fill="none" stroke="{palette["information"]}" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{drawing}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"Invalid activity artwork: {state}")
    pixmap = QPixmap(round(64 * pixel_ratio), round(64 * pixel_ratio))
    pixmap.setDevicePixelRatio(pixel_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter, QRectF(0, 0, 64, 64))
    finally:
        painter.end()
    return pixmap
