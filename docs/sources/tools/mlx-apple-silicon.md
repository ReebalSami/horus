---
source_url: "https://github.com/ml-explore/mlx"
source_title: "MLX — Apple's array framework for ML on Apple Silicon"
source_author: "Apple Machine Learning Research"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["mlx", "apple-silicon", "inference-framework", "unified-memory", "primary-stack"]
archived_pdf: ""
status: stub
---

MLX — Apple's open-source array framework optimized for Apple Silicon (M1/M2/M3/M4 unified memory). Reported throughput on M-class Macs ~230 tok/s for LLM inference (per brainstorm v2 §7.2 — directional, single-source, to-verify). Cited in HORUS as the **primary inference framework** for local Layer-1 + Layer-2 deployment on the M1 Pro target hardware. Granite-Docling 258M ships with native MLX support (per `docs/sources/papers/ibm-2025-granite-docling.md`). The throughput claim must be verified with a HORUS-internal benchmark before any thesis-claim is made (per ADR-001 current-state-survey discipline).
