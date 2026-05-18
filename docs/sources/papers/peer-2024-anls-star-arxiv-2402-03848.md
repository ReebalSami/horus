---
source_url: "https://arxiv.org/abs/2402.03848"
source_title: "ANLS* — A Universal Document Processing Metric for Generative Large Language Models"
source_author: "David Peer, Philemon Schöpf, Volckmar Nebendahl, Alexander Rietzler, Sebastian Stabinger"
source_date: "2024-02"
retrieved_date: "2026-05-18"
extracted_concepts: ["ANLS*", "dict-structured outputs", "missing-key semantics", "hallucination penalty", "list-aware matching"]
tags: ["metric", "anls-star", "document-ai", "generative-llm", "evaluation", "adr-013", "pilot-13"]
archived_pdf: ""
status: stub
---

Peer et al., **"ANLS\* — A Universal Document Processing Metric for Generative Large Language Models"** (arXiv 2402.03848, Feb 2024). Extends Biten et al.'s **ANLS** (ICCV 2019) to handle the dict-structured outputs typical of modern generative document-AI systems. Key extensions:

1. **Dict-aware**: ANLS\* over `{"key": "value"}` mappings; supports nested dicts and lists.
2. **Missing-key penalty**: when prediction omits a GT key (or invents an extra key), the metric assigns 0 for that cell — no longer a silent skip.
3. **Hallucination guard**: scores invented fields as 0 in the numerator, preventing models from gaming the metric by emitting extra content.
4. **Backward-compatible**: on flat string pairs, ANLS\* reduces to plain ANLS.

**Role in HORUS (per ADR-013)**: cited as the **canonical document-AI evaluation framework** for generative VLM systems extracting structured fields. HORUS's pilot #13 scorer uses **plain ANLS** for per-field strings (the per-field comparator operates on flat string pairs, where ANLS\* and ANLS coincide) — ANLS\* dict-mode is reserved for a future amendment if line-items (BG-25) land, at which point the predicted line-item array would benefit from ANLS\*'s list-aware matching.

**ADR cross-references**:
- ADR-013 §"Decision + integration thoughts" cites this paper as the dict-aware extension reference
- ADR-013 §"Supersession trigger" notes that line-item support (BG-25) would require swapping to `anls_dict()` from `anls()` in the comparator

**What HORUS does NOT take from this paper**: the specific generative LLM benchmarks (HORUS uses local VLMs not LLMs); the absolute ANLS\* numbers from the paper's experiments (different cohorts + different corpora).

**Stub note**: full PDF citation pending Obsidian Web Clipper pass. arXiv ID 2402.03848 is firm.
