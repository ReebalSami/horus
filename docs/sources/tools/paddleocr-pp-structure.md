---
source_url: "https://github.com/PaddlePaddle/PaddleOCR"
source_title: "PP-Structure — classical modular orchestrated document-parsing pipeline (PaddleOCR ecosystem)"
source_author: "Baidu PaddlePaddle"
source_date: ""
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["pp-structure", "paddleocr", "orchestrated-pipeline", "modular", "classical-cv", "layout-analysis", "ocr", "table-recognition", "chinese-origin-pretraining"]
archived_pdf: ""
status: stub
---

PP-Structure — the classical modular orchestrated document-parsing pipeline within Baidu's PaddleOCR ecosystem (Apache 2.0). Combines layout analysis + text detection + text recognition + table structure recognition + key-value pair extraction as separate model stages. **Distinct from the newer single-shot `PaddleOCR-VL` 1.5** (covered in `paddleocr-vl.md`): PP-Structure represents the orchestrated-specialist architecture, while PaddleOCR-VL is the single-shot small-VLM architecture.

Cited in HORUS ADR-008 as **considered cross-check candidate** for the orchestrated-baseline. **Caveat**: Chinese-origin pretraining is a documented concern for German-invoice ground-truth evaluation — verification gate at pilot loop #13. Pre-Oct-2025-wave architectural lineage (mature, stable, but classical CV models). Not chosen as the cross-check companion in ADR-008 (lean toward MinerU pipeline backend with same Chinese-origin caveat but newer 2025–26 lineage); preserved as fallback if MinerU has Apple-Silicon install friction or if pilot reveals Docling+MinerU systematic Chinese-pretraining bias.
