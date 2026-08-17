---
source_url: "https://doi.org/10.1007/978-3-030-86797-3_1"
source_title: "Information Extraction from Invoices: A Graph Neural Network Approach for Datasets with High Layout Variety"
source_author: "Felix Krieger, Paul Drews, Burkhardt Funk, Till Wobbe"
source_date: "2021"
retrieved_date: "2026-08-16"
extracted_concepts: []
tags: ["dataset", "invoice", "english", "annotated", "gnn", "auditing", "related-work", "wi2021"]
archived_pdf: ""
status: verified
---

**Supersedes the stub at `gi-2021-german-invoices.md`** — with a correction history. The stub recorded an unnamed "GI 2021 paper" holding 977 German invoices; the third-pass review (2026-08-16) resolved the stub to THIS paper and transplanted the stub's corpus description onto it. The **fourth-pass review (2026-08-17)** found that transplant wrong: this paper's corpus is English (see below); the 977-German-invoice corpus belongs to the same group's later design-science study, archived at `thiee-2023-invoice-extraction-pipeline.md`. A claim of verification is itself a claim to be checked.

**Full citation.** Krieger, Drews, Funk & Wobbe (2021), *Information Extraction from Invoices: A Graph Neural Network Approach for Datasets with High Layout Variety*, in **Innovation Through Information Systems (WI 2021)**, Lecture Notes in Information Systems and Organisation, Springer, **pp. 5–20**, DOI **10.1007/978-3-030-86797-3_1**. Presented at the 16. Internationale Tagung Wirtschaftsinformatik, Universität Duisburg-Essen, March 2021.

**Corpus (corrected 2026-08-17, from the paper's own dataset section).** "The dataset is composed of **1129 English one-page invoices from 277 different vendors**. We annotated the invoices ourselves **by hand** for the key items." All invoices are addressed to the **same recipient** (provided by an audit firm; co-author Wobbe is at EY). Three key items — invoice number, invoice date, total amount — plus an "unlabeled" class; sharply imbalanced (of 243,704 textboxes, ~0.58 % invoice numbers, ~0.91 % total amounts, ~1.06 % invoice dates). The limitations section states: "we only used English invoices." The layout-variety contrast against prior single-vendor datasets is the paper's point.

**Result.** Macro-averaged F1 of **0.8753** over the three key items with a graph attention model over OCR output (Tesseract).

**Open access.** AISeL mirror: <https://aisel.aisnet.org/wi2021/RDataScience/Track09/4> (the full text used for the fourth-pass verification of the dataset section).

**Why this matters to the thesis.** This is the origin of the auditing-digitalisation line of invoice-extraction work that Chapter 3 §"German invoices have been extracted before, and by whom" engages: the graph model introduced here is the one the group later carried to German documents (`thiee2023invoices`, F1 0.823 on the same three fields). Chapter 3 describes both accurately since the fourth pass and states the reasons the numbers are **not** comparable to the thesis's — corpus scale and realism, kind of ground truth (hand-/rule-annotated in-house class lists vs. reference extracted from the document's own embedded record under EN 16931), and setting (OCR-plus-layout models under no hardware constraint vs. open-weights VLMs under a 16 GB envelope and no separate recognition engine). No ranking is licensed by the fact that this paper's 0.8753 and the thesis's held-out figure both round to 0.88.

Cited in `thesis/references.bib` as `krieger2021german`. Companion records: `thiee-2023-invoice-extraction-pipeline.md`, `krieger-2023-longtail.md`.
