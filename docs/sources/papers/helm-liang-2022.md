---
source_url: "https://arxiv.org/abs/2211.09110"
source_title: "Holistic Evaluation of Language Models (HELM)"
source_author: "Percy Liang, Rishi Bommasani, Tony Lee, et al. (Stanford CRFM)"
source_date: "2022-11-16"
retrieved_date: "2026-05-21"
extracted_concepts:
  - "saved-generations-as-canonical-evidence"
  - "multi-metric-reporting"
  - "scenario-x-model-product-with-per-tuple-artefacts"
tags: ["evaluation-methodology", "reproducibility", "scientific-correctness"]
archived_pdf: ""
status: stub
---

HELM — landmark holistic-evaluation paper from Stanford CRFM. Two adoptions in HORUS post-audit work:

1. **Saved per-scenario / per-model generations as canonical evidence** (§"Methodology" + §"Reproducibility"). HELM logs every model's raw output alongside its metric score, preserving the artefact that lets future readers re-derive the score. This is the load-bearing precedent for ADR-020 §"Offline rescore from saved transcripts": treat saved transcripts as canonical evidence; re-score offline against fixed adapters; never mutate historical MLflow runs.

2. **Multi-metric reporting** (§6 "Results"). HELM reports across 7 metrics per (scenario, model) tuple SIMULTANEOUSLY rather than collapsing to a single number. ADR-021's 2 × 2 verdict matrix (pre-registered × amended × N-of-7 × N-of-6) is the same shape: reader picks the methodology lens; disagreement between cells is itself the finding.

Cited at:

- ADR-019 §"Context" (audit motivation — saved-evidence reproducibility)
- ADR-020 §"Current-state survey" §"HELM + EleutherAI precedent"
- ADR-021 §"Decision" §"Option 2 (dual verdict)"
- `docs/retros/m2d.5-structured-output-probe.md` §"Post-audit amendment"

To populate via Obsidian web-clipper: visit `https://arxiv.org/abs/2211.09110`, clip §"Methodology" + §"Reproducibility" + §6 "Results", and replace this stub.
