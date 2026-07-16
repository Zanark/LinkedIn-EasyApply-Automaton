# Resume Studio

One master file of your career content → a polished, pixel-tuned resume PDF that
the automaton submits. Content lives in **one** place (`master.yaml`); the design
lives in templates. Change a bullet once and re-render — you never keep several
Word/PDF copies in sync by hand.

```powershell
# from the repo root, with the venv Python
.\.venv\Scripts\python.exe resume_studio\render.py pick        # build the resume (design)
.\.venv\Scripts\python.exe resume_studio\render.py pick-fonts  # preview it across 20 fonts
.\.venv\Scripts\python.exe resume_studio\render.py publish     # copy the final PDF into resumes/
```

> 🧠 The learning-oriented deep dive (why it's built this way, the engine
> trade-offs, the typography tricks) lives in
> **[../docs/resume-studio.md](../docs/resume-studio.md)**.

---

## Why this exists

- **Single source of truth.** Your experience, skills, awards and links live once
  in `master.yaml`. Keep the *full superset* here (add back everything you trimmed
  to fit a page); a render can select a subset.
- **Content ⟂ presentation.** The same content flows through a template to become
  a PDF. Restyle without retyping; retype without restyling.
- **It was a bake-off.** Three engines were trialled (RenderCV → Typst, a
  hand-written Typst template, and an HTML/CSS design printed by a headless
  browser). The **HTML/CSS design — called `pick` — won** because only it allowed
  per-element font sizing, an exact split header, and a phone number printed
  verbatim. The other engines remain wired up for comparison but are legacy.

---

## Requirements

Everything needed is already in the project venv (`pip install -e .`):

- **Playwright** with **Microsoft Edge** (preferred) or bundled Chromium — prints
  the HTML design to PDF. `python -m playwright install chromium` if you have no
  Edge/Chrome.
- **Jinja2** — HTML templating. **PyYAML** — reads `master.yaml`.
- **PyMuPDF** (`fitz`) — preview PNGs + contact sheets. **Pillow** — montages.
- **RenderCV** (optional) — only for the legacy `rendercv` / `pick` (RenderCV half)
  and gallery commands. Needs a network connection the first time (fonts).

An internet connection is needed on first render so **Google Fonts** and **Font
Awesome** load from their CDNs.

---

## The master file — `master.yaml`

The one place your content lives. **It contains personal data, so it is
git-ignored.** Shape (values elided):

```yaml
basics:
  name:  "…"
  title: "…"                 # headline under your name
  summary: "…"               # not shown on the pick design; kept for other engines
  email: "…"
  phone: "+91 …"             # printed verbatim on the header (see typography notes)
  location: "…"
  links:
    - { network: LinkedIn, label: LinkedIn, username: "…", url: "https://…" }
    - { network: GitHub,   label: GitHub,   username: "…", url: "https://…" }

experience:
  - company: "…"
    role: "…"
    start: 2024-07           # ISO YYYY-MM so machines can sort; templates print "Jul 2024"
    end: present             # "present" for ongoing roles
    highlights: [ "…", "…" ] # a flat bullet list …
  - company: "…"
    groups:                  # … OR bold sub-headings, each with its own bullets
      - { name: "…", bullets: [ "…" ] }

skills:   [ … ]
awards:   [ … ]
education:[ … ]
```

Dates are ISO (`YYYY-MM`); use `present` for current roles. Edit content here,
then re-render.

---

## The finalized design — `pick`

`templates/pick.html.j2`, rendered to PDF by a headless browser. Design choices
that are locked in:

| Aspect        | Choice                                                            |
| ------------- | ----------------------------------------------------------------- |
| Font          | **Raleway** (default), weights 400/600/700 — swap via `pick-fonts` |
| Accent colour | Seafoam teal `#2aa198` (Solarized-ish)                            |
| Page          | Single **A4** page, ~**1 cm** margins                             |
| Header        | Split — name + headline **left**, contacts in a **2×2 grid** right, with Font Awesome icons and short clickable `LinkedIn` / `GitHub` labels |
| Numerals      | Lining + **tabular** figures, so the phone reads exactly `+91 …`  |
| Body          | **Ragged-right** (left-aligned) bullets — no justified text jammed to the margin |
| Titles        | Per-entry job titles set a step larger than body (HTML-only trick) |

