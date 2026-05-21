# ADR-020: Probe rescore methodology — offline-rescore-from-saved-transcripts + `rescore_of` MLflow tag convention

**Status**: Accepted
**Date**: 2026-05-21
**Parent**: ADR-019 (probe bug catalog) — Phase 4 reuse / methodology lock
**Siblings**: ADR-018 (parent probe), ADR-016 (parent `scripts/rescore.py` infrastructure), ADR-021 (verdict matrix amendments)

---

## Context

ADR-019 catalogued bugs in the structured-output probe pipeline (ADR-018) and ratified Wave 3.1 (multipage adapter API) + Wave 3.2 (verdict matrix module). The catalog's Phase 4 entry requires offline re-scoring of the saved probe transcripts against the FIXED adapter, producing NEW MLflow runs cross-linked to the original buggy runs. The methodology choices that govern this rescore — re-inference vs. offline rescore, MLflow-tagging convention, supersession rules — are load-bearing for the audit trail and the verdict matrix downstream. Locking them in their own ADR (this one) keeps ADR-019 focused on the bug catalog and gives the rescore policy supersession-trail anchorage of its own.

This ADR ratifies what was implemented in commits `0ccbf0f` (extension of `scripts/rescore.py`) + `22ec028` (`scripts/compute_probe_verdict.py` orchestrator + saved rescore artefacts in `eval/`).

---

## Current-state survey

### Pre-decision constraints (ADR-019 Phase 4 + locked decision D1)

User-locked decisions for the rescore (from the planning session 2026-05-21, captured in `~/.windsurf/plans/horus-probe-bug-cleanup-and-reverdict-4f44ea.md` §0):

- **D1 — Re-inference IN-SCOPE with strict gating**: extractor bugs (broken `max_new_tokens` / missing stop-token / wrong chat-template) require re-inference; model-behavior failures (decoder-loops on JSON OOD prompts) do not. Phase 1 audit concluded that the 3 suspected extractor bugs (B6 Granite / B7 PaddleOCR / B11 MinerU) are model-behavior, not extractor bugs — closing Wave 3.3 as no-op.

