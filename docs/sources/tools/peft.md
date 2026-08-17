---
source_url: "https://github.com/huggingface/peft"
source_title: "PEFT — Parameter-Efficient Fine-Tuning methods for large pretrained models"
source_author: "Hugging Face Inc. + open-source contributors"
source_date: "2026-07"
retrieved_date: "2026-08-09"
extracted_concepts: ["LoraConfig", "target_modules", "adapter serialization", "get_peft_model", "trainable parameter accounting"]
tags: ["peft", "lora", "fine-tuning", "huggingface", "adr-068", "cuda"]
archived_pdf: ""
status: stub
---

PEFT (Hugging Face) — the library that materialises the ADR-067 LoRA recipe. Pinned in `pyproject.toml` as `peft>=0.18.0`, inside the `[dependency-groups]` CUDA training extra rather than the base runtime, because delivered inference is fully local and never loads an adapter.

Cited in HORUS for three concrete reasons. `LoraConfig` is where rank, $\alpha$, dropout and `target_modules` are declared, so the recipe lives in configuration rather than in a hand-rolled training loop — which is what let the pre-registration in ADR-067 be checked mechanically against what actually ran. Its trainable-parameter accounting is the evidence for the claim that the intervention touched 258 modules confined to the text tower and left the vision tower frozen. And its adapter serialisation format is what made the two arms directly comparable: both adapters are the same shape over the same frozen base, so the 2×2 evaluation grid varies only the training input distribution.

Ships `py.typed`, so the configuration surface is type-checked in this project's `mypy` run (ADR-068).

Added 2026-08-09 during thesis authoring to close the archival gap noted alongside `hu-2021-lora`.
