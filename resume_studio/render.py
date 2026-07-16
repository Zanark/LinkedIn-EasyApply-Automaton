r"""
Resume bake-off renderer.

Reads ONE master file (master.yaml) and produces the SAME resume through three
independent engines, so you can compare the results side by side:

    out/1_rendercv.pdf   RenderCV  -> Typst engine + a batteries-included ATS theme
    out/2_typst.pdf      Typst     -> a hand-written modern single-column template
    out/3_html.pdf       Playwright-> an HTML/CSS design printed to PDF by headless Edge

Usage:
    .\.venv\Scripts\python.exe resume_studio\render.py            # build all three
    .\.venv\Scripts\python.exe resume_studio\render.py rendercv   # build one
"""
from __future__ import annotations

import subprocess
import sys
import os
import shutil
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TEMPLATES = HERE / "templates"
MASTER = HERE / "master.yaml"
DESIGNS = HERE / "designs"

ACCENT = "#1f5fa8"
MUTED = "#5b6470"
RULE = "#d9dee5"
SUBHEAD = "#33404f"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_master() -> dict:
    return yaml.safe_load(MASTER.read_text(encoding="utf-8"))


def mon(v) -> str:
    """ISO 'YYYY-MM' -> 'Jul 2024'; 'present' -> 'Present'; '' -> ''."""
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if s.lower() == "present":
        return "Present"
    parts = s.split("-")
    year = parts[0]
    if len(parts) >= 2 and parts[1].isdigit():
        idx = int(parts[1])
        if 1 <= idx <= 12:
            return f"{MONTHS[idx - 1]} {year}"
    return s


def strip_http(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def date_range(e: dict) -> str:
    a, b = mon(e.get("start")), mon(e.get("end"))
    if a and b:
        return f"{a} \u2013 {b}"
    return a or b


# --------------------------------------------------------------------------- #
# 1. RenderCV
# --------------------------------------------------------------------------- #
def build_rendercv(m: dict, theme: str = "engineeringresumes") -> dict:
    b = m["basics"]
    known = {"LinkedIn", "GitHub", "GitLab", "ORCID", "Mastodon",
             "StackOverflow", "ResearchGate", "YouTube", "Google Scholar",
             "Telegram", "Instagram", "X"}
    social = [{"network": l["network"], "username": l["username"]}
              for l in b.get("links", []) if l.get("network") in known]

    sections: dict = {}
    if b.get("summary"):
        sections["Summary"] = [b["summary"]]

    experience = []
    for e in m.get("experience", []):
        highlights = list(e.get("highlights") or [])
        for g in e.get("groups", []) or []:
            hs = list(g.get("highlights") or [])
            if hs:
                hs[0] = f"**{g['name']}** \u2014 {hs[0]}"
                highlights.extend(hs)
        experience.append({
            "company": e["company"],
            "position": e["role"],
            "location": e.get("location") or None,
            "start_date": str(e["start"]) if e.get("start") else None,
            "end_date": str(e["end"]) if e.get("end") else None,
            "highlights": highlights,
        })
    if experience:
        sections["Experience"] = experience

    education = []
    for e in m.get("education", []) or []:
        education.append({
            "institution": e["institution"],
            "area": e.get("area") or None,
            "degree": e.get("degree") or None,
            "location": e.get("location") or None,
            "start_date": str(e["start"]) if e.get("start") else None,
            "end_date": str(e["end"]) if e.get("end") else None,
            "highlights": e.get("highlights") or None,
        })
    if education:
        sections["Education"] = education

    skills = [{"label": s["category"], "details": ", ".join(s["items"])}
              for s in m.get("skills", [])]
    if m.get("certifications"):
        skills.append({"label": "Certifications",
                       "details": ", ".join(m["certifications"])})
    if skills:
        sections["Skills"] = skills

    awards = []
    for a in m.get("awards", []) or []:
        awards.append({
            "name": a["title"],
            "date": a.get("date") or None,
            "summary": a.get("detail") or None,
        })
    if awards:
        sections["Awards and Recognition"] = awards

    cv = {
        "name": b["name"],
        "location": b.get("location") or None,
        "email": b.get("email") or None,
        "phone": b.get("phone") or None,
        "social_networks": social,
        "sections": sections,
    }
    if b.get("title"):
        cv["headline"] = b["title"]

    return {"cv": cv, "design": {"theme": theme}}


def render_rendercv(m: dict) -> Path:
    data = build_rendercv(m)
    src = OUT / "_rendercv_input.yaml"
    src.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                   encoding="utf-8")
    exe = Path(sys.executable).with_name("rendercv.exe")
    cmd = [str(exe) if exe.exists() else "rendercv", "render", src.name,
           "--pdf-path", "1_rendercv.pdf",
           "--output-folder", "_rcv_work",
           "--dont-generate-markdown", "--dont-generate-html",
           "--dont-generate-png"]
    # RenderCV prints unicode status glyphs; force UTF-8 so it does not crash on
    # the Windows cp1252 console when its stdout is a pipe.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run(cmd, cwd=OUT, capture_output=True, text=True,
                         env=env, encoding="utf-8", errors="replace")
    pdf = OUT / "1_rendercv.pdf"
    if res.returncode != 0 or not pdf.exists():
        raise RuntimeError((res.stdout + res.stderr)[-1500:])
    return pdf


# --------------------------------------------------------------------------- #
# 2. Typst (hand-written template, generated as source)
# --------------------------------------------------------------------------- #
def te(s) -> str:
    """Escape Typst markup metacharacters in dynamic text."""
    s = str(s)
    for a, b in (("\\", "\\\\"), ("#", "\\#"), ("$", "\\$"), ("*", "\\*"),
                 ("_", "\\_"), ("`", "\\`"), ("@", "\\@"), ("<", "\\<"),
                 (">", "\\>"), ("[", "\\["), ("]", "\\]")):
        s = s.replace(a, b)
    return s


def _typ_list(items: list[str]) -> str:
    body = ",\n  ".join(f"[{te(h)}]" for h in items)
    return f"#list(indent: 2pt, spacing: 3.2pt,\n  {body}\n)"


