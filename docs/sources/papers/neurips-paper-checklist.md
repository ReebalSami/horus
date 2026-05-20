---
source_url: "https://neurips.cc/public/guides/PaperChecklist"
source_title: "NeurIPS Paper Checklist Guidelines (2024 / 2025)"
source_author: "NeurIPS conference organizing committee"
source_date: "2024"
retrieved_date: "2026-05-20"
extracted_concepts: ["pre-registered-hypotheses", "no-harking", "reproducibility-checklist", "limitations-disclosure"]
tags: ["machine-learning", "methodology", "reproducibility", "neurips", "no-harking", "primary-source", "adr-016"]
archived_pdf: ""
status: stub
---

The NeurIPS Paper Checklist is the canonical reproducibility + methodological-rigor questionnaire that NeurIPS submissions have been required to complete since 2021 (formalized + tightened in 2024/2025). It enumerates ~15 questions across four categories: **Claims** (do they match the experimental scope?), **Limitations** (explicit assumptions disclosed?), **Reproducibility** (data + code + compute described in enough detail to replicate?), and **Ethics** (broader-impact + societal-risk + responsible-release considerations).

Two principles from the checklist load-bear on HORUS's methodology, cited across multiple ADRs + retros:

- **No HARKing** (Hypothesizing After the Results are Known) — the experimental hypothesis set MUST be defined BEFORE looking at the data. In HORUS, this is enforced via brainstorm v2 §6 H1–H6 pre-registration (timestamped 2026-05-08) + the `dev_only=true` schema field (ADR-016) + the train/test/dev split tier separation (issue #46 substrate). The dev cohort is for ITERATIVE tuning ONLY; final reported F1 numbers come from the held-out test split.

- **Claims must match evidence** — every numeric claim in the thesis writeup must trace back to a specific experimental run (with reproducible config, seed, hardware fingerprint). HORUS's MLflow integration (ADR-011) + per-run tag manifest (ADR-014) + `dev_only` audit-trail tagging (ADR-016) together provide the substrate for this discipline.

Cross-references:

- Brainstorm v2 §2 ("No HARKing") — the pre-registered hypothesis discipline that ADR-016's `dev_only` forcing function enforces at the harness layer.
- ADR-016 §"Decision + integration thoughts" — the `dev_only` schema field + `_CANONICAL_PRODUCTION_EXPERIMENTS` block are direct implementations of the NeurIPS Paper Checklist's no-HARKing discipline.
- `docs/retros/m2d.5-mid-heartbeat-2026-05-19.md` + `~/.codeium/windsurf/memories/global_rules.md` `make-sure-it-works` — cite the checklist as the canonical reference for "evidence over claims".

Supporting arxiv references cited alongside the checklist in HORUS's brainstorm + retro corpus:

- `arxiv:2406.14325` — *"Reproducibility in Machine-Learning-based Research"* (June 2024) — empirical study of ML reproducibility practices.
- `arxiv:2503.08124` — *"Confirmatory Methodological Research"* (March 2025) — pre-registration discipline for ML.
- NERVE-ML checklist (April 2025) — neural engineering reproducibility + validity counterpart.

License: NeurIPS conference materials (publicly available checklist guidelines; this stub records the citation, no content is reproduced beyond fair-use quotation).
