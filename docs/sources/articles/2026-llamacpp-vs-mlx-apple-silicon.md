---
source_url: "https://medium.com/@michael.hannecke/llama-cpp-vs-mlx-on-apple-silicon"
source_title: "Llama.cpp vs MLX on Apple Silicon"
source_author: "(Medium — @michael.hannecke; not authoritative-source-class)"
source_date: "2026"
retrieved_date: "2026-05-21"
extracted_concepts: []
tags: ["mlx", "apple-silicon", "constrained-decoding", "gbnf", "xgrammar", "structured-output"]
archived_pdf: ""
status: stub
---

Medium article comparing llama.cpp and MLX on Apple Silicon stacks. Cited in HORUS ADR-018 §"Current-state survey" for the **load-bearing constraint** verbatim: *"MLX has no equivalent [to GBNF / XGrammar constrained decoding] in the core stack. Custom samplers possible but nobody has shipped a polished version. For agent work where you need a JSON object with a specific shape, this is invaluable."* This justifies why HORUS's structured-output probe is PROMPT-ONLY (no grammar-based constrained decoding): the existing local-VLM inference stack (MLX-VLM on M1 Pro per ADR-007) provides no path to constrained decoding without writing a custom sampler from scratch — out of scope for issue #53. **Provenance caveat**: Medium article; supporting evidence verified by inspecting `mlx_vlm.generate` API surface (no `grammar` / `outlines` / `lm-format-enforcer` integration as of mlx-vlm 0.1.x) + the absence of any MLX-side equivalent to llama.cpp's GBNF or vLLM's XGrammar integration. Status: stub; if the thesis cites this in §3 (system constraints), upgrade to the MLX-VLM upstream README OR clip the full Medium HTML via Obsidian web-clipper at that time.
