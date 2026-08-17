---
source_url: "https://doi.org/10.1016/j.iswa.2023.200285"
source_title: "Automated Invoice Processing: Machine Learning-Based Information Extraction for Long Tail Suppliers"
source_author: "Felix Krieger, Paul Drews, Burkhardt Funk"
source_date: "2023"
retrieved_date: "2026-08-16"
extracted_concepts: []
tags: ["invoice", "layout-shift", "template-shift", "layoutlm", "auditing", "related-work"]
archived_pdf: ""
status: verified
---

**Full citation.** Krieger, Drews & Funk (2023), *Automated Invoice Processing: Machine Learning-Based Information Extraction for Long Tail Suppliers*, **Intelligent Systems with Applications 20:200285**, DOI **10.1016/j.iswa.2023.200285**.

**Corpus note (fourth-pass review, 2026-08-17).** The study runs on the audit firm's experimental invoice collection — per Krieger's dissertation (Leuphana, 2023), the languages of the documents across this line of work are "primarily English". It is cited in the thesis for the **template-shift methodology**, not as German-language prior art (the original `german` tag was a residue of the two-paper conflation corrected in this pass).

**What it studies.** How extraction quality behaves when the training population of invoice layouts is skewed towards a few frequent suppliers while the test layouts are not — the "long tail" of infrequent suppliers. The research pipeline pays explicit attention to the **distribution of layouts in the data split**, which is the methodological point. Finding: the accuracy gap between in-sample and out-of-sample layouts is **much larger for Chargrid and random-forest models than for a LayoutLM transformer**, which also has the best overall predictive quality.

**Why archived (2026-08-16, third-pass thesis review).** This is the closest published treatment of the **template-shift** question that this thesis registered as a hypothesis and then left unevaluated (Chapter 10, unevaluated hypothesis 6: performance on invoice layouts drawn from vendors absent from the fitting set). Leaving it uncited while reporting the hypothesis as untested would have been an omission of directly relevant prior art. Chapter 3 §"German invoices have been extracted before, and by whom" now cites it in that role, and the positioning section names it alongside the 2021 corpus paper.

Cited in `thesis/references.bib` as `krieger2023longtail`. Companion record: `krieger-2021-invoice-gnn.md`.
