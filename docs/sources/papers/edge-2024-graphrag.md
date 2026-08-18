---
source_url: "https://arxiv.org/abs/2404.16130"
source_title: "From Local to Global: A Graph RAG Approach to Query-Focused Summarization"
source_author: "Edge, Darren; Trinh, Ha; Cheng, Newman; Bradley, Joshua; Chao, Alex; Mody, Apurva; Truitt, Steven; Larson, Jonathan"
source_date: "2024-04-24"
retrieved_date: "2026-05-06"
verified_date: "2026-08-18"
extracted_concepts: ["GraphRAG", "query-focused summarization", "graph-structured retrieval", "community detection", "global vs local queries"]
tags: ["graphrag", "rag", "retrieval", "knowledge-graph", "summarization", "microsoft", "primary-paper", "layer-3"]
archived_pdf: ""
status: verified
verified: [authors, title, arxiv-id]
---

> **Created 2026-08-18** (fifth-pass audit, F7). This record did not exist, although
> `edge2024graphrag` is cited three times in the manuscript. The nearest existing
> record, `docs/sources/tools/microsoft-graphrag.md`, covers the **GraphRAG library**
> (github.com/microsoft/graphrag) as a Layer-3 baseline candidate — not this paper.
> The bibliography header asserts that every entry is backed by a record under
> `docs/sources/<type>/`, and the project's own archival rule holds that a citation
> without a completed record is "a citation this project is not entitled to make",
> so the assertion was false for this entry until now.

Edge et al. 2024 — the paper that introduced **GraphRAG**: instead of retrieving flat
text chunks, build an entity-and-relation graph over the corpus, detect communities
within it, pre-generate community summaries, and answer a query by map-reducing over
those summaries. The motivating distinction is between **local** questions (answerable
from a few chunks, which conventional vector RAG already handles) and **global** ones
(requiring aggregation across a whole corpus, where chunk retrieval has nothing to
retrieve). Query-focused summarization is the evaluation task.

## Why cited in HORUS

Cited three times, always as *design input for layers this thesis specified but did not
build*, and never as a result this thesis relies on:

- **§2.3** (background vocabulary) — paired with `han2025` to establish that the
  graph-versus-flat retrieval question is "an active and unsettled question rather than
  a settled result". Both citations exist to keep the Layer-2/3 vocabulary honest.
- **§3.4** (related work, knowledge-graph layer) — one of three works that shaped the
  unbuilt Layer-2/3 design.
- **§4.3** (system design) — supports the design principle that *retrieval strategy is a
  question to be measured, not assumed*, motivating per-question routing rather than
  committing to one mechanism.

The pairing with `han2025` is deliberate and load-bearing: Han et al. report GraphRAG
**under-performing** vanilla vector RAG on single-hop QA at ~2.3× the latency, so citing
Edge et al. alone would overstate the case for a graph layer. Together they support the
thesis's actual position — the graph is a hypothesis, registered and unevaluated (ADR-054
scope freeze), not a claimed benefit.

## Relationship to the library record

`docs/sources/tools/microsoft-graphrag.md` is the implementation; this is the paper.
Kept separate deliberately: the thesis cites the paper for the *idea* and would cite the
library only if Layer 3 were built, which it was not.
