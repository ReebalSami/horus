---
source_url: "https://medium.com/@rentierdigital/json-prompting-is-dead-15-failure-rate"
source_title: "JSON Prompting for LLMs Is Broken — 15% Failure Rate"
source_author: "(Medium — @rentierdigital; pseudonym; not authoritative-source-class)"
source_date: "2025"
retrieved_date: "2026-05-21"
extracted_concepts: []
tags: ["json-prompting", "llm-instruction-following", "format-drift", "structured-output"]
archived_pdf: ""
status: stub
---

Medium article reporting that manual JSON prompting fails 15-20% of the time even on instruction-tuned LLMs (format drift dominates: trailing commas, markdown fences, extra commentary, hallucinated keys). Cited in HORUS ADR-018 §"Current-state survey" as the **failure-rate prior**: even Gemma-4-E4B-it (the most JSON-friendly model in the 7-model cohort) is expected to have a non-trivial failure rate on the probe, so the threshold for "adheres" allows partial-validity (parses + has ≥12 canonical keys) rather than strict 16/16 schema conformance. **Provenance caveat**: Medium articles are NOT authoritative-source-class for thesis citations; this article informs design intuition but the thesis itself will cite peer-reviewed equivalents (arXiv:2509.04469 + Poznanski+ 2025) for the same point. Status: stub; if the thesis ends up citing this article in §5 (related work), upgrade to a peer-reviewed equivalent OR clip the full Medium HTML via Obsidian web-clipper at that time.
