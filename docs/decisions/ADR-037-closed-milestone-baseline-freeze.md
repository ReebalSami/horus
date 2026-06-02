# ADR-037 — Closed-milestone baseline freeze: `score(fields=…)` field-subset scoring; the ADR-035 schema extension is forward-only for scoring scope

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-02 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (coding session implementing ADR-035 PR1; surfaced during `make test`) |
| **Issue** | [`ReebalSami/horus#88`](https://github.com/ReebalSami/horus/issues/88) |
| **Relationship** | **Sub-decision of ADR-035** (resolves an internal tension in its §Integration clause). Touches the scorer (ADR-013/027) + the closed in-sample baselines of ADR-014 / ADR-028 / ADR-029 / ADR-030. |

## Context

ADR-035 extends the canonical schema from 16 → 19 scored fields (adds `tax_rate` BT-119 + `seller_address`/`buyer_address` BG-5/BG-8). Because `FIELDS` is the single global registry the scorer iterates, that extension is **global**: every `score()` call now scores 19 fields.

Implementing PR1 surfaced a consequence the strategy ADR did not fully reconcile. Four **closed-milestone** test suites pin **published in-sample diagnostic baselines** by reproducing their exact numbers:

| Test | Pins | Published value (16-field) |
|---|---|---|
| `test_scorer_integration_multipage.py::test_minero_multipage_lift_einfach` | ADR-014/028 MinerU lift | micro_F1 `0.929` |
| `test_rescore.py::test_rescore_baseline_only_matches_legacy_ablation_at_tau_0_5` | ADR-028 cohort baseline | pooled F1 `0.6729` |
| `test_reading_ceiling.py::test_json_arm_reproduces_baseline_metrics` | ADR-029 `json-baseline-metrics.txt` archive | Gemma `0.707` / olmOCR `0.660` / GLM `0.475` |

Under a global 16→19 extension these all drop (MinerU → `0.839`, cohort → `0.5891`, JSON means shift), because the regex/JSON arms that produced those transcripts **never targeted** addresses or tax-rate — those 3 fields are GT-present on real invoices but predicted-`None`, so they score as honest FN.

ADR-035 §Integration carries the unresolved tension verbatim:

> *"additive to `FIELDS` + the scorer dispatch (ADR-027 **metrics recompute over the larger field set**); the regex baseline (ADR-013/028) is **unaffected on its existing 16 fields** and simply reports null on the 3 new ones (honest)."*

"recompute over the larger field set" ⟹ baselines shift. "unaffected on its existing 16 fields" ⟹ they don't. Both cannot hold for the historical reproductions. This ADR resolves which wins.

## Current-state survey (2026-06-02)

| Component | Where | State |
|---|---|---|
| Scorer field set | `src/horus/eval/scorer.py` `score()` | iterated the global `FIELDS` (now 19) with no subset hook; `InvoiceFieldScores.per_field` docstring already anticipated *"or whichever subset of FIELDS was scored"* |
| Group partition | `scorer.py` `FIELD_GROUPS` / `DOCUMENT_FIELDS` | already extended to 19 (seller/buyer_address → party groups; tax_rate → document scalars); `group_level_counts` already guards `if k in by_key` |
| Reproduction baselines | ADR-014/028 (`0.929`/`0.6729`), ADR-029 (`json-baseline-metrics.txt` + `reading_ceiling._JSON_BASELINE_REF_MEAN_MICRO_F1`) | published, committed, cited in their ADRs as in-sample diagnostics |
| Reproduction call sites | `rescore.rescore_transcripts` + `reading_ceiling._process_dir` + the multipage test's direct `score()` | all called the global-`FIELDS` scorer |

## Options considered

| Option | Why considered | Why not / why chosen |
|---|---|---|
| **A — Update all 3 baselines to the new 19-field numbers** + regenerate `json-baseline-metrics.txt` | Matches ADR-035's literal "recompute over the larger field set"; simplest | **Rejected.** Rewrites the *published* ADR-014/028/029 in-sample results. Worse, it records a **meaningless measurement**: a 16-field-targeted system scored against 19 fields is penalized for fields it was never asked to extract — comparable neither to the original 16-field experiment nor to a fair 19-field system. Corrupts the scientific record for no analytic gain. |
| **B — Freeze closed-milestone reproductions at 16 fields; schema extension is forward-only for scoring scope (chosen)** | Preserves every published number; the new fields are measured where they are *fair* (systems asked to emit them) | **Chosen.** Honors ADR-035's *"unaffected on its existing 16 fields"* clause. Zero published numbers change; no artifact regeneration. The 3 new fields are exercised by the new `test_schema.py` (49 cases) + the structurer-arm tests (forward work). Cost: a small backward-compatible `score(fields=…)` parameter threaded through 2 reproduction helpers. |
| C — Two parallel schemas (legacy `FIELDS_16` + new `FIELDS_19`) everywhere | clean separation | **Rejected.** The GT parser must emit 19 fields for the held-out eval; maintaining two registries duplicates the catalog and invites drift. The subset is derivable from the one registry (option B) — no second source of truth. |

## Decision + integration thoughts

1. **`score(*, fields: Mapping[str, FieldSpec] | None = None)`** — backward-compatible. `None` ⟹ the full 19-field `FIELDS` (every existing call site unchanged). A subset restricts which keys are scored; specs are always read from `FIELDS` (the subset must be ⊆ `FIELDS`). The aggregates (`presence_conditional_f1`, `group_level_f1`, `spurious_emission_rate`) already operate on `per_field.values()` and the group partition already guards missing keys — so a 16-key `per_field` reproduces every metric exactly.
2. **`ground_truth.LEGACY_EXPERIMENT_FIELDS`** — the frozen 16-field set the closed milestone measured, derived as `FIELDS \ {tax_rate, seller_address, buyer_address}` with an import-time `assert len == 16` drift guard. One source of truth; no hand-maintained second catalog.
3. **Threading:** `fields=` added to `rescore.rescore_transcripts` + `reading_ceiling._process_dir` (both pass through to `score`); the multipage test calls `score()` directly. The 3 reproduction tests pass `fields=LEGACY_EXPERIMENT_FIELDS`; their published ranges are **unchanged**.
4. **Scope rule (the resolution):** closed-milestone in-sample reproductions are scored at **their original field scope**. New work — the structurer arms (Arm A/B, ADR-034) and the frozen held-out eval (#78) — always scores the full 19-field `FIELDS`. "Forward-only for scoring scope" = the schema grows for new measurements; finished measurements keep the scope they were taken at.

**Integration:** purely additive. No production behavior changes for any default-`fields` caller (the harness, `run_cohort`, live cohort runs). Only the 3 historical reproductions opt into the 16-field subset. No change to the harness contract, MLflow logging, or adapter APIs.

## Source archival

Internal only: ADR-035 (parent — schema extension + the §Integration tension this resolves), ADR-012 (16-field origin), ADR-013/027 (scorer + metrics surface), ADR-014/028 (the `0.929`/`0.6729` MinerU + cohort baselines), ADR-029 (`json-baseline-metrics.txt` archive + the 3 JSON-capable models), ADR-030 (reading-ceiling determinism cross-check), ADR-034 (held-out strategy — the forward consumer of the 19-field set). No external source.

## Supersession trigger

Superseded if **any** of:

1. The held-out evaluation re-runs the historical cohort transcripts **as a 19-field system** (e.g. re-prompted for all 19 fields) — then a *new* 19-field baseline is a fair, first-class number and gets its own record (this freeze stays valid for the original 16-field runs).
2. The canonical field set changes again (add/remove scored fields) — `LEGACY_EXPERIMENT_FIELDS` + this scope rule are revisited (a future "legacy = 19" snapshot may itself need freezing).
3. `score(fields=…)` grows beyond subset-of-`FIELDS` semantics (e.g. arbitrary ad-hoc specs) — requires a new ADR defining the contract.

## Consequences

- **Zero published numbers change.** ADR-014/028/029/030 results + `json-baseline-metrics.txt` remain exactly as recorded; the reproduction tests guard them at their honest 16-field scope.
- The scorer gains a reusable, backward-compatible field-subset capability (the `per_field` docstring already anticipated it).
- A clear, citable scope rule for all future schema growth: **closed milestones freeze at their field scope; the schema grows forward.** Prevents the "every schema change silently rewrites history" failure mode.
- The 3 new ADR-035 fields are measured where the measurement is meaningful (systems asked to emit them), not retroactively against systems that never targeted them.
