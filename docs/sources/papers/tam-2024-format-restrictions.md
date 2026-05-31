---
source_url: "https://arxiv.org/abs/2408.02442"
source_title: "Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models"
source_author: "Zhi Rui Tam et al. (arXiv 2408.02442 — full authorship to verify on next clip pass)"
source_date: "2024-08"
retrieved_date: "2026-05-31"
extracted_concepts: []
tags: ["structured-output", "json", "format-restriction", "constrained-decoding", "llm-evaluation", "literature-anchor", "adr-030"]
archived_pdf: ""
status: stub
---

arXiv:2408.02442 (EMNLP 2024 industry track) — empirical study of how **format restrictions** (forcing JSON/XML output, constrained decoding, format-restricted instructions) affect LLM task performance. Headline finding: strict structured-generation modes can **degrade** reasoning-task accuracy (e.g., output misordering under strict JSON), i.e. structured output is **not a free win**; the paper compares constrained decoding, format-restricting-instructions (FRI), and NL-to-format conversion across datasets/models.

**Role in HORUS (ADR-030):** cited as the trustworthy external anchor for the gate's empirical observation that prompt-only JSON does not obviously beat free-form+adapter — and specifically that JSON mode can *reduce* what a model emits (HORUS in-house: gemma-4 reading-ceiling 0.96 free-form → 0.61 JSON, ADR-030 §Findings).

**Scope caveat (honest citation):** Tam et al. study *reasoning/classification* tasks and *constrained decoding* / format-restricting instructions. HORUS's "native JSON" arm is **prompt-only** (no constrained decoding — MLX has none available, per ADR-018) on a *field-extraction* task. So this paper corroborates the **general phenomenon** ("format restriction ≠ guaranteed improvement"), NOT a domain-identical result. Do not over-claim it as direct evidence for invoice extraction.

**Stability:** arXiv + EMNLP-published; the qualitative finding is stable. Full authorship + exact per-dataset deltas to be verified on the next Obsidian-clipper pass.
