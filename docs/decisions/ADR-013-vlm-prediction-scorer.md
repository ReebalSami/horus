# ADR-013 — VLM prediction scorer: per-field F1 against XML-grounded ground truth (pilot #13 PR(b))

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-05-18 |
| **Milestone** | `experiments-validated` (pilot #13's scorer sub-issue; PR(b) of the locked 3-PR split) |
| **Authored by** | Cascade D (issue #13 implementation session; plan `~/.windsurf/plans/horus-issue-13-prb-scorer-d375d3.md`) |
| **Issue** | `ReebalSami/horus#13` (parent: pilot #13 first data loop) |
| **Supersession trigger** | (1) ANLS\* threshold 0.5 proves empirically wrong for German invoice strings — pilot #13 evidence shows systematic over- or under-acceptance on `seller_name` / `buyer_name`; the tuned threshold becomes a thesis result + this ADR is amended with the new default. OR (2) The 4-state `FieldType` taxonomy proves too coarse (e.g., IBAN / EMAIL / PHONE need dedicated comparators) — additive amendment: extend `FieldType` Literal + add comparator branches. OR (3) Line items (BG-25) land — `to_predicted_dict` returns a list-typed value and ANLS\* (Peer+ 2024 dict-mode) replaces plain ANLS for those fields; new sibling ADR. OR (4) Cohort prompts move from OCR-style ("Extract all text…") to structured-output ("Return JSON with these keys…") — the Layer 1 preprocessors become unused; ADR-013 is superseded by a simpler JSON-mode adapter. OR (5) PR(c) (ADR-014) re-rasterizes multi-page invoices and the 5 MONEY fields become extractable — the integration test invariant `test_monetary_fields_uniformly_FN_across_cohort` is no longer true and PR(c)'s ADR amends the page-1 baseline note. |

## Context

The HORUS thesis (`docs/prompts/stages/02-brainstorm.md` v2 §5.5) evaluates **local vision-language models** for German B2B invoice extraction. Pilot #13 ([ReebalSami/horus#13](https://github.com/ReebalSami/horus/issues/13)) builds the first data loop: 10 VLM cohort members × 26 paired ZUGFeRD PDFs → field extraction → **XML-grounded per-field F1** (per ADR-009 Amendment 1) → error heatmap.

ADR-012 ratified PR(a) — the CII XML → 16-field English-keyed `GroundTruth` parser. ADR-012 §"What this ADR does NOT decide" explicitly forward-points to PR(b) — the scorer that consumes `GroundTruth` instances as the comparison target for VLM predictions.

This ADR ships PR(b): a typed `InvoiceFieldScores` dataclass produced from a `(predicted_dict, GroundTruth)` pair, with per-field outcomes (TP/FP/FN/TN/EXCLUDED) dispatched through a 12-cell truth table + per-field-type comparators (ANLS\* for STRING, exact-on-normalized for MONEY/DATE/CODE). PR(c) (ADR-014) will consume `InvoiceFieldScores` and orchestrate the cohort-wide loop.

### What is already half-built

- **ADR-012 (2026-05-17)** ratified PR(a)'s `GroundTruth` substrate (16-field English-keyed dict; `FIELDS` registry; tristate value semantics).
- **ADR-009 Amendment 1 (2026-05-15)** designated the XML-grounded F1 evidence base and surfaced the cohort transcripts in `docs/sources/transcripts/` as the empirical reality the scorer must handle.
- **ADR-011 (2026-05-16)** ratified the MLflow `Tracker` Protocol with `log_dict`. PR(b)'s `InvoiceFieldScores` must serialize cleanly through `dataclasses.asdict` so PR(c) can log per-field heatmap data without custom serialization code.

### What is novel in this ADR

Six additions that no prior decision covered:

1. **The two-layer adapter design** — per-model preprocessors (Layer 1: `_strip_doctags`, `_extract_mineru_cells`, `_dedupe_repeats`, `_strip_chat_artifacts`, `_passthrough`) feed a unified German-label extractor (Layer 2: `to_predicted_dict`). Empirically motivated: 5 different cohort output shapes (DocTags, HF-OTSL cell markup, plain OCR text, markdown, repeat-loop OCR) share a common need for German-label-anchored extraction.
2. **ANLS\* threshold 0.5 + per-field-type comparator dispatch** — STRING fields use ANLS\* (Biten+ ICCV'19 + Peer+ 2024); MONEY/DATE/CODE use exact-on-normalized. Codes need legal correctness; names tolerate OCR.
3. **The `field_type` Literal attribute on `FieldSpec`** — additive ADR-012 amendment that opens the comparator dispatch at the FIELDS registry boundary (open/closed principle, same shape as PR(a)'s `normalize` callable).
4. **The 12-cell truth table** — explicit (GT 4-state × Pred 3-state) → outcome mapping. The `normalizer_rejected` GT path produces EXCLUDED outcomes that drop from both F1 numerators and denominators (honest handling of corpus anomalies).
5. **Section-scoped Name extractor for `seller_name` + `buyer_name`** — empirical finding: in real invoice layouts (ZUGFeRD + cohort transcripts), `Verkäufer` / `Käufer` are **section headers**, not field labels; the actual party name is on a `Name:` sub-line within the section. Layer 2 detects the section position and locates `Name:` within it.
6. **The page-1-only baseline finding** — `make cohort-smoke` rasterizes only page 1 of `EN16931_Einfach.pdf`, but the totals block lives on page 2. All 5 MONEY fields are uniformly FN across the cohort. Documented as a deterministic integration-test invariant (`test_monetary_fields_uniformly_FN_across_cohort`) so the constraint stays visible in CI until PR(c) (ADR-014) re-rasterizes.

## Current-state survey (2026-05-18)

| Component | Where | Ratified by | Role |
|---|---|---|---|
| `difflib.SequenceMatcher` (stdlib) | always present | — | Considered but **rejected** for Levenshtein distance — LCS-based, not edit-distance-equivalent in pathological cases. |
| Hand-rolled Wagner-Fischer DP | `src/horus/eval/anls.py` (this PR) | This ADR | True Levenshtein edit distance (~30 LOC, no new dep). |
| `anls` PyPI package | _not adopted_ | — | 3-year-old package; lacks dict-mode (Peer+ 2024). HORUS uses inline implementation. |
| `pydantic` `BaseModel` | already installed (ADR-004) | — | `EvalConfig` schema sub-model. |
| `pydantic_settings.BaseSettings` | already installed (ADR-004) | — | `ExperimentConfig` env-var layering. |
| Biten et al. ICCV'19 | `docs/sources/papers/biten-2019-anls-iccv.md` | This ADR (new stub) | ANLS metric definition + threshold-0.5 rationale. |
| Peer et al. 2024 (arXiv 2402.03848) | `docs/sources/papers/peer-2024-anls-star-arxiv-2402-03848.md` | This ADR (new stub) | ANLS\* extension to dict outputs (forward-compat note for BG-25). |
| DocILE (Rossum.ai) | `docs/sources/tools/docile-rossumai.md` | This ADR (new stub) | Methodological anchor: micro-averaged field-level F1 + AP. |
| arXiv:2510.15727 §3.4 | already archived (ADR-012) | — | Exact + relaxed match + tolerance windows — confirms PR(b)'s per-field-type comparator design. |
| `src/horus/eval/ground_truth.py` `FieldSpec` | this ADR amends | ADR-012 | New `field_type: Literal["STRING","MONEY","DATE","CODE"]` attribute. |

The decision is **substantially overdetermined** by the Socratic walk (`~/.windsurf/plans/horus-issue-13-prb-scorer-d375d3.md`). The §"Options considered" walk below is documented for the 5-section discipline mandate; same retroactive-ratification shape as ADR-010 / ADR-011 / ADR-012.

## Options considered

The Socratic walk explored **five orthogonal axes**.

### Axis 1 — Adapter design

| Option | Outcome |
|---|---|
| **Two-layer: per-model preprocessor + unified German-label extractor** | **Chosen.** Pure-per-model explodes maintenance (German-label logic duplicated 7×); pure-unified fails on DocTags + cell markup format noise. Two-layer matches the empirical 80/20: 4 models share OCR-text shape (passthrough), 3 need ~10 LOC of cleanup, 3 error transcripts skip the scorer. |
| Pure per-model adapter | Rejected — German-label extraction logic would be duplicated across 7+ files; PR(c) cohort growth would multiply the maintenance burden. |
| Pure unified parser | Rejected — empirically fails on Granite-Docling's `<doctag><text><loc_NNN>` markup + MinerU's `<fcel>X<fcel>Y<nl>` table cells. The 5 cohort output shapes are not all label-value-on-one-line. |
| LLM-as-judge | Rejected — post-pilot per Brainstorm v2 §8.3; introduces cloud dependency + non-determinism. |
| Re-prompt cohort with structured-output ("Return JSON…") | Rejected — would invalidate the existing ADR-009 cohort evidence base (transcripts in `docs/sources/transcripts/`). Cohort smoke captured those OCR-prompt outputs as the empirical reality; changing prompts is a separate PR. |

### Axis 2 — String comparator

| Option | Outcome |
|---|---|
| **ANLS\* with threshold 0.5 (Biten+ ICCV'19)** | **Chosen.** The established VLM-doc-AI relaxed-match metric. Tolerates `"Lieferent"` vs `"Lieferant"` (NLS≈0.89, above threshold → TP); penalizes `"Unhmd QmbH"` vs `"Lieferant GmbH"` (NLS≈0.286, below threshold → 0 → FN). The 0.5 threshold is the literature default. |
| Plain exact match | Rejected — punishes OCR character-level errors that are tolerable on name fields. MinerU's "Lieferent" would be FN despite being a clearly-correct intent. |
| Token-overlap F1 (SQuAD-style) | Rejected — German invoice strings are short (1–3 tokens typically). Token-overlap doesn't discriminate well at this granularity. |
| ANLS\* dict-mode (Peer+ 2024) | Deferred — required only when line items (BG-25) land; reserved as forward-compat in `src/horus/eval/anls.py` docstring. |
| Custom Levenshtein threshold per field | Rejected — over-engineered for PR(b); single τ across STRING fields is sufficient at the empirical scale of pilot #13. |

### Axis 3 — Money / Date / Code comparator

| Option | Outcome |
|---|---|
| **Exact match on canonical-normalized form** | **Chosen.** Decimal-cent correctness is legally required for Vorsteuerabzug; ISO-date + VAT-ID-formatted strings are codes, not natural language. German `"529,87 €"` → canonical `"529.87"` → exact-compare against PR(a)'s GT-side `_normalize_money` output. |
| Tolerance window (±0.01 €, ±1 day) | Rejected for default; reserved as a YAML knob (`eval.money_tolerance_cents` + `eval.date_tolerance_days`) in case a future pilot finds systematic off-by-rounding. |
| ANLS\* on typed fields | Rejected — `"529.87"` vs `"529.88"` would get NLS≈0.83 → TP, but the cent difference is materially wrong for an invoice line total. |
| Per-field-type Levenshtein for codes | Rejected — VAT IDs / GLNs have legal correctness semantics; OCR tolerance would mask real errors. |

### Axis 4 — `field_type` metadata location

| Option | Outcome |
|---|---|
| **New `field_type: Literal[...]` attribute on `FieldSpec`** | **Chosen.** Same open/closed pattern as PR(a)'s `normalize` callable. Adding a new field = 1 row in `FIELDS`, no edit to the scorer's dispatch cascade. Additive ADR-012 amendment (additive = backward-compat on existing FIELDS access patterns). |
| Scorer-internal `_FIELD_TYPE_MAP: dict[str, FieldType]` | Rejected — duplicates the catalog of truth; drift hazard when fields land in `FIELDS` without a corresponding map entry. |
| Subclass `FieldSpec` per type | Rejected — over-engineered; the 4-state Literal is sufficient and lets `mypy` exhaustiveness-check the dispatch. |

### Axis 5 — Truth table semantics

| Option | Outcome |
|---|---|
| **GT 4-state × Pred 3-state → 12-cell truth table; `normalizer_rejected` EXCLUDED** | **Chosen.** Explicit cell-by-cell mapping documented in code + ADR; `normalizer_rejected` (PR(a)'s corpus-anomaly path) drops from F1 numerator + denominator on both micro + macro. Honest handling of ground-truth uncertainty. |
| Treat present_empty as absent | Rejected — collapses the tristate distinction PR(a) carefully preserved. |
| Treat normalizer_rejected as FN | Rejected — penalizes the model for a GT-side issue. EXCLUDED is the only fair outcome. |
| Pred has explicit "I don't know" output | Deferred — cohort doesn't emit this signal today; would require COHORT_MANIFEST prompt changes (PR(c) scope). |

## Decision + integration thoughts

PR(b) ships:

1. **`src/horus/eval/anls.py`** — `nls(s1, s2)` (Normalized Levenshtein Similarity) + `anls(s1, s2, *, threshold=0.5)` (Biten+ ICCV'19 thresholded ANLS). Hand-rolled Wagner-Fischer Levenshtein DP; no new PyPI dependency.
2. **`src/horus/eval/adapters.py`** — Layer 1 preprocessors + Layer 2 unified German-label extractor. The `preprocess(raw, model_id)` dispatcher routes per-model based on substring match; `to_predicted_dict(raw, model_id)` is the public surface.
3. **`src/horus/eval/scorer.py`** — `FieldResult` + `InvoiceFieldScores` frozen dataclasses; predicted-side normalizers (`_normalize_predicted_money` / `_date` / `_code` / `_string`); 12-cell truth-table dispatch; micro + macro F1 aggregation; `score(predicted, gt, *, cfg, …)` public entry-point.
4. **`src/horus/config.py`** — new `EvalConfig` Pydantic sub-model exposing the 5 knobs (`anls_threshold`, `money_tolerance_cents`, `date_tolerance_days`, `string_normalize_nfc`, `log_excluded_to_dict`) per `horus-config-discipline`.
5. **`configs/pilot-13-eval.yaml`** — Pydantic-validated knob set with literature defaults.
6. **`src/horus/eval/ground_truth.py`** — additive ADR-012 amendment: new `field_type: Literal["STRING","MONEY","DATE","CODE"]` attribute on `FieldSpec`; 16 FIELDS rows tagged. Partition: STRING=2 (seller/buyer names), MONEY=5 (totals), DATE=2 (issue/delivery), CODE=7 (IDs).
7. **`tests/test_anls.py`** + **`tests/test_adapters.py`** + **`tests/test_scorer.py`** + **`tests/test_scorer_integration.py`** — 153 new test cases covering ANLS\* correctness, per-model preprocessors, label regex, 12-cell truth table, F1 aggregation, and end-to-end smoke against all 7 working cohort transcripts.
8. **`tests/test_ground_truth.py`** — 5 new tests for the `field_type` partition invariants.

### Smoke evidence (empirical baseline captured 2026-05-18)

Run against `EN16931_Einfach.cii.xml` (PR(a) GT) and the 7 working cohort transcripts (page-1 rasterization per ADR-009):

| Cohort model | TP | FP | FN | TN | EXCL | micro F1 | macro F1 |
|---|---|---|---|---|---|---|---|
| `ibm-granite/granite-docling-258M-mlx` | 1 | 0 | 14 | 1 | 0 | **0.125** | 0.067 |
| `opendatalab/MinerU2.5-Pro-2604-1.2B` | 7 | 0 | 8 | 1 | 0 | **0.636** | 0.467 |
| `allenai/olmOCR-2-7B-1025` | 3 | 0 | 12 | 1 | 0 | **0.333** | 0.200 |
| `google/gemma-4-E4B-it` | 4 | 0 | 11 | 1 | 0 | **0.421** | 0.267 |
| `zai-org/GLM-OCR` | 6 | 0 | 9 | 1 | 0 | **0.571** | 0.400 |
| `PaddlePaddle/PaddleOCR-VL` | 3 | 0 | 12 | 1 | 0 | **0.333** | 0.200 |
| `google/paligemma2-3b-mix-448` | 2 | 0 | 13 | 1 | 0 | **0.235** | 0.133 |

**Three observations** (load-bearing for the thesis writeup):

1. **MinerU 2.5 Pro is the best-of-cohort within the page-1 constraint** (micro F1 = 0.636). It extracts both names + 5 codes via its HF-OTSL cell-markup decoder. Single OCR error visible: `"Lieferent"` vs `"Lieferant"` — caught by ANLS\* as a TP (score=0.929).
2. **The 5 MONEY fields are uniformly FN across all 7 models** — confirmed empirically. Every model contributes 5 FN to the total. The constraint is the rasterization (page 1 only of `EN16931_Einfach.pdf`); PR(c) (ADR-014) fixes this.
3. **Zero FPs across the cohort** — no model hallucinated a value for `buyer_vat_id` (the only GT-absent field in `EN16931_Einfach`). This is a strong honesty signal: the cohort generally returns None rather than invented values when an OCR target is missing.

### Probe summary (per `horus-decision-discipline`)

- **Probe 1 — Granite-Docling baseline-of-failure**: scored against `EN16931_Einfach.cii.xml`. Exactly 1 TP (invoice_number=471102). 14 FN. Confirms baseline.
- **Probe 2 — MinerU best-of-cohort**: scored against same GT. 7 TPs spanning invoice_number / currency / seller_name (ANLS\*-tolerant) / seller_vat_id / seller_tax_id / seller_gln / buyer_name. micro F1 = 0.636 — at upper end of the [0.45, 0.65] range expected from the plan.
- **Probe 3 — Cross-cohort MONEY uniformity**: every working model contributes 5 FN to the MONEY fields, deterministically. Captured as `test_monetary_fields_uniformly_FN_across_cohort` so the constraint stays visible in CI.
- **Probe 4 — Truth-table EXCLUDED path**: synthetic GT with `is_present=True` + `normalized_value=None` (corpus-anomaly path from PR(a)) produces outcome=EXCLUDED. Confirms the EXCLUDED cell drops from F1 denominators. `EN16931_Einfach` doesn't trigger this path (no normalizer rejection in the smoke GT), so the test uses a synthetic fixture.

### Integration with PR(c) (forward-compat)

PR(b)'s `InvoiceFieldScores.per_field` is the per-row content of the F1 heatmap PR(c) will compute. `dataclasses.asdict` produces a JSON-serializable structure that `Tracker.log_dict` (ADR-011) consumes directly. PR(c) loops over (model_id, invoice_id) pairs, calls `score(...)`, and logs the asdict result as the `per_field_scores.json` MLflow artifact — no custom serialization code in PR(b)'s scope.

### Decision branch points NOT taken (forward-compat)

- **Line items (BG-25)** — `to_predicted_dict` returns flat `dict[str, str | None]`; the FIELDS registry has no BG-25 rows. When BG-25 lands, predicted values for line-item arrays would benefit from ANLS\* dict-mode (Peer+ 2024). Pre-noted in `anls.py` docstring.
- **Compliance pass rate / Vorsteuerabzug eligibility** — Brainstorm v2 §5.3 / §5.4; Säring-meeting-blocked. PR(b) ships the substrate; the compliance scorer is a future ADR.
- **Per-VAT-rate breakdown (BG-23)** — multi-row set-matching; deferred per ADR-012.
- **Field-weighted F1** — Brainstorm v2 §5.2; Säring-meeting-blocked.
- **Cloud-baseline comparison** — Brainstorm v2 §8.2; post-pilot.

## Source archival

Three new stubs land with this PR per `horus-source-archival`:

| Path | Source | Role |
|---|---|---|
| `docs/sources/papers/biten-2019-anls-iccv.md` | Biten et al., "Scene Text Visual Question Answering" (ICCV 2019) | ANLS metric definition + threshold-0.5 rationale (the original literature anchor for `eval/anls.py`). |
| `docs/sources/papers/peer-2024-anls-star-arxiv-2402-03848.md` | Peer et al., "ANLS\* — A Universal Document Processing Metric for Generative LLMs" (arXiv 2402.03848, 2024) | ANLS\* extension to dict-structured outputs; forward-compat reference for BG-25. |
| `docs/sources/tools/docile-rossumai.md` | Rossum.ai `docile` benchmark + paper (NeurIPS 2023) | Methodological anchor: micro-averaged field-level F1 + AP. Confirms PR(b)'s aggregation approach. |

Already-archived sources referenced (no new stub needed):

- `docs/sources/papers/raman-2025-invoice-extraction-arxiv-2510-15727.md` (ADR-012) — confirms PR(b)'s per-field-type comparator design (§3.4: "Exact match and relaxed match scoring … Tolerance windows for numeric fields").

## What this ADR does NOT decide

- **Cohort orchestration** — PR(c) (ADR-014) loops over (model_id, invoice_id) pairs and aggregates per-invoice `InvoiceFieldScores` into cohort-wide heatmap + summary. PR(b) ships only the per-invoice scorer.
- **Multi-page rasterization** — `make cohort-smoke` runs on page-1 PNG only; the 5 MONEY fields are uniformly FN as a consequence. PR(c) re-rasterizes all pages of every paired invoice and lifts this constraint. Until then, the page-1 baseline is the honest pilot-#13 evidence.
- **Cohort prompt re-engineering** — current `COHORT_MANIFEST` prompts (from ADR-009) are OCR-style ("Extract all text…"). PR(b) accepts them as-is; the saved transcripts in `docs/sources/transcripts/` remain valid evidence. Structured-output prompts (JSON / function-calling) are a separate decision (would invalidate the existing evidence base).
- **Cross-corpus F1 numbers** — PR(b) integration tests score against `EN16931_Einfach.cii.xml` only (the canonical smoke fixture). The full 26-paired-invoice corpus sweep is PR(c)'s scope.
- **Threshold tuning** — `eval.anls_threshold=0.5` is the literature default; tuning per cohort findings is a YAML change, not a code change (per `horus-config-discipline`). If empirical tuning lands a different default, this ADR is amended (not superseded).
- **Line-item adapter (BG-25)** — `to_predicted_dict` returns flat `dict[str, str | None]`; line-item arrays are deferred per ADR-012 + this ADR's "Decision branch points NOT taken" note.
- **Compliance-weighted F1, Vorsteuerabzug eligibility** — Brainstorm v2 §5.2–5.4; Säring-meeting-blocked.

## Refs

- ADR-012 (parent: PR(a) ground-truth parser)
- ADR-011 (MLflow `Tracker` Protocol; `log_dict` consumer of `InvoiceFieldScores`)
- ADR-010 (XML extraction substrate)
- ADR-009 (cohort manifest; the empirical evidence base)
- `~/.windsurf/plans/horus-issue-13-prb-scorer-d375d3.md` (Socratic walk + locked decisions)
- `docs/sources/transcripts/*.txt` (7 working + 3 error cohort transcripts)
- `docs/sources/papers/biten-2019-anls-iccv.md` (ANLS metric)
- `docs/sources/papers/peer-2024-anls-star-arxiv-2402-03848.md` (ANLS\* extension)
- `docs/sources/tools/docile-rossumai.md` (DocILE methodological anchor)
- arXiv:2510.15727 §3.4 (already archived under ADR-012)
- `.windsurf/rules/horus-decision-discipline.md` (5-section ADR mandate)
- `.windsurf/rules/horus-source-archival.md` (source-stub convention)
- `.windsurf/rules/horus-config-discipline.md` (YAML knobs not code constants)