def build_typst(m: dict) -> str:
    b = m["basics"]
    L: list[str] = []
    L.append('#set document(title: "' + b["name"].replace('"', "") + ' - Resume")')
    L.append('#set page(paper: "a4", margin: (x: 1.5cm, top: 1.3cm, bottom: 1.3cm))')
    L.append('#set text(font: ("Source Sans 3", "Segoe UI", "Arial"), '
             'size: 10pt, fill: rgb("#1a1a1a"))')
    L.append("#set par(justify: false, leading: 0.6em)")
    L.append(f'#let accent = rgb("{ACCENT}")')
    L.append(f'#let muted = rgb("{MUTED}")')
    L.append('#show link: set text(fill: accent)')
    L.append("")

    # header
    L.append(f'#text(size: 22pt, weight: 700, fill: accent)[{te(b["name"])}]')
    L.append("#v(3pt)")
    if b.get("title"):
        L.append(f'#text(size: 11pt, weight: 600, fill: muted)[{te(b["title"])}]')
        L.append("#v(4pt)")
    contact = []
    if b.get("email"):
        contact.append(f'#link("mailto:{b["email"]}")[{te(b["email"])}]')
    if b.get("phone"):
        contact.append(te(b["phone"]))
    if b.get("location"):
        contact.append(te(b["location"]))
    for l in b.get("links", []):
        contact.append(f'#link("{l["url"]}")[{te(strip_http(l["url"]))}]')
    sep = ' #text(fill: rgb("' + RULE + '"))[ | ] '
    L.append(f'#text(size: 9.3pt, fill: muted)[{sep.join(contact)}]')
    L.append("#v(3pt)")
    L.append("#line(length: 100%, stroke: 1.2pt + accent)")
    if b.get("summary"):
        L.append("#v(5pt)")
        L.append(f"{te(b['summary'])}")

    def section(title: str) -> None:
        L.append("#v(9pt)")
        L.append(f'#text(size: 10.5pt, weight: 700, fill: accent, '
                 f'tracking: 0.8pt)[{te(title.upper())}]')
        L.append("#v(2pt)")
        L.append(f'#line(length: 100%, stroke: 0.5pt + rgb("{RULE}"))')
        L.append("#v(4pt)")

    # experience
    if m.get("experience"):
        section("Work Experience")
        for e in m["experience"]:
            head = f'*{te(e["company"])}* / {te(e["role"])}'
            meta = date_range(e)
            if e.get("location"):
                meta += f' \u00b7 {te(e["location"])}'
            L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
            L.append(f"  [{head}],")
            L.append(f'  align(right)[#text(fill: muted, size: 9pt)[{meta}]]')
            L.append(")")
            if e.get("highlights"):
                L.append(_typ_list(e["highlights"]))
            for g in e.get("groups", []) or []:
                L.append("#v(2pt)")
                L.append(f'#text(weight: 700, size: 9.7pt, '
                         f'fill: rgb("{SUBHEAD}"))[{te(g["name"])}]')
                if g.get("highlights"):
                    L.append(_typ_list(g["highlights"]))
            L.append("#v(5pt)")

    # skills
    if m.get("skills"):
        section("Skills")
        rows = []
        for s in m["skills"]:
            rows.append(f'  [*{te(s["category"])}*], [{te(", ".join(s["items"]))}]')
        if m.get("certifications"):
            rows.append(f'  [*Certifications*], [{te(", ".join(m["certifications"]))}]')
        L.append("#grid(columns: (135pt, 1fr), column-gutter: 6pt, row-gutter: 3.5pt,")
        L.append(",\n".join(rows))
        L.append(")")

    # education
    if m.get("education"):
        section("Education")
        for e in m["education"]:
            head = f'*{te(e["institution"])}*'
            if e.get("degree"):
                head += f' / {te(e["degree"])}'
                if e.get("area"):
                    head += f', {te(e["area"])}'
            meta = date_range(e)
            if e.get("location"):
                meta += f' \u00b7 {te(e["location"])}'
            L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
            L.append(f"  [{head}],")
            L.append(f'  align(right)[#text(fill: muted, size: 9pt)[{meta}]]')
            L.append(")")
            if e.get("highlights"):
                L.append(_typ_list(e["highlights"]))
            L.append("#v(5pt)")

    # awards
    if m.get("awards"):
        section("Awards and Recognition")
        for a in m["awards"]:
            L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
            L.append(f'  [*{te(a["title"])}*],')
            L.append(f'  align(right)[#text(fill: muted, size: 9pt)[{te(a.get("date",""))}]]')
            L.append(")")
            if a.get("detail"):
                L.append(f'{te(a["detail"])}')
            L.append("#v(4pt)")

    return "\n".join(L) + "\n"


def render_typst(m: dict) -> Path:
    import typst
    src = OUT / "_typst_input.typ"
    src.write_text(build_typst(m), encoding="utf-8")
    pdf = OUT / "2_typst.pdf"
    font_paths = []
    try:
        import rendercv_fonts
        font_paths = [str(Path(rendercv_fonts.__file__).resolve().parent)]
    except Exception:
        pass
    typst.compile(str(src), output=str(pdf), font_paths=font_paths)
    if not pdf.exists():
        raise RuntimeError("typst produced no PDF")
    return pdf


# --------------------------------------------------------------------------- #
# 2b. extra Typst LAYOUT variants (same content, very different structure)
# --------------------------------------------------------------------------- #
def _typ_contacts(b: dict) -> list[str]:
    """Contact chips WITH links (for light backgrounds)."""
    c = []
    if b.get("location"):
        c.append(te(b["location"]))
    if b.get("email"):
        c.append(f'#link("mailto:{b["email"]}")[{te(b["email"])}]')
    if b.get("phone"):
        c.append(te(b["phone"]))
    for l in b.get("links", []):
        c.append(f'#link("{l["url"]}")[{te(strip_http(l["url"]))}]')
    return c


def _typ_contacts_plain(b: dict) -> list[str]:
    """Contact chips as plain text (for dark/coloured backgrounds)."""
    c = []
    if b.get("location"):
        c.append(te(b["location"]))
    if b.get("email"):
        c.append(te(b["email"]))
    if b.get("phone"):
        c.append(te(b["phone"]))
    for l in b.get("links", []):
        c.append(te(strip_http(l["url"])))
    return c


def _typ_exp_grid(L: list[str], m: dict, sub_hex: str) -> None:
    """Emit experience entries as company/role + right-aligned dates + bullets."""
    for e in m["experience"]:
        head = f'*{te(e["company"])}* / {te(e["role"])}'
        meta = date_range(e)
        if e.get("location"):
            meta += f' \u00b7 {te(e["location"])}'
        L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
        L.append(f"  [{head}],")
        L.append(f'  align(right)[#text(fill: rgb("{MUTED}"), size: 9pt)[{meta}]]')
        L.append(")")
        if e.get("highlights"):
            L.append(_typ_list(e["highlights"]))
        for g in e.get("groups", []) or []:
            L.append("#v(2pt)")
            L.append(f'#text(weight: 700, size: 9.7pt, '
                     f'fill: rgb("{sub_hex}"))[{te(g["name"])}]')
            if g.get("highlights"):
                L.append(_typ_list(g["highlights"]))
        L.append("#v(5pt)")


