---
source_url: "https://arxiv.org/abs/2604.04771"
source_title: "MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale"
source_author: "Bin Wang, Tianyao He, Linke Ouyang, et al. (OpenDataLab)"
source_date: "2026-04"
retrieved_date: "2026-07-31"
extracted_concepts: []
tags: ["mineru", "mineru2.5-pro", "document-parsing", "omnidocbench-v1.6", "data-engineering", "qwen2_vl", "reader-bakeoff", "adr-054"]
archived_pdf: ""
status: stub
---

MinerU2.5-Pro — April 2026 follow-up establishing **absolute SOTA on OmniDocBench v1.6 (95.69)**,
surpassing GLM-OCR, PaddleOCR-VL-1.5, Gemini 3 Pro, and Qwen3-VL-235B — while keeping the 1.2 B
qwen2_vl architecture of MinerU2.5 completely fixed. All gains from data engineering: 10 M → 65.5 M
samples via Diversity-and-Difficulty-Aware Sampling, Cross-Model Consistency Verification for
annotation, Judge-and-Refine render-then-verify correction, and a three-stage pre-train →
hard-sample fine-tune → GRPO pipeline. The paper also *defines* OmniDocBench v1.6 (fixes v1.5
element-matching biases + adds a Hard subset). Key thesis-relevant claim: SOTA models across
architectures share failure patterns on the same hard samples → the bottleneck is data, not
architecture. Checkpoints: `opendatalab/MinerU2.5-Pro-2604-1.2B` (paper) and
`opendatalab/MinerU2.5-Pro-2605-1.2B` (MinerU 3.3 release, 2026-06-11: stability fixes + native
multilingual OCR — the HORUS bake-off lead candidate per ADR-054). Tool stub:
`docs/sources/tools/mineru-2-5.md`. Cited in ADR-054 §Current-state survey.
