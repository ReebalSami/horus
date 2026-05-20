# ADR-016 — Fast dev config + adapter-iterate harness mode (post-pilot-13 Seq 2)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-20 |
| **Milestone** | `experiments-validated` (post-pilot-13 follow-ups; Seq 2 per `~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5) |
| **Authored by** | Cascade D (issue #51 implementation session; plan `~/.windsurf/plans/horus-issue-51-fast-dev-config-cb6372.md`) |
| **Issue** | [`ReebalSami/horus#51`](https://github.com/ReebalSami/horus/issues/51) |
| **Supersession trigger** | (1) `pydantic-settings` 3.x ships breaking changes to the multi-file YAML composition semantics (`deep_merge=True`, list-replacement behaviour, source ordering) — re-evaluate against the new surface; new ADR ratifies the migration. OR (2) `_CANONICAL_PRODUCTION_EXPERIMENTS` set in `src/horus/eval/harness.py` grows past ~5 entries — the inline frozenset becomes brittle; refactor to a declarative field on `MLflowConfig` (e.g., `is_canonical: bool`) + supersession ADR ratifies the schema change. OR (3) Adapter A/B grows past 2 variants (e.g., 3-way comparison across post-fine-tuning candidates) — the side-by-side pattern from rescore.py becomes the special case of a full pluggable pipeline (B3 from this ADR's options); new ADR ratifies the broader shape. OR (4) The dev-fixture tier separation proves insufficient (HARKing slips through despite the `dev_only=true` guard — e.g., a developer manually overrides the experiment name on the CLI to log dev runs to the canonical experiment) — extend the guard with a positive `is_canonical` field on `MLflowConfig` + supersession ADR ratifies the stronger contract. OR (5) `importlib.util.spec_from_file_location` causes a runtime problem (e.g., circular import with `horus.eval.adapters` when the candidate uses `from horus.eval.adapters import ...`) — fall back to a CLI-supplied module-attribute path (`--adapter-candidate-module horus.eval.adapters_candidate`) instead of file-path loading; new ADR documents the migration. |

## Context

Pilot #13 ([`ReebalSami/horus#13`](https://github.com/ReebalSami/horus/issues/13), closed via PR #42, ratified by ADR-014) produced **182 saved transcripts** at `docs/sources/transcripts-multipage/` (7 working models × 26 invoices) and the **canonical thesis-defense F1 evidence base**: cohort pooled micro_F1 = 0.4908 at τ=0.5. The pipeline is now `(PDF) → rasterize → VLM extract → adapter Layer 1+2 → scorer → per-field F1`.

The pilot-13 retro (`docs/retros/m2d.5-pilot-13-cohort-harness.md` §"Out of scope (explicit deferrals)") and the post-pilot-13 rethink plan (`~/.windsurf/plans/horus-post-pilot13-rethink-46eaaa.md` §5 Seq 2) identified a friction: **iterating on adapter heuristics requires re-running the harness end-to-end**, which is ~3-5 min for the smallest cohort and ~3-5 h for the full sweep. Per-page rasterization + VLM inference dominate that wall-clock; the adapter + scorer themselves are sub-second per transcript. The dev loop wants to skip rasterization + VLM and ONLY re-run adapter + scorer.

The substrate for this is **already** present:

- 182 saved transcripts are deterministic snapshots of the VLM outputs (multi-page concatenated text per `_extract_and_concat` + `===== PAGE N =====` separators).
- `scripts/ablation_threshold.py` (ADR-014 §Step 8) already re-scores transcripts at different τ values WITHOUT re-running the VLM. The substrate works.

What's missing for the **~5-15 second adapter dev loop**:

1. A minimal config (1 model × 3 invoices) so the dev loop runs on the smallest representative cohort, without duplicating ~50 lines of YAML between `pilot-13.yaml` and the dev variant.
2. A re-scoring tool that consumes a candidate adapter (not just a candidate τ) and emits per-field Δ between baseline + candidate.
3. A HARKing-prevention guard so iterative adapter tuning on the dev cohort never accidentally produces a "final thesis-reported F1 number" (per brainstorm v2 §2 No-HARKing + NeurIPS Paper Checklist).

This ADR ratifies the design for (1)+(2)+(3). Authored alongside the implementation across a 6-commit branch (`feat/issue-51-fast-dev-config-adapter-iterate`); the chunks are dependency-ordered: schema → harness wiring → dev YAML → script rename + A/B mode → Makefile target + README → this ADR.

## Current-state survey (2026-05-20)

Authoritative-source verification per `context7-and-docs-first`.

| Source | Finding | Where verified |
|---|---|---|
| `pydantic-settings` 2.x | `YamlConfigSettingsSource` accepts a list of file paths via `yaml_file=[...]` in `SettingsConfigDict` and supports `deep_merge=True` for nested-dict union. Lists are REPLACED (not concatenated) — the canonical semantics for "later file wins". | `context7` MCP query against `/pydantic/pydantic-settings`; cross-checked at `https://docs.pydantic.dev/latest/concepts/pydantic_settings/` |
| Google "Rules of Machine Learning" — Rule #24 | *"Measure the delta between models... Make sure that a model when compared with itself has a low (ideally zero) symmetric difference."* — direct endorsement of side-by-side Δ measurement + the self-stability sanity check. | `https://developers.google.com/machine-learning/guides/rules-of-ml` (full chunk read via `view_content_chunk`, position 15) |
| MLflow canonical A/B pattern | "Two runs logged separately, then compared via `mlflow.search_runs` filter OR UI side-by-side." Heavier ceremony than fast dev loops want — right shape for the promote-moment audit trail. | `https://apxml.com/courses/data-versioning-experiment-tracking/chapter-3-tracking-experiments-mlflow/comparing-mlflow-runs` (full chunk read) |
| NeurIPS Paper Checklist 2024/2025 | No-HARKing + claims-match-evidence + reproducibility + limitations disclosure. Implementation in HORUS: pre-registered H1–H6 (brainstorm v2 §6) + train/test/dev split (issue #46) + `dev_only` schema field (this ADR). | `https://neurips.cc/public/guides/PaperChecklist` |
| Python `importlib.util` | `spec_from_file_location` + `module_from_spec` + `loader.exec_module` is the canonical pattern for loading a module from a known filesystem path. `importlib.reload` has stale-reference pitfalls; fresh-process invocation is simpler. | Python stdlib docs `https://docs.python.org/3/library/importlib.html` + `qt.io` live-update analysis |
| ADR-004 (pydantic-settings + pyyaml) | Already-locked HORUS config library. Multi-file composition rides on top — NO new dependency required. | `docs/decisions/ADR-004-config-library.md` |
| ADR-013 + ADR-014 substrate | `src/horus/eval/adapters.py::preprocess` + `to_predicted_dict` are pure module-level callables. Trivially swappable via `importlib`. The 2-layer adapter contract was designed to be model-agnostic + replaceable. | `src/horus/eval/adapters.py:352,562` |
| `scripts/ablation_threshold.py` (ADR-014 §Step 8) | Already implements the re-score-cached-transcripts pattern (specialised to τ-sweep). Generalisation to adapter A/B is a small additive flag, not a rewrite. | `scripts/ablation_threshold.py:144-208` (pre-rename) |

The decision is **substantially overdetermined** by the kickoff plan + the 5 predecessor ADRs (ADR-004 + ADR-011 + ADR-013 + ADR-014 + ADR-015). The §"Options considered" walk below is documented for the 5-section discipline mandate; same retroactive-ratification shape as ADR-014 / ADR-015.

## Options considered

The plan (`~/.windsurf/plans/horus-issue-51-fast-dev-config-cb6372.md` §5-7) walked three orthogonal forks. Each fork is recorded below per `horus-decision-discipline` minimum-2-options requirement.

### Axis 1 — YAML composition mechanism for the dev config

| Option | Outcome |
|---|---|
| **A1** — Standalone duplicate (re-state every field from `pilot-13.yaml` in `pilot-13-dev.yaml` with the ~5 overrides inlined) | **Rejected.** ~50 lines of duplication. Silent drift hazard: when `pilot-13.yaml` changes (e.g., DPI bumped 300 → 400), the dev variant falls behind unless manually synced. |
| **A2** — Native `pydantic-settings` multi-file composition via `from_yaml(list[Path])` + deep-merge | **Accepted.** Library-native feature; no new dependency; eliminates drift. Pattern scales to future variants (`pilot-13-tau-03.yaml`, `pilot-13-finetuned.yaml`). ~20 LOC schema change + a private `_deep_merge` helper in `src/horus/config.py`. |
| **A3** — Explicit `__base__:` directive in the dev YAML pointing to the parent | **Rejected.** Non-standard YAML pattern. Reinvents what `pydantic-settings` already does natively. Custom loader code to maintain. |
| **A4** — Switch to Hydra (composition + CLI overrides + multi-run) | **Rejected.** New dependency. ADR-004 already locked `pydantic-settings`. Hydra's strengths (CLI override syntax, multi-run launcher) are not currently needed; its gaps (no Union types, no validation framework — both offloaded to Pydantic per the Towards Data Science 2024 evaluation) make the combination Hydra + Pydantic the only viable shape. The combination's cost (new dep + new ADR + learning curve) exceeds the benefit at HORUS's current scale (3 configs, growing). Re-evaluation trigger: 10-15+ config variants OR a need for Hydra's CLI override syntax. |

### Axis 2 — Adapter-iterate tool shape

| Option | Outcome |
|---|---|
| **B1** — Edit-and-rerun (single-pass; edit `adapters.py` in place, re-run, see the new F1; compare with last run's number from memory or terminal scrollback) | **Rejected.** The existing `ablation_threshold.py --thresholds 0.5` already implements this. Forces serial workflow (no in-run A/B). No mental bookkeeping if the user works very disciplined; vulnerable to self-deception otherwise. |
| **B2 (refined)** — A/B side-by-side: canonical baseline at `src/horus/eval/adapters.py` + candidate at `src/horus/eval/adapters_candidate.py` (gitignored); tool scores both against same transcripts in one pass; emits per-field Δ table | **Accepted.** Direct authoritative endorsement from Google "Rules of Machine Learning" §24 (*"measure the delta between models"*). One-shot verdict — no memory needed, no `git stash` gymnastics. Stability self-check baked in for free (when candidate is missing OR byte-identical to baseline, Δ must be 0; non-zero signals non-determinism bug). Opt-in MLflow logging via `--log-mlflow` flag preserves the canonical audit trail when promoting. |
| **B3** — Full pluggable pipeline (every adapter variant declared in YAML; arbitrary callables loaded at boot; baseline becomes a special case) | **Rejected (for now).** Over-engineered for current state (1 open adapter issue, not adapter-zoo problem). Reserved as supersession trigger (3) for when the substrate grows to 3+ variants. |

### Axis 3 — Make target naming

| Option | Outcome |
|---|---|
| **C1** — Patch issue #51 body only; reuse `make pilot-13 CFG=...,pilot-13-dev.yaml` | **Rejected.** `make pilot-13` still runs the VLM (~3-5 min for the dev cohort). Fails the 30-second target. Confuses the slow-path / fast-path verb-purpose distinction. |
| **C2** — Add dedicated `make adapter-iterate` target (fast path); `make pilot-13` stays as the slow path that produces canonical transcripts; patch issue #51 body comment | **Accepted.** Verb tells the user what speed to expect. `make pilot-13` = "produce canonical transcripts, take coffee break". `make adapter-iterate` = "score my heuristic tweak, see result in seconds". Six months later when reading shell history, the user knows immediately what they ran. |
| **C3** — Extend `make cohort-smoke` to support multi-page + scoring + CFG composition + adapter A/B | **Rejected.** Major scope creep. `cohort-smoke` is preserved per ADR-014 as ADR-009 §Decision-evidence reproducibility (page-1-only `sips` rasterization); rewriting its semantics silently breaks that contract. |

## Decision + integration thoughts

ADR-016 ratifies **A2 + B2-refined + C2** as the locked design. The implementation lands as a 6-chunk bundle on the `feat/issue-51-fast-dev-config-adapter-iterate` branch:

**Chunk 1 — Schema extension** (`src/horus/config.py`):

- `CohortConfig.invoice_subset: list[str] | None = None` — declarative YAML subset (per ADR-016).
- `CohortConfig.dev_only: bool = False` — HARKing-prevention forcing function.
- `ExperimentConfig.from_yaml(cfg_paths: str | Path | list[str | Path])` — accepts a single path (back-compat) OR a list (multi-file composition).
- Private `_deep_merge(base, override)` helper — recursive nested-dict merge; lists REPLACED (canonical `pydantic-settings` semantics).

**Chunk 2 — Harness wiring** (`src/horus/eval/harness.py`):

- CLI > YAML > full-corpus precedence in `run_cohort`: CLI `invoice_subset=` kwarg wins; falls through to `cohort_cfg.invoice_subset`; falls through to None (full corpus).
- `_CANONICAL_PRODUCTION_EXPERIMENTS: frozenset[str] = frozenset({"pilot-13-full"})` — module-level constant defining the canonical experiment names that `dev_only=true` configs MUST NOT target. Fail-fast at `run_cohort` entry.
- `dev_only` audit-trail tag on parent + 4 nested-run sites (success + load_failed + no_facturx_attachment + exception).
- `_filter_invoices` strengthened to raise on ANY unknown subset entry (was: silent-skip-when-partial-match; now: typos in dev-overlay YAML caught at boot).

**Chunk 3 — Dev config** (`configs/pilot-13-dev.yaml` + `configs/README.md`):

- ~15-line overlay: 1 model (MinerU-2.5-Pro 1.2B), 3 invoices (`EN16931_Einfach`, `XRECHNUNG_Einfach`, `EN16931_Reisekostenabrechnung`), distinct experiment name + transcript dir, `dev_only: true`.
- `configs/README.md` §"Multi-file composition" documents the deep-merge semantics + drift prevention + fail-fast.

**Chunk 4 — Adapter A/B + stability check** (`scripts/rescore.py` renamed from `scripts/ablation_threshold.py`):

- `load_adapter_pair(candidate_path)` — loads canonical baseline + candidate via `importlib.util.spec_from_file_location`. Returns `AdapterPair` dataclass with `is_identical` flag + SHA-256 diff hash. Stability semantics: candidate missing OR byte-identical → baseline-vs-baseline (Δ should be 0).
- `rescore_transcripts(..., adapters_pair)` — scores baseline + candidate against the same transcripts in one pass; emits `{adapter_label: {threshold: {model_id: list[scores]}}}`.
- `_print_ab_delta_table` — per-(model, field) baseline TP/FP/FN vs candidate TP/FP/FN with Δ TP arrow; cohort pooled Δ headline.
- `--log-mlflow` flag — opt-in 2 nested MLflow runs under `adapter-iterate-<UTC-timestamp>` parent. Default off (dev loop stays fast).
- τ-sweep mode preserved as `--thresholds 0.3,0.5,0.7` (composes with A/B: 2 thresholds × 2 adapters = 4 columns).
- `src/horus/eval/adapters_candidate.py` gitignored — candidate is a working file, never committed.

**Chunk 5 — Make target + README** (`Makefile` + `README.md`):

- `make adapter-iterate CFG=base.yaml,dev.yaml [THRESHOLDS=0.5] [ADAPTER=path] [LOG_MLFLOW=1]` — wraps `scripts/rescore.py` with the dev-config defaults.
- `scripts/run_pilot_13.py` + `scripts/rescore.py` both accept `--cfg PATH[,OVERLAY,...]` for multi-file composition.
- `README.md` §"Fast adapter dev loop (per ADR-016)" — documents slow-path / fast-path verb-purpose pairing + stability check + opt-in MLflow + HARKing guard.

**Chunk 6 — This ADR** (`docs/decisions/ADR-016-fast-dev-config-adapter-iterate.md`):

- 5-section discipline per `horus-decision-discipline`.
- INDEX.md status flipped Proposed → Accepted on merge.

### Empirical results (verification, per `make-sure-it-works`)

End-to-end smoke `make adapter-iterate CFG=configs/pilot-13.yaml` (against the 182 canonical transcripts) at chunk-5 verification time:

- Stability mode (no candidate present) → cohort pooled F1 baseline=0.4908 candidate=0.4908 Δ=+0.0000.
- **Reproduces ADR-014 §"Empirical results" — pilot-13 cohort F1 = 0.4908 — to 4 decimal places.**
- Stability check explicit: *"✓ stability check OK (baseline-vs-baseline Δ = 0)."*

Test coverage end-state: **379 tests pass** across the full suite (+19 from the chunk 1+2+3+4 additions; 0 regressions).

## Source archival

Two new source stubs land with this ADR per `horus-source-archival`:

- `docs/sources/papers/google-2018-rules-of-ml.md` — Google's "Rules of Machine Learning" (Zinkevich 2018) — cited for Rule #23 (you are not a typical end user) + Rule #24 (measure the delta between models; baseline-vs-baseline stability check). Rule #24 is the direct methodological precedent for `scripts/rescore.py`'s A/B + stability design.
- `docs/sources/papers/neurips-paper-checklist.md` — NeurIPS Paper Checklist 2024/2025 — cited for no-HARKing + claims-match-evidence + reproducibility discipline. Closes the prior-citation gap: brainstorm v2 + mid-heartbeat retro + multiple ADRs reference the checklist without a stub; this ADR adds the stub retroactively.

Re-used sources (no new stub needed):

- `docs/sources/tools/pydantic-settings.md` (ADR-004) — multi-file YAML composition substrate.
- `docs/sources/tools/mlflow.md` (ADR-011) — opt-in `--log-mlflow` parent + 2 nested runs pattern.
- `docs/sources/tools/pyyaml.md` (ADR-004) — `yaml.safe_load` consumed by `_deep_merge`.

Empirical evidence (re-used, no new artifact):

- `docs/sources/transcripts-multipage/*.txt` (ADR-014 §Step 7) — 182 saved transcripts that ADR-016's fast dev loop re-scores. Determinism-verified (baseline-vs-baseline Δ = 0).

## Cross-references

- **Predecessor ADRs**: [ADR-004](ADR-004-config-library.md) (pydantic-settings substrate), [ADR-011](ADR-011-experiment-tracker-integration.md) (MLflow tracker — opt-in `--log-mlflow`), [ADR-013](ADR-013-vlm-prediction-scorer.md) (per-field F1 scorer — the substrate this ADR re-scores), [ADR-014](ADR-014-cohort-harness-multipage.md) (cohort harness — produces the transcripts), [ADR-015](ADR-015-mlflow-ui-makefile-wire.md) (MLflow UI — adapter-iterate runs visible in the same UI).
- **Plan**: `~/.windsurf/plans/horus-issue-51-fast-dev-config-cb6372.md` (Q1-Q5 Socratic walk + 6-chunk implementation bundle).
- **Issue**: [`ReebalSami/horus#51`](https://github.com/ReebalSami/horus/issues/51) (closed by this PR).
- **Plan provenance**: post-pilot-13 rethink plan §5 Seq 2 + post-pilot-13 handoff item 2D (the original issue-#51 framing the plan supersedes).
