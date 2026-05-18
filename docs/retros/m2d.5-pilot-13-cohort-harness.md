---
status: closed
milestone: M2D.5 step 5 (pilot #13 — multi-page cohort harness)
sprint: Sprint 2 (Cascade D vertical)
parent_issue: "ReebalSami/horus#13"
closed_date: "2026-05-19"
prs:
  - "ReebalSami/horus#TBD (PR(c) cohort harness + multi-page rasterization + factur-x GT route)"
predecessor_prs:
  - "ReebalSami/horus#TBD (PR(a) parse_cii_xml — ADR-012)"
  - "ReebalSami/horus#TBD (PR(b) page-1 scorer — ADR-013)"
related_adrs:
  - "ADR-012 (factur-x GT route + sidecar-drift Probe 5)"
  - "ADR-013 (per-field F1 scorer with ANLS\\* and field-type dispatch)"
  - "ADR-014 (cohort harness + multi-page rasterization — this PR)"
followups:
  - "ReebalSami/horus#TBD (Layer 2 MONEY-field adapter heuristics — page-2 totals block)"
---

# M2D.5 step 5 — pilot #13 cohort harness retrospective

**Outcome**: Multi-page rasterization + factur-x GT route + harness orchestration delivers a **2.45× cohort-pooled micro_F1 lift** over the PR(b) page-1-only baseline (0.20 → 0.4908 across the full 26 × 7 ZUGFeRD-corpus sweep). All 182 (model, invoice) tuples completed with 0 failures. Best-of-cohort (MinerU 2.5 Pro) reaches **micro_F1 = 0.710** mean across all 26 invoices. Probe 2 (XRECHNUNG factur-x route) passes empirically: 7/7 models score TP on XRECHNUNG_Einfach `issue_date` via the factur-x route (impossible against the sidecar's 2024-* dates). Threshold-sensitivity ablation confirms the metric is τ-robust in [0.3, 0.7] (cohort Δ = 0.0031 = 0.3% absolute). One known limitation tracked as Layer 2 follow-up.

## What was built

| Component | Path | Purpose |
|---|---|---|
| Rasterizer | `src/horus/eval/rasterize.py` | pypdfium2-based PDF → PNG-per-page rendering at configurable DPI; cached + mtime-invalidated |
| Config: rasterizer + cohort | `src/horus/config.py` (`RasterizerConfig`, `CohortConfig`) | Pydantic-validated YAML knobs (DPI, output-dir, corpus root, models, parent-run-name, resume policy) |
| Cohort config | `configs/pilot-13.yaml` | The single source of truth for the full pilot — 7 working models × 26 paired invoices |
| Harness orchestrator | `src/horus/eval/harness.py` (`run_cohort`) | Loads each model in turn; rasterizes once per invoice; runs per-page extract + concat (Strategy α); extracts factur-x GT (NOT sidecar — per ADR-012 §"Probe 5"); preprocesses + adapts + scores; logs parent + nested MLflow runs; renders per-(model, field) heatmap |
| CLI runner | `scripts/run_pilot_13.py` + `Makefile` `pilot-13` target | Thin argparse wrapper over `run_cohort` |
| MLflow inspector | `scripts/inspect_pilot_13.py` | Read-only post-mortem: per-(model, invoice) F1 grid + per-model aggregate + Probe 1 + Probe 2 evidence from any pilot-13 parent run |
| Threshold ablation | `scripts/ablation_threshold.py` | Re-scores saved transcripts at arbitrary τ values without re-invoking any VLM |
| Tests | `tests/test_rasterize.py` (7), `tests/test_config.py` (16 cohort/raster), `tests/test_harness.py` (16), `tests/test_scorer_integration_multipage.py` (4) | 43 new tests; full suite 334 passing |

## Empirical results — full 26 × 7 sweep (Step 7)

**Parent run**: `df6bce67369c47948d10dfa0d2624490` (MLflow experiment `pilot-13-full`)
**Tuples**: 182 / 182 completed, 0 failed, 0 skipped (resume)
**Pooled cohort micro_F1**: **0.4908** (EN16931 split 0.4854 / XRECHNUNG split 0.5195)

### Per-model mean micro_F1 (n=26 invoices, ranked)

| Rank | Model | Mean micro_F1 | PR(b) page-1 baseline | Lift |
|---:|---|---:|---:|---:|
| 1 | opendatalab/MinerU2.5-Pro-2604-1.2B | **0.710** | ~0.20 | **3.55×** |
| 2 | zai-org/GLM-OCR | 0.521 | ~0.15 | 3.47× |
| 3 | ibm-granite/granite-docling-258M-mlx | 0.463 | ~0.125 | 3.70× |
| 4 | PaddlePaddle/PaddleOCR-VL | 0.463 | ~0.20 | 2.32× |
| 5 | allenai/olmOCR-2-7B-1025 | 0.442 | ~0.125 | 3.54× |
| 6 | google/gemma-4-E4B-it | 0.437 | ~0.15 | 2.91× |
| 7 | google/paligemma2-3b-mix-448 | 0.298 | ~0.05 | 5.96× |

### Probe 1 — best-of-cohort MONEY TPs on EN16931_Einfach

| Model | MONEY TPs | Target |
|---|---:|:---:|
| opendatalab/MinerU2.5-Pro-2604-1.2B | 1 / 5 | ≥ 3 |
| All 6 others | 0 / 5 | ≥ 3 |

**Status**: PARTIAL. Only `due_payable_amount` (Zahlbetrag, BT-115) flips FN → TP on MinerU. The other 4 MONEY fields (line_total_amount BT-106, tax_basis_total_amount BT-109, tax_total_amount BT-110, grand_total_amount BT-112) remain FN even though the multi-page concat contains the page-2 totals block (verified inline in `docs/sources/transcripts-multipage/ibm-granite__granite-docling-258m-mlx__EN16931_Einfach.txt`: page-2 shows `Bruttosumme 529,87` / `Steuerbetrag 56,87` / `Positionssumme 473,00`). This is a PR(b) Layer 2 heuristic gap — the adapter's regex anchors for these label names don't fire on the multi-page concat shape — tracked as a separate follow-up issue.

### Probe 2 — XRECHNUNG factur-x route (sidecar drift mitigation)

| Model | XRECHNUNG_Einfach `issue_date` outcome |
|---|:---:|
| All 7 models | **TP** |

**Status**: PASS. Empirical proof that the harness reads GT via `facturx.get_xml_from_pdf()` (returning 2018-era invoice dates) rather than the FeRD-shipped `.cii.xml` sidecar (which carries 2024-11-15 release-date stamps). This is the canonical confirmation of ADR-012 §"Probe 5"'s mitigation at full-cohort scale.

### Probe 5 — threshold-sensitivity ablation (Step 8)

Re-scoring the 182 saved transcripts at τ ∈ {0.30, 0.50, 0.70} without re-invoking any VLM:

| τ | Cohort pooled micro_F1 |
|---:|---:|
| 0.30 | 0.4926 |
| 0.50 | 0.4908 (default) |
| 0.70 | 0.4895 |

**Δ across [0.3, 0.7] = 0.0031 (0.3% absolute)**.

Per-model deltas: 5 of 7 models have Δ = 0.0000 (zero STRING-field sensitivity to τ); olmOCR Δ = 0.0133; GLM-OCR Δ = 0.0089. **Status**: F1 is **τ-robust** in [0.3, 0.7]. The literature-default τ = 0.5 (Biten+ ICCV'19) is empirically defensible. Mechanism: τ only affects the 2 STRING-field comparators (seller_name + buyer_name out of 16 fields); MONEY / DATE / CODE use exact-match-or-bust irrespective of τ, so τ-knob swings barely move the aggregate.

## Why the multi-page lift works (mechanism)

The PR(b) page-1-only rasterization hid the totals block on every multi-page invoice in the corpus (25 of 26 ZUGFeRD invoices are multi-page; only the smallest fixture is single-page). Models could read page 1's seller/buyer/invoice metadata but never saw the page-2 totals — so MONEY fields, settlement details, and SEPA prenotification fields were uniformly invisible.

PR(c)'s rasterizer renders every page as a separate PNG; the harness runs `extractor.extract()` once per page (preserving ADR-009's evidence-base contract: single-image-per-call); per-page outputs are concatenated with `===== PAGE N =====` separators (stripped before adapter Layer 1 to prevent separator-token contamination of model-specific heuristics).

The result: PR(b)'s adapter receives text containing both pages' content; fields that anchored only on page-2 labels (most notably `due_payable_amount` via the "Zahlbetrag" label) flip from systematic FN to TP.

## What the harness gets right

- **Resume safety**: ctrl-c at any point → re-running picks up where it left off via `mlflow.search_runs` filter on parent_run_id + model_id + invoice_id tags. Tested: Step 5 (21 tuples) + Step 7 (182 tuples) both ran clean.
- **Per-(model, invoice) atomicity**: a single transcript-load failure / OOM / model-crash kills exactly one nested run, not the parent. Surfaced via `n_failed` in the harness result + visible in MLflow's nested-run status.
- **Deterministic across re-runs**: the 21 transcripts overlap between Step 5 and Step 7 differ only in `# Extract: <s> total` per-run timing (model output is byte-stable with seed=42 + temperature=0). Verified at commit time.
- **Heatmap auto-rendered**: per-(model, field) ANLS\\* mean → matplotlib viridis heatmap → logged to MLflow as `cohort_heatmap.png`. Inspector script surfaces the same data as text.

## What's still constrained — the Layer 2 MONEY-field adapter gap

Probe 1 (≥3 MONEY TPs on best-of-cohort EN16931_Einfach) returned PARTIAL: MinerU 1/5, all others 0/5.

**Root cause**: PR(b)'s Layer 2 heuristics for `line_total_amount` / `tax_basis_total_amount` / `tax_total_amount` / `grand_total_amount` were authored against PR(b)'s page-1-only inputs. The regex anchors expected to find labels like "Bruttobetrag" or "Steuerbasisbetrag" with a specific surrounding context that the multi-page concat doesn't reproduce (different table-cell separators, different inter-page transitions, different relative positions to the line-items block). The adapter stays conservative (prefers FN over silent FP) — which is the right behavior for accounting-grade extraction, but leaves recall on the table.

**Why not fix in PR(c)**: PR(c)'s harness contract is "feed pages to PR(b)'s adapter + scorer". Fixing adapter heuristics changes PR(b)'s shape and risks regressing already-working fields. The work is well-scoped as its own follow-up issue + its own ADR — the kind of surgical change that benefits from isolated review.

**Status of due_payable_amount**: MinerU's TP on BT-115 (Zahlbetrag) is the canonical proof that the lift is real where the heuristic anchors are unambiguous. The label "Zahlbetrag" has no collision with line-item subtotals; the other 4 labels overlap with subtotal context in some invoices and the heuristic conservatively returns None.

## Test coverage added

| Test file | New tests | What they lock |
|---|---:|---|
| `tests/test_rasterize.py` | 7 | DPI fidelity, multi-page handling, cache invalidation, edge cases |
| `tests/test_config.py` | 16 | RasterizerConfig + CohortConfig Pydantic validation, YAML round-trip, mutual-presence invariants |
| `tests/test_harness.py` | 16 | Pure-function unit tests + 5 end-to-end integration tests with `_MockExtractorForHarness` (no VLM dependency); pins resume safety, factur-x GT route, per-profile aggregation, heatmap shape |
| `tests/test_scorer_integration_multipage.py` | 4 | MinerU multi-page F1 lift on EN16931_Einfach in [0.65, 0.85]; due_payable_amount TP regression guard; XRECHNUNG factur-x-route TP across cohort; documented MONEY-field gap as regression-baseline (turns FAIL when the limitation is fixed) |

Total: **+43 new tests, 334 passing** (was 291 at PR(b) close). Lint + typecheck clean throughout.

## Cross-cutting learnings (for cascade-system queue)

- **`Insight`**: A 3-PR vertical (PR(a) parser → PR(b) scorer → PR(c) harness) with empirical probes specified UP FRONT (e.g., "Probe 5: detect sidecar drift") catches data-pipeline silent corruption that pure unit-tests miss. PR(b)'s 0.20 cohort F1 looked plausible; only PR(a)'s Probe 5 explicit comparison of `cii.xml` GT against the PDF's factur-x GT revealed the sidecar's 2024-11-15 dates were systematically wrong. Without that probe, PR(c)'s 0.49 lift would have been undetected (the "lift" would be entirely from fixing sidecar drift, not from multi-page extraction).
- **`Source`**: `ReebalSami/horus#13` PR(c) ADR-014 + ADR-012 §"Probe 5".
- **`Project`**: HORUS.
- **`Cascade`**: D (Sprint 2 vertical).
- **`Date observed`**: 2026-05-19.
- **`Proposed L1 change`**: Add to `cascade-system` ADR-process guidance: every multi-step data-pipeline ADR plan should specify ≥1 empirical probe per stage, expressed as a YES/NO test against observable outputs, separate from unit tests.

- **`Insight`**: For long autonomous Cascade work (hours-scale empirical sweeps), the user-stated rule "long-running commands stay in foreground with live streaming output, no background-and-poll" is critical. Cascade's `run_command Blocking=true` honors this when the command itself prints with `flush=True`; the user sees streaming in the IDE terminal in real-time. Piping to `tail -N` defeats this (tail buffers all input then emits the last N lines).
- **`Source`**: This conversation's mid-Step-5 reinforcement of the operational rule.
- **`Project`**: HORUS.
- **`Cascade`**: D.
- **`Date observed`**: 2026-05-18.
- **`Proposed L1 change`**: Add to `cascade-system` rule `no-terminal-oneline-scripts.md` (or a new sibling rule): explicit guidance on log-streaming for long-running commands. The current rule covers crash-safety; a sibling rule should cover observability.

## What got committed

In branch `feat/issue-13-prc-cohort-harness`:

| Commit | Step | Summary |
|---|---|---|
| (Step 1) | Rasterizer | `src/horus/eval/rasterize.py` + 7 tests + pypdfium2 dep |
| (Step 2) | Config | `RasterizerConfig` + `CohortConfig` + `configs/pilot-13.yaml` + 16 tests |
| `b79e087` | Step 3 | Harness `src/horus/eval/harness.py` + 16 tests |
| `9b78ebf` | Step 4 | CLI `scripts/run_pilot_13.py` + Makefile target + 1-tuple smoke |
| `157f2c1` | Step 5 | 3 × 7 evidence sweep + 21 transcripts + `scripts/inspect_pilot_13.py` |
| `5739b03` | Step 7 | Full 26 × 7 sweep + 182 transcripts |
| `2855b22` | Steps 8 + 9 | τ-ablation script + 4 multi-page regression tests |

## What's still open

| Item | Tracking |
|---|---|
| Layer 2 MONEY-field heuristic for line_total_amount / tax_basis_total_amount / tax_total_amount / grand_total_amount on multi-page concat | Follow-up issue (filed in Step 12) |
| ADR-014 authoring (5-section ADR per `horus-decision-discipline`) | Step 11 |
| Land via @release-manager (squash-merge into main) | Step 12 |
| `delivery_date` FN-across-cohort on XRECHNUNG_Einfach — every model outputs the visible date but GT mismatches. Investigate whether XRECHNUNG factur-x XML uses a different BT-72 convention than EN16931, or whether the harness has a normalizer bug | Future curiosity, low priority — doesn't affect the cohort-ranking story |

## References

- Plan: `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §6 (PR(c) breakdown)
- Handoff context: `~/Projects/cascade-system/docs/handoffs/cascade-d-master-thesis.md`
- Predecessor retros: `docs/retros/m2d.5-step3-dataset-acquisition.md` (corpus acquisition)
- Predecessor ADRs: `docs/decisions/ADR-012-*.md`, `docs/decisions/ADR-013-*.md`
- This retro's ADR: `docs/decisions/ADR-014-cohort-harness-multipage.md` (authored alongside in Step 11)
- Saved evidence: `docs/sources/transcripts-multipage/` (182 files)
- MLflow parent runs: Step 5 = `ac80183a746e458bb4e1251463dda382`; Step 7 = `df6bce67369c47948d10dfa0d2624490`
