---
source_url: "https://arxiv.org/abs/2603.04205"
source_title: "Real5-OmniDocBench: A Full-Scale Physical Reconstruction Benchmark for Robust Document Parsing in the Wild"
source_author: "Zhou, Changda; Gao, Ziyue; Wang, Xueqing; Gao, Tingquan; Cui, Cheng; Tang, Jing; Liu, Yi (PaddlePaddle)"
source_date: "2026-03-04"
retrieved_date: "2026-05-13"
verified_date: "2026-08-18"
extracted_concepts: []
tags: ["real5-omnidocbench", "benchmark", "dataset", "real-world", "physical-conditions", "deferred", "tier-3"]
archived_pdf: ""
status: verified
verified: [authors, title, venue, arxiv-id, five-conditions-claim]
license_spdx: ""
license_url: ""
data_manifest: ""
acquisition_status: deferred
---

> **Corrected 2026-08-18** (fifth-pass audit, F3). This record previously read
> `source_author: "OpenDataLab (extension paper)"` with a paraphrased title, and
> the summary below invented the five condition names. OpenDataLab authored the
> **parent** OmniDocBench; this extension is from the PaddlePaddle group.
> Verified against arXiv 2603.04205 and the Hugging Face papers record; the
> dataset is hosted at `PaddlePaddle/Real5-OmniDocBench`.

Real5-OmniDocBench — a one-to-one physical reconstruction of the entire OmniDocBench v1.5 (1,355 images) across five real-world scenarios: **Scanning, Warping, Screen-Photography, Illumination and Skew**. The complete ground-truth mapping is the point: it enables factor-wise attribution of degradation (geometric distortion vs optical artefact vs model limitation), which partial-sampling benchmarks cannot. arXiv 2603.04205 (March 2026). Cited in HORUS brainstorm v2 §9.1 as a **distribution-shift validation companion to OmniDocBench**. **Deferred (Tier 3)** per Q4 of the M2D.5 issue #12 Q&A round: OmniDocBench v1.6 already covers the synthetic/clean dimension; Real5 is the photographed/real-world variant — useful only after the pilot establishes Layer-1 baselines on synthetic invoices and we have headroom to evaluate physical-degradation robustness. Re-evaluate at experiments-validated milestone.
