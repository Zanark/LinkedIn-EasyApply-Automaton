# Resume generation — how the automaton gets its PDF

> Written for an SDE growing toward architect. The resume that this tool submits
> is **not built here** — it is produced by a separate, standalone project,
> [**dynamic-resume-builder**](https://github.com/Zanark/dynamic-resume-builder).
> This page explains *why* that boundary exists and how the two tools connect.
> For the builder's own internals (content model, engine bake-off, templating,
> typography, headless-browser PDF generation) read its docs in that repo.

## Contents

1. [The boundary: two tools, one direction of dependency](#1-the-boundary)
2. [Single source of truth (the content model)](#2-single-source-of-truth)
3. [How a PDF reaches the automaton](#3-how-a-pdf-reaches-the-automaton)
4. [Where industry uses these ideas](#4-where-industry-uses-these-ideas)

---

## 1. The boundary

The automaton and the resume builder are **decoupled**: neither imports the
other. The builder's only job is *content in → PDF out*; the automaton's only job
is *pick a PDF from `generated/resume/` and upload it*. The seam between them is a
folder path, not a function call.

```
dynamic-resume-builder          LinkedIn-EasyApply-Automaton
┌──────────────────────┐        ┌───────────────────────────────┐
│ master.yaml (content)│        │ configs/config.yaml            │
│        │             │        │   resume.directory: generated/ │
│        ▼             │  PDF   │                        resume  │
│  render.py publish ──┼───────▶│ generated/resume/*.pdf         │
│  --out-dir …/generated/resume │        │                      │
└──────────────────────┘        │        ▼                      │
                                │ ResumeSelector → Easy Apply    │
                                └───────────────────────────────┘
```

Why keep them separate?

- **Different lifecycles.** You tweak resume design far more often than you touch
  the automation. A design change should not risk the applier, and vice-versa.
- **Different audiences.** The builder is a shareable product (its sample persona
  is fictional — "Peter Parker"); the automaton is your private job-search tool
  holding real PII. Keeping them apart keeps PII out of the public repo.
- **One direction of dependency.** The automaton depends on *files in a folder*,
  the most decoupled contract there is. You could swap the builder for any tool
  that writes PDFs into `generated/resume/` and nothing here would change.

This is the same **separation of concerns** you reach for in services: a producer
and a consumer that share a contract (here, "PDFs in a folder"), not a codebase.

---

## 2. Single source of truth

Inside the builder, `master.yaml` holds the content — and nothing about looks:

```yaml
basics: { name: …, title: …, email: …, phone: …, links: [ … ] }
experience: [ … ]
skills: [ … ]
variants: [ … ]   # role-tailored projections of the same content
```

Content is data; a résumé PDF is a *view*. Every representation (one-page,
two-page, per-role) is derived from that one file, so the copies can never drift.
The builder's docs cover the model in full.

---

## 3. How a PDF reaches the automaton

You run the builder and point its output straight at this repo's resume folder:

```powershell
cd C:\devdesk\homedesk\dynamic-resume-builder

# one resume:
python render.py publish       --out-dir C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\generated\resume

# every role variant defined in master.yaml:
python render.py publish-variants --out-dir C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\generated\resume
```

Any existing file of the same name is backed up to `<stem>.backup-<stamp>.pdf`
first, so nothing is lost. The filenames must match `resume.mapping` /
`resume.default` in `configs/config.yaml`. From then on the automaton's
`ResumeSelector` chooses among whatever PDFs live in `generated/resume/`
(mapping match → filename-keyword overlap → default). See
[configuration.md](configuration.md) and [generated/resume/README.md](../generated/resume/README.md).

---

## 4. Where industry uses these ideas

- **Producer/consumer via a shared artifact store** — CI builds an artifact; a
  deploy job consumes it from a bucket. Same "files in a folder" contract.
- **Content vs. presentation** — headless CMS, static-site generators, and design
  systems all model content once and render many views.
- **Repo boundaries that follow PII/lifecycle** — public SDK vs. private app is a
  common split; keeping secrets and shareable tooling in different repos is a
  standard supply-chain and privacy practice.