The font is fully parameterised: `_html_context()` in `render.py` supplies
`font_href` (the Google Fonts URL) and `font_stack` (the CSS `font-family`).
Change those two lines to make any font the permanent default.

---

## Commands

Invoke as `.\.venv\Scripts\python.exe resume_studio\render.py <command>`.

### The blessed workflow

| Command      | What it does                                                                                 | Output |
| ------------ | -------------------------------------------------------------------------------------------- | ------ |
| `pick`       | Build the resume. Renders the HTML design → `hybrid_html.pdf` **and** the RenderCV twin → `hybrid.pdf`, plus preview PNGs. | `out/pick/` |
| `pick-fonts` | Render the design across **20 distinct fonts** and stitch a labelled contact sheet to shortlist a typeface. | `out/pick/fonts/` |
| `publish`    | Render the design and **copy the PDF into `resumes/`** so the automaton submits it. Optional filename arg; any existing file of that name is backed up first. | `resumes/` |
| `publish-variants` | Render **one PDF per variant** from the `variants:` block in `master.yaml` (role emphasis and/or page-length cut) and copy each into `resumes/`. | `resumes/` |

```powershell
.\.venv\Scripts\python.exe resume_studio\render.py publish                       # -> resumes/<Your_Name>_Resume.pdf
.\.venv\Scripts\python.exe resume_studio\render.py publish "Backend_Resume.pdf"  # custom filename
```

### Legacy / exploration (the original bake-off)

| Command          | What it does                                                          | Output |
| ---------------- | -------------------------------------------------------------------- | ------ |
| *(no argument)*  | Build all three base engines side by side.                           | `out/1_rendercv.pdf`, `2_typst.pdf`, `3_html.pdf` |
| `rendercv`       | RenderCV → Typst engine, one PDF.                                    | `out/` |
| `typst`          | Hand-written Typst template.                                         | `out/` |
| `html`           | Original HTML/CSS design.                                            | `out/` |
| `gallery`        | Many RenderCV themes + a contact sheet.                              | `out/gallery/` |
| `fonts`          | RenderCV across several fonts + a contact sheet.                     | `out/gallery_fonts/` |
| `typst-variants` | Several hand-written Typst layouts + a contact sheet.               | `out/gallery_typst/` |
| `html-themes`    | Several HTML themes + a contact sheet.                              | `out/gallery_html/` |

---

## Choosing a different font

```powershell
.\.venv\Scripts\python.exe resume_studio\render.py pick-fonts
# open out/pick/fonts/CONTACT_SHEET_PICK_FONTS.png and compare
```

Found one you prefer? Make it permanent by editing the two default lines in
`render.py → _html_context()`:

```python
font_href="https://fonts.googleapis.com/css2?family=<Font+Name>:wght@400;600;700&display=swap",
font_stack='"<Font Name>", "Segoe UI", Arial, sans-serif',
```

> ⚠️ Google Fonts `css2` returns **400** for the *whole* request if you ask for a
> weight the font lacks — and the font then silently falls back. The design uses
> 400/600/700; the `PICK_FONTS` table curates per-font weights so every one of the
> 20 renders. If you add a font, request only weights it actually ships.

---

## Publishing into the automaton

`publish` bridges the studio and the app:

```
resume_studio/out/pick/hybrid_html.pdf  ──publish──▶  resumes/<Name>_Resume.pdf
```

The automaton picks a resume from `configs/config.yaml`:

```yaml
resume:
  directory: resumes
  default: Debashish_Mishra_Resume.pdf
  mapping:
    software engineer: Debashish_Mishra_Resume.pdf
    full stack developer: Debashish_Mishra_Resume.pdf
```

So the published filename must match an entry there. Verify end-to-end with:

