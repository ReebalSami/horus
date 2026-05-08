---
source_url: "https://arxiv.org/abs/2501.00309"
source_title: "Retrieval-Augmented Generation with Graphs (GraphRAG) — empirical study"
source_author: "Haoyu Han et al."
source_date: "2025-01"
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["graphrag", "rag", "vector-rag", "retrieval", "knowledge-graph", "benchmark", "qa"]
archived_pdf: ""
status: stub
---

Han et al. 2025 — empirical study of GraphRAG vs. vanilla vector RAG on standard QA benchmarks. Reports: GraphRAG ~13.4% lower accuracy on Natural Questions, modest 4.5% gain on HotpotQA multi-hop, ~2.3× higher latency on average. Refutes the casual assumption that "graphs always help retrieval." Cited in HORUS as the **literature-consensus pivot point** for the Layer-3 design (per brainstorm v2 §7.3). The implication for HORUS: the headline question is NOT "does the graph help" (presumed yes) but "*when* does it help, *when* does it hurt, can we predict per query." Steers the thesis toward a per-query routing or hybrid Layer-3 (LightRAG-flavoured) rather than a graph-always Layer 3. arXiv ID to be confirmed at deep-read; the v2 brainstorm cites Han et al. 2025 by author + year.
