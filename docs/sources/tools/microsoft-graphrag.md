---
source_url: "https://github.com/microsoft/graphrag"
source_title: "GraphRAG (Microsoft) — original graph-based RAG framework"
source_author: "Microsoft Research"
source_date: "2024"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["graphrag", "microsoft", "rag", "knowledge-graph", "heavyweight", "layer-3-baseline"]
archived_pdf: ""
status: stub
---

GraphRAG (Microsoft) — the original heavyweight graph-RAG framework. Builds an LLM-extracted KG from a corpus, then performs community-based hierarchical summarization for retrieval. Cited in HORUS as the **Layer-3 heavyweight baseline** to be benchmarked against LightRAG (hybrid) and HippoRAG (multi-hop) per brainstorm v2 §7.3. Han et al. 2025's finding that GraphRAG often LOSES to vanilla vector RAG on standard QA benchmarks (~13.4% lower accuracy on Natural Questions, ~2.3× higher latency) is the literature-consensus pivot that motivates why GraphRAG is a baseline rather than the chosen architecture.
