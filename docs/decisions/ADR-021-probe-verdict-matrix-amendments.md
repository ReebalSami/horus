# ADR-021: Structured-output probe verdict matrix + threshold / denominator amendments

**Status**: Accepted
**Date**: 2026-05-21
**Parent**: ADR-018 (the probe being amended)
**Siblings**: ADR-019 (probe bug catalog), ADR-020 (rescore methodology)

---

## Context

ADR-018 ratified a single-cell verdict for the structured-output probe (#53): "≥ 3 of 7 models pass `(json_validity=True ∧ canonical_keys ≥ 12)` → FILE #54; else DEFER". The DEFER verdict committed at `d01afd1` was structurally invalid (multi-page adapter bug per ADR-019 §B1 — load-bearing). The Phase 4 rescore against the FIXED adapter (per ADR-020) recovered the real metrics; this ADR amends ADR-018's verdict surface to honestly report what those metrics say.

Two methodology gaps in ADR-018's pre-registration surfaced empirically during the audit:

1. **Schema-mimicry threshold gap** (ADR-019 §B4): GLM-OCR Arm A passes the pre-registered threshold with 16 canonical keys all containing the prompt's placeholder strings (`<BT-1>`, `<BT-2 ISO 8601>`, etc.) and F1 = 0.0. The threshold credits schema conformance without value extraction.

2. **PaliGemma2 base-VLM in denominator** (ADR-019 §B8): the HF model card declares PaliGemma2 as a base VLM (not instruction-tuned). Arm A produces verbatim refusal ("Sorry, as a base VLM I am not trained to answer this question."). Including a structurally-non-participating model in the 7-of-7 denominator was a pre-registration error (knowable at ADR-009 §smoke time).

This ADR ratifies the additive amendments + the dual-verdict surface that Wave 3.2 (`src/horus/eval/probe_verdict.py`) implements.

---

## Current-state survey

### What ADR-018 pre-registered

From ADR-018 §"Pre-registered conditional verdict":

- Per-arm criterion: `(json_validity = True) ∧ (canonical_keys ≥ 12)`.
- Per-model rule: combined-max-per-arm — model passes if EITHER arm satisfies the criterion.
- Aggregate rule: ≥ 3 of 7 models pass → FILE #54; else DEFER.
- Single-cell verdict surface.

### What the audit found empirically (ADR-019 + rescore output)

Per `eval/probe-verdict-matrix.md` (Phase 5 output):

| Model | Arm A: JSON | Arm A: keys/16 | Arm A: F1 | Arm B: JSON | Arm B: keys/16 | Arm B: F1 | Note |
|---|---|---|---|---|---|---|---|
| `PaddlePaddle/PaddleOCR-VL` | ✗ | 0 | 0.0000 | ✗ | 0 | 0.0000 | — |
| `allenai/olmOCR-2-7B-1025` | ✓ | 16 | 0.6667 | ✓ | 16 | 0.6667 | — |
| `google/gemma-4-E4B-it` | ✓ | 9 | 0.6957 | ✓ | 9 | 0.6957 | highest F1; emits JSON null for genuinely-missing fields |
| `google/paligemma2-3b-mix-448` | ✗ | 0 | 0.0000 | ✗ | 0 | 0.0000 | base-VLM; N-of-6 excluded |
| `ibm-granite/granite-docling-258M-mlx` | ✓ | 16 | 0.0000 | ✗ | 0 | 0.0000 | schema-mimicry on Arm A (all `<BT-N>` placeholders); DocTags on Arm B |
| `opendatalab/MinerU2.5-Pro-2604-1.2B` | ✗ | 0 | 0.0000 | ✗ | 0 | 0.0000 | DocTags on both arms; JSON OOD |
| `zai-org/GLM-OCR` | ✓ | 16 | 0.0000 | ✓ | 16 | 0.5714 | schema-mimicry on Arm A; real values on Arm B |

Applied to ADR-018's pre-registered single-cell rule: 3 of 7 pass (olmOCR + Granite + GLM-OCR) → **FILE #54**.

But the 3-of-7 count masks two failure modes that any honest verdict must surface:

- Granite Arm A and GLM-OCR Arm A pass the threshold via schema-mimicry (F1 = 0). The pre-registered criterion does not distinguish "model echoed the schema with placeholder values" from "model extracted real values".
- PaliGemma2 was always going to fail (HF card: base VLM, knowable pre-probe). Counting it in the 7 inflates the threshold's effective stringency by 1/7.

---

## Options considered

### Option 1 — Single amended verdict (replace pre-registered)

- Amend the pre-registered criterion to `(json_validity = True) ∧ (canonical_keys ≥ 12) ∧ (micro_F1 ≥ 0.1)` and exclude PaliGemma from the denominator. Report the single resulting verdict.
- **Pros**: clean one-number output.
- **Cons**: HARKing (changing the pre-registered criterion after seeing the data); the pre-registration record loses force; future readers cannot reconstruct what the pre-registration said vs. what the amendment said.

### Option 2 — Dual verdict (pre-registered + amended) × dual denominator (N-of-7 + N-of-6)

- Report a 2 × 2 verdict matrix. Pre-registered cells preserve ADR-018 verbatim. Amended cells add the F1 gate. N-of-7 cells preserve the original denominator. N-of-6 cells exclude PaliGemma per the structural-flag rule.
- **Pros**: pre-registration verbatim; methodology amendments visible; reader picks the lens; no goalpost-move possible because all 4 cells are reported alongside.
- **Cons**: more output to read; potentially conflicting verdicts across cells (which is itself a methodological finding).

### Option 3 — Keep pre-registered single-cell verdict; document the gaps in §"Caveats"

- Report 3-of-7 FILE per ADR-018; flag schema-mimicry + PaliGemma in caveats.
- **Pros**: maximum pre-registration discipline.
- **Cons**: the headline verdict (FILE) is misleading without the caveats; readers who don't read caveats walk away with a wrong picture; the schema-mimicry and PaliGemma gaps are methodology BUGS, not background colour.

### Decision: Option 2

Report the 2 × 2 verdict matrix. The amendments are honest methodology-discovery — both gaps were ratified by ADR-019 as bugs in the methodology, not background noise. The 4-cell matrix:

- Honors pre-registration (cells A + C unchanged from ADR-018).
- Surfaces the gaps (amended cells B + D show what changes when F1 gate / PaliGemma flag are applied).
- Forces the reader to confront the disagreement when cells diverge (cell A FILE vs. cell B DEFER is itself the finding).
- Refuses goalpost-move because pre-registered + amended verdicts are reported alongside.

This pattern (dual / matrix verdict for honest methodology amendment) matches how rigorous ML evals report multi-metric outcomes (HELM §6 reports across 7 metrics simultaneously; CheckList paper reports across 5 capability dimensions). It's the OSS-evaluation convention.

---

## Decision + integration thoughts

### The 2 × 2 verdict matrix (locked)

| Denominator | Pre-registered threshold `(json_validity ∧ canonical_keys ≥ 12)` | Amended threshold `(... ∧ micro_F1 ≥ 0.1)` |
|---|---|---|
| **N of 7** (PaliGemma counted) | **Cell A** — pre-registered ADR-018 verbatim | **Cell B** — schema-mimicry-gated |
| **N of 6** (PaliGemma flagged) | **Cell C** — denominator-corrected | **Cell D** — schema-mimicry-gated + denominator-corrected |

Per-arm criterion is conjunctive across all components. Per-model rule (combined-max-per-arm): a model passes if EITHER arm satisfies the cell's criterion. Aggregate rule (unchanged from ADR-018): `n_passing ≥ 3` → FILE; else DEFER. The pass-count threshold (`3`) is NOT amended; only the per-arm criterion + the denominator are.

### Verdict surface (from `eval/probe-verdict-matrix.md`)

| Cell | Verdict | Passing models |
|---|---|---|
| **A** — Pre-registered × N of 7 | **FILE (3 of 7)** | `allenai/olmOCR-2-7B-1025` (F1 ≈ 0.67), `ibm-granite/granite-docling-258M-mlx` (F1 = 0; schema-mimicry), `zai-org/GLM-OCR` (Arm B F1 ≈ 0.57; Arm A is schema-mimicry) |
| **B** — Amended × N of 7 | **DEFER (2 of 7)** | `allenai/olmOCR-2-7B-1025`, `zai-org/GLM-OCR` |
| **C** — Pre-registered × N of 6 | **FILE (3 of 6)** | same as cell A |
| **D** — Amended × N of 6 | **DEFER (2 of 6)** | same as cell B |

### What this verdict surface says — read across cells

- **Reading by row (pre-registered → amended)**: 1 model flips out of the passing list when the F1 gate is added (Granite Arm A: 16 placeholder `<BT-N>` keys, F1 = 0). This 1-model flip is enough to push the verdict from FILE to DEFER under the amended threshold, in both denominators. **The schema-mimicry gap is empirically material.**
- **Reading by column (N-of-7 → N-of-6)**: PaliGemma2 moves from "failing" to "excluded"; the verdict in each row stays the same because removing 1 failing model from both numerator (0) and denominator doesn't change the inequality `n_passing ≥ 3`. **PaliGemma's flag is methodologically honest but doesn't change the verdict under this cohort.**
- **Diagonal (cell A FILE → cell D DEFER)**: the two methodology amendments TOGETHER flip the verdict from FILE to DEFER. The pre-registered FILE was an artefact of the methodology gaps; the amended DEFER is the honest answer to the probe question "can general-instruction-tuned VLMs reliably emit canonical-schema JSON for German B2B invoices?". Answer: **only 2 of 6 (olmOCR, GLM-OCR via Arm B).**

### Canonical_keys interpretation (additional finding)

The verdict matrix computes `canonical_keys` as "count of non-None values in the adapter's predicted_dict" (option 2 of the two defensible interpretations — see ADR-019 §"Empirical evidence — Gemma-4 finding"). Under this interpretation:

- Gemma-4-E4B-it has 9 of 16 canonical_keys (the model correctly emits JSON `null` for genuinely-missing fields: no `buyer_vat_id`, no `buyer_reference`, no MONEY fields on page 1, etc.).
- The model that does the BEST extraction (F1 = 0.6957) is rejected by the canonical_keys ≥ 12 gate because it is HONEST about which fields are not extractable.

The alternative interpretation (option 1 — count of canonical keys "present in the JSON dict regardless of value") would credit Gemma with 16 keys and let it pass both thresholds. Both interpretations are defensible; the existing implementation uses option 2 because it aligns with the adapter's tristate (None = "not extracted"; empty string = "present empty"; string = "present content") per ADR-012.

**This ADR locks option 2 as the canonical interpretation for the probe verdict**, on the grounds that the pre-registered threshold's intent was "model emitted real values for ≥ 12 of 16 fields" (not "model echoed the schema"). The Gemma penalty is a methodology-noticed asymmetry — flagged here for future probe design but NOT corrected post-hoc (would be HARKing). Probe re-design (e.g., for issue #55 fine-tuning ADR) should pre-register a metric that credits null-for-missing (e.g., `keys_with_decision ≥ 12` where "decision" = `value ∈ {real, null} ∩ key ∈ predicted_dict`).

### What ADR-018 pre-registered says vs. what this ADR amends

ADR-018 pre-registered:

- Per-arm criterion: `json_validity = True ∧ canonical_keys ≥ 12`. **Unchanged in cells A + C.**
- Denominator: 7 (all working models). **Unchanged in cells A + B.**
- Pass-count threshold: 3. **Unchanged in all 4 cells.**
- Per-model rule: combined-max-per-arm. **Unchanged.**

This ADR amends ADR-018 with:

- Additive cells B + D adding `micro_F1 ≥ 0.1` per-arm gate.
- Additive cells C + D excluding PaliGemma2 from the denominator.
- Locked `canonical_keys` interpretation as "non-null value count" (option 2 — implicit in the implementation; made explicit here).

### No mutation of the pre-registered surface

Cells A + C compute identically to the ADR-018 pre-registration. The new code in `src/horus/eval/probe_verdict.py` reports them alongside the amended cells — does not REPLACE them. The pre-registration record is preserved.

---

## Source archival

- ADR-018 (parent — the pre-registration this ADR amends; verbatim preservation in cells A + C).
- ADR-019 §"Threshold-design gap (B4)" + §"PaliGemma2 pre-registration error (B8)" (parent — the bugs this ADR closes via amendments).
- ADR-020 (sibling — rescore methodology that produced the metrics this matrix consumes).
- HELM (Liang et al., 2022, [arxiv:2211.09110](https://arxiv.org/abs/2211.09110)) §6 (multi-metric reporting precedent).
- Ribeiro et al., 2020, "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList" ([arxiv:2005.04118](https://arxiv.org/abs/2005.04118)) — multi-dimensional capability reporting precedent.
- ADR-009 §"Per-model native prompt strategy" + Amendment 1 (the structural priors for B6 / B7 / B11 / B8 documented at smoke time).

Each cited reference gets an archive stub under `docs/sources/{papers,tools}/` in the Phase 6.6 source-archival batch.

---

## Supersession trigger

This ADR is superseded when:

- A future probe re-pre-registers a SINGLE threshold + denominator (e.g., for issue #55 fine-tuning ADR), at which point the new probe's pre-registration ADR rebases.
- The `canonical_keys` interpretation is reconsidered (e.g., a new amendment ratifies "count keys present in JSON regardless of value" — option 1).
- The probe cohort changes such that PaliGemma2 is replaced with an instruction-tuned model (ADR-009 cohort amendment), invalidating the N-of-6 row of the matrix.

Until any of those happen, the 2 × 2 matrix in this ADR is canonical for ADR-018's verdict surface.

---

## Refs

- ADR-018 (parent — single-cell verdict pre-registration; amended by this ADR)
- ADR-019 (bug catalog; ratifies the gaps this ADR closes)
- ADR-020 (rescore methodology; produces the metrics this matrix consumes)
- ADR-009 (cohort selection; the priors that motivate the PaliGemma denominator flag)
- ADR-012 (tristate value semantics; the basis for the canonical_keys option-2 interpretation)
- `src/horus/eval/probe_verdict.py` (the matrix engine — Wave 3.2, commit `df45611`)
- `tests/test_probe_verdict.py` (22 tests covering all 4 cells)
- `eval/probe-verdict-matrix.md` (the rendered verdict surface)
- `scripts/compute_probe_verdict.py` (the orchestrator that produced it)
- `~/.windsurf/plans/horus-probe-bug-cleanup-and-reverdict-4f44ea.md` §0 (locked decisions D2 + D3 that this ADR ratifies)