def _typ_body(L: list[str], m: dict, sub_hex: str) -> None:
    """Full-width body: Experience -> Skills -> Education -> Awards, via `#sec`."""
    if m.get("experience"):
        L.append('#sec("Work Experience")')
        _typ_exp_grid(L, m, sub_hex)
    if m.get("skills"):
        L.append('#sec("Skills")')
        rows = [f'  [*{te(s["category"])}*], [{te(", ".join(s["items"]))}]'
                for s in m["skills"]]
        if m.get("certifications"):
            rows.append(f'  [*Certifications*], [{te(", ".join(m["certifications"]))}]')
        L.append("#grid(columns: (135pt, 1fr), column-gutter: 6pt, row-gutter: 3.5pt,")
        L.append(",\n".join(rows))
        L.append(")")
    if m.get("education"):
        L.append('#sec("Education")')
        for e in m["education"]:
            head = f'*{te(e["institution"])}*'
            if e.get("degree"):
                head += f' / {te(e["degree"])}'
                if e.get("area"):
                    head += f', {te(e["area"])}'
            L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
            L.append(f"  [{head}],")
            L.append(f'  align(right)[#text(fill: rgb("{MUTED}"), size: 9pt)[{date_range(e)}]]')
            L.append(")")
            if e.get("highlights"):
                L.append(_typ_list(e["highlights"]))
            L.append("#v(5pt)")
    if m.get("awards"):
        L.append('#sec("Awards and Recognition")')
        for a in m["awards"]:
            L.append("#grid(columns: (1fr, auto), column-gutter: 10pt,")
            L.append(f'  [*{te(a["title"])}*],')
            L.append(f'  align(right)[#text(fill: rgb("{MUTED}"), size: 9pt)[{te(a.get("date",""))}]]')
            L.append(")")
            if a.get("detail"):
                L.append(f'{te(a["detail"])}')
            L.append("#v(4pt)")


def build_typst_serif(m: dict) -> str:
    """Variant A: classic serif, centered header, small-caps section rules."""
    b = m["basics"]
    L: list[str] = []
    L.append('#set document(title: "' + b["name"].replace('"', "") + ' - Resume")')
    L.append('#set page(paper: "a4", margin: (x: 1.7cm, top: 1.4cm, bottom: 1.3cm))')
    L.append('#set text(font: ("EB Garamond", "Georgia", "serif"), '
             'size: 10.8pt, fill: rgb("#111111"))')
    L.append("#set par(justify: true, leading: 0.58em)")
    L.append('#show link: set text(fill: rgb("#444444"))')
    L.append("#let sec(t) = {")
    L.append("  v(9pt)")
    L.append("  text(size: 11.5pt, weight: 700, tracking: 1pt)[#smallcaps(t)]")
    L.append("  v(1pt)")
    L.append('  line(length: 100%, stroke: 0.6pt + rgb("#999999"))')
    L.append("  v(3pt)")
    L.append("}")
    L.append("")
    L.append("#align(center)[")
    L.append(f'  #text(size: 23pt, weight: 700)[{te(b["name"])}]')
    if b.get("title"):
        L.append("  #linebreak()")
        L.append("  #v(2pt)")
        L.append(f'  #text(size: 11pt, style: "italic")[{te(b["title"])}]')
    L.append("  #linebreak()")
    L.append("  #v(4pt)")
    sep = ' #text(fill: rgb("#bbbbbb"))[ | ] '
    L.append(f'  #text(size: 9.3pt)[{sep.join(_typ_contacts(b))}]')
    L.append("]")
    L.append('#v(3pt)')
    L.append('#line(length: 100%, stroke: 1pt + rgb("#111111"))')
    if b.get("summary"):
        L.append("#v(5pt)")
        L.append(f'#align(center)[#text(style: "italic")[{te(b["summary"])}]]')
    _typ_body(L, m, SUBHEAD)
    return "\n".join(L) + "\n"


def build_typst_band(m: dict) -> str:
    """Variant C: bold filled accent card header, upper-case accent sections."""
    accent = "#b8322f"
    b = m["basics"]
    L: list[str] = []
    L.append('#set document(title: "' + b["name"].replace('"', "") + ' - Resume")')
    L.append('#set page(paper: "a4", margin: (x: 1.5cm, top: 1.2cm, bottom: 1.3cm))')
    L.append('#set text(font: ("Poppins", "Segoe UI", "Arial"), '
             'size: 9.8pt, fill: rgb("#1a1a1a"))')
    L.append("#set par(justify: false, leading: 0.6em)")
    L.append(f'#let accent = rgb("{accent}")')
    L.append("#show link: set text(fill: accent)")
    L.append("#let sec(t) = {")
    L.append("  v(9pt)")
    L.append("  text(size: 11pt, weight: 800, fill: accent)[#upper(t)]")
    L.append("  v(2pt)")
    L.append("  line(length: 100%, stroke: 1.5pt + accent)")
    L.append("  v(4pt)")
    L.append("}")
    L.append("")
    L.append('#block(fill: accent, width: 100%, inset: (x: 14pt, y: 12pt), radius: 4pt)[')
    L.append(f'  #text(fill: white, size: 22pt, weight: 800)[{te(b["name"])}]')
    if b.get("title"):
        L.append("  #linebreak()")
        L.append(f'  #text(fill: rgb("#f2dede"), size: 11pt, weight: 500)[{te(b["title"])}]')
    L.append("  #linebreak()")
    L.append("  #v(3pt)")
    sep = ' #text(fill: rgb("#e6a9a7"))[ | ] '
    L.append(f'  #text(fill: white, size: 9pt)[{sep.join(_typ_contacts_plain(b))}]')
    L.append("]")
    if b.get("summary"):
        L.append("#v(6pt)")
        L.append(f'{te(b["summary"])}')
    _typ_body(L, m, "#7a2422")
    return "\n".join(L) + "\n"


