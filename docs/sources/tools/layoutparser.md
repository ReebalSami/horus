---
source_url: "https://github.com/Layout-Parser/layout-parser"
source_title: "LayoutParser — unified toolkit for deep-learning-based document image analysis"
source_author: "Allen Institute for AI / Shen et al. (ICDAR 2021)"
source_date: "2021"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["layoutparser", "detectron2", "layout-analysis", "classical-cv", "pre-2025-wave", "rejected-on-staleness"]
archived_pdf: ""
status: stub
---

LayoutParser — Allen AI's unified toolkit for deep-learning-based document image analysis (Shen et al., ICDAR 2021). Built on Detectron2 (Facebook AI Research, 2019). Apache-2.0. Supplies pretrained layout-detection models (PubLayNet, PrimaLayout, Newspaper Navigator) plus an OCR wrapper API. Last public release in 2022; minimal upstream activity since.

Cited in HORUS issue #11 as alternative for the orchestrated-baseline ADR. **Rejected** in ADR-008 on staleness grounds — pre-Oct-2025-wave architectural lineage (Detectron2 = 2019-vintage; LayoutParser = 2021–22 era). Brainstorm v2 §7.1 implication: *"building Layer 1 around [pre-Oct-2025-wave tools] would be like building an NLP thesis around word2vec in 2023."* The orchestrated-specialist scope is well-served by 2025–26 tools (Docling, MinerU pipeline backend) that incorporate transformer-era layout/parsing models; LayoutParser's CNN-era foundation would force HORUS to either accept stale baselines or rebuild the layout stage from scratch — both compromise thesis-time scope per `know-your-hardware`.
