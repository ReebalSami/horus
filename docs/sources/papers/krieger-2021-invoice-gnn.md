---
source_url: "https://doi.org/10.1007/978-3-030-86797-3_1"
source_title: "Information Extraction from Invoices: A Graph Neural Network Approach for Datasets with High Layout Variety"
source_author: "Felix Krieger, Paul Drews, Burkhardt Funk, Till Wobbe"
source_date: "2021"
retrieved_date: "2026-08-16"
extracted_concepts: []
tags: ["dataset", "invoice", "german", "annotated", "gnn", "auditing", "related-work", "wi2021"]
archived_pdf: ""
status: verified
---

**Supersedes the stub at `gi-2021-german-invoices.md`,** which recorded this work as an unnamed "GI 2021 paper" with `source_url: ""` and "specific authors TBD at deep-read". The deep-read happened on 2026-08-16 during the third-pass thesis review; nothing further is TBD.

**Full citation.** Krieger, Drews, Funk & Wobbe (2021), *Information Extraction from Invoices: A Graph Neural Network Approach for Datasets with High Layout Variety*, in **Innovation Through Information Systems (WI 2021)**, Lecture Notes in Information Systems and Organisation, Springer, **pp. 5–20**, DOI **10.1007/978-3-030-86797-3_1**. Presented at the 16. Internationale Tagung Wirtschaftsinformatik, Universität Duisburg-Essen, March 2021.

**Corpus.** 977 real German invoice PDFs, **494 vendors / 531 recipients**, with rule-based label annotations and OCR extracts over **more than 60 classes**, segmented at word level. Labels include invoice date, invoice number, total amount, payment information, IBAN and commercial-register number. Compared in the paper against a prior 1,129-invoice set from 277 vendors and a single recipient — the layout-variety contrast is the paper's point.

**Result.** Macro-averaged F1 of **0.8753** with a graph-based model over OCR output.

**Why this matters to the thesis, and why it is now engaged rather than merely mentioned.** Chapter 3 previously cited this corpus only as something that exists and is access-restricted. That understated the prior art: this is the closest *published extraction result* on German invoices, and an examiner from the auditing side will know it and will ask how the thesis's 0.88 compares. Chapter 3 §"German invoices have been extracted before, and by whom" now makes the comparison explicit and states the three reasons the numbers are **not** comparable — corpus scale and realism (977 real vs. 39 real), kind of ground truth (rule-annotated in-house class list vs. reference extracted from the document's own embedded record under EN 16931), and setting (OCR-plus-layout models under no hardware constraint vs. open-weights VLMs under a 16 GB envelope and no separate recognition engine). A macro-average over their class list and a mean per-invoice score over EN 16931 business terms are different measurements.

Cited in `thesis/references.bib` as `krieger2021german`. Companion record: `krieger-2023-longtail.md`.
