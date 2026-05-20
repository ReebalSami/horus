---
source_url: "https://developers.google.com/machine-learning/guides/rules-of-ml"
source_title: "Rules of Machine Learning: Best Practices for ML Engineering"
source_author: "Martin Zinkevich (Google)"
source_date: "2018"
retrieved_date: "2026-05-20"
extracted_concepts: ["measure-delta-between-models", "stability-self-check", "feature-engineering-discipline", "training-serving-skew"]
tags: ["machine-learning", "best-practices", "google-developers", "methodology", "primary-source", "adr-016"]
archived_pdf: ""
status: stub
---

Authoritative ML engineering guide from Google, originally a Google internal training document, later published publicly. Covers 43 numbered rules across Phase I (first pipeline), Phase II (feature engineering), and Phase III (slowed growth + optimization refinement). Widely cited in industry ML methodology (academic + industrial); the closest thing to a canonical "best practices" reference outside academic textbooks.

**Cited by HORUS in ADR-016** for two specific rules:

- **Rule #23** ("You are not a typical end user") — informs the dev-loop substrate design: the developer iterating on adapters is too close to the code to evaluate quality on the dev set alone; final F1 numbers must come from a held-out test split (issue #46 substrate). The `dev_only=true` schema field (ADR-016 chunk 1) encodes this discipline as a forcing function.

- **Rule #24** ("Measure the delta between models") — directly endorses the side-by-side baseline-vs-candidate Δ pattern implemented in `scripts/rescore.py`. Verbatim quote:

  > *"One of the easiest and sometimes most useful measurements you can make before any users have looked at your new model is to calculate just how different the new results are from production... If the difference is very small, then you can tell without running an experiment that there will be little change. If the difference is very large, then you want to make sure that the change is good. Looking over queries where the symmetric difference is high can help you to understand qualitatively what the change was like. Make sure, however, that the system is stable. Make sure that a model when compared with itself has a low (ideally zero) symmetric difference."*

The "model compared with itself" sanity-check sentence is the canonical reference for the stability self-check implemented in `scripts/rescore.py::load_adapter_pair` (when candidate is missing OR byte-identical to baseline, Δ must be exactly 0; non-zero signals a non-determinism bug).

Cross-references:

- ADR-016 §"Options considered" cites Rule #24 as the methodological precedent for the A/B side-by-side design.
- ADR-016 §"Decision + integration thoughts" cites Rule #23 + #24 as the justification for the `dev_only=true` HARKing-prevention guard + the stability self-check.

License: Google Developers content (terms apply to the documentation page; this stub records the citation, no content is reproduced beyond fair-use quotation).
