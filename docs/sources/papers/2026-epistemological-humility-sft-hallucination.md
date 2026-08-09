---
source_url: "https://arxiv.org/abs/2603.17504"
source_title: "Inducing Epistemological Humility in Large Language Models: A Targeted SFT Approach to Reducing Hallucination"
source_author: "(TBD — first-author + co-authors to confirm at deep-read prior to thesis-citation)"
source_date: "2026-03"
retrieved_date: "2026-08-09"
extracted_concepts: ["SFT implicitly rewards always responding", "epistemological humility", "uncertainty vector", "controlled LoRA SFT sweep"]
tags: ["fine-tuning", "sft", "lora", "hallucination", "abstention", "gemma"]
archived_pdf: ""
status: stub
---

States the premise HORUS measured directly: LLMs hallucinate *"partly because supervised
fine-tuning (SFT) implicitly rewards always responding"* — discouraging the admission of
ignorance. Introduces an SFT dataset built from questions about non-existent ("hypothetical")
terms to teach generalized uncertainty recognition, decoupled from specific factual content,
and reports a mechanistic finding that the learned behaviour is carried by an **orthogonal
uncertainty vector in the residual stream**, geometrically separate from knowledge and safety
representations.

Two reasons it is the closest methodological neighbour to ADR-067:

1. **Same model family, same adaptation method, same direction of concern.** The study runs
   **800 controlled LoRA SFT runs across Llama3.1-8B and Gemma3-4B** (base and instruct) with
   paired controls. HORUS fine-tuned `gemma-4-E4B-it` with LoRA and observed the
   always-respond bias appear as a *measured* rate (`spurious_emission` 0.1575 → 0.2012)
   rather than as a benchmark score.
2. **It shows the bias is fixable by data composition, not by hyperparameters.** Their lever
   is replacing generic instruction data with humility-teaching examples. HORUS's analogue —
   and the honest future-work statement — is training with a materially higher share of
   honest-null examples, since the 100-invoice set was mostly-populated by construction. This
   is preferable to the sweep ADR-067 clause 6 forbids, because it is a *hypothesis about the
   data* rather than a search over configurations.

Contrast to record in Ch. 8: their setting rewards a *linguistic* refusal ("I don't know");
HORUS's schema already encodes absence as a typed null that the scorer grades, so abstention
needs no special vocabulary and no special metric.

Cite-as-stub per `horus-source-archival`. Author/venue confirmation deferred to the Ch. 8
deep-read.
