---
source_url: "https://github.com/huggingface/trl"
source_title: "TRL — Transformer Reinforcement Learning: post-training library for supervised fine-tuning, PPO, DPO and GRPO"
source_author: "Hugging Face Inc. + open-source contributors"
source_date: "2026-07"
retrieved_date: "2026-08-09"
extracted_concepts: ["SFTTrainer", "completion_only_loss", "load_best_model_at_end", "metric_for_best_model", "cosine schedule with warmup", "checkpoint selection"]
tags: ["trl", "sft", "fine-tuning", "huggingface", "adr-067", "adr-068", "checkpoint-selection"]
archived_pdf: ""
status: stub
---

TRL (Hugging Face) — the trainer used for both structurer LoRA arms. Pinned as `trl>=0.25.0` in the CUDA training dependency group.

Chosen over a hand-rolled loop for a reason that is methodological rather than ergonomic (ADR-068): **the entire ADR-067 selection rule is native configuration in `SFTTrainer`.** `load_best_model_at_end` with `metric_for_best_model="eval_loss"` implements "minimum dev loss selects the checkpoint" declaratively, so the pre-registered rule cannot drift from the executed rule. Cosine decay with warmup is likewise a scheduler argument. This makes the discipline better-tested than a bespoke loop would have been, not harder to audit.

Two of its type annotations caught real defects before any GPU time was spent, which is why the library is cited in the measurement-validity chapter and not only in implementation:

- `lora_alpha` is typed `int`; passing a float would have been silently rounded, changing the $\alpha/r$ scaling that governs every adapted forward pass.
- `completion_only_loss` defaults to `None` (auto-resolved), which decides whether the loss covers the roughly three-thousand-token prompt or only the completion. HORUS sets it explicitly to `True`; leaving it implicit would have made the training objective depend on a library default rather than on a recorded decision.

Ships `py.typed`.

Added 2026-08-09 during thesis authoring to close the archival gap noted alongside `hu-2021-lora`.
