---
source_url: "https://arxiv.org/abs/2311.11856"
source_title: "FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis and Understanding"
source_author: "Mahmoud Limam, Marwa Dhiaf, Yousri Kessentini"
source_date: "2023-11-20"
retrieved_date: "2026-08-16"
extracted_concepts: []
tags: ["dataset", "invoice", "synthetic", "multi-layout", "related-work"]
archived_pdf: ""
status: verified
---

**Full citation.** Limam, Dhiaf & Kessentini (2023), *FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis and Understanding*, arXiv **2311.11856**. Authors at the Digital Research Center of Sfax, Tunisia. Dataset at Zenodo record 8261508; the Hugging Face redistribution used in this project is `mathieu1256/FATURA2-invoices`, whose own dataset card cites this paper.

**Content.** 10,000 synthetic invoice images generated from **50 distinct templates** (200 per template), with 3×10,000 JSON annotation files in three formats (own schema, COCO, and a LayoutLMv3-compatible HuggingFace format). **24 field classes**, deliberately imbalanced. Two evaluation strategies are provided: intra-template (new content, seen layouts) and inter-template (unseen layouts).

**Authorship correction, 2026-08-16 (third-pass thesis review).** `thesis/references.bib` previously credited this dataset to **"Brandt, Mathieu"** with year 2024. There is no such author: `mathieu1256` is the Hugging Face account name of the redistribution, and the entry had been built from the account handle rather than from the work. This is the same defect class as the fabricated title caught earlier in the `cai2025` entry, and it is why the bibliography's blanket "verified against the primary source" claim has been qualified in place.

**How the thesis uses it.** Chapter 3 §"Benchmarks and corpora" cites it as a public invoice corpus that does **not** cover the thesis's setting: synthetic, and annotated over an invented 24-class list rather than a legally grounded schema. The corrected sentence now also states the scale (10,000 images), which the previous wording omitted while the corpus was being contrasted with this thesis's 146-document synthetic set.

Cited in `thesis/references.bib` as `fatura2`.
