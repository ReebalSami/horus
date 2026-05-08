---
source_url: "https://github.com/mlc-ai/mlc-llm"
source_title: "MLC LLM — universal LLM deployment engine"
source_author: "MLC AI / OctoML / CMU collaborators"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["mlc-llm", "inference-framework", "apple-silicon", "tvm", "benchmark-comparand"]
archived_pdf: ""
status: stub
---

MLC LLM — TVM-Unity-based LLM compilation + serving framework with Apple Silicon support. Reported throughput on M-class Macs ~190 tok/s (per brainstorm v2 §7.2 — directional, to-verify). Cited in HORUS as a **secondary inference-framework comparand** to MLX for the local-deployment performance benchmark; the gap between MLX and MLC-LLM is small enough that operator-graph compilation differences may dominate model-architecture differences for some VLMs. Relevant only if MLX support for a candidate Layer-1 VLM is missing or buggy.
