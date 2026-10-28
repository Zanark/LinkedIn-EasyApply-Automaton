"""Generate docs/readme-banner.svg.

The wordmark is drawn as **vector outlines**, not set in a font. GitHub renders
a README SVG inside an ``<img>``, which blocks web fonts, so any `font-family`
the reader does not already have silently falls back to Arial. Outlines render
identically everywhere and carry no font licence.

The letterforms are original: a wide, squared, heavy techno face with 45-degree
chamfers and small "circuit" notches bitten out of the stems. Each glyph is
defined on a 76 x 100 box (y=0 is the cap line, y=100 the baseline) as a list of
filled rectangles/polygons, plus a list of notches that are painted in the
background colour on top - the banner has a solid background, so painting a
notch and cutting one look identical.

    .\\.venv\\Scripts\\python.exe tools\\build_banner.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "readme-banner.svg"

# --- palette (DeepSeaFoam) --------------------------------------------------
BG = "#000F13"
INK = "#EEE8D5"
ACCENT = "#00A591"
MUTED = "#586E75"
TEXT = "#93A1A1"

# --- glyph geometry ---------------------------------------------------------
BOX_W, BOX_H = 76.0, 100.0
STEM = 26.0
BAR = 24.0
GAP = 16.0
SPACE = 42.0


def rect(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


# Each glyph: ("shapes", "notches"). Notches are painted in BG afterwards.
GLYPHS: dict[str, tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]] = {
    "A": (
        [
            rect(0, 18, STEM, 82),
            rect(50, 18, STEM, 82),
            rect(8, 0, 60, BAR),
            rect(STEM, 48, 24, 22),
        ],
        # chamfer the top-left shoulder, and bite a slot out of the right stem
        [[(0, 18), (14, 18), (0, 32)], rect(62, 76, 14, 9)],
    ),
    "E": (
        [rect(0, 0, STEM, 100), rect(0, 0, 72, BAR), rect(0, 38, 56, 22), rect(0, 76, 76, BAR)],
        [rect(0, 64, 13, 8), [(62, 0), (72, 0), (72, 10)]],
    ),
    "S": (
        [
            rect(0, 0, 76, BAR),
            rect(0, 18, STEM, 34),
            rect(0, 38, 76, 22),
            rect(50, 56, STEM, 28),
            rect(0, 76, 76, BAR),
        ],
        [[(0, 0), (12, 0), (0, 12)], rect(63, 64, 13, 8)],
    ),
    "Y": (
        [rect(0, 0, STEM, 46), rect(50, 0, STEM, 46), rect(25, 40, STEM, 60)],
        [rect(0, 30, 12, 8), [(64, 0), (76, 0), (76, 12)]],
    ),
    "P": (
        [rect(0, 0, STEM, 100), rect(0, 0, 70, BAR), rect(44, 18, STEM, 28), rect(0, 40, 70, 22)],
        [rect(0, 72, 13, 8), [(60, 0), (70, 0), (70, 10)]],
    ),
    "L": ([rect(0, 0, STEM, 100), rect(0, 76, 76, BAR)], [rect(0, 28, 12, 8)]),
    "U": (
        [rect(0, 0, STEM, 100), rect(50, 0, STEM, 100), rect(0, 76, 76, BAR)],
        [rect(0, 20, 12, 8), rect(64, 44, 12, 8)],
    ),
    "T": ([rect(0, 0, 76, BAR), rect(25, 18, STEM, 82)], [[(0, 0), (12, 0), (0, 12)]]),
    "O": (
        [rect(0, 0, 76, 100)],
        # counter, plus a chamfer and a stem slot
        [rect(STEM, BAR, 24, 52), [(0, 0), (14, 0), (0, 14)], rect(0, 62, 11, 8)],
    ),
    "M": (
        [rect(0, 0, 24, 100), rect(52, 0, 24, 100), rect(0, 0, 76, BAR), rect(30, 18, 16, 46)],
        [rect(0, 76, 11, 8), rect(65, 76, 11, 8)],
    ),
    "N": (
        [rect(0, 0, STEM, 100), rect(50, 0, STEM, 100), [(26, 0), (50, 62), (50, 100), (26, 38)]],
        [[(0, 0), (12, 0), (0, 12)], rect(64, 84, 12, 8)],
    ),
}


def glyph_svg(char: str, x: float, y: float, scale: float) -> tuple[str, str]:
    """Return (ink paths, notch paths) for *char* placed at *x*, *y*."""
    shapes, notches = GLYPHS[char]

    def render(polys: list[list[tuple[float, float]]]) -> str:
        out = []
        for poly in polys:
            points = " ".join(
                f"{x + px * scale:.2f},{y + py * scale:.2f}" for px, py in poly
            )
            out.append(f'<polygon points="{points}"/>')
        return "".join(out)

    return render(shapes), render(notches)


def word(text: str, x: float, y: float, scale: float) -> tuple[str, str, float]:
    """Lay out *text*; returns (ink, notches, advance width)."""
    ink: list[str] = []
    notches: list[str] = []
    cursor = x
    for index, char in enumerate(text):
        if char == " ":
            cursor += SPACE * scale
            continue
        if index and text[index - 1] != " ":
            cursor += GAP * scale
        shapes, cuts = glyph_svg(char, cursor, y, scale)
        ink.append(shapes)
        notches.append(cuts)
        cursor += BOX_W * scale
    return "".join(ink), "".join(notches), cursor - x


# Advance width of Cascadia Mono / Consolas as a fraction of font-size, measured
# from a rendered sample (451.2px for 35 characters at 22px).
MONO_ADVANCE = 0.586


def build() -> str:
    width, height = 960.0, 320.0
    scale = 0.76  # cap height in px
    mono = "'Cascadia Mono', Consolas, 'DejaVu Sans Mono', monospace"
    tagline = "Automate your LinkedIn applications"
    tagline_size = 22

    line1_ink, line1_cut, w1 = word("EASY APPLY", 0, 0, scale)
    line2_ink, line2_cut, w2 = word("AUTOMATON", 0, 0, scale)
    block = max(w1, w2)
    left = round((width - (28 + block)) / 2)
    text_x = left + 28

    line1_ink, line1_cut, _ = word("EASY APPLY", text_x, 86, scale)
    line2_ink, line2_cut, _ = word("AUTOMATON", text_x, 176, scale)
    cursor_x = round(text_x + len(tagline) * tagline_size * MONO_ADVANCE + 13)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" \
viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="title description">
  <title id="title">Easy Apply Automaton - Automate your LinkedIn applications.</title>
  <desc id="description">A wide squared techno wordmark in warm ivory on near-black teal, under a \
shell prompt and above a tagline with a seafoam block cursor.</desc>
  <rect width="{width:.0f}" height="{height:.0f}" rx="12" fill="{BG}"/>
  <rect x="{left}" y="48" width="5" height="226" rx="2.5" fill="{ACCENT}"/>

  <text x="{text_x}" y="62" font-family="{mono}" font-size="17">\
<tspan fill="{ACCENT}">$</tspan>\
<tspan fill="{MUTED}" xml:space="preserve"> apply.py apply --limit 15</tspan></text>

  <g fill="{INK}">{line1_ink}{line2_ink}</g>
  <g fill="{BG}">{line1_cut}{line2_cut}</g>

  <text id="tagline" x="{text_x}" y="298" fill="{TEXT}" font-family="{mono}" \
font-size="{tagline_size}">{tagline}</text>
  <rect id="cursor" x="{cursor_x}" y="280" width="12" height="23" fill="{ACCENT}"/>
</svg>
"""


if __name__ == "__main__":
    TARGET.write_text(build(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size} bytes)")
