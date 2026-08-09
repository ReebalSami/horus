---
source_url: "https://arxiv.org/abs/2403.05612"
source_title: "Unfamiliar Finetuning Examples Control How Language Models Hallucinate"
source_author: "(TBD — first-author + co-authors to confirm at deep-read prior to thesis-citation)"
source_date: "2024-03"
retrieved_date: "2026-08-09"
extracted_concepts: ["hedged prediction", "unfamiliar finetuning examples", "SFT-induced hallucination", "abstention relabeling"]
tags: ["fine-tuning", "sft", "hallucination", "lora", "negative-result", "abstention", "structured-extraction"]
archived_pdf: ""
status: stub
---

**The mechanistic explanation for HORUS's negative LoRA result (ADR-067).** Finds that
fine-tuned LLMs do not produce arbitrary predictions on unfamiliar inputs; instead their
predictions collapse toward a **hedged prediction** that minimizes aggregate finetuning loss
over the unfamiliar examples — i.e. toward *"the distribution of ground-truth answers
associated with unfamiliar finetuning examples."* Consequently the model emits a
plausible-sounding answer rather than admitting ignorance. The paper's proposed remedy is to
relabel unfamiliar finetuning queries with "I don't know"-style responses, which steers the
default hedge toward abstention.

Why it matters here: ADR-067's 2×2 LoRA study trained on **100 mostly-populated** ZUGFeRD
invoices and measured `spurious_emission` (ADR-027) rising **0.1575 → 0.2012** on reader
input while flat micro-F1 barely moved (0.8843 → 0.8798) — the damage concentrated in fields
whose correct answer is *absent*. That is precisely this paper's predicted mechanism: the
training distribution taught the model that emitting a value is usually right, so the default
hedge became "emit". It also explains the otherwise-counterintuitive observation that the
**oracle-trained** adapter regressed *less* on reader input (−0.0126 vs −0.0234): with no
reader noise in its training text it acquired less of the over-emission habit.

Scope difference worth stating in the thesis: this work studies factual QA, where abstention
is a special behaviour to be taught. HORUS's setting is **structured extraction, where
"absent" is already a first-class legitimate answer** and is scored — so the phenomenon is
directly measurable as a rate rather than inferred from hallucination judgements. That gap is
the contribution angle for Ch. 8.

Cite-as-stub per `horus-source-archival` (stub-then-clip; frontmatter matches
Obsidian-web-clipper output shape). Author/venue confirmation deferred to the Ch. 8 deep-read.
