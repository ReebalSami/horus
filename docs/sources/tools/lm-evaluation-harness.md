---
source_url: "https://github.com/EleutherAI/lm-evaluation-harness"
source_title: "EleutherAI lm-evaluation-harness"
source_author: "EleutherAI"
source_date: ""
retrieved_date: "2026-05-21"
extracted_concepts:
  - "--log_samples-for-offline-rescore"
  - "--cache_requests-for-deterministic-reruns"
  - "saved-samples-as-canonical-evidence"
tags: ["evaluation-tool", "open-source", "offline-rescore-precedent"]
archived_pdf: ""
status: stub
---

EleutherAI lm-evaluation-harness — the de-facto open-source evaluation framework for language-model benchmarks (powers HuggingFace Open LLM Leaderboard, Lighteval, many academic evaluations). Adopted in HORUS at ADR-020 as the OSS precedent for the offline-rescore-from-saved-transcripts pattern:

- **`--log_samples` flag** — saves every model's raw output alongside per-sample metric scores. Lets future runs re-score the SAME samples against new metrics / new normalisation without re-running inference. This is exactly the pattern ADR-020 §"Pipeline change" implements via `scripts/rescore.py` extension: walk saved transcripts, rescore with fixed adapter.
- **`--cache_requests` flag** — when paired with a deterministic backend, lets reruns reproduce the exact same samples without re-invoking the model. The HORUS analogue is the saved-transcripts archive (`docs/sources/transcripts-*/`) — same canonical-evidence preservation pattern.

Cited at:

- ADR-019 §"Current-state survey" (saved-evidence precedent)
- ADR-020 §"Current-state survey" §"HELM + EleutherAI precedent" (load-bearing citation)
- `docs/retros/m2d.5-structured-output-probe.md` §"Post-audit amendment" §"NEW Tooling discovery"

To populate via Obsidian web-clipper: visit `https://github.com/EleutherAI/lm-evaluation-harness` README + §"Saving and Loading Samples" + the `--log_samples` flag documentation, and replace this stub.