- **HELM + EleutherAI precedent**: Liang et al. (2022, [arxiv:2211.09110](https://arxiv.org/abs/2211.09110)) treat saved generations as canonical evidence — per-scenario / per-model artefacts preserved alongside metric scores. EleutherAI's [lm-evaluation-harness `--log_samples`](https://github.com/EleutherAI/lm-evaluation-harness) flag formalizes this as an OSS pattern: save the model output once; rescore as many times as the analysis methodology evolves. NeurIPS Paper Checklist treats "result recoverable from artefacts" as the reproducibility bar.

- **MLflow convention**: historical runs are immutable in practice — mutating finished runs erases the audit trail. The accepted pattern is "new run with parent-pointer tag" (see Stack Overflow MLflow Q&A + MLflow docs §"Parent-Child Runs"). A `rescore_of=<original_run_id>` tag is queryable via `mlflow.search_runs("tags.rescore_of='<id>'")` for cross-referencing.

### What ADR-016 already provided

`scripts/rescore.py` (introduced by ADR-016 for the adapter A/B dev loop) had three load-bearing pieces ready for reuse:

- `load_adapter_pair(*, candidate_path)` returning an `AdapterPair` with stability semantics.
- `rescore_transcripts(*, transcripts_dir, corpus_root, thresholds, adapters_pair)` walking transcripts, parsing per-page, scoring against GT.
- Opt-in `_log_to_mlflow_runs(...)` logging baseline + candidate as 2 nested runs under a parent.

What it lacked for the ADR-019 probe rescore:

- Hardcoded `from horus.eval import adapters as baseline_adapters` — no way to swap the baseline to `adapters_json`.
- Hardcoded `mlflow.set_experiment("adapter-iterate")` — no way to log into the probe's experiments.
- No `rescore_of` tag mechanism.
- Used the brittle `_strip_page_separators(body) → preprocess → to_predicted_dict` chain (Wave 3.1 superseded this in the harness; rescore.py needed to match).

---

## Options considered

### Option 1 — Build a parallel `scripts/rescore_probe.py`

- **Pros**: zero risk to the ADR-016 dev-loop callers; each script focused on one job; no contract changes.
- **Cons**: ~600 lines of duplicated transcript-parse + GT-cache + adapter-load + MLflow-tagging logic; two scripts to maintain; the parallel evolution risk every refactor.

### Option 2 — Extend `scripts/rescore.py` additively

- **Pros**: reuses tested infrastructure (transcript parser, GT cache, scoring loop, stability self-check); 4 new CLI flags are additive (default values preserve backward compat with the ADR-016 dev loop); single source of truth for offline rescore.
- **Cons**: requires careful contract migration (the multipage adapter API change is load-bearing; candidate-adapter contract must add `to_predicted_dict_multipage`); 2 existing test fixtures need updating to mirror the new contract.

### Option 3 — Inline the rescore inside `scripts/compute_probe_verdict.py`

- **Pros**: single script for the probe rescore + verdict matrix.
- **Cons**: duplicates rescore.py's logic; couples the rescore methodology to the verdict matrix consumer; can't reuse for future post-audit rescores.

### Decision: Option 2

Extend `scripts/rescore.py`. The extension is additive (4 new CLI flags with backward-compatible defaults) and the multipage migration is required anyway because Wave 3.1's harness rewire already moved the canonical pipeline to the multipage API — rescore.py needed to match for the rescore output to reflect the fixed pipeline. The candidate-adapter contract change (must also expose `to_predicted_dict_multipage`) is a principled tightening: the adapter API is uniformly multipage post-Wave-3.1.

---

## Decision + integration thoughts

### Architecture (committed in `0ccbf0f` + `22ec028`)

**Four additive CLI flags** on `scripts/rescore.py`:

| Flag | Default | Purpose |
|---|---|---|
| `--baseline-adapter-module` | `horus.eval.adapters` | Dotted module path resolved via `importlib.import_module`. Selects between regex (default; ADR-016 dev loop) and JSON (`horus.eval.adapters_json`; ADR-019 probe rescore). |
| `--mlflow-experiment-name` | `"adapter-iterate"` | MLflow experiment to log into. For the probe rescore: `structured-output-probe-uniform` / `structured-output-probe-native-json` to keep new rescore runs in the SAME experiment as the original buggy parent runs. |
| `--rescore-of-run-id` | `None` | Optional. MLflow `run_id` of the ORIGINAL buggy parent run that this rescore supersedes. When set: (a) parent run name becomes `rescore-of-<id[:8]>-<timestamp>`; (b) parent + both nested runs are tagged `rescore_of=<run_id>`; (c) parent's `adr` tag becomes `ADR-019` (vs `ADR-016` for the dev-loop default). |
| `--adapter-candidate-path` | `src/horus/eval/adapters_candidate.py` | (Pre-existing — ADR-016.) For the probe rescore we point at a non-existent path, so the script runs in stability mode (`candidate = baseline = fixed adapter`); each new MLflow parent run carries 2 nested runs both reporting the fixed-adapter metrics. |

**Contract change** on candidate adapter modules: must now expose three public callables (`preprocess`, `to_predicted_dict`, `to_predicted_dict_multipage`). The pre-existing ADR-016 contract required only the first two; Wave 3.1 added the multipage entry point. `tests/test_rescore.py` synthetic candidates updated accordingly.

**Pipeline change** in `rescore_transcripts`: replaces

```python
scorer_input = _strip_page_separators(body)
for adapter_label, (preprocess_fn, to_predicted_dict_fn) in adapter_funcs.items():
    preprocessed = preprocess_fn(scorer_input, model_id)
    predicted_dict = to_predicted_dict_fn(preprocessed, model_id)
```

with

```python
per_page_texts = _split_per_page_texts(body)
for adapter_label, multipage_fn in adapter_funcs.items():
    predicted_dict = multipage_fn(per_page_texts, model_id)
```

The `_split_per_page_texts` helper (new in this commit) is the inverse of `harness._extract_and_concat`: splits the saved-transcript body on the canonical `===== PAGE N =====` separator, strips per-chunk whitespace, drops empty leading/trailing chunks.

**Pinned-F1 regression guardrail held**: `tests/test_rescore.py::test_rescore_baseline_only_matches_legacy_ablation_at_tau_0_5` pins F1 ≈ 0.49 against ADR-014 Step 7 evidence. The pin survived the rewire because the regex adapter's `to_predicted_dict_multipage` joins per-page texts with `\n\n` (NOT `\n`) — preserving the inter-page blank line that the legacy `_strip_page_separators(body)` path produced. Verified empirically (test green post-rewire).

### `rescore_of` tag convention

When `--rescore-of-run-id <orig_run_id>` is set:

- **Parent run name**: `rescore-of-<orig_run_id[:8]>-<UTC timestamp>` — short-ID prefix makes MLflow UI sorting group rescore runs together (alphabetical by name); timestamp suffix prevents collision on re-runs.
- **Parent + both nested run tags**:
  - `rescore_of = <orig_run_id>` (cross-link for `mlflow.search_runs`)
  - `adr = ADR-019` (vs. `ADR-016` for the dev-loop default — disambiguates rescore origin)
  - `candidate_diff_sha256 = <sha>` (pre-existing; preserves audit trail when candidate ≠ baseline)
  - `script = "scripts/rescore.py"` (pre-existing)
  - `is_identical = "true" | "false"` (pre-existing — stability mode marker)
- **No mutation** of the original parent run or its nested children. The original buggy MLflow runs (`f9273a9d196742cdaa0831d7dcaa8608` for Arm A; `fced15055ae244e095cf5347760daf25` for Arm B) stay as-is, including their wrong F1 numbers. The bug-trail = the audit-trail; mutating it erases the diagnostic value.

### Cross-referencing convention

To find rescore runs from an original run (e.g., during a future audit):

```python
mlflow.search_runs(
    experiment_ids=[<exp_id>],
    filter_string="tags.rescore_of = 'f9273a9d196742cdaa0831d7dcaa8608'",
)
```

To find the original from a rescore: read `tags.rescore_of` on the rescore run.

### Model-behavior vs. extractor-bug classification

The discipline that decides re-inference (Wave 3.3) vs. offline rescore (Phase 4):

| Bug class | Mechanism evidence | Resolution path |
|---|---|---|
| **Adapter bug** | Per-transcript audit + Python REPL trace shows the adapter discards model output that contains correct data | Fix adapter (Wave 3.1); offline rescore (Phase 4) — NO re-inference needed |
| **Extractor bug** | `vlm_extractor.py` audit shows the model would emit JSON cleanly under correct chat template / stop-token / max_new_tokens settings | Fix extractor (Wave 3.3); RE-INFERENCE for affected (model, arm); old transcripts renamed `*.superseded-by-r1.txt`; new transcripts in `*-r1/` dirs; new MLflow parent run with `extractor_bug_fix=<commit>` tag |
| **Model-behavior failure** | Model is structurally unable to comply (base VLM refuses; Cat-1 task-prefix lock for OCR; quant × OOD-prompt decoder collapse). Confirmed by HF model card + per-transcript output pattern | DIAGNOSTIC ONLY. Document in §"Caveats" of the parent ADR. Saved transcripts are canonical evidence of the model's failure mode. No code change. |

For the ADR-019 probe rescore, Phase 1 concluded all suspected extractor bugs were model-behavior. Wave 3.3 closed as no-op; Phase 4 offline-rescored both arms against the FIXED adapter (`adapters_json` post-Wave-3.1).

### Empirical evidence (the rescore actually produced)

For both probe arms (single invoice `EN16931_Einfach`, 7 models, τ = 0.5):

- **Arm A** (`structured-output-probe-uniform`, original parent `f9273a9d...`):
  - New rescore parent: `0968311cb471414ead9c321b5719c68d`
  - Cohort pooled micro_F1: **0.2581** (vs. 0.0000 for the buggy DEFER verdict's 0/7 keys-recovered count)
- **Arm B** (`structured-output-probe-native-json`, original parent `fced1505...`):
  - New rescore parent: `923855e9b39d45329eb889957600bc1a`
  - Cohort pooled micro_F1: **0.3438**

Per-(model, arm) breakdown in `eval/probe-rescore-arm-{a,b}.txt`; verdict matrix in `eval/probe-verdict-matrix.md` (ratified by ADR-021).

---

## Source archival

External references underpinning the methodology:

- **HELM** — Liang et al., 2022, "Holistic Evaluation of Language Models" ([arxiv:2211.09110](https://arxiv.org/abs/2211.09110)). §"Methodology" + §"Reproducibility" lock saved per-scenario / per-model generations as canonical evidence. Cite location: §"Scientific evidence" of every benchmark contribution.
- **EleutherAI lm-evaluation-harness** — `--log_samples` flag + `--cache_requests` patterns. GitHub: [github.com/EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) §"Saving and Loading Samples". The canonical OSS pattern for offline rescore from cached model outputs.
- **NeurIPS Paper Checklist** — [neurips.cc/public/guides/PaperChecklist](https://neurips.cc/public/guides/PaperChecklist). §"Reproducibility" treats "result recoverable from artefacts" as the bar.
- **MLflow parent-child run hierarchy** — [mlflow.org/docs/latest/ml/tracking/](https://mlflow.org/docs/latest/ml/tracking/) §"Parent and Child Runs" + tag-based querying patterns. Locks the "new run with parent-pointer tag" approach over mutate-historical.
- **Google "Rules of Machine Learning"** — §24 "Measure the delta between two models". Already archived under `docs/sources/papers/google-rules-of-ml.md` per ADR-016; this ADR inherits the stability self-check pattern verbatim.

Per `horus-source-archival`, each external reference cited above gets a stub archive under `docs/sources/{papers,tools}/` in a separate Phase 6 commit (sources archival batch).

---

## Supersession trigger

This ADR is superseded when:

- The rescore-from-saved-transcripts methodology proves insufficient for a future audit (e.g., a future probe needs per-token output, which the current transcript format doesn't preserve) — at which point a new ADR amends the saved-transcript schema and this ADR's tag convention.
- MLflow's parent-child run mechanism changes (e.g., MLflow 4.x introduces a first-class "supersession" relationship that obviates the `rescore_of` tag).
- A different rescore engine replaces `scripts/rescore.py` (e.g., a refactor to a library API).

Until any of those happen, the policy in this ADR is canonical for HORUS post-audit rescores.

---

## Refs

- ADR-019 (parent — bug catalog + Phase 4 entry pointer)
- ADR-018 (probe being rescored)
- ADR-021 (verdict matrix amendments — consumer of this rescore's output)
- ADR-016 (parent `scripts/rescore.py` infrastructure — additively extended)
- ADR-014 (parent multi-page harness — `_extract_and_concat` shape + pinned F1 baseline)
- `scripts/rescore.py` (the rescore engine; committed `0ccbf0f`)
- `scripts/compute_probe_verdict.py` (the verdict matrix orchestrator; committed `22ec028`)
- `eval/probe-rescore-arm-{a,b}.txt` (the rescore output artefacts)
- `eval/probe-verdict-matrix.md` (the verdict matrix output)
- `~/.windsurf/plans/horus-probe-bug-cleanup-and-reverdict-4f44ea.md` (planning record + locked decisions D1/D2/D3)
