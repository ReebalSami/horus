---
source_url: "https://pytorch.org/docs/stable/notes/mps.html"
source_title: "PyTorch MPS backend — Apple GPU support via Metal Performance Shaders"
source_author: "PyTorch / Meta AI"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["pytorch", "mps", "apple-silicon", "inference-framework", "benchmark-comparand", "slow-baseline"]
archived_pdf: ""
status: stub
---

PyTorch MPS (Metal Performance Shaders) backend — runs PyTorch tensor ops on Apple GPU. Reported throughput on M-class Macs ~7–9 tok/s for LLM inference (per brainstorm v2 §7.2) — by far the slowest of the surveyed paths (~25× slower than MLX). Cited in HORUS as the **slow-baseline reference** to be cited only as the worst-case naïve PyTorch path; for any real HORUS inference workload, MLX or llama.cpp is preferred. Relevant if a candidate VLM has only PyTorch reference-implementation support (no MLX port, no GGUF quantization), in which case the thesis must either accept the slow path or invest in porting effort.
