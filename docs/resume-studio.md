# Resume Studio — a learning guide

> Written for an SDE growing toward architect. The studio (`resume_studio/`) is a
> small system, but it packs several patterns you'll meet again at scale:
> content/presentation separation, a renderer bake-off, templating, and
> **headless-browser PDF generation**. Every claim points at real code
> (`resume_studio/render.py`, `templates/pick.html.j2`). The task-focused usage
> doc is **[../resume_studio/README.md](../resume_studio/README.md)**.

## Contents

1. [The problem: one you, many formats](#1-the-problem)
2. [Single source of truth (the content model)](#2-single-source-of-truth)
3. [The engine bake-off — and why HTML/CSS won](#3-the-engine-bake-off)
4. [The rendering pipeline](#4-the-rendering-pipeline)
5. [Templating with Jinja2 (and the autoescape trap)](#5-templating-with-jinja2)
6. [Typography as engineering](#6-typography-as-engineering)
7. [Publishing: bridging studio and app](#7-publishing)
8. [Where industry uses these ideas](#8-where-industry-uses-these-ideas)

---

## 1. The problem

You have **one** career history but need it in several shapes: a one-page PDF, a
two-page superset, maybe a variant tuned per role. The naïve approach — keep a
Word doc, a PDF, and a LaTeX file and edit each — guarantees they drift out of
sync. The moment three copies exist, at least one is wrong.

The fix is the same one you'd reach for in a service: **model the data once, and
derive every representation from it.** Content is data; a résumé PDF is a *view*.

---

## 2. Single source of truth

`master.yaml` holds the content — and nothing about looks:

```yaml
basics: { name: …, title: …, email: …, phone: …, links: [ … ] }
experience:
  - { company: …, role: …, start: 2024-07, end: present, highlights: [ … ] }
skills: [ … ]
awards: [ … ]
```

Two deliberate decisions worth stealing:

- **Machine-friendly dates.** `start`/`end` are ISO `YYYY-MM`; the template formats
  them for humans (`mon()` in `render.py` → `"Jul 2024"`). Store canonical, render
  localized — the same rule you apply to timestamps in a database.
- **Keep the superset.** The file holds *everything*; a given render can trim. You
  never delete content to fit a page — you filter a view. This is
  **projection**: the store is complete, each view is a subset.

**Role variants make projection concrete.** An optional `variants:` block lets one
master produce several role-tuned PDFs — the same facts, re-emphasized (a
different headline, skills reordered so the role's keywords lead). `_apply_variant`
does this on a **deep copy** (the master is never mutated), and the template — a
plain ordered `{% for s in skills %}` loop — renders whatever order it's handed.
That's the "single source, many views" rule again: you don't fork the résumé per
role, you *derive* each view. `publish-variants` writes one PDF per variant so the
automaton's `resume.mapping` can send a tailored file to each search.

`load_master()` is the whole "repository" here — one function, one YAML read. The
rest of the system depends on the *shape* of that dict, not on any file format.

---

## 3. The engine bake-off

Rather than guess, the studio renders the **same** `master.yaml` through three
independent engines and lets you compare printed PDFs:

| Engine | How | Strength | Why it lost |
| ------ | --- | -------- | ----------- |
| **RenderCV** (`render_rendercv`, `render_pick`) | YAML → RenderCV → Typst | Batteries-included ATS themes | Only whole-document knobs — you can't size *one* element, and it reformats the phone number |
| **Typst** (`render_typst` + variants) | hand-written `.typ` | Precise, fast, no browser | Another niche language to maintain for one document |
| **HTML/CSS** (`render_html`, `render_pick_html`) | Jinja2 → HTML → headless-browser print | The entire web layout engine + fonts you already know | **won** |

The HTML/CSS design — **`pick`** — won on concrete requirements the others
couldn't meet:

- **Per-element control.** RenderCV exposes font sizes only for
  body/name/headline/connections/section-titles. The design needed a job *title*
  a step larger than body text — trivial in CSS (`--fs-title`), impossible in
  stock RenderCV.
- **Exact strings.** RenderCV pipes the phone through the `phonenumbers` library,
  whose formats (`national`/`international`/`e164`/`rfc3966`) all mangle
  `+91 9873824499`. HTML prints the raw string.
- **Familiar tooling.** Flexbox, CSS grid, web fonts — no new DSL.

**Architect's lesson:** a bake-off turns an aesthetic argument ("which looks
better?") into an engineering one ("which can satisfy these constraints?"). Build
the cheap comparison harness; let evidence pick the winner. Keep the losers wired
up (they still build) so the comparison stays reproducible.

---

## 4. The rendering pipeline

`render_pick_html()` is the reference path:

```
master.yaml ─load_master─▶ dict ─_html_context─▶ template vars
          ─Jinja2 render─▶ HTML string ─write─▶ _hybrid_html_input.html
          ─Playwright(Edge→Chromium) goto(file://) ─▶ page.pdf(A4, 1cm) ─▶ hybrid_html.pdf
          ─PyMuPDF─▶ preview PNGs
```

Details that matter:

- **Browser selection with graceful fallback.** It tries
  `channel="msedge"` first, then plain Chromium — the same *try-preferred,
  fall-back-to-portable* pattern you'd use for any optional native dependency:

  ```python
  for launch in (lambda: p.chromium.launch(channel="msedge", headless=True),
                 lambda: p.chromium.launch(headless=True)):
  ```

- **`wait_until="networkidle"`.** The page pulls Google Fonts + Font Awesome from
  CDNs. Printing before they load would fall back to system fonts. Waiting for the
  network to settle is an explicit **readiness gate** — the same reason you wait
  for health checks before routing traffic.
- **Print-to-PDF, not screenshot.** `page.pdf(format="A4", print_background=True,
  margin=1cm)` uses the browser's *print* engine — vector text, real page boxes,
  selectable/ATS-readable output. A screenshot would be a fuzzy raster.
- **One browser, many renders.** `render_pick_fonts()` launches **one** browser and
  loops all 20 fonts inside it. Process startup dwarfs per-page render, so amortise
  it — the same instinct as connection pooling.

---

## 5. Templating with Jinja2

`templates/pick.html.j2` is HTML with holes. Custom filters bridge the data and
the view — registered as `mon` (ISO month → `"Jul 2024"`) and `striphttp` (drop
the scheme for display). The engine is created with **autoescape on**:

```python
env = Environment(loader=FileSystemLoader(...),
                  autoescape=select_autoescape(["html"]))
```

Autoescaping is a **security default** — it stops content with `<`, `&`, `"`
from breaking (or injecting) markup. It also created a subtle bug worth
remembering:

> The font is injected as CSS: `font-family: {{ font_stack }}`. With
> `font_stack = '"Raleway", …'`, autoescape turned the quotes into `&quot;` and
> **broke the CSS**. The fix is `{{ font_stack | safe }}` — an explicit "I trust
> this value" opt-out, used *only* for the font URL and stack.

That's the right mental model: **escape by default, unescape by exception, and
make the exception loud.** The same tension (safe defaults vs. trusted raw HTML)
shows up in every web framework's `dangerouslySetInnerHTML` / `mark_safe` /
`| raw`.

---

## 6. Typography as engineering

Three "cosmetic" problems that were really data/rendering bugs:

- **Wobbly phone digits.** Raleway's default *old-style* figures give digits
  varying heights/baselines, so `+91 9873824499` looked ransom-note. Fix — ask the
  font for **lining, tabular** figures on `body`:

  ```css
  font-variant-numeric: lining-nums tabular-nums;
  font-feature-settings: "lnum" 1, "tnum" 1;
  ```

  Lining = uniform height; tabular = uniform width. This is exactly why financial
  tables use tabular figures — columns line up.

- **"Clipping" at the right margin.** Reported three times. Measuring every PDF
  (via PyMuPDF span boxes) proved text sat inside symmetric ~1 cm margins with
  `MediaBox == CropBox` — nothing was actually off-page. The culprit was
  **justified** body text stretching flush to the narrow margin (and any viewer
  that trims a few mm would shave a justified glyph). Fix: `text-align: left`
  (ragged right). *Lesson: measure before you "fix". The bug was perception; the
  data disproved it; the change addressed the perception without inventing an
  imaginary overflow.*

- **The Google Fonts `css2` 400 trap.** Requesting a weight a font doesn't ship
  makes the **entire** stylesheet request 400 — and the font silently falls back
  to a system face, so the PDF looks "wrong" for no obvious reason. The
  `PICK_FONTS` table curates valid weights per font so all 20 render. *Lesson:
  a dependency that fails **silently** by falling back is worse than one that
  fails loudly; know your third-party API's failure modes.*

---

## 7. Publishing

The studio produces PDFs under `out/`; the automaton reads resumes from
`resumes/`. `render_publish()` is the seam between them:

```python
pdf = render_pick_html(m)                 # out/pick/hybrid_html.pdf
dest = repo/"resumes"/f"{name}_Resume.pdf"
if dest.exists():                         # back up, never overwrite blindly
    copy dest -> resumes/<stem>.backup-<timestamp>.pdf
copy pdf -> dest
```

Two engineering habits in a tiny function:

- **Idempotent + safe.** Re-runnable; an existing file is backed up first (and the
  backup name still matches the `resumes/*.pdf` ignore rule, so PII stays out of
  git). Automations that touch user files should be **non-destructive by
  default** — treat "overwrite" as a deploy and keep the previous artifact.
- **Convention over configuration.** The default filename derives from
  `basics.name`, which happens to match `config.yaml → resume.mapping`, so
  `publish` needs no arguments in the common case. Verify the wiring with
  `apply.py resume-test "<title>"`.

The studio and the app stay **decoupled**: the app knows only "a PDF exists in
`resumes/`"; the studio knows only "put a PDF there." Neither imports the other.

---

## 8. Where industry uses these ideas

- **Static site generators** (Hugo, Jekyll, VitePress — the very tool this repo's
  wiki uses): content in Markdown/YAML → templates → HTML. Same content/presentation
  split, same "single source, many views."
- **Headless-browser PDF services.** Invoicing, contracts, boarding passes, and
  report exports are routinely rendered with Puppeteer/Playwright printing HTML —
  because reusing the browser's layout + font engine beats hand-rolling a PDF
  layout library. This studio is a one-document version of that service.
- **Design tokens.** The `:root` CSS variables (`--fs-*`, `--teal`) are exactly how
  design systems centralise sizing/colour so one edit re-themes everything.
- **Golden-file comparison.** The contact sheets (`pick-fonts`, the galleries) are
  a visual bake-off harness — the eyeball equivalent of snapshot tests.

**Takeaway for your own designs:** separate the *what* from the *how*, derive views
instead of duplicating them, make automation non-destructive, and when taste is
involved, build the harness that turns opinion into measurable comparison.