def build_typst_sidebar(m: dict) -> str:
    """Variant B: full-height navy sidebar (contact/skills/certs) + main column."""
    navy = "#1f3a5f"
    b = m["basics"]
    L: list[str] = []
    L.append('#set document(title: "' + b["name"].replace('"', "") + ' - Resume")')
    L.append('#set page(paper: "a4", margin: (x: 0pt, y: 0pt),')
    L.append(f'  background: place(top + left, '
             f'rect(width: 34%, height: 100%, fill: rgb("{navy}"))))')
    L.append('#set text(font: ("Source Sans 3", "Segoe UI", "Arial"), '
             'size: 9.6pt, fill: rgb("#1a1a1a"))')
    L.append("#set par(justify: false, leading: 0.6em)")
    L.append(f'#let accent = rgb("{navy}")')
    L.append("#let sec(t) = {")
    L.append("  v(8pt)")
    L.append("  text(size: 11pt, weight: 700, fill: accent)[#upper(t)]")
    L.append("  v(2pt)")
    L.append("  line(length: 100%, stroke: 1pt + accent)")
    L.append("  v(4pt)")
    L.append("}")
    L.append("#let ssec(t) = {")
    L.append("  v(10pt)")
    L.append("  text(size: 10pt, weight: 700, fill: white, tracking: 1pt)[#upper(t)]")
    L.append("  v(2pt)")
    L.append('  line(length: 100%, stroke: 0.7pt + rgb("#7f9bc0"))')
    L.append("  v(4pt)")
    L.append("}")
    L.append("")
    L.append("#grid(columns: (34%, 66%), column-gutter: 0pt,")
    # ---- sidebar cell ----
    L.append("  pad(x: 15pt, top: 20pt, bottom: 16pt)[")
    L.append("    #set text(fill: white, size: 9.2pt)")
    L.append(f'    #text(size: 19pt, weight: 800, fill: white)[{te(b["name"])}]')
    if b.get("title"):
        L.append("    #linebreak()")
        L.append("    #v(2pt)")
        L.append(f'    #text(size: 10.5pt, fill: rgb("#c9d8ec"))[{te(b["title"])}]')
    L.append('    #ssec("Contact")')
    L.append(f'    #text(size: 8.8pt)[{" \\\\ ".join(_typ_contacts_plain(b))}]')
    if m.get("skills"):
        L.append('    #ssec("Skills")')
        for s in m["skills"]:
            L.append(f'    #block(below: 6pt)[#text(weight: 700, '
                     f'fill: rgb("#dbe6f4"))[{te(s["category"])}] \\\\ '
                     f'#text(size: 8.6pt, fill: rgb("#eaf0f8"))'
                     f'[{te(", ".join(s["items"]))}]]')
    if m.get("certifications"):
        L.append('    #ssec("Certifications")')
        L.append(f'    #text(size: 8.6pt, fill: rgb("#eaf0f8"))'
                 f'[{" \\\\ ".join(te(c) for c in m["certifications"])}]')
    if m.get("awards"):
        L.append('    #ssec("Awards")')
        for a in m["awards"]:
            L.append(f'    #block(below: 5pt)[#text(weight: 700, '
                     f'fill: rgb("#dbe6f4"), size: 8.8pt)[{te(a["title"])}]]')
    L.append("  ],")
    # ---- main cell ----
    L.append("  pad(x: 18pt, top: 20pt, bottom: 16pt)[")
    if b.get("summary"):
        L.append('    #sec("Summary")')
        L.append(f'    {te(b["summary"])}')
    if m.get("experience"):
        L.append('    #sec("Work Experience")')
        _typ_exp_grid(L, m, SUBHEAD)
    if m.get("education"):
        L.append('    #sec("Education")')
        for e in m["education"]:
            head = f'*{te(e["institution"])}*'
            if e.get("degree"):
                head += f' / {te(e["degree"])}'
            L.append(f"    {head} #h(1fr) "
                     f'#text(fill: rgb("{MUTED}"), size: 9pt)[{date_range(e)}]')
            L.append("    #linebreak()")
    L.append("  ]")
    L.append(")")
    return "\n".join(L) + "\n"


TYPST_VARIANTS = [
    ("modern_blue", build_typst),      # the original single-column, for context
    ("serif_centered", build_typst_serif),
    ("sidebar_navy", build_typst_sidebar),
    ("bold_band", build_typst_band),
]


def render_typst_variants(m: dict) -> list:
    import typst
    gdir = OUT / "gallery_typst"
    gdir.mkdir(exist_ok=True)
    font_paths = []
    try:
        import rendercv_fonts
        font_paths = [str(Path(rendercv_fonts.__file__).resolve().parent)]
    except Exception:
        pass
    made = []
    for tag, fn in TYPST_VARIANTS:
        try:
            src = gdir / f"typst_{tag}.typ"
            src.write_text(fn(m), encoding="utf-8")
            pdf = gdir / f"typst_{tag}.pdf"
            typst.compile(str(src), output=str(pdf), font_paths=font_paths)
            made.append((tag, pdf))
            print(f"[ok] typst:{tag}")
        except Exception as exc:
            print(f"[FAIL] typst:{tag}: {str(exc)[:300]}")
    _contact_sheet(made, gdir / "CONTACT_SHEET_TYPST.png")
    return made


# --------------------------------------------------------------------------- #
# 3. Playwright / HTML
# --------------------------------------------------------------------------- #
def render_html(m: dict) -> Path:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from playwright.sync_api import sync_playwright

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["mon"] = mon
    env.filters["striphttp"] = strip_http
    html = env.get_template("resume.html.j2").render(
        b=m["basics"],
        experience=m.get("experience", []),
        skills=m.get("skills", []),
        certifications=m.get("certifications", []),
        awards=m.get("awards", []),
        education=m.get("education", []),
    )
    src = OUT / "_html_input.html"
    src.write_text(html, encoding="utf-8")
    pdf = OUT / "3_html.pdf"

    with sync_playwright() as p:
        browser = None
        for launch in (lambda: p.chromium.launch(channel="msedge", headless=True),
                       lambda: p.chromium.launch(headless=True)):
            try:
                browser = launch()
                break
            except Exception:
                browser = None
        if browser is None:
            raise RuntimeError("no Chromium/Edge available for PDF printing")
        page = browser.new_page()
        page.goto(src.as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf), format="A4", print_background=True,
                 margin={"top": "1.3cm", "bottom": "1.3cm",
                         "left": "1.5cm", "right": "1.5cm"})
        browser.close()
    if not pdf.exists():
        raise RuntimeError("playwright produced no PDF")
    return pdf


# --------------------------------------------------------------------------- #
# 3b. HTML/CSS THEME gallery (~10 skins over 2 structural bases)
# --------------------------------------------------------------------------- #
def _google(fam: str) -> str:
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link href="https://fonts.googleapis.com/css2?family={fam}&display=swap"'
            ' rel="stylesheet">')


