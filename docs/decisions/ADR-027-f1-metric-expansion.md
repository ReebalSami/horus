# ADR-027 — F1 evaluation-metric expansion (experiment-phase prerequisite)

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-05-30 |
| **Milestone** | `experiments-validated` (HND-0 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`) |
| **Authored by** | Cascade (issue #74 implementation session; plan `~/.windsurf/plans/horus-hnd0-hnd2-metrics-money-adapter-5e032c.md`) |
| **Issue** | [`ReebalSami/horus#74`](https://github.com/ReebalSami/horus/issues/74) |
| **Supersession trigger** | (1) Line-items (BG-25) land in the `FIELDS` registry → the group partition gains a `line_items` group + the per-canonical-label set grows; a new ADR ratifies the expanded partition. OR (2) The Belege held-out test split (#78) becomes the canonical thesis-reporting surface → these 4 metrics are computed there and the in-corpus pilot-13 numbers become diagnostic-only; supersession ADR documents the migration. OR (3) KIEval publishes a v2 (or a reviewer rejects the single-instance Hungarian-trivial simplification) that revises the group-matching semantics → re-evaluate the group-level F1 implementation against the new surface. OR (4) A 5th reporting metric proves necessary (e.g., per-field calibration / abstention-precision) → additive amendment, same `InvoiceFieldScores`-extension shape. OR (5) The truth table changes such that FP becomes possible on a GT-present row (e.g., a future "present_empty + content → FP" reclassification) → presence-conditional F1 stops being recall-faithful and must be re-derived as a genuine P/R/F1; supersession ADR documents it. |

## Context

The HORUS evaluation surface (ADR-013 scorer) reports exactly two numbers per (invoice, model): **micro F1** and **macro F1**. The post-audit work surfaced two reasons this is insufficient:

1. **The honest-extractor problem (ADR-021).** The structured-output probe's `canonical_keys` gate counted *non-null* values as a quality signal, which **penalised the most honest extractor** — Gemma-4-E4B-it (probe F1 = 0.6957) emits `null` for genuinely-missing fields and was rejected by a value-count gate. A single F1 number does not distinguish "failed to extract" from "correctly abstained".

2. **Single-number reporting hides failure modes.** HELM (`helm-liang-2022.md` §6) established multi-metric reporting as the holistic-evaluation standard: report several orthogonal metrics per (scenario, model) tuple simultaneously rather than collapsing to one number; disagreement between metrics is itself a finding.

This ADR ratifies a **4-metric additive expansion** (micro/macro F1 preserved verbatim) and resolves Decision-Register **DR-7**. Critically, all four metrics are **derivable offline from the per-field `outcome` data already logged** as `per_field_scores.json` artifacts (ADR-011) — **no VLM inference, no re-run** (consistent with ADR-020's offline-rescore methodology).

## Current-state survey (2026-05-30)

| Source | Finding | Where verified |
|---|---|---|
| `src/horus/eval/scorer.py` truth table | FP is produced **only on the `absent`-GT row** (GT absent + pred content). GT-present rows yield only `{TP, FN, TN, EXCLUDED}`. **Structural consequence**: F1 restricted to GT-present fields has precision ≡ 1 → it is **recall-faithful**; hallucination lives entirely on the absent row. | `scorer.py:359-504` (`_gt_state` + `_score_one_field`) |
| `InvoiceFieldScores` | Frozen dataclass; adding fields with defaults is back-compatible (existing call sites + serialised artifacts unaffected). | `scorer.py:97-128` |
| `scripts/inspect_pilot_13.py` | Already downloads `per_field_scores.json` per nested run (Probe 1/2) — each record carries `outcome` + `field_type` + `gt_present`. Cohort pooling is therefore possible offline without re-running the harness. | `inspect_pilot_13.py:360-401` |
| KIEval (arXiv 2503.05488) §4.1 | **Group F1 = all-or-nothing**: a group is TP only when predicted ∧ GT groups are identical (`𝟙[·]`); Hungarian group-matching; **non-group entities excluded as the 1ˢᵗ group `G′`**. §5.3: generative models grouped via JSON structuring. Verified from the printed HTML render per #74's explicit mandate. | `docs/sources/papers/kieval-2025-arxiv-2503-05488.md` |
| HELM (Liang+ 2022) §6 | Multi-metric simultaneous reporting is the holistic-evaluation standard. | `docs/sources/papers/helm-liang-2022.md` |
| ANLS\* (Peer+ 2024) / ANLS (Biten+ 2019) | The per-field STRING comparator (`_compare_string`) is unchanged by this ADR — the 4 metrics re-aggregate existing per-field outcomes. | `docs/sources/papers/{peer-2024-anls-star-arxiv-2402-03848,biten-2019-anls-iccv}.md` |

The decision is largely determined by #74's explicit 4-metric list. The §"Options considered" walk documents the **definitional forks** within each metric (the genuinely open choices), per `horus-decision-discipline`'s minimum-2-options mandate.

## Options considered

### Fork 1 — `presence-conditional F1` definition

| Option | Outcome |
|---|---|
| **1A** — F1 restricted to GT-present fields (recall-faithful; absent fields excluded from the denominator) | **Accepted.** Standard KIE "evaluate on annotated fields" lens. Given the truth table yields FP only on absent rows, precision ≡ 1 on the present subset → this is a faithful recall measure (documented as such, not disguised). Pairs with Fork 3's spurious-emission rate to decompose micro F1 into its recall/precision axes. |
| **1B** — Credit correct-null inside F1 (`TP′ = TP + TN`) | **Rejected.** Mixing TN into an F1 numerator is non-standard, inflates the score, and breaks comparability with the KIE literature. The "credit null-for-genuinely-missing" intent (#74) is satisfied instead by the **(1A + Fork-3) decomposition**: a model that abstains correctly on absent fields earns a low spurious-emission rate AND is not penalised in presence-conditional F1 — credited on both axes without contaminating either. |
| **1C** — Status quo (no presence conditioning) | **Rejected.** Leaves DR-7 / ADR-021 unresolved. |

### Fork 2 — `group-level F1` partition (KIEval §4.1)

| Option | Outcome |
|---|---|
| **2A** — EN16931 business groups: `seller` / `buyer` / `totals`; document-level scalars (invoice_number, issue_date, currency, delivery_date) as the excluded non-group `G′` | **Accepted.** Maps directly onto KIEval's group/non-group split (§4.1); the document scalars are exactly the "same-structural-format" non-group entities KIEval folds into the excluded 1ˢᵗ group. Surfaces block-coherence (did the model get the WHOLE totals block, not 3-of-5 fields). |
| **2B** — Single group of all 16 fields | **Rejected.** Degenerates to "invoice-exact-match" (1.0 iff every field is TP) — no structural signal, and near-always 0 on the current cohort. |
| **2C** — Group by `field_type` (STRING/MONEY/DATE/CODE) | **Rejected.** KIEval groups are *semantic business groups*, not type buckets; a STRING+CODE "seller" block is the unit a practitioner corrects together, not "all CODE fields". |

### Fork 3 — `spurious-emission rate` denominator

| Option | Outcome |
|---|---|
| **3A** — `FP / (FP + TN)` — fraction of genuinely-absent fields where the model hallucinated a value | **Accepted.** Since FP occurs only on absent rows, this is exactly the hallucination rate on fields that have no ground-truth value (1 − specificity on absent fields). Clean precision-axis complement to Fork 1. |
| **3B** — `FP / (total fields)` | **Rejected.** Diluted by the present-field count; not comparable across invoices with different absent-field counts. |
| **3C** — `FP / (emitted fields)` | **Rejected.** Conflates absent-field hallucination with present-field extraction; harder to interpret. |

### Fork 4 — aggregation scope + DRY

| Option | Outcome |
|---|---|
| **4A** — per-invoice metrics as additive `InvoiceFieldScores` fields; cohort pooling in `inspect_pilot_13.py` by **reconstructing `FieldResult` from `per_field_scores.json`** and calling the *same* scorer metric functions | **Accepted.** Single-source metric math (no drift between per-invoice + cohort paths). `FieldResult(**json_dict)` round-trips cleanly (frozen dataclass, JSON-friendly per ADR-011). |
| **4B** — Re-implement the metric math in the inspector | **Rejected.** Two code paths drift; violates DRY. |

**per-canonical-label F1 scope**: cohort/cross-invoice only (per-invoice it is degenerate — each field has exactly one outcome, so its F1 is 1.0/0.0/undefined). Computed in the inspector by pooling each label's TP/FP/FN across invoices (per-model and cohort-wide). Not stored as an `InvoiceFieldScores` scalar.

## Decision + integration thoughts

Ratifies **1A + 2A + 3A + 4A**. Implementation:

**`src/horus/eval/scorer.py`** (additive):
- `FIELD_GROUPS: dict[str, frozenset[str]]` — the Fork-2A partition (`seller` / `buyer` / `totals`). `DOCUMENT_FIELDS` = the `G′` complement, exported for the inspector + tests.
- Pure functions over `Mapping[str, FieldResult]` (per-invoice) — reusable for cohort pooling over any `Iterable[FieldResult]`:
  - `presence_conditional_f1(...) -> tuple[float, float, float]` (p, r, f1 over GT-present fields)
  - `group_level_counts(...) -> tuple[int, int, int]` (per-invoice group TP/FP/FN; poolable across invoices) + `group_level_f1(...)`
  - `spurious_emission_rate(...) -> float` (`FP / (FP + TN)`; 0.0 when no absent fields)
  - `label_outcome_counts(...) -> dict[str, tuple[int, int, int]]` (per-label TP/FP/FN — the pooling primitive for per-canonical-label F1)
- `InvoiceFieldScores` gains `presence_conditional_f1`, `group_level_f1`, `spurious_emission_rate` (defaults `0.0`). `score()` populates them. Micro/macro unchanged.

**`scripts/inspect_pilot_13.py`** (additive): `_print_extended_metrics(nested)` reconstructs `FieldResult` from each `per_field_scores.json`, pools per-model + cohort, and prints four sections (per-canonical-label F1 table, presence-conditional F1, group-level F1 per group, spurious-emission rate). Wired into `main()` after the existing probes. `make inspect-pilot-13` therefore reports all four with no harness re-run.

**The recall/precision decomposition (the resolving insight for ADR-021/DR-7)**: presence-conditional F1 (recall on present fields) + spurious-emission rate (hallucination on absent fields) are the two orthogonal failure modes that micro F1 silently averages. An honest abstainer (Gemma-4) scores well on both — high presence-conditional F1 where it extracts, low spurious-emission because it emits `null` rather than inventing values — and is no longer punished by a single conflated number.

### Empirical results (verification, per `make-sure-it-works`)

`make inspect-pilot-13` against the canonical `pilot-13-full` parent (`df6bce67369c47948d10dfa0d2624490`, 182 tuples) renders all four metrics with **zero harness re-run**. Cohort-pooled:

| Metric | Cohort value |
|---|---|
| micro F1 (unchanged — additive) | 0.491 (reproduces ADR-014's 0.4908) |
| presence-conditional F1 | 0.493 |
| group-level F1 (KIEval) | 0.060 |
| spurious-emission rate | 0.032 |

Per-model presence-conditional F1 ranks MinerU 2.5 Pro top (0.721), consistent with its micro-F1 lead. **Group-level F1 is brutal** (cohort 0.060; only MinerU clears 0.05, at 0.359): models rarely reproduce a *whole* EN16931 business group identically — a thesis-relevant block-coherence finding the single-number F1 hid. **Spurious-emission is low** across the cohort (0.032): the models abstain rather than hallucinate, which is exactly why the single micro F1 under-credited honest abstainers (the ADR-021 motivation — now made explicit).

The per-canonical-label F1 table surfaces the HND-2 (#41) MONEY gap as a first-class number: `line_total_amount` / `tax_basis_total_amount` / `tax_total_amount` / `grand_total_amount` each score **F1 = 0.000 (0 TP / 182 FN)**, while `due_payable_amount` (the one label whose synonym matches) scores 0.216 (22 TP). Easiest: `issue_date` (0.972), `invoice_number` (0.963); hard tail: `delivery_date` + `buyer_*`.

Test coverage end-state: **682 tests pass** (+20 ADR-027 metric tests; 0 regressions). `make lint` + `make typecheck` clean (78 source files).

## Source archival

- **New stub**: `docs/sources/papers/kieval-2025-arxiv-2503-05488.md` — KIEval (arXiv 2503.05488); §4.1 group-level F1 definition verified from the HTML render (per #74).
- **Re-used** (no new stub): `helm-liang-2022.md` (§6 multi-metric reporting), `peer-2024-anls-star-arxiv-2402-03848.md` + `biten-2019-anls-iccv.md` (STRING comparator, unchanged).
- **Empirical evidence (re-used)**: `docs/sources/transcripts-multipage/*.txt` + the `pilot-13-full` MLflow artifacts — re-aggregated offline, never re-run.

## Cross-references

- **Predecessor ADRs**: [ADR-013](ADR-013-vlm-prediction-scorer.md) (the scorer this extends), [ADR-021](ADR-021-probe-verdict-matrix-amendments.md) (canonical_keys asymmetry this resolves), [ADR-011](ADR-011-experiment-tracker-integration.md) (`per_field_scores.json` artifact this re-aggregates), [ADR-020](ADR-020-probe-rescore-methodology.md) (offline-rescore precedent).
- **Plan**: `~/.windsurf/plans/horus-hnd0-hnd2-metrics-money-adapter-5e032c.md`.
- **Issue**: [`ReebalSami/horus#74`](https://github.com/ReebalSami/horus/issues/74) (closed by this PR). Prerequisite for HND-1 (#54) / HND-2 (#41) / HND-3 / HND-4.
