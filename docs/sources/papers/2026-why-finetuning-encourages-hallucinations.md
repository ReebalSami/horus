---
source_url: "https://arxiv.org/abs/2604.15574"
source_title: "Why Fine-Tuning Encourages Hallucinations and How to Fix It"
source_author: "Guy Kaplan, Zorik Gekhman, Zhen Zhu, Lotem Rozner, Yuval Reif, Swabha Swayamdipta, Derek Hoiem, Roy Schwartz"
source_date: "2026-04"
retrieved_date: "2026-08-09"
extracted_concepts: ["SFT-induced hallucination", "stability-plasticity tradeoff", "self-distillation", "parameter freezing", "representation interference"]
tags: ["fine-tuning", "sft", "hallucination", "continual-learning", "negative-result"]
archived_pdf: ""
status: stub
---

Frames SFT-induced hallucination as a **stability–plasticity tradeoff** borrowed from the
continual-learning literature: parameter updates that acquire new facts distort
representations of facts learned in pre-training, so models begin answering incorrectly
questions they previously answered correctly. Investigates three candidate mechanisms
(capacity limits, behaviour cloning, localized interference) and reports that the dominant
driver is **interference among overlapping semantic representations**. Two mitigations:
self-distillation to regularize output-distribution drift, and — where new knowledge
acquisition is unnecessary — **freezing parameter groups to suppress factual plasticity**,
which preserves task performance while reducing hallucination.

Why it matters here: the second mitigation is the theoretical argument for *not* fine-tuning
HORUS's structurer at all. The ADR-067 study needed no new factual knowledge — the schema and
the field semantics were already available zero-shot (0.9778 on oracle input) — so on this
paper's account the adaptation carried the interference cost with no offsetting plasticity
benefit. That is a principled reading of why the cheapest correct outcome was the one ADR-054
§4 pre-registered as acceptable: *LoRA skipped and recorded as not-needed.*

Useful for Ch. 8's "what would we do differently" paragraph, and for framing the future-work
option of adapting the **reader** rather than the structurer.

Cite-as-stub per `horus-source-archival`. Author/venue confirmation deferred to the Ch. 8
deep-read.