# (key, base, font_links, skin_css)
HTML_THEMES = [
    ("modern_sans", "single", "", ""),
    ("elegant_serif", "single",
     _google("EB+Garamond:ital,wght@0,400;0,600;0,700;1,400"),
     """
  :root { --accent:#7b2d3a; --name-color:#7b2d3a; --h2-color:#7b2d3a;
    --body-font:"EB Garamond","Cambria",Georgia,serif;
    --head-font:"EB Garamond","Cambria",Georgia,serif;
    --hdr-border:2px solid #7b2d3a; --h2-transform:none; --h2-spacing:.4px;
    --h2-border:1px solid #d9c7cb; --fs:11pt; --lh:1.4; --name-size:24pt; }
  .name { letter-spacing:0; }
"""),
    ("tech_mono", "single", "",
     """
  :root { --accent:#0f7b3f; --name-color:#0f7b3f; --h2-color:#0f7b3f;
    --head-font:"Consolas","SFMono-Regular","Courier New",monospace;
    --name-font:"Consolas","Courier New",monospace;
    --hdr-border:2px solid #0f7b3f; --h2-spacing:1px;
    --h2-border:1px dashed #a9d5bb; --name-size:21pt; }
  h2::before { content:"# "; color:#0f7b3f; }
  .entry-title, .skill-cat { font-family:var(--head-font); }
"""),
    ("timeline", "single", "",
     """
  :root { --accent:#0d7377; --name-color:#0d7377; --h2-color:#0d7377;
    --hdr-border:2px solid #0d7377; --h2-border:1px solid #bfe3e4; }
  .entry { position:relative; padding-left:16px; border-left:2px solid #bfe3e4;
    margin-left:2px; }
  .entry::before { content:""; position:absolute; left:-6px; top:5px; width:9px;
    height:9px; border-radius:50%; background:#0d7377; }
"""),
    ("minimalist", "single", "",
     """
  :root { --accent:#111111; --name-color:#111111; --muted:#777777;
    --body-font:"Helvetica Neue",Arial,sans-serif;
    --hdr-border:1px solid #111111; --h2-spacing:2.5px; --h2-size:9pt;
    --h2-color:#111111; --h2-border:none; --name-size:22pt;
    --name-weight:600; --lh:1.45; }
  .name { letter-spacing:1px; }
  h2 { border-bottom:none; padding-bottom:0; }
  section { margin-top:16px; }
  .contact a { color:#111111; }
"""),
    ("header_band", "single", "",
     """
  :root { --accent:#c9791f; --name-color:#ffffff; --h2-color:#c9791f;
    --h2-border:2px solid #f0d9bd; }
  header { background:#22303c; border-bottom:none; padding:16px 18px;
    margin-bottom:14px; border-radius:5px; }
  .title { color:#f0c78c; }
  .contact { color:#c7d2db; }
  .contact a { color:#ffd9a8; }
  .contact .sep { color:#4a5a67; }
  .summary { color:#e8edf1; }
"""),
    ("compact", "single", "",
     """
  :root { --accent:#3b3f9c; --name-color:#3b3f9c; --h2-color:#3b3f9c;
    --hdr-border:2px solid #3b3f9c; --h2-border:1px solid #d3d4ee;
    --fs:9.6pt; --lh:1.28; --name-size:20pt; --h2-size:9.8pt; }
  section { margin-top:9px; }
  .entry { margin-bottom:7px; }
  ul { margin-top:2px; }
  li { margin:1px 0; }
  .skill-cat { flex:0 0 110px; }
"""),
    ("warm_pills", "single", "",
     """
  :root { --accent:#c0532b; --name-color:#c0532b; --h2-color:#c0532b;
    --body-font:"Trebuchet MS","Segoe UI",sans-serif;
    --hdr-border:3px solid #c0532b; --h2-transform:none; --h2-spacing:.3px;
    --h2-border:2px dotted #e8c3b2; --name-size:23pt; }
  .chip { display:inline-block; background:#f6e6de; color:#8f3d1e;
    border-radius:10px; padding:1px 8px; margin:2px 4px 2px 0;
    font-size:8.8pt; font-weight:600; }
  .chip:not(:last-child)::after { content:""; }
  .skill-row { align-items:flex-start; }
  .certs .chip { background:#eef0e6; color:#5a6b2f; }
"""),
    ("sidebar_navy", "sidebar", "", ""),
    ("sidebar_teal", "sidebar",
     _google("Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700"),
     """
  :root { --side-bg:#0e6b6f; --accent:#0e6b6f; --main-h2-color:#0e6b6f;
    --side-rule:#7cc0c2; --side-soft:#c5e8e9; }
  .main { font-family:"Source Serif 4",Georgia,"Cambria",serif; }
  .main h2 { font-family:"Source Serif 4",Georgia,serif; }
"""),
]


def _html_context(m: dict) -> dict:
    return dict(
        b=m["basics"],
        experience=m.get("experience", []),
        skills=m.get("skills", []),
        certifications=m.get("certifications", []),
        awards=m.get("awards", []),
        education=m.get("education", []),
        font_href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;500;600;700&display=swap",
        font_stack='"Raleway", "Segoe UI", Arial, sans-serif',
    )


def render_html_themes(m: dict) -> list:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from playwright.sync_api import sync_playwright

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["mon"] = mon
    env.filters["striphttp"] = strip_http
    ctx = _html_context(m)
    gdir = OUT / "gallery_html"
    gdir.mkdir(exist_ok=True)
    made = []

    with sync_playwright() as p:
        browser = None
        for launch in (lambda: p.chromium.launch(channel="msedge", headless=True),
                       lambda: p.chromium.launch(headless=True)):
            try:
                browser = launch()
                break
            except Exception:
                browser = None
        if browser is None:
            raise RuntimeError("no Chromium/Edge available for PDF printing")
        page = browser.new_page()
        for key, base, font_links, skin in HTML_THEMES:
            try:
                tpl = "base_sidebar.html.j2" if base == "sidebar" else "base_single.html.j2"
                html = env.get_template(tpl).render(
                    font_links=font_links, theme_css=skin, body_class=key, **ctx)
                src = gdir / f"_src_{key}.html"
                src.write_text(html, encoding="utf-8")
                pdf = gdir / f"html_{key}.pdf"
                page.goto(src.as_uri(), wait_until="networkidle")
                if base == "sidebar":
                    margin = {"top": "0", "bottom": "0", "left": "0", "right": "0"}
                else:
                    margin = {"top": "1.3cm", "bottom": "1.3cm",
                              "left": "1.5cm", "right": "1.5cm"}
                page.pdf(path=str(pdf), format="A4", print_background=True, margin=margin)
                made.append((key, pdf))
                print(f"[ok] html:{key}")
            except Exception as exc:
                print(f"[FAIL] html:{key}: {str(exc)[:300]}")
        browser.close()
    _contact_sheet(made, gdir / "CONTACT_SHEET_HTML.png")
    return made


