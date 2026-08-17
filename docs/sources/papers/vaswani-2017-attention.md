---
source_url: "https://arxiv.org/abs/1706.03762"
source_title: "Attention Is All You Need"
source_author: "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin"
source_date: "2017-06-12"
retrieved_date: "2026-08-09"
extracted_concepts: ["self-attention", "multi-head attention", "encoder-decoder", "positional encoding", "quadratic sequence cost"]
tags: ["architecture", "transformer", "foundational", "background"]
archived_pdf: ""
status: stub
---

The Transformer (Google Brain / Google Research) — the architecture underlying every model in this thesis, on both sides of the pipeline. NeurIPS 2017. Replaces recurrence and convolution with self-attention, so that the representation of each position is computed from a weighted combination of all positions in the sequence.

Cited in HORUS **as background only**, to establish two facts the later chapters depend on. First, both stages of the Layer 1 pipeline are Transformer decoders over a shared token stream, which is why a reading error and a structuring error are not separable by architecture and had to be separated by experiment instead (the attribution design). Second, attention cost grows quadratically with sequence length, which is the reason the structurer runs under a fixed token budget (`max_length` 6144) and the reason a token-budget defect was able to depress an entire measurement arm before it was found — the budget is not an arbitrary configuration value but a direct consequence of the architecture.

Added 2026-08-09 during thesis authoring to satisfy `horus-source-archival` for the background chapter.
