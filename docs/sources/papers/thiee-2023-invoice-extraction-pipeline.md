---
source_url: "https://doi.org/10.18420/inf2023_180"
source_title: "Extraction of Information from Invoices – Challenges in the Extraction Pipeline"
source_author: "Lukas-Walter Thiée, Felix Krieger, Burkhardt Funk"
source_date: "2023"
retrieved_date: "2026-08-17"
extracted_concepts: []
tags: ["dataset", "invoice", "german", "annotated", "rule-based", "gnn", "design-science", "auditing", "related-work", "informatik2023"]
archived_pdf: ""
status: verified
---

**Full citation.** Thiée, Krieger & Funk (2023), *Extraction of Information from Invoices — Challenges in the Extraction Pipeline*, in **INFORMATIK 2023 — Designing Futures: Zukünfte gestalten** (Lecture Notes in Informatics P337), Gesellschaft für Informatik, Bonn, **pp. 1777–1792**, DOI **10.18420/inf2023_180**. Joint Workshop IntDig 2023 / MOC 2023, Berlin. Open access: GI digital library item `5c508847-1654-434b-8097-0e87f1a6798a`, PDF `09_01_06_Thiee.pdf` (bitstream `38f719d8-6af3-4dd7-a0c6-bdb08bb893c1`).

**Why this record exists (fourth-pass thesis review, 2026-08-17).** This is the paper that actually carries the **977-invoice German corpus** that HORUS had tracked since the brainstorm as an unnamed "GI 2021 paper" (`gi-2021-german-invoices.md`) and that the third-pass review mis-attributed to `krieger-2021-invoice-gnn.md`. The old dataset record `docs/sources/datasets/gi-2021-de-invoices.md` had been pointing at this paper's PDF bitstream all along — under a chimera title fusing this paper's title with the 2021 paper's.

**Corpus (from the paper's own text).** "977 pdf files with rule-based label annotations and OCR extracts for over 60 classes, which provides segmentation on word level" — real German invoices, **494 vendors / 531 recipients** (the paper's own comparison table prints "977 (494/531)" against Krieger 2021's "1129 (277/1)"). Labels include invoice date, invoice number, total amount, payment information, IBAN and commercial-register number. OCR engine: Abbyy (vs. Tesseract in the 2021 study). Access-restricted; not bundled with the paper (acquisition was attempted and deferred — see `gi-2021-de-invoices.md`).

**Method and result.** A design-science study of the raw-data-to-structured-information pipeline (morphological framework). Its first design cycle adapts the graph model of Krieger et al. (2021) — chosen "because it is the most recent one and integrates semantic, syntactic and positional information types" — and **integrates a German-BERT model for semantic features**. Line items are excluded in this cycle; the classified labels are the three headline fields (invoice date, invoice number, total amount). Reported test **F1 0.823**, against 0.905 for the benchmark model on its original English data.

**Role in the thesis.** Cited in `thesis/references.bib` as `thiee2023invoices`; engaged in Chapter 3 §"German invoices have been extracted before, and by whom" as the German-language prior, alongside `krieger2021german` (the model's origin, English corpus) and `krieger2023longtail` (the template-shift question). Companion records: `krieger-2021-invoice-gnn.md`, `krieger-2023-longtail.md`.