# --------------------------------------------------------------------------- #
# gallery: render the SAME content through every RenderCV theme + custom engines
# --------------------------------------------------------------------------- #
RENDERCV_THEMES = ["classic", "engineeringresumes", "engineeringclassic",
                   "sb2nov", "moderncv", "ember", "harvard", "ink", "opal"]


def _render_rcv_yaml(data: dict, rel_pdf: str, tag: str) -> Path:
    src = OUT / f"_rcv_{tag}.yaml"
    src.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                   encoding="utf-8")
    exe = Path(sys.executable).with_name("rendercv.exe")
    cmd = [str(exe) if exe.exists() else "rendercv", "render", src.name,
           "--pdf-path", rel_pdf, "--output-folder", "_rcv_work",
           "--dont-generate-markdown", "--dont-generate-html",
           "--dont-generate-png"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run(cmd, cwd=OUT, capture_output=True, text=True,
                         env=env, encoding="utf-8", errors="replace")
    pdf = (OUT / rel_pdf).resolve()
    if res.returncode != 0 or not pdf.exists():
        raise RuntimeError((res.stdout + res.stderr)[-800:])
    src.unlink(missing_ok=True)
    return pdf


def _rendercv_to(m: dict, theme: str, rel_pdf: str) -> Path:
    return _render_rcv_yaml(build_rendercv(m, theme=theme), rel_pdf, theme)


def render_gallery(m: dict) -> list[tuple[str, Path]]:
    gdir = OUT / "gallery"
    gdir.mkdir(exist_ok=True)
    made: list[tuple[str, Path]] = []
    for theme in RENDERCV_THEMES:
        label = f"rendercv:{theme}"
        try:
            pdf = _rendercv_to(m, theme, f"gallery/rendercv_{theme}.pdf")
            made.append((label, pdf))
            print(f"[ok] {label}")
        except Exception as exc:
            print(f"[FAIL] {label}: {str(exc)[:200]}")
    # custom engines
    for label, fn, name in (("typst:custom", render_typst, "typst_custom.pdf"),
                            ("html:custom", render_html, "html_custom.pdf")):
        try:
            pdf = fn(m)
            dest = gdir / name
            shutil.copy(pdf, dest)
            made.append((label, dest))
            print(f"[ok] {label}")
        except Exception as exc:
            print(f"[FAIL] {label}: {str(exc)[:200]}")
    shutil.rmtree(OUT / "_rcv_work", ignore_errors=True)
    _contact_sheet(made, gdir / "CONTACT_SHEET.png")
    return made


def _contact_sheet(items: list[tuple[str, Path]], dest: Path) -> None:
    import math
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    thumbs = []
    for label, pdf in items:
        try:
            doc = fitz.open(str(pdf))
            pix = doc[0].get_pixmap(dpi=68)
            thumbs.append((label, Image.frombytes(
                "RGB", (pix.width, pix.height), pix.samples)))
            doc.close()
        except Exception:
            pass
    if not thumbs:
        return
    cols = 4
    tw = max(i.width for _, i in thumbs)
    th = max(i.height for _, i in thumbs)
    lh, pad = 30, 18
    rows = math.ceil(len(thumbs) / cols)
    W = cols * (tw + pad) + pad
    H = rows * (th + lh + pad) + pad
    sheet = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (label, img) in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + lh + pad)
        draw.text((x + 2, y + 4), label, fill=(31, 95, 168), font=font)
        sheet.paste(img, (x, y + lh))
        draw.rectangle([x, y + lh, x + img.width, y + lh + img.height],
                       outline=(210, 214, 220), width=1)
    sheet.save(str(dest))
    print(f"[ok] contact sheet -> {dest}")


# --------------------------------------------------------------------------- #
# option 3: one clean theme rendered across many RenderCV fonts
# --------------------------------------------------------------------------- #
FONT_SHOWCASE = ["Source Sans 3", "Lato", "Roboto", "Poppins", "Raleway",
                 "Open Sans", "Ubuntu", "EB Garamond", "XCharter",
                 "Libertinus Serif"]


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def render_fonts(m: dict, theme: str = "engineeringresumes") -> list:
    gdir = OUT / "gallery_fonts"
    gdir.mkdir(exist_ok=True)
    made = []
    for font in FONT_SHOWCASE:
        try:
            data = build_rendercv(m, theme=theme)
            data["design"]["typography"] = {
                "font_family": {k: font for k in
                                ("body", "name", "headline",
                                 "connections", "section_titles")}}
            pdf = _render_rcv_yaml(data, f"gallery_fonts/font_{_slug(font)}.pdf",
                                   f"font_{_slug(font)}")
            made.append((font, pdf))
            print(f"[ok] font:{font}")
        except Exception as exc:
            print(f"[FAIL] font:{font}: {str(exc)[:200]}")
    shutil.rmtree(OUT / "_rcv_work", ignore_errors=True)
    _contact_sheet(made, gdir / "CONTACT_SHEET_FONTS.png")
    return made


# --------------------------------------------------------------------------- #
# the CHOSEN design: engineeringclassic + Raleway + opal colours + narrow
# margins + harvard entry layout (designs/hybrid.yaml). Iterate here.
# --------------------------------------------------------------------------- #
def render_pick(m: dict) -> Path:
    pdir = OUT / "pick"
    pdir.mkdir(exist_ok=True)
    data = build_rendercv(m, theme="engineeringclassic")
    design = yaml.safe_load(
        (DESIGNS / "hybrid.yaml").read_text(encoding="utf-8"))["design"]
    data["design"] = design
    cv = data["cv"]
    cv.pop("location", None)                       # no location in the header contact line
    cv.get("sections", {}).pop("Summary", None)    # no summary section; start at Experience
    pdf = _render_rcv_yaml(data, "pick/hybrid.pdf", "hybrid")
    shutil.rmtree(OUT / "_rcv_work", ignore_errors=True)
    try:
        import fitz
        doc = fitz.open(str(pdf))
        for i, pg in enumerate(doc):
            pg.get_pixmap(dpi=120).save(str(pdir / f"hybrid_p{i + 1}.png"))
        doc.close()
    except Exception as exc:
        print(f"[warn] preview failed: {exc}")
    return pdf


