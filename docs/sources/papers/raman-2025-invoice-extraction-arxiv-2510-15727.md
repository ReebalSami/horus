---
source_url: "https://arxiv.org/abs/2510.15727"
source_title: "Invoice Information Extraction: Methods and Performance Evaluation"
source_author: "(arXiv 2510.15727 — full authorship to be verified on next clip pass)"
source_date: "2025-10"
retrieved_date: "2026-05-17"
extracted_concepts: []
tags: ["invoice-extraction", "f1-evaluation", "docile-aligned", "field-vs-line-item", "header-evaluation", "methodology", "literature-anchor", "adr-009", "adr-012", "pilot-13"]
archived_pdf: ""
status: stub
---

arXiv:2510.15727 — invoice information extraction methods + evaluation framework. Cited in HORUS as the **methodological precedent** for separating **field-level F1 (header)** from **line-item F1 (row-wise assignment)** when evaluating invoice extraction systems. The DocILE benchmark (Stanisławek et al. 2023) established this separation; this 2025 paper carries it into the modern VLM-evaluation context and §3.4 makes the rationale explicit: header-level field extraction is a single-value-per-field task with well-defined F1; line-item extraction is a multi-row task requiring row-wise assignment + set-matching + table-level completeness — methodologically distinct research problems that warrant separate metrics.

**Role in HORUS (per ADR-012)**: cited as the scientific anchor for the **"header-only" scope decision** in pilot #13's ground-truth parser. The 16-field HORUS scope is header + totals only; line items (BG-25), per-VAT-rate breakdown (BG-23), and per-charge/allowance details (BG-20) are deferred to a future ADR amendment. The deferral is not because line items don't matter for the thesis — they likely do for compliance scoring — but because mixing header F1 + line-item F1 in a single per-field metric is methodologically muddled (per the §3.4 framing).

**ADR cross-references**:
- ADR-009 cohort smoke designated 5 fields as the manual-Excel evidence base; ADR-012 expanded this to the full 16-field XML-grounded ground truth per ADR-009 Amendment 1
- ADR-012's `GroundTruth(header=...)` wrapper reserves a forward-compat `line_items` field for a future amendment that will adopt this paper's separated metrics

**What HORUS does NOT take from this paper**: the specific cohort of VLMs benchmarked (HORUS has its own ADR-007 dual-track local-VLM cohort per ADR-009), the specific dataset selection (HORUS uses FeRD-shipped ZUGFeRD test invoices, not the paper's corpus), or the absolute F1 numbers (different cohorts, different corpora — comparison would be misleading).

**Stability**: arXiv preprint — may be revised. The §3.4 methodological framing is unlikely to change; specific empirical numbers are not load-bearing for HORUS citations. Re-verify §3.4 wording on the next clip pass (Obsidian Web Clipper, target: `docs/sources/papers/raman-2025-invoice-extraction-arxiv-2510-15727.md`).

**Stub note**: full authorship + verified abstract content pending clip pass. The methodological cite point (§3.4 field-vs-line-item separation) is firm; the rest is to be verified.
