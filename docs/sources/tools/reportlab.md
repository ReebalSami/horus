---
source_url: "https://github.com/MrBitBucket/reportlab-mirror"
source_title: "ReportLab — The Python PDF library"
source_author: "ReportLab Inc."
source_date: ""
retrieved_date: "2026-05-11"
extracted_concepts: []
tags: ["reportlab", "pdf-generation", "python-library", "financial-reports", "bsd-3", "fallback-tooling", "adr-006"]
archived_pdf: ""
status: stub
---

Mature Python PDF generation library (BSD-3-Clause) maintained by ReportLab Inc. since 2000. PyPI: `reportlab 4.5.0` (2026-04-29). Wheel: `py3-none-any` (dropped compiled C extensions in 4.x; `py3-none-any` wheel). Python ≥ 3.9 required; HORUS ≥ 3.14 satisfies.

**Runtime dependencies**: `Pillow`, `charset-normalizer`. Optional extras: `rl_accel` (C acceleration), `renderPM` (bitmap), `pycairo`, `bidi`, `shaping`.

**Role in HORUS (per ADR-006)**: **named fallback renderer** in ADR-006 §5 supersession trigger (a) (fpdf2 maintenance lapses) + trigger (b) (HORUS distribution context shifts to public commercial, making LGPL-3.0 obligations material). Multiple 2025/2026 library-comparison articles specifically position ReportLab as "best for financial reports, data-heavy documents, and precise layouts" — consistent with invoice generation use cases.

**Why not chosen (ADR-006 §3 decision)**: ReportLab's `Canvas` + `Platypus` combination is more verbose than fpdf2's `with pdf.table()` context-manager API for simple tabular invoices; py-pdf org consistency (`fpdf2` same org as existing `pypdf` dep) was the deciding factor; fpdf2's `Templates` system is purpose-built for the upcoming bulk-pilot generator. BSD-3 license is cleaner (no copyleft) — this is a known trade-off against fpdf2's LGPL-3.0+.

**Key API concepts**: `reportlab.pdfgen.canvas.Canvas(path, pagesize=A4)` (low-level drawing); `reportlab.platypus.{Table, TableStyle, SimpleDocTemplate, Paragraph}` (Platypus story-based layout, preferred for multi-element documents).

**Commercial offering**: ReportLab PLUS (volume-based annual license) adds tagged PDF, parsing, and DocEngine hosting. Core library remains BSD. Not relevant for HORUS (thesis-internal scope).

**PyPI**: https://pypi.org/project/reportlab/ | **Docs**: https://docs.reportlab.com/