# --------------------------------------------------------------------------- #
# the CHOSEN design, ported to the HTML/CSS engine so we can do the two things
# stock RenderCV cannot: (5) a split header (name+headline LEFT, contacts
# stacked RIGHT, like the attachment) and (8) a bigger per-entry title font.
# Same content (master.yaml), same teal palette + Raleway.
# --------------------------------------------------------------------------- #
def render_pick_html(m: dict, dest: Path | None = None, previews: bool = True,
                     compact: bool = False) -> Path:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from playwright.sync_api import sync_playwright

    pdir = OUT / "pick"
    pdir.mkdir(exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["mon"] = mon
    env.filters["striphttp"] = strip_http
    html = env.get_template("pick.html.j2").render(compact=compact, **_html_context(m))
    pdf = dest or (pdir / "hybrid_html.pdf")
    src = pdir / f"_{pdf.stem}_input.html"
    src.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = None
        for launch in (lambda: p.chromium.launch(channel="msedge", headless=True),
                       lambda: p.chromium.launch(headless=True)):
            try:
                browser = launch()
                break
            except Exception:
                browser = None
        if browser is None:
            raise RuntimeError("no Chromium/Edge available for PDF printing")
        page = browser.new_page()
        page.goto(src.as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf), format="A4", print_background=True,
                 margin={"top": "1cm", "bottom": "1cm",
                         "left": "1cm", "right": "1cm"})  # ~0.4in narrow margins
        browser.close()
    if not pdf.exists():
        raise RuntimeError("playwright produced no PDF")
    if previews:
        try:
            import fitz
            doc = fitz.open(str(pdf))
            for i, pg in enumerate(doc):
                pg.get_pixmap(dpi=120).save(str(pdir / f"{pdf.stem}_p{i + 1}.png"))
            doc.close()
        except Exception as exc:
            print(f"[warn] preview failed: {exc}")
    return pdf


# --------------------------------------------------------------------------- #
# the PICK design (pick.html.j2) rendered across 20 distinct fonts so the user
# can shortlist a typeface. Each font -> its own PDF + a labeled contact sheet.
# Weights are curated PER FONT so the Google Fonts css2 request never 400-errors
# (the design only uses weights 400 / 600 / 700; fonts lacking 600 just map the
# name+section-titles to their nearest heavier weight).
# --------------------------------------------------------------------------- #
PICK_FONTS = [
    # (display name, generic fallback kind, weights to request)
    ("Raleway",        "sans",  "400;600;700"),
    ("Inter",          "sans",  "400;600;700"),
    ("Roboto",         "sans",  "400;500;700"),
    ("Lato",           "sans",  "400;700"),
    ("Open Sans",      "sans",  "400;600;700"),
    ("Montserrat",     "sans",  "400;600;700"),
    ("Source Sans 3",  "sans",  "400;600;700"),
    ("Work Sans",      "sans",  "400;600;700"),
    ("Poppins",        "sans",  "400;600;700"),
    ("IBM Plex Sans",  "sans",  "400;600;700"),
    ("Nunito Sans",    "sans",  "400;600;700"),
    ("DM Sans",        "sans",  "400;500;700"),
    ("Rubik",          "sans",  "400;500;700"),
    ("Karla",          "sans",  "400;700"),
    ("Merriweather",   "serif", "400;700"),
    ("Lora",           "serif", "400;600;700"),
    ("PT Serif",       "serif", "400;700"),
    ("Source Serif 4", "serif", "400;600;700"),
    ("EB Garamond",    "serif", "400;600;700"),
    ("Bitter",         "serif", "400;600;700"),
]

_PICK_FALLBACK = {
    "sans":  '"Segoe UI", Arial, sans-serif',
    "serif": 'Georgia, "Times New Roman", serif',
}


def render_pick_fonts(m: dict) -> list:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from playwright.sync_api import sync_playwright

    fdir = OUT / "pick" / "fonts"
    fdir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["mon"] = mon
    env.filters["striphttp"] = strip_http
    tmpl = env.get_template("pick.html.j2")
    base = _html_context(m)

    made = []
    with sync_playwright() as p:
        browser = None
        for launch in (lambda: p.chromium.launch(channel="msedge", headless=True),
                       lambda: p.chromium.launch(headless=True)):
            try:
                browser = launch(); break
            except Exception:
                browser = None
        if browser is None:
            raise RuntimeError("no Chromium/Edge available for PDF printing")
        page = browser.new_page()
        for i, (name, kind, weights) in enumerate(PICK_FONTS, 1):
            slug = _slug(name)
            fam = name.replace(" ", "+")
            href = (f"https://fonts.googleapis.com/css2?family={fam}"
                    f":wght@{weights}&display=swap")
            stack = f'"{name}", {_PICK_FALLBACK[kind]}'
            html = tmpl.render(**dict(base, font_href=href, font_stack=stack))
            src = fdir / f"_src_{i:02d}_{slug}.html"
            src.write_text(html, encoding="utf-8")
            pdf = fdir / f"{i:02d}_{slug}.pdf"
            try:
                page.goto(src.as_uri(), wait_until="networkidle")
                page.pdf(path=str(pdf), format="A4", print_background=True,
                         margin={"top": "1cm", "bottom": "1cm",
                                 "left": "1cm", "right": "1cm"})
                made.append((f"{i:02d}  {name}", pdf))
                print(f"[ok] font {i:02d}: {name}")
            except Exception as exc:
                print(f"[FAIL] font {i:02d} {name}: {str(exc)[:160]}")
        browser.close()

    for f in fdir.glob("_src_*.html"):
        f.unlink(missing_ok=True)
    _contact_sheet(made, fdir / "CONTACT_SHEET_PICK_FONTS.png")
    return made


# --------------------------------------------------------------------------- #
# publish: bake the FINAL (pick / HTML) resume straight into the app's resumes/
# folder so the automaton submits it. The chosen filename should match an entry
# in configs/config.yaml -> resume.mapping / resume.default. Any existing file
# of the same name is copied to resumes/<stem>.backup-<stamp>.pdf first (that
# still matches the resumes/*.pdf git-ignore rule), so nothing is ever lost.
# --------------------------------------------------------------------------- #
def _place_in_resumes(src_pdf: Path, name: str) -> Path:
    """Copy a rendered PDF into resumes/<name>, backing up any existing file to
    resumes/<stem>.backup-<stamp>.pdf first (still matches the resumes/*.pdf
    git-ignore rule), so nothing is ever lost."""
    from datetime import datetime

    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    dest_dir = HERE.parent / "resumes"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / name
    if dest.exists() and dest.resolve() != src_pdf.resolve():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = dest_dir / f"{dest.stem}.backup-{stamp}{dest.suffix}"
        shutil.copy2(dest, backup)
        print(f"[backup] existing {name} -> {backup.name}")
    shutil.copy2(src_pdf, dest)
    return dest


def render_publish(m: dict, name: str | None = None) -> Path:
    pdf = render_pick_html(m)                       # out/pick/hybrid_html.pdf (1 page)
    if not name:
        who = str(m.get("basics", {}).get("name", "resume")).strip() or "resume"
        name = who.replace(" ", "_") + "_Resume.pdf"
    return _place_in_resumes(pdf, name)