```powershell
.\.venv\Scripts\python.exe apply.py resume-test "software engineer"
# -> Debashish_Mishra_Resume.pdf -> resumes\Debashish_Mishra_Resume.pdf
```

Publishing over an existing file first copies it to
`resumes/<stem>.backup-<timestamp>.pdf` (which still matches the `resumes/*.pdf`
git-ignore rule), so your previous resume is never lost.

---

## Variants — role & page length

Want a resume tuned per role, or a one- vs two-page cut? Add a `variants:` block
to `master.yaml`. Every variant is the **same** content, only re-emphasized or
filtered — nothing is invented, and the master is never mutated:

```yaml
variants:
  # role emphasis: same content, headline + skills order tuned per search
  - key: software-engineer
    filename: Debashish_Mishra_SoftwareEngineer.pdf
    title: "Software Engineer · Backend, Cloud & AI"
    skills_order: [".NET & Backend", "Cloud & DevOps", "Data & AI", "Frontend"]
  - key: full-stack
    filename: Debashish_Mishra_FullStack.pdf
    title: "Full Stack Engineer · .NET, React & Azure"
    skills_order: ["Frontend", ".NET & Backend", "Cloud & DevOps", "Data & AI"]

  # page-length cuts: a recency-weighted 1-pager and the full 2-pager
  - key: onepage
    filename: Debashish_Mishra_1page.pdf
    condense_older: true        # current role in full; older roles -> their `summary`
    include_awards: false       # drop the Awards section
    compact: true               # same fonts/sizes, tighter line spacing
  - key: twopage
    filename: Debashish_Mishra_2page.pdf
    include_awards: true        # full detail + awards (the default look)
```

| Field            | Effect                                                                       |
| ---------------- | ---------------------------------------------------------------------------- |
| `filename`       | The PDF written into `resumes/` — point `config.yaml → resume.mapping` at it  |
| `title`          | Overrides the headline under your name                                       |
| `skills_order`   | Reorders the skills **categories** (any not listed sink to the end)          |
| `include_awards` | `false` hides the Awards section                                             |
| `condense_older` | `true` keeps the most-recent role in full and collapses older roles to their short `summary:` list |
| `compact`        | `true` keeps every font size but tightens the vertical rhythm so a dense cut still fits one page |

`condense_older` needs each older experience entry to carry a `summary:` list
(2–3 quantified lines) alongside its full `groups:` — the 2-pager renders the
groups, the 1-pager swaps in the summary. Role emphasis and page cuts compose
freely (a variant can set `skills_order` *and* `condense_older`).

```powershell
.\.venv\Scripts\python.exe resume_studio\render.py publish-variants
```

Then map each search to its variant:

```yaml
resume:
  default: Debashish_Mishra_1page.pdf           # generic 1-page, for anything unmapped
  mapping:
    software engineer: Debashish_Mishra_SoftwareEngineer.pdf     # 1-page, role-tailored
    full stack developer: Debashish_Mishra_FullStack.pdf         # 1-page, role-tailored
# Debashish_Mishra_2page.pdf stays in resumes/ as a manual full-detail backup (unmapped).
```

---

## Output layout

```
resume_studio/
  master.yaml            your content (PII, git-ignored)
  render.py              the renderer + CLI
  templates/
    pick.html.j2         THE finalized design
    resume.html.j2, base_*.html.j2   legacy HTML templates
  designs/
    hybrid.yaml          RenderCV design used by the pick twin
  out/                   ALL generated PDFs/PNGs (git-ignored)
    pick/                hybrid_html.pdf (main) + hybrid.pdf + preview PNGs
    pick/fonts/          20 font PDFs + CONTACT_SHEET_PICK_FONTS.png
    gallery*/            legacy contact sheets
```

## What is committed vs. local

Committed (safe, no personal data): `render.py`, `templates/`, `designs/`, this
README. **Never committed** (personal data): `master.yaml` and everything under
`out/`. Both are covered by `.gitignore`. Your published resume in `resumes/` is
git-ignored too.
