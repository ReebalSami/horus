---
source_url: "https://arxiv.org/abs/2005.04118"
source_title: "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList"
source_author: "Marco Tulio Ribeiro, Tongshuang Wu, Carlos Guestrin, Sameer Singh"
source_date: "2020-05-08"
retrieved_date: "2026-05-21"
extracted_concepts:
  - "multi-dimensional-capability-reporting"
  - "behavioural-testing-vs-aggregate-metric"
  - "no-single-number-summary"
tags: ["evaluation-methodology", "behavioural-testing", "ACL-2020-best-paper"]
archived_pdf: ""
status: stub
---

CheckList — ACL 2020 best-paper that argued for replacing aggregate accuracy with multi-dimensional capability reports. Adopted in HORUS at ADR-021 §"Decision" as precedent for the 2 × 2 verdict matrix shape: rather than report a single pass/fail per probe, report across the orthogonal methodology dimensions (threshold variant × denominator variant). The reader sees the disagreement between dimensions and can decide which lens is most appropriate for their downstream question.

Cited at:

- ADR-021 §"Decision" §"Option 2 (dual verdict)" (multi-dimensional reporting precedent alongside HELM §6)
- `docs/retros/m2d.5-structured-output-probe.md` §"Post-audit amendment" §"Cross-project candidates"

To populate via Obsidian web-clipper: visit `https://arxiv.org/abs/2005.04118`, clip §3 "CheckList" + §4 "Testing the Capabilities" + §5 "User Studies", and replace this stub.
