---
source_url: "https://github.com/opendatalab/MinerU"
source_title: "MinerU — dual-backend document parsing tool (orchestrated pipeline + single-shot VLM)"
source_author: "OpenDataLab"
source_date: "2025-2026"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["mineru", "document-parsing", "orchestrated-pipeline", "single-shot-vlm", "dual-backend", "cohort-2025", "opendatalab", "apache-2", "chinese-origin-pretraining"]
archived_pdf: ""
status: stub
---

MinerU — document-parsing tool from OpenDataLab (Apache-2.0). **Critical distinction**: MinerU ships TWO backends with different architectural classifications:

- **Pipeline backend** (`mineru -p <input> -o <output> -b pipeline`) — orchestrated specialist pipeline; CPU-friendly; **86.2 score on OmniDocBench v1.5** per OpenDataLab GitHub README. Belongs in the orchestrated-baseline scope.
- **VLM backend / MinerU2.5-Pro-VLM** (1.2B params, arXiv 2604.04771) — single-shot vision-language model; **95.69 score on OmniDocBench v1.6** (April 2026, "absolute SOTA overall score" per OpenDataLab HuggingFace card `opendatalab/MinerU2.5-Pro-2604-1.2B`). Belongs in the single-shot cohort scope.

Cited in HORUS ADR-008 as the **chosen cross-check companion** (lean) for the orchestrated baseline — specifically the **pipeline backend** (`-b pipeline` flag), independent codebase + research lab from Docling, recent active 2025–26 development. **Caveat**: Chinese-origin pretraining is a documented concern for German-invoice ground-truth evaluation per brainstorm v2 §9.1 — verification gate at pilot loop #13. The VLM backend (95.69 v1.6) is **out of scope for ADR-008** and is properly the concern of cohort ADR #14 (single-shot pilot cohort selection). Both backends supported on Apple Silicon per OpenDataLab README; pipeline backend is pure-CPU compatible.
