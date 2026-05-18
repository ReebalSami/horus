---
source_url: "https://openaccess.thecvf.com/content_ICCV_2019/papers/Biten_Scene_Text_Visual_Question_Answering_ICCV_2019_paper.pdf"
source_title: "Scene Text Visual Question Answering"
source_author: "Ali Furkan Biten, Rubèn Tito, Andres Mafla, Lluis Gomez, Marçal Rusiñol, Ernest Valveny, C.V. Jawahar, Dimosthenis Karatzas"
source_date: "2019-10"
retrieved_date: "2026-05-18"
extracted_concepts: ["ANLS", "Average Normalized Levenshtein Similarity", "OCR-tolerant metric", "threshold-0.5"]
tags: ["metric", "anls", "ocr-evaluation", "vqa", "scene-text", "iccv-2019", "adr-013", "pilot-13"]
archived_pdf: ""
status: stub
---

Biten et al., **"Scene Text Visual Question Answering"** (ICCV 2019). Defines the **ANLS** (Average Normalized Levenshtein Similarity) metric for OCR-tolerant evaluation of VQA systems where predictions must match noisy OCR-derived ground truth. ANLS = `max(0, 1 - LD(pred, gt) / max(|pred|, |gt|))` with a **threshold of 0.5** — predictions scoring below threshold collapse to 0 (penalizes severe OCR errors); predictions at or above threshold report their NLS as the soft score.

**Role in HORUS (per ADR-013)**: cited as the **canonical OCR-tolerant string-matching metric** for pilot #13's per-field F1 scorer. The `STRING` field-type comparator (used for `seller_name` and `buyer_name`) applies ANLS with the literature-default threshold 0.5 — tolerates character-level OCR errors like "Lieferent" vs "Lieferant" (NLS ≈ 0.89, above threshold → TP) while penalizing severe errors like "Lederart" vs "Lieferant" (NLS ≈ 0.39, below threshold → 0 → FN). The threshold is exposed as a YAML knob (`eval.anls_threshold` in `EvalConfig`) per `horus-config-discipline`.

**ADR cross-references**:
- ADR-013 §"Decision + integration thoughts" cites this paper as the metric definition source
- `src/horus/eval/anls.py` module docstring cites the threshold-0.5 rationale

**Extension**: Peer et al. 2024 (arXiv 2402.03848) extend ANLS to **ANLS\*** for dict-structured outputs with missing-key semantics. HORUS uses plain ANLS for per-field strings; ANLS\* dict-mode is reserved for a future amendment if line-items (BG-25) land.

**Stub note**: paper PDF citation is from the CVF open-access proceedings (ICCV 2019). Full BibTeX + DOI to be verified on next clip pass.
