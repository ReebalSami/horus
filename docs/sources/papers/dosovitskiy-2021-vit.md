---
source_url: "https://arxiv.org/abs/2010.11929"
source_title: "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale"
source_author: "Alexey Dosovitskiy, Lucas Beyer, Alexander Kolesnikov, Dirk Weissenborn, Xiaohua Zhai, Thomas Unterthiner, Mostafa Dehghani, Matthias Minderer, Georg Heigold, Sylvain Gelly, Jakob Uszkoreit, Neil Houlsby"
source_date: "2020-10-22"
retrieved_date: "2026-08-09"
extracted_concepts: ["vision transformer", "patch embedding", "image tokenization", "resolution sensitivity", "vision tower"]
tags: ["architecture", "vision-transformer", "foundational", "background", "resolution"]
archived_pdf: ""
status: stub
---

Vision Transformer (Google Research, Brain Team) — establishes that an image can be treated as a sequence of fixed-size patches and fed to a standard Transformer encoder with no convolutional inductive bias. arXiv preprint 2020-10-22; ICLR 2021.

Cited in HORUS **as background** for the vision tower every candidate reader shares, and for one consequence that turns out to be central to the results. Because the image is tokenized into fixed-size patches, the number of pixels covered by each patch is fixed by the input resolution — so the legibility of small print (a footer VAT identifier, a compact IBAN, a till-receipt line) is a function of rasterization resolution and patch size, not of model capability. This is the mechanism behind the degraded-input finding: phone photographs lose 11.6 points of mean per-invoice F1 against email-native PDFs, and the manual findability audit repeatedly located misses in footer and letterhead regions rather than in the body of the page.

It also explains why the vision and audio towers could be frozen during fine-tuning without affecting the study's claim (ADR-068): the intervention targeted the text tower, so the reading pathway was held fixed by construction.

Added 2026-08-09 during thesis authoring to satisfy `horus-source-archival` for the background chapter.
