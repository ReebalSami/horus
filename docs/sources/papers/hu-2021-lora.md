---
source_url: "https://arxiv.org/abs/2106.09685"
source_title: "LoRA: Low-Rank Adaptation of Large Language Models"
source_author: "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen"
source_date: "2021-06-17"
retrieved_date: "2026-08-09"
extracted_concepts: ["low-rank adaptation", "parameter-efficient fine-tuning", "rank", "alpha scaling", "adapter merging", "frozen base weights"]
tags: ["peft", "lora", "fine-tuning", "adaptation", "method-origin", "adr-067", "adr-068"]
archived_pdf: ""
status: stub
---

LoRA (Microsoft) — the adaptation method HORUS uses for every structurer fine-tuning arm. Freezes the pre-trained weights and injects trainable rank-decomposition matrices into selected projection layers, so only the low-rank factors receive gradients. Two hyperparameters carry the method: the rank $r$ (capacity of the update) and $\alpha$ (a scaling factor applied as $\alpha/r$). Published as an arXiv preprint 2021-06-17; presented at ICLR 2022.

Cited in HORUS as the **method-of-record for the fine-tuning study** (ADR-067 recipe: rank 8, $\alpha$ 16, dropout 0.05, 258 target modules confined to the text tower; ADR-068 venue: CUDA + TRL/PEFT). Two properties of the method are load-bearing for the thesis argument. First, because the base weights are frozen and the update is low-rank, the *capacity* of the intervention is explicitly bounded — which is what makes "the adapter did not help" a statement about the recipe rather than about fine-tuning in general. Second, the $\alpha/r$ scaling is what made `trl`'s int-vs-float type check on `lora_alpha` a real defect rather than a cosmetic one (ADR-068): a rounded $\alpha$ silently changes the magnitude of every adapted forward pass.

This record was added 2026-08-09 during the thesis authoring phase. It closes a genuine archival gap: the entire fine-tuning chapter rests on this method and no source record existed for it, which `horus-source-archival` forbids at citation time.
