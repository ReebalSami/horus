# ADR-028 — Section-scoped invoice-totals adapter fallback (Belegsummen): recovering the 4 silently-missing MONEY fields

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-30 |
| **Milestone** | `experiments-validated` (HND-2 per re-audit plan `~/.windsurf/plans/horus-reaudit-review-d23373.md`; implements the Layer-2 MONEY-field follow-up deferred by ADR-014 §"Known limitation") |
| **Authored by** | Cascade (issue #41 implementation session; plan `~/.windsurf/plans/fix-issue-41-money-totals-adapter-222218.md`) |
| **Issue** | [`ReebalSami/horus#41`](https://github.com/ReebalSami/horus/issues/41) |
| **Supersession trigger** | (1) Line-items (BG-25) land in the `FIELDS` registry → the totals fallback gains per-line MONEY recovery + the synonym map grows; new ADR ratifies it. OR (2) A future corpus/locale ships a totals block whose display labels differ from the FeRD `Belegsummen` set (e.g., an English-locale ZUGFeRD profile, or a non-FeRD German layout) → the synonym map needs locale-aware extension; new ADR documents the per-locale synonym source. OR (3) A future cohort model emits a totals shape not covered by the 4 handled here (e.g., a JSON-totals block, or a 2-D image-grid layout) → the section-normalizer gains a 5th shape branch. OR (4) The `tax_basis_total_amount` ⟷ `line_total_amount` ambiguity surfaces on a corpus where `Positionssumme ≠ Rechnungssumme ohne USt.` (i.e., invoices WITH document-level allowances/charges) → the synonym map must be revisited because the two fields would carry different values and a mis-mapped synonym becomes a wrong-value FP rather than a harmless duplicate. OR (5) The held-out Belege split (#78) becomes the canonical thesis-reporting surface → the totals recovery is re-measured there and the in-corpus pilot-13 numbers become diagnostic-only. |

## Context

The HORUS evaluation pipeline (ADR-013 scorer + ADR-014 cohort harness) extracts 16 EN16931-anchored fields from local-VLM invoice transcripts and scores them against factur-x XML ground truth. ADR-014 §"Known limitation" documented an honest gap: of the 5 MONEY fields, only `due_payable_amount` (BT-115) flipped FN→TP on the multi-page corpus; the other 4 (`line_total_amount` BT-106, `tax_basis_total_amount` BT-109, `tax_total_amount` BT-110, `grand_total_amount` BT-112) remained uniformly FN **even though the page-2 totals block is present in the archived transcripts**. ADR-014 deferred the fix to "a separate PR, separate ADR" and pinned the gap as a regression baseline (the test this fix flips and renames to `test_multipage_money_fields_recovered_minero_einfach`). This ADR ships that fix. Issue #41 is the canonical follow-up.

### Root cause (verified against the archived transcripts)

The Layer-2 extractor (`to_predicted_dict`) searches for each field's `FieldSpec.german_label` via a line-anchored regex. The 5 MONEY fields' `german_label`s are **formal EN16931 terminology**, but the FeRD "Belegsummen" (document-totals) block in every ZUGFeRD invoice prints **colloquial display labels**. Only `due_payable_amount` happens to match verbatim:

| Field | BT | `german_label` (what the regex searches) | Belegsummen display label (what models emit) | Pre-fix |
|---|---|---|---|---|
| `line_total_amount` | BT-106 | `Summe Nettobeträge` | `Positionssumme` | FN |
| `tax_basis_total_amount` | BT-109 | `Steuerlicher Bemessungsbetrag` | `Rechnungssumme ohne USt.` | FN |
| `tax_total_amount` | BT-110 | `Umsatzsteuer gesamt` | `Steuerbetrag` | FN |
| `grand_total_amount` | BT-112 | `Bruttobetrag` | `Bruttosumme` | FN |
| `due_payable_amount` | BT-115 | `Zahlbetrag` | `Zahlbetrag` | **TP** (exact match) |

The values are sitting in the transcript (`Positionssumme … 473,00`, `Steuerbetrag … 56,87`, `Bruttosumme … 529,87`); the regex simply never asked for those labels. This is a Layer-2 adapter gap, not a harness or rasterization gap — confirmed because the same transcripts that score FN contain the data verbatim.

### Two complications the fix must handle

1. **The `Steuerbetrag` collision.** `Steuerbetrag` appears **twice** in every transcript: once as the VAT-breakdown table (`Umsatzsteueraufschlüsselung`) **column header** (earlier in the document, with per-rate values 19,25 / 37,62), and once as the `Belegsummen` total row (`Steuerbetrag … 56,87`). A naive document-wide search for `Steuerbetrag` grabs the wrong occurrence. **Section-scoping to the Belegsummen block is mandatory.**
2. **Four distinct post-Layer-1 text shapes.** Each totals-emitting model's Layer-1 preprocessor leaves the Belegsummen block in a different shape:

   | Model | Layer-1 strategy | Belegsummen shape reaching Layer 2 |
   |---|---|---|
   | MinerU 2.5 Pro | `mineru_cells` | clean `Positionssumme: 473,00` lines (cells already flattened by `_extract_mineru_cells`) |
   | Granite-Docling | `doctags` | `<fcel>Positionssumme<fcel>473,00<nl>…` inline tokens on **one physical line** (`_strip_doctags` strips `<otsl>`/`<loc_N>` but leaves `<fcel>`/`<nl>` + `<section_header_level_1>`) |
   | PaddleOCR-VL | `_passthrough` | label and value on **separate consecutive lines** (`Steuerbetrag\n56,87`) |
   | gemma-4-E4B-it | `_passthrough` | markdown table `\| Positionssumme \| 473,00 \|` (some `**bold**`) |

   The other 3 cohort models emit **no** Belegsummen block on `EN16931_Einfach` (olmOCR-2: empty VAT header only; GLM-OCR + PaliGemma-2: decoder collapse / loop). So **only 4 of 7 models** can yield MONEY TPs on this invoice — the acceptance bar (best-of-cohort ≥ 3) is met by MinerU alone (recovers all 5), but the fix is built to serve all 4 emitting shapes.

## Current-state survey (2026-05-30)

| Component | Where | Role |
|---|---|---|
| `to_predicted_dict` (Layer 2) | `src/horus/eval/adapters.py` | Per-field label-anchored regex + secondary/tertiary/quaternary fallbacks (invoice_number/issue_date via "Nr. X vom Y"; GLN; tax-IDs; section-scoped seller/buyer `Name:`). **No MONEY fallback** — this ADR adds it. |
| `_extract_section_name` + `_VERKAUFER_HEADER_RE` | same | Existing section-scoped extraction precedent (seller/buyer `Name:` within `Verkäufer`/`Käufer` sections). The MONEY fallback mirrors this proven pattern. |
| `FieldSpec.german_label` + `FIELDS` | `src/horus/eval/ground_truth.py` | Single source of truth for the EN16931 labels; the MONEY synonym map is keyed on the 4 `english_key`s, NOT hardcoded field names. |
| `_normalize_predicted_money` (scorer MONEY comparator) | `src/horus/eval/scorer.py` | Normalizes `"473,00"` → `"473.00"` on the predicted side before exact-match against GT. The fallback returns the raw German-decimal string; the scorer normalizes — no double-normalization. |
| `scripts/rescore.py` | `scripts/` | Offline A/B re-score of cached transcripts (ADR-016). Computes full `score()` per invoice; prints per-(model,field) Δ. This ADR additively extends its output with the ADR-027 4-metric cohort summary. |
| ADR-027 metric helpers | `src/horus/eval/scorer.py` | `presence_conditional_counts` / `group_level_counts` / `spurious_emission_counts` / `label_outcome_counts` / `f1_from_counts` — already public; reused verbatim by the rescore extension. |
| `tests/test_scorer_integration_multipage.py::test_multipage_money_fields_recovered_minero_einfach` | `tests/` | Was the regression baseline asserting the 4 fields are FN; designed to FAIL when the fix landed → flipped + renamed to assert recovery. |

## Options considered

### Axis 1 — where the fix lives (Layer 1 vs Layer 2)

| Option | Outcome |
|---|---|
| **(a) Normalize-in-Layer-1**: extend each model's preprocessor to flatten the Belegsummen block to uniform `label: value` lines (decode Granite `<fcel>` cells like MinerU; join PaddleOCR label/value lines; parse Gemma markdown rows), then a single line-anchored Layer-2 synonym lookup. | **Rejected.** Higher blast radius: changing Granite's `_strip_doctags` / the passthrough preprocessors ripples to *every* field for those models, risking the per-model extraction-count baselines (`test_to_predicted_dict_extraction_count_baseline_per_model`) and the single-page invariant. Layer-1 changes are global; the bug is local to one section. |
| **(b) Shape-tolerant Layer-2 fallback** with **local** Belegsummen-window normalization. | **Accepted.** The normalization touches only the Belegsummen substring inside the fallback — it never alters the text other fields are extracted from. Zero blast radius on other fields/models. Contained in one new helper + one fallback block in `to_predicted_dict`. Mirrors the existing `_extract_section_name` section-scoped precedent. |

### Axis 2 — synonym source

| Option | Outcome |
|---|---|
| Hardcode the 4 synonyms inline | **Rejected** (in spirit) — but the FeRD display labels are genuinely corpus constants, not config knobs. They live as a module-level mapping keyed on `english_key`, alongside the existing `_ABSENCE_MARKERS` / `_NR_VOM_RE` corpus constants. This matches `horus-config-discipline`'s boundary: experiment *knobs* go in YAML; *parsing vocabulary* (like the absence-marker list) is adapter logic. |
| Derive synonyms from a new `FieldSpec` field | **Deferred.** Adding `display_label_synonyms` to `FieldSpec` is the cleaner long-term home, but it's a ground_truth.py schema change affecting all 16 fields + their tests; out of scope for a focused bug fix. Captured as a follow-up candidate. The current module-level map is explicitly cross-referenced to `FIELDS` keys so the indirection is one hop. |

### Axis 3 — section-window end boundary

| Option | Outcome |
|---|---|
| Fixed char/line cap after the `Belegsummen` anchor | **Rejected.** Brittle across the 4 shapes (Granite packs all rows on one physical line; PaddleOCR spreads them over ~16 lines). |
| End at the next section header (`Zahlungsbedingungen`, present in all 4 after Belegsummen) or EOF | **Accepted.** All 4 transcripts have `Zahlungsbedingungen` immediately after the totals block; anchoring the window end on it (case-insensitive, first occurrence after the Belegsummen anchor) is shape-robust. Falls back to EOF if absent. |

## Decision + integration thoughts

Add a **section-scoped, shape-tolerant MONEY fallback** to `to_predicted_dict`, run only for the 4 target fields that are still `None` after the primary pass:

1. **Locate the totals section.** Find the `Belegsummen` anchor (case-insensitive) in the preprocessed text. If absent → no-op (this is what preserves the single-page guarantee: page-1-only transcripts carry no Belegsummen). Window = from the anchor to the next `Zahlungsbedingungen`/`Zahlungsbedingung` occurrence, or EOF.
2. **Locally normalize the window** (this substring only): `<nl>` → newline; `<fcel>`/`<ecel>`/`<lcel>`/`<ched>`/`<rhed>`/`<srow>` → space; strip `<section_header_level_1>` wrappers, markdown table pipes `|`, and emphasis `*`/`` ` ``. This turns all 4 shapes into `label … value` (or `label` then `value` on the next line for PaddleOCR).
3. **Per-field synonym lookup.** A module-level map keyed on `english_key` → ordered synonym list (`line_total_amount`→[`Positionssumme`, `Summe Nettobeträge`], `tax_basis_total_amount`→[`Rechnungssumme ohne USt.`, `Steuerlicher Bemessungsbetrag`], `tax_total_amount`→[`Steuerbetrag`, `Umsatzsteuer`], `grand_total_amount`→[`Bruttosumme`, `Bruttobetrag`]). For each synonym, find a German-decimal number (`-?\d{1,3}(?:\.\d{3})*,\d{2}`) either on the same line after the label or on the immediately following non-empty line. The formal `german_label` is kept as a secondary synonym so the fallback stays correct on hypothetical corpora that DO print the formal term.
4. **Conservative.** No number adjacent to the synonym within the window → leave the field `None`. A miss is preferable to a wrong value (FN over FP). The returned value is the raw German-decimal string; the scorer's MONEY comparator normalizes it.

The fallback fires after the primary/secondary/tertiary/quaternary heuristics and only fills still-`None` targets, so `due_payable_amount` (already TP via the primary regex on MinerU) is untouched, while models whose primary pass missed `Zahlbetrag` (Granite/PaddleOCR/Gemma — inline/next-line/markdown shapes the primary `^`-anchored regex can't see) can additionally recover it.

### Reporting extension (`scripts/rescore.py`)

`inspect_pilot_13.py` reads *saved* per-field scores from a prior MLflow run scored with the OLD adapter; it cannot reflect this fix without re-running the VLM sweep (forbidden — the fix is post-transcription). The reproducible evidence path is therefore the offline A/B re-score over the cached transcripts. This ADR additively extends `scripts/rescore.py` to print the **ADR-027 4-metric cohort summary** (per-canonical-label F1, presence-conditional F1, group-level F1, spurious-emission rate) for baseline vs candidate, reusing the already-public scorer helpers. This is purely additive output — the A/B comparison logic (ADR-016) is unchanged. It gives ADR-028's before/after table its numbers and re-baselines the shifted tests in one reproducible `make adapter-iterate` run.

### No-HARKing

The metric set (ADR-027) and this fix (the ADR-014-deferred Layer-2 MONEY follow-up) were both **pre-registered** in the HND-0/HND-2 plan before any post-fix numbers existed. The cohort baseline shift (`0.4908` → higher) is a documented bug fix applied to a **fixed, cached** transcript set, not metric-shopping-after-results. The in-corpus pilot-13 numbers remain **diagnostic**; the held-out Belege split (#78) stays the canonical thesis-reporting surface.

### Empirical results — full 26-invoice cohort A/B re-score

Source: `make adapter-iterate CFG=configs/pilot-13.yaml` over the 182 cached transcripts (no VLM). Baseline = canonical `adapters.py`; candidate = the fallback. The candidate converged on the **first** design (no tuning) — grounded directly in the actual Belegsummen transcript shapes.

**Cohort micro-F1: `0.4908` → `0.6729` (Δ +0.1821).** Per-model, every model improved: MinerU `0.718`→`0.917`, Granite `0.467`→`0.789`, PaddleOCR `0.467`→`0.718`, gemma-4 `0.445`→`0.675`, GLM-OCR `0.524`→`0.593`, olmOCR `0.444`→`0.476`, PaliGemma `0.304`→`0.397`.

**Strictly safe — zero regressions, zero new false positives.** Across all 112 (model × field) cells, every Δ TP is `+0` or positive and every candidate FP equals its baseline FP. The fallback only flips FN→TP, never FN→FP or TP→FN (the conservative "no number adjacent → leave None" design).

**ADR-027 4-metric cohort summary (τ = 0.50):**

| Metric | Baseline | Candidate | Δ |
|---|---|---|---|
| presence-conditional F1 | 0.4926 | 0.6750 | +0.1825 |
| group-level F1 (KIEval) | 0.0604 | 0.1832 | +0.1227 |
| spurious-emission rate | 0.0317 | 0.0317 | **+0.0000** |

The spurious-emission rate is **unchanged** — the recovery adds no hallucinations on genuinely-absent fields (it is purely a recall gain on present totals).

**Per-canonical-label F1 (cohort-pooled) — the 4 recovered fields + due_payable:**

| Field | Baseline | Candidate | Δ |
|---|---|---|---|
| `line_total_amount` | 0.0000 | 0.6812 | +0.6812 |
| `tax_basis_total_amount` | 0.0000 | 0.6764 | +0.6764 |
| `tax_total_amount` | 0.0000 | 0.7046 | +0.7046 |
| `grand_total_amount` | 0.0000 | 0.7361 | +0.7361 |
| `due_payable_amount` | 0.2157 | 0.6764 | +0.4607 |

**Acceptance bar (best-of-cohort ≥ 3 MONEY TPs on `EN16931_Einfach`): met.** MinerU recovers `tax_basis` + `tax_total` + `grand_total` on all 26 invoices (so `EN16931_Einfach` is necessarily included) plus `line_total` (23/26) and `due_payable` (24/26) → 5/5 on `EN16931_Einfach`. Pinned by the flipped + renamed regression test `tests/test_scorer_integration_multipage.py::test_multipage_money_fields_recovered_minero_einfach`.

## Source archival

No new external sources. This ADR builds on already-archived literature (ADR-013's ANLS\* metric stubs; ADR-027's KIEval reference) and tooling. The empirical evidence base is the existing cited archive `docs/sources/transcripts-multipage/` (the 182 cached transcripts from ADR-014 Step 7). The FeRD Belegsummen display labels are derived directly from those transcripts (FeRD ZUGFeRD 2.2 reference invoices, already cited in ADR-005/ADR-012).

## Cross-references

- Predecessor: `docs/decisions/ADR-013-vlm-prediction-scorer.md` (two-layer adapter), `docs/decisions/ADR-014-cohort-harness-multipage.md` (§"Known limitation" deferring this fix; §"Empirical results" `0.4908` baseline superseded here), `docs/decisions/ADR-016-fast-dev-config-adapter-iterate.md` (the A/B re-score harness extended here), `docs/decisions/ADR-027-f1-metric-expansion.md` (the 4 metrics reported here; flipped to Accepted in this PR).
- Immutable snapshot (NOT edited, per `document-as-you-go` retro-immutability): `docs/retros/m2d.5-pilot-13-cohort-harness.md` (records the `0.4908` baseline + Probe-1 1/5 as true at its close date).
- Plan: `~/.windsurf/plans/fix-issue-41-money-totals-adapter-222218.md`.
- Issue: [`ReebalSami/horus#41`](https://github.com/ReebalSami/horus/issues/41) — closed by this PR.

## Amendment 1 — threats to validity, real timing, and a worked example

**Date:** 2026-05-30 · **Author:** Cascade (issue #41 clean-delivery follow-through, plan `~/.windsurf/plans/issue-41-followthrough-clean-delivery-222218.md`)

**Why:** the §"Empirical results" numbers above (cohort `0.6729`, MinerU `0.917`, the per-label table) are easy to misread as HORUS's real-world accuracy. This amendment (a) bounds what they do and do not claim, (b) records a real MinerU latency/RAM measurement instead of the sparse/contradictory pilot-13 `perf.*` logs, and (c) shows two per-field worked examples so the F1 magnitude can be judged field-by-field. Nothing above is retracted — this is additive scope-bounding.

### A. Threats to validity / scope of these numbers

1. **In-sample / construct bias (internal validity).** Every number in §"Empirical results" was computed on the *same* 26-invoice cached transcript corpus used to design the Belegsummen fallback. The candidate converged on the first design (no tuning loop), so over-fitting risk is low — but these are **diagnostic, in-sample** numbers, not a generalization claim. No held-out split was used here.
2. **External validity — reference invoices, not real scans.** The corpus is the FeRD ZUGFeRD 2.2 **reference** set: clean, digitally-generated PDFs with regular layouts and machine-set text. Real firm documents (scanner noise, skew, stamps, handwriting, photocopies, heterogeneous layouts) will score **materially lower**. These numbers do **not** predict real-scan accuracy.
3. **Construct validity — what "F1" measures here.** Reported F1 is **micro-F1 with exact-match on normalized values** for every field except seller/buyer name (which use ANLS\* fuzzy matching). A MONEY/DATE/CODE/ID field is a TP only if its normalized prediction equals the normalized ground truth **exactly**. So `0.917` is **not** "92 % of fields right" in a colloquial sense — it is the harmonic mean of precision and recall over exact-match field outcomes on clean reference invoices.
4. **Canonical reporting surface.** The out-of-sample generalization claim is deferred to the held-out Belege split (#78 / HND-5) + cloud comparison (#80 / HND-6). **Until #78 lands, no number in this ADR may be cited as HORUS's real-world accuracy.**

### B. Real MinerU latency + memory (point measurement)

Replaces reliance on the sparse/self-contradictory pilot-13 `perf.*` logs with one clean, foreground run.

**Run:** `HORUS_DASHBOARD=plain make cohort-smoke MODEL=opendatalab/MinerU2.5-Pro-2604-1.2B CFG=configs/cohort-smoke.yaml` (MLflow `cohort-smoke`, 2026-05-30).

| metric | value | note |
|---|---|---|
| `load_seconds` | 24.10 | weights → MPS |
| `extract_seconds` (1 page) | **1323.29** (≈ 22 min) | output 940 chars |
| peak RAM | **15.75 GB mean / 16.63 GB max** | from pilot-13 `perf.peak_memory_gb`, n=4 (cohort-smoke does not instrument peak RAM — #77) |
| hardware | M1 Pro / 16 GB unified / Metal (no CUDA) | per `know-your-hardware` |
| n | 1 page | single point measurement, not a benchmark |

**Heavy swap caveat (load-bearing).** MinerU's peak (~15.75 GB) ≈ total RAM (16 GB) → the machine **swaps during inference**. The 1323 s/page is therefore a worst-case, memory-starved figure, **not** MinerU's compute cost on adequate hardware; a ≥ 32 GB / no-swap host (or a CUDA GPU) would be dramatically faster. Per-invoice cost ≈ `load` (once, amortized) + `pages × per-page-extract`. The controlled-hardware efficiency re-run is #77 (HND-4).

**Operational note.** The default `textual` TUI dashboard crashes MinerU load under a non-TTY pty (`ValueError: bad value(s) in fds_to_keep`); the `HORUS_DASHBOARD=plain` env var is the verified workaround. Filed as #85.

### C. Worked example — per-field GT vs predicted (MinerU)

Regenerate: `uv run python scripts/error_analysis.py --model opendatalab/MinerU2.5-Pro-2604-1.2B --invoices EN16931_Einfach,EN16931_Elektron` (offline, no VLM; reuses the same parser + adapter + scorer as `make adapter-iterate`).

Across MinerU's 26 invoices, per-invoice micro-F1 ranges **[0.5556, 1.0000]**, mean ≈ **0.912** — i.e. the headline pooled `0.917` is an **average that masks wide per-invoice variance**, not a uniform per-document accuracy.

**Clean invoice — `EN16931_Einfach`, micro-F1 0.9286 (TP 13 / FP 0 / FN 2 / TN 1):** all 5 MONEY fields are now TP (this fix); the two residual FN are `delivery_date` (BT-72) and `buyer_reference` (BT-46).

| field | BT | outcome | ground truth | predicted |
|---|---|---|---|---|
| `invoice_number` | BT-1 | TP | `471102` | `471102` |
| `issue_date` | BT-2 | TP | `2018-03-05` | `2018-03-05` |
| `invoice_currency_code` | BT-5 | TP | `EUR` | `EUR` |
| `delivery_date` | BT-72 | FN | `2018-03-05` | _(not extracted)_ |
| `seller_name` | BT-27 | TP | `Lieferant GmbH` | `Lieferant GmbH` |
| `seller_vat_id` | BT-31 | TP | `DE123456789` | `DE123456789` |
| `seller_tax_id` | BT-32 | TP | `201/113/40209` | `201/113/40209` |
| `seller_gln` | BT-29 (scheme 0088) | TP | `4000001123452` | `4000001123452` |
| `buyer_name` | BT-44 | TP | `Kunden AG Mitte` | `Kunden AG Mitte` |
| `buyer_reference` | BT-46 | FN | `GE2020211` | _(not extracted)_ |
| `buyer_vat_id` | BT-48 | TN | _(absent)_ | _(not extracted)_ |
| `line_total_amount` | BT-106 | TP | `473.00` | `473.00` |
| `tax_basis_total_amount` | BT-109 | TP | `473.00` | `473.00` |
| `tax_total_amount` | BT-110 | TP | `56.87` | `56.87` |
| `grand_total_amount` | BT-112 | TP | `529.87` | `529.87` |
| `due_payable_amount` | BT-115 | TP | `529.87` | `529.87` |

**Hardest invoice — `EN16931_Elektron`, micro-F1 0.5556 (TP 5 / FP 0 / FN 8 / TN 3):** all 5 MONEY fields are TP (the totals block read cleanly), but the **entire page-1 header is FN** — MinerU failed to read the header page on this layout while succeeding on the totals page. This is the multi-page failure mode that pulls the cohort average down, and it is invisible in a single pooled F1.

| field | BT | outcome | ground truth | predicted |
|---|---|---|---|---|
| `invoice_number` | BT-1 | FN | `181301674` | _(not extracted)_ |
| `issue_date` | BT-2 | FN | `2018-04-25` | _(not extracted)_ |
| `invoice_currency_code` | BT-5 | FN | `EUR` | _(not extracted)_ |
| `delivery_date` | BT-72 | FN | `2018-03-06` | _(not extracted)_ |
| `seller_name` | BT-27 | FN | `ELEKTRON Industrieservice GmbH` | _(not extracted)_ |
| `seller_vat_id` | BT-31 | FN | `DE136695976` | _(not extracted)_ |
| `seller_tax_id` | BT-32 | TN | _(absent)_ | _(not extracted)_ |
| `seller_gln` | BT-29 (scheme 0088) | TN | _(absent)_ | _(not extracted)_ |
| `buyer_name` | BT-44 | FN | `ConsultingService GmbH` | _(not extracted)_ |
| `buyer_reference` | BT-46 | FN | `16259` | _(not extracted)_ |
| `buyer_vat_id` | BT-48 | TN | _(absent)_ | _(not extracted)_ |
| `line_total_amount` | BT-106 | TP | `252.10` | `252.10` |
| `tax_basis_total_amount` | BT-109 | TP | `252.10` | `252.10` |
| `tax_total_amount` | BT-110 | TP | `47.90` | `47.90` |
| `grand_total_amount` | BT-112 | TP | `300.00` | `300.00` |
| `due_payable_amount` | BT-115 | TP | `300.00` | `300.00` |

### D. Deferred to HND-2

| Deferred item | Status | Issue |
|---|---|---|
| Out-of-sample generalization (held-out Belege split) | open | #78 (HND-5) + #80 (HND-6) |
| Real-scan robustness (noise / skew / layout) | subsumed by the held-out Belege set (real documents) | #78 (HND-5) |
| Controlled-hardware efficiency re-run (tokens/s + peak RAM) | open | #77 (HND-4) |
| TUI dashboard `fds_to_keep` crash on MinerU load | open (new) | #85 |

None of these are addressed in this PR by design; this table exists so they are not silently dropped.
