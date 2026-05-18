---
source_url: "https://github.com/rossumai/docile"
source_title: "DocILE — Document Information Localization and Extraction benchmark"
source_author: "Rossum.ai (Štěpán Šimsa, Milan Šulc, Michal Uřičář, Yash Patel, et al.)"
source_date: "2023-05"
retrieved_date: "2026-05-18"
extracted_concepts: ["DocILE benchmark", "KILE task", "LIR task", "field-level F1", "average precision", "micro-averaging"]
tags: ["benchmark", "invoice-extraction", "field-extraction", "f1-evaluation", "methodology", "adr-013", "pilot-13"]
archived_pdf: ""
status: stub
---

**DocILE** (Document Information Localization and Extraction) — benchmark released by Rossum.ai in 2023. Two tasks: **KILE** (Key Information Localization and Extraction — predict bounding-box + value for each field type) and **LIR** (Line Item Recognition — recognize per-row line-items in tabular sections). Establishes **micro-averaged field-level F1 + Average Precision (AP)** as the canonical evaluation metric for invoice / business-document extraction systems.

**Role in HORUS (per ADR-013)**: cited as the **methodological anchor** for pilot #13's evaluation framework. HORUS adopts DocILE's **field-level F1 separation** from line-item metrics (per arXiv 2510.15727 §3.4 which explicitly cites DocILE on this point). The 16-field HORUS scope = the "header + totals" subset that maps onto DocILE's KILE task; line-items (BG-25) would map onto LIR but are deferred per ADR-012.

**Methodological points adopted in HORUS**:
1. **Micro-averaging across documents** (sum TP/FP/FN over the corpus, then compute one F1) — captured as `InvoiceFieldScores.micro_f1`
2. **Per-field F1 breakdown** — captured as `FieldResult.outcome` × per-field aggregation in `InvoiceFieldScores.per_field`
3. **Exact + relaxed match scoring** per field type — captured as the `field_type` dispatch in the comparator (CODE = exact; STRING = ANLS\* relaxed; MONEY/DATE = exact-on-normalized)
4. **Tolerance windows for numeric fields** (DocILE allows ±tolerance on dates and money) — captured as `eval.money_tolerance_cents` and `eval.date_tolerance_days` knobs (default 0 = strict; tunable per pilot finding)

**What HORUS does NOT take from DocILE**: bounding-box localization (HORUS is OCR-free single-page evaluation; no spatial scoring); the specific cohort of models DocILE benchmarks; the absolute F1 numbers (different corpus — DocILE uses 6.7K business documents, HORUS uses the FeRD-shipped ZUGFeRD test invoices).

**ADR cross-references**:
- ADR-012 §"Decision" cites DocILE as the precedent for the header-only scope
- ADR-013 §"Decision + integration thoughts" cites DocILE for the field-level F1 + micro-averaging framework

**Stub note**: DocILE paper (NeurIPS 2023 Datasets & Benchmarks Track) PDF citation pending clip pass. GitHub repo is canonical for benchmark + evaluation tooling.
