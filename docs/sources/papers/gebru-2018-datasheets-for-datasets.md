---
source_url: "https://arxiv.org/abs/1803.09010"
source_title: "Datasheets for Datasets"
source_author: "Timnit Gebru, Jamie Morgenstern, Briana Vecchione, Jennifer Wortman Vaughan, Hanna Wallach, Hal Daumé III, Kate Crawford"
source_date: "2018-03-23"
retrieved_date: "2026-05-25"
extracted_concepts: ["datasheets", "dataset-documentation", "ml-transparency", "responsible-ai", "research-practice"]
tags: ["methodology", "scientific-correctness", "dataset-documentation", "datasheets-for-datasets", "ml-research-practice", "adr-025"]
archived_pdf: ""
status: stub
---

Gebru et al. 2018 — *Datasheets for Datasets* (arXiv:1803.09010; ACM CACM 64(12), 86–92, 2021). Foundational paper proposing standardized dataset documentation for machine-learning research, modelled on the electronics-industry datasheet (every component, no matter how simple, ships with a datasheet documenting its operating characteristics, recommended uses, and known limitations). The paper proposes ~50 questions structured into seven canonical sections:

1. **Motivation** — for what purpose was the dataset created?
2. **Composition** — what do the instances represent? how many? what are the schemas / labels / annotations?
3. **Collection process** — how was the data acquired? what was the sampling strategy? who was involved?
4. **Preprocessing / cleaning / labeling** — was the raw data preprocessed? if so, how? labeling instructions / inter-annotator-agreement?
5. **Uses** — what tasks has the dataset been used for? for what tasks should it NOT be used?
6. **Distribution** — how is the dataset distributed? license? maintainer?
7. **Maintenance** — who hosts? for how long? versioning? errata channel?

The paper has been highly influential: cited >3000 times as of 2025; adopted by major ML conferences (NeurIPS Datasets and Benchmarks Track requires Datasheet-style documentation); inspired derivative templates (Hugging Face Hub Dataset Cards, Google's Model Cards for Model Reporting at Mitchell et al. 2019, Bender & Friedman's Data Statements for NLP). The `bridge2ai/data-sheets-schema` GitHub project provides a machine-readable schema mirroring the paper's questions.

**Role in HORUS (per ADR-025)** — the canonical per-dataset documentation template adopted across all 7 chapters of the EDA Quarto Book. Each chapter of `experiments/0X-<slug>.py` ends with a Datasheet appendix entry (consolidated in `experiments/A1-datasheets.qmd`) covering Gebru's seven canonical sections; the 50+ canonical questions are answered for each dataset where they apply (with explicit "N/A — see <reason>" for those that don't). Adopting Datasheets-for-Datasets mid-thesis is cheaper than retrofitting it post-defense, and aligns the EDA artifact with academic norms expected at thesis defense (FH Wedel SS 2026).

**Mirrors / archives**:
- arXiv: `https://arxiv.org/abs/1803.09010` (canonical; perpetual irrevocable license)
- arXiv PDF: `https://arxiv.org/pdf/1803.09010`
- Microsoft Research: `https://www.microsoft.com/en-us/research/wp-content/uploads/2019/01/1803.09010.pdf`
- ACM CACM: `https://cacm.acm.org/research/datasheets-for-datasets/` (December 2021 expanded version)

**Adjacent / derivative works** (not adopted directly in HORUS but worth flagging):
- Mitchell et al. 2019 — *Model Cards for Model Reporting* (FAT*) — sibling standard for model documentation; potentially relevant for the HORUS thesis's results chapter when documenting fine-tuned VLMs.
- Bender & Friedman 2018 — *Data Statements for NLP* — narrower focus on language datasets; the HORUS substrate is multilingual + multimodal, so Datasheets is the broader fit.
- Pushkarna et al. 2022 — *Data Cards* (Google) — operational adaptation of Datasheets for production ML pipelines; less aligned with thesis-grade research-corpus documentation.
