# generated/resume — resume PDFs the automaton attaches

This folder holds the resume PDFs the automaton uploads to Easy Apply forms.
The PDFs are **git-ignored** (personal documents), but this folder and its
guidance are kept so a fresh clone has the structure.

Point `configs/config.yaml` at this folder:

```yaml
resume:
  directory: generated/resume
  default: Your_Name_1page.pdf
  mapping:
    software engineer: Your_Name_SoftwareEngineer.pdf
    full stack developer: Your_Name_FullStack.pdf
```

## How resumes get here

Resumes are built by the standalone **[dynamic-resume-builder](https://github.com/Zanark/dynamic-resume-builder)**
(kept locally at `C:\devdesk\homedesk\dynamic-resume-builder`). It keeps all your
content in one `master.yaml` and renders pixel-tuned PDFs. Publish straight into
this folder with the `--out-dir` option:

```powershell
cd C:\devdesk\homedesk\dynamic-resume-builder
# one resume:
python render.py publish --out-dir C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\generated\resume
# every role variant defined in master.yaml:
python render.py publish-variants --out-dir C:\devdesk\homedesk\LinkedIn-EasyApply-Automaton\generated\resume
```

Any existing file of the same name is backed up to `<stem>.backup-<stamp>.pdf`
first, so nothing is ever lost. Filenames must match `resume.mapping` /
`resume.default` in `configs/config.yaml`.
