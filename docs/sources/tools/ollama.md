---
source_url: "https://ollama.com"
source_title: "Ollama — local LLM model server"
source_author: "Ollama Inc."
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["ollama", "inference-framework", "model-server", "benchmark-comparand", "ergonomics"]
archived_pdf: ""
status: stub
---

Ollama — local LLM model-server wrapping llama.cpp + a model registry + a REST API. Reported throughput on M-class Macs ~20–40 tok/s (per brainstorm v2 §7.2 — substantially slower than llama.cpp directly because of the overhead of the daemonized HTTP layer). Cited in HORUS for the **ergonomics-vs-throughput trade-off** discussion: Ollama is the easiest local-inference UX, but at non-trivial throughput cost. Relevant for the demo / API-surface decision (Layer 4) — if the thesis ships a demo, Ollama may be the right choice for "user installs in 30 seconds" even if its throughput is ~5× slower than direct MLX.