# --------------------------------------------------------------------------- #
# variants: the SAME master content, projected per target. A `variants:` list
# in master.yaml may override the headline `title`, reorder `skills` (by
# category name via `skills_order`), toggle the Awards section
# (`include_awards`), and produce a recency-weighted one-pager that keeps the
# current role in full while collapsing older roles to their short `summary`
# (`condense_older`). Content is never invented - only emphasized/reordered/hidden.
# --------------------------------------------------------------------------- #
def _apply_variant(m: dict, v: dict) -> dict:
    import copy

    mv = copy.deepcopy(m)
    if v.get("title"):
        mv.setdefault("basics", {})["title"] = v["title"]
    order = v.get("skills_order")
    if order:
        rank = {name: i for i, name in enumerate(order)}
        mv["skills"] = sorted(
            mv.get("skills", []),
            key=lambda s: rank.get(s.get("category"), len(order)),
        )
    # --- page-length controls (opt-in; role variants leave these unset) ---
    if v.get("include_awards") is False:          # drop the Awards section
        mv["awards"] = []
    if v.get("condense_older"):                   # recency-weighted 1-pager:
        # keep the most-recent role in full; collapse older roles to their
        # short `summary` bullets (no-op for a role without a summary).
        for e in (mv.get("experience") or [])[1:]:
            summ = e.get("summary")
            if summ:
                e["highlights"] = list(summ)
                e.pop("groups", None)
    return mv


def render_publish_variants(m: dict) -> list:
    variants = m.get("variants") or []
    made = []
    for v in variants:
        stem = _slug(str(v.get("key") or v.get("filename") or "variant"))
        mv = _apply_variant(m, v)
        tmp = OUT / "pick" / f"_variant_{stem}.pdf"
        render_pick_html(mv, dest=tmp, previews=False, compact=bool(v.get("compact")))
        name = v.get("filename") or f"{stem}.pdf"
        dest = _place_in_resumes(tmp, name)
        tmp.unlink(missing_ok=True)
        (OUT / "pick" / f"_{tmp.stem}_input.html").unlink(missing_ok=True)
        title = mv.get("basics", {}).get("title", "")
        print(f"[ok] {v.get('key', stem):18s} -> {dest.name}   ({title})")
        made.append((name, dest))
    return made


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
RENDERERS = {
    "rendercv": render_rendercv,
    "typst": render_typst,
    "html": render_html,
}


def pages(pdf: Path) -> str:
    try:
        from pypdf import PdfReader
        return str(len(PdfReader(str(pdf)).pages))
    except Exception:
        return "?"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    master = load_master()
    args = sys.argv[1:]
    if args and args[0] == "gallery":
        made = render_gallery(master)
        print(f"\nGallery: {len(made)} resumes in {OUT / 'gallery'}")
        print(f"Scan them all at once: {OUT / 'gallery' / 'CONTACT_SHEET.png'}")
        return 0
    if args and args[0] == "fonts":
        made = render_fonts(master)
        print(f"\nFont gallery: {len(made)} in {OUT / 'gallery_fonts'}")
        print(f"Contact sheet: {OUT / 'gallery_fonts' / 'CONTACT_SHEET_FONTS.png'}")
        return 0
    if args and args[0] == "typst-variants":
        made = render_typst_variants(master)
        print(f"\nTypst variants: {len(made)} in {OUT / 'gallery_typst'}")
        print(f"Contact sheet: {OUT / 'gallery_typst' / 'CONTACT_SHEET_TYPST.png'}")
        return 0
    if args and args[0] == "html-themes":
        made = render_html_themes(master)
        print(f"\nHTML themes: {len(made)} in {OUT / 'gallery_html'}")
        print(f"Contact sheet: {OUT / 'gallery_html' / 'CONTACT_SHEET_HTML.png'}")
        return 0
    if args and args[0] == "pick-fonts":
        made = render_pick_fonts(master)
        print(f"\nPick-design font gallery: {len(made)}/20 PDFs in {OUT / 'pick' / 'fonts'}")
        print(f"Compare them all at once: {OUT / 'pick' / 'fonts' / 'CONTACT_SHEET_PICK_FONTS.png'}")
        return 0
    if args and args[0] == "publish-variants":
        made = render_publish_variants(master)
        if not made:
            print("No `variants:` defined in master.yaml — nothing to publish.")
        else:
            print(f"\nPublished {len(made)} role-tailored resume(s) into "
                  f"{HERE.parent / 'resumes'}")
            print("Point configs/config.yaml -> resume.mapping at these filenames.")
        return 0
    if args and args[0] == "publish":
        name = args[1] if len(args) > 1 else None
        dest = render_publish(master, name)
        kb = dest.stat().st_size / 1024
        print(f"\nPublished resume -> {dest}  ({kb:.0f} KB, {pages(dest)} page/s)")
        print("The automaton submits this via configs/config.yaml -> "
              "resume.mapping / resume.default (match the filename there).")
        return 0
    if args and args[0] == "pick":
        pdf = render_pick(master)
        kb = pdf.stat().st_size / 1024
        print(f"\nHybrid resume (RenderCV) -> {pdf}  ({kb:.0f} KB, {pages(pdf)} page/s)")
        print(f"Preview PNGs:  {OUT / 'pick'}\\hybrid_p*.png")
        try:
            hpdf = render_pick_html(master)
            hkb = hpdf.stat().st_size / 1024
            print(f"Hybrid resume (HTML)     -> {hpdf}  ({hkb:.0f} KB, {pages(hpdf)} page/s)")
            print(f"Preview PNGs:  {OUT / 'pick'}\\hybrid_html_p*.png")
        except Exception as exc:
            print(f"[FAIL] html pick: {exc}")
        return 0
    which = args or list(RENDERERS)
    results = []
    for name in which:
        fn = RENDERERS.get(name)
        if not fn:
            print(f"[skip] unknown renderer '{name}'")
            continue
        print(f"[..] rendering {name} ...")
        try:
            pdf = fn(master)
            kb = pdf.stat().st_size / 1024
            print(f"[ok] {name:9s} -> {pdf.name}  ({kb:.0f} KB, {pages(pdf)} page/s)")
            results.append((name, True))
        except Exception as exc:  # keep going; report per-renderer
            print(f"[FAIL] {name}: {exc}")
            results.append((name, False))
    ok = sum(1 for _, s in results if s)
    print(f"\nDone: {ok}/{len(results)} renderers succeeded. Output in {OUT}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
