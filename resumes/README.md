# Place your resume files here

Drop your resume PDFs / DOCX files in this directory. They are **git-ignored**
so your personal documents never get committed.

Reference them from `configs/config.yaml` under `resume.mapping` (role/keyword ->
filename) and/or `resume.default`. See `docs/configuration.md`.

## Prefer to generate one?

Use the bundled **[Resume Studio](../resume_studio/README.md)**: keep your content
in one `master.yaml` and run `python resume_studio\render.py publish` to drop a
pixel-tuned one-page PDF right here (any existing file is backed up first).
