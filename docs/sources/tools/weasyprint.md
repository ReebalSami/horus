---
source_url: "https://github.com/Kozea/WeasyPrint"
source_title: "WeasyPrint — The Awesome Document Factory (HTML/CSS → PDF)"
source_author: "Kozea / CourtBouillon"
source_date: ""
retrieved_date: "2026-05-11"
extracted_concepts: []
tags: ["weasyprint", "pdf-generation", "html-css-to-pdf", "python-library", "system-deps", "fallback-tooling", "adr-006"]
archived_pdf: ""
status: stub
---

Python library (BSD-3-Clause) that converts HTML/CSS documents to PDF via `Pango` + `Cairo` rendering backends. Maintained by CourtBouillon. PyPI: `weasyprint 68.1` (2026-02-06). Python ≥ 3.10 required; HORUS ≥ 3.14 satisfies.

**System dependencies (critical)**: Pango, Cairo, GLib — must be installed via Homebrew on macOS (`brew install pango`). This is **not** resolved by `pip install weasyprint` alone; it requires system-level package installation. On a clean developer machine this is a first-time setup step; in CI it adds ~50 MB of Homebrew deps to the pipeline.

**Role in HORUS (per ADR-006)**: **named fallback renderer** in ADR-006 §5 supersession trigger (c): if the thesis adopts a per-locale HTML/CSS templated-design workflow demanding visual richness beyond fpdf2's Helvetica canvas. The HTML/CSS paradigm has strong thesis-defensibility when explaining rendering choices to an academic audience ("standard web technologies, well-understood layout model").

**Why not chosen (ADR-006 §3 decision)**: system-deps install (Pango + Cairo via Homebrew) is fragile on macOS; conflicts directly with HORUS's `know-your-hardware` rule (prefer zero-system-dep tooling). No advantage over fpdf2 for our simple 6-field A4 invoice. Would complicate CI setup.

**If used in future (trigger (c) fires)**:
1. `brew install pango` — installs Cairo + GLib as transitive deps
2. `uv add weasyprint`
3. Template invoice as Jinja2 HTML + CSS; render via `weasyprint.HTML(string=rendered_html).write_pdf(path)`
4. Pass resulting PDF to `facturx.generate_from_file` for PDF/A-3 bonding (same bonding step)

**PyPI**: https://pypi.org/project/weasyprint/ | **Docs**: https://doc.courtbouillon.org/weasyprint/stable/
