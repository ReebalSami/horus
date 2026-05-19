# ADR-014 — Cohort harness + multi-page rasterizer: full ZUGFeRD-corpus F1 evaluation (pilot #13 PR(c))

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-05-19 |
| **Milestone** | `experiments-validated` (pilot #13's harness sub-issue; PR(c) of the locked 3-PR split) |
| **Authored by** | Cascade D (issue #13 implementation session; plan `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §6 PR(c)) |
| **Issue** | `ReebalSami/horus#13` (parent: pilot #13 first data loop) |
| **Supersession trigger** | (1) The `(model × invoice) → MLflow nested-run` orchestration proves too coarse — e.g., per-page scoring becomes the comparison unit instead of per-invoice; new ADR re-shapes the harness contract. OR (2) Page-aggregation strategy α (per-page extract + concat) proves dominated by strategy β (image-grid composition) or γ (multi-page-aware prompt) on a future model — `_extract_and_concat` becomes one of N pluggable strategies. OR (3) pypdfium2 ships a breaking API change in its v5.x line (LICENSE or behavior) — re-evaluate against pdf2image / PyMuPDF / Apache PDFBox; new ADR ratifies the replacement. OR (4) The factur-x GT route returns ambiguous data on a future corpus (e.g., factur-x XML differs systematically from the visible PDF on a specific field) — Probe 5 protocol gets extended with a per-field divergence test + the harness gains a per-field GT-route override. OR (5) MLflow's `search_runs` resume protocol breaks on a future MLflow major version — fall back to a hash-based resume index in `mlartifacts/` + amend the harness contract. |

## Context

The HORUS thesis (`docs/prompts/stages/02-brainstorm.md` v2 §5.5) evaluates **local vision-language models** for German B2B invoice extraction. Pilot #13 ([ReebalSami/horus#13](https://github.com/ReebalSami/horus/issues/13)) builds the first data loop: 10 VLM cohort members × 26 paired ZUGFeRD PDFs → field extraction → **XML-grounded per-field F1** (per ADR-009 Amendment 1) → error heatmap.

ADR-012 ratified PR(a) — the CII XML → 16-field English-keyed `GroundTruth` parser. ADR-013 ratified PR(b) — the per-field F1 scorer with ANLS\* / field-type dispatch / two-layer adapter. Both ADRs explicitly forward-pointed to PR(c) — the **cohort harness** that orchestrates `(model × invoice)` pairs across the full corpus, replacing the page-1-only `make cohort-smoke` baseline with full multi-page extraction.

This ADR ships PR(c). Three load-bearing components:

1. **pypdfium2-based multi-page rasterizer** (`src/horus/eval/rasterize.py`) — replaces `make cohort-smoke`'s `sips` page-1-only render. Renders every PDF page at configurable DPI; caches PNGs with mtime invalidation.
2. **Cohort harness orchestrator** (`src/horus/eval/harness.py`) — loads each model once, iterates over paired invoices, runs per-page extract + concat (Strategy α), extracts factur-x GT (NOT sidecar — per ADR-012 §"Probe 5"), preprocesses + adapts + scores via PR(b), logs nested MLflow runs with resume safety.
3. **Pilot-13 CLI runner + Makefile target** (`scripts/run_pilot_13.py`, `make pilot-13`) — thin argparse wrapper for `make pilot-13 CFG=configs/pilot-13.yaml`.

### What is already done (predecessors)

- **ADR-009 Amendment 1 (2026-05-15)** designated the XML-grounded F1 evidence base for pilot #13.
- **ADR-010 (2026-05-15)** ratified `factur-x` (Python) as the canonical XML-extraction engine.
- **ADR-011 (2026-05-16)** ratified MLflow with `Tracker` Protocol + `log_dict` / `log_figure`.
- **ADR-012 (2026-05-17)** ratified the CII XML → `GroundTruth` parser AND surfaced the **Probe 5 sidecar-drift discovery**: the FeRD-shipped `.cii.xml` sidecars carry 2024-11-15 release-date stamps that diverge from the canonical 2018-era invoice dates in the embedded factur-x XML attachments. PR(c) MUST read GT via the factur-x route.
- **ADR-013 (2026-05-18)** ratified PR(b)'s scorer; the integration test `test_monetary_fields_uniformly_fn_across_cohort` documented PR(b)'s page-1-only baseline as an explicit deferral to PR(c).

### What is novel in this ADR

Five additions that no prior decision covered:

1. **The multi-page rasterizer with mtime-invalidated cache.** First write-side dependency on `pypdfium2` (DPI-configurable, page-iterable, Apache-2.0 / BSD-3-Clause). The cache (`<output_dir>/<pdf_stem>/page-N.png`) lets re-runs skip rasterization when the source PDF hasn't changed — load-bearing for the resume-safe sweep.
2. **The `(model × invoice) → MLflow nested-run` orchestration with resume safety.** Parent run accumulates cohort-pooled metrics + heatmap; nested runs hold per-(model, invoice) outcomes; resume queries `tags.mlflow.parentRunId = '<id>' AND tags.model_id = '<m>' AND tags.invoice_id = '<i>' AND status = 'FINISHED'` to skip completed tuples on re-run after ctrl-c.
3. **Strategy α: per-page extract + concat with `===== PAGE N =====` separators.** Three architecturally-different strategies were considered (α: per-page → concat; β: composite image grid → single extract; γ: multi-page-aware prompt). Strategy α won on three grounds: preserves ADR-009's single-image-per-call evidence-base contract, is the smallest deviation from PR(b)'s adapter assumptions, and lets per-model failure modes isolate to one page (a crash on page 7 doesn't lose pages 1-6's text). The separator is stripped before adapter Layer 1 to prevent separator-token contamination of per-model heuristics.
4. **The factur-x GT route enforced harness-wide via `_extract_groundtruth_via_facturx`.** ALL 26 invoices' GTs come from the PDF's embedded factur-x XML attachment; the FeRD-shipped sidecar is used only as a pairing discriminator ("if a sidecar exists, treat the PDF as a paired ZUGFeRD invoice"), never as a GT source. Empirically validated at full-cohort scale: 7/7 models score TP on XRECHNUNG_Einfach `issue_date` via this route (impossible via the sidecar, whose 2024-* dates every model reads as 2018-* from the visible PDF → silent FN).
5. **The threshold-sensitivity ablation as a methodology contribution.** Saved transcripts → offline re-score at arbitrary τ → cohort F1 by threshold. Established as `scripts/ablation_threshold.py`. Empirical finding: τ-knob swings produce ≤0.3% absolute Δ on cohort F1 across [0.3, 0.7] — the literature-default τ = 0.5 (Biten+ ICCV'19) is empirically defensible for this corpus. Thesis writeup does NOT need to argue for a specific τ.

## Current-state survey (2026-05-19)

| Component | Where | Ratified by | Role in PR(c) |
|---|---|---|---|
| `pypdfium2` | new dep this PR | This ADR | Multi-page PDF rasterization (PDF → PNG-per-page). |
| `sips` (macOS) | `make cohort-smoke` | ADR-009 (incidental) | Page-1-only render; preserved for ADR-009 §Decision evidence backwards-compatibility. NOT used by PR(c). |
| `factur-x` (Python) | `src/horus/zugferd/extract.py` | ADR-010 | Re-used in `harness._extract_groundtruth_via_facturx` for ALL 26 GT extractions. |
| `mlflow` | `src/horus/tracking.py` | ADR-011 | Parent + nested runs; `log_figure` for heatmap PNG; `search_runs` for resume. |
| `src/horus/eval/ground_truth.py` `FIELDS` registry | `parse_cii_xml` consumer | ADR-012 | 16-field schema; `FieldType.MONEY` / `DATE` / `STRING` / `CODE` discriminator drives scorer dispatch. |
| `src/horus/eval/scorer.py` `score()` + `EvalConfig` | per-invoice scoring | ADR-013 | Called once per `(model, invoice)` tuple inside the harness's nested run. |
| `src/horus/eval/adapters.py` `preprocess` + `to_predicted_dict` | per-model adapter pipeline | ADR-013 | Receives the multi-page concat as input (with separators stripped); existing Layer 1 + Layer 2 heuristics unchanged. |
| `matplotlib` | already installed (ADR-007) | — | Heatmap rendering for parent run. |
| `pdf2image` / `Pillow` `convert_from_path` | _not adopted_ | — | Considered for rasterization. Rejected: requires system poppler binary; pypdfium2 is pure-Python wheel + thread-safe + Apache-2.0. |
| PyMuPDF (`fitz`) | _not adopted_ | — | Considered for rasterization. Rejected: AGPL-3.0 (incompatible with thesis-defense distribution requirement); pypdfium2's BSD-3-Clause is unconstrained. |
| Apache PDFBox (Java) | _not adopted_ | — | Considered for rasterization. Rejected: adds JVM dep alongside Mustang (ADR-005); pypdfium2 keeps the Python-side single-toolchain story clean. |
| Embedded `make pilot-13` smoke | `Makefile` | This ADR | Documentation target — smallest-possible-smoke (1 model × 1 invoice) for re-validation after harness changes. |

The decision is **substantially overdetermined** by the kickoff plan + the 3 predecessor ADRs. The §"Options considered" walk below is documented for the 5-section discipline mandate; same retroactive-ratification shape as ADR-010 / ADR-011 / ADR-012 / ADR-013.

## Options considered

The kickoff explored **four orthogonal axes**.

### Axis 1 — Rasterization engine

| Option | Outcome |
|---|---|
| `sips` (macOS native, current `make cohort-smoke` baseline) | **Rejected.** macOS-only — incompatible with Linux CI / future cloud GPU experiments. Page-1-only flag wired in `make cohort-smoke`'s shell; expanding to per-page would require either a tight Make loop with subprocess overhead or a per-PDF Python wrapper that defeats the "just shell out" simplicity. Preserved for ADR-009 evidence reproducibility only. |
| pdf2image (`Pillow` `convert_from_path`) | **Rejected.** Requires system `poppler` binary (`brew install poppler` / `apt install poppler-utils`); adds an installation step + an OS-level dependency layer. Pure-Python wheel-based alternatives are preferable. |
| PyMuPDF (`fitz`) | **Rejected.** AGPL-3.0 license; incompatible with the thesis-defense distribution requirement (the thesis artifact is published under permissive license, not viral copyleft). Otherwise excellent (better PDF parsing than pypdfium2). |
| Apache PDFBox (Java) | **Rejected.** Adds a JVM dependency alongside Mustang (ADR-005). The thesis already has one Java tool; doubling that footprint isn't justified for rasterization. |
| **pypdfium2** | **Accepted.** Pure-Python (manylinux + macos-universal wheels); thread-safe; Apache-2.0 / BSD-3-Clause; PDFium-backed (Google Chrome's PDF renderer — substantial real-world testing). The `PdfDocument.render()` API gives per-page PIL images at configurable DPI in a few LOC. No system dependencies beyond what `uv` resolves. |

### Axis 2 — Page-aggregation strategy

| Strategy | Outcome |
|---|---|
| α: per-page `extractor.extract()` × N + `===== PAGE N =====` concat | **Accepted.** Preserves ADR-009's single-image-per-call contract (the evidence base for the cohort selection). Per-page outputs are independently inspectable in archived transcripts. Per-page failures isolate (one crashed page doesn't lose the other N-1). Separator stripped before adapter Layer 1 to prevent token contamination. |
| β: composite image grid (e.g., 2×2 layout of page PNGs) → single `extract()` | **Rejected.** Changes the input shape away from ADR-009's contract; would require re-validating the cohort against the new input shape (effort-equivalent to re-running ADR-009's smoke). Resolution-vs-information tradeoff: a grid layout halves the per-page rendered resolution for an A4 page, hurting model recall on small text (line items / VAT IDs). |
| γ: multi-page-aware prompt ("here are pages 1 and 2 of an invoice…") | **Rejected.** Cohort models (per ADR-009) have heterogeneous prompt-engineering responsiveness — some honor system-prompt format hints, others ignore them. Strategy α requires no per-model prompt tuning; γ requires per-model prompt audits. |

### Axis 3 — Ground-truth route (factur-x vs sidecar)

ADR-012 §"Probe 5" already discovered the sidecar-drift issue (FeRD's `.cii.xml` files carry 2024-11-15 release-date stamps, not the canonical 2018 invoice dates). PR(c) makes the harness-level enforcement explicit.

| Option | Outcome |
|---|---|
| Read GT from `.cii.xml` sidecar (PR(b) `test_scorer_integration.py`'s approach) | **Rejected at full-cohort scope.** Would silently corrupt the F1 numerator on every XRECHNUNG fixture (4 of 26 invoices) + suspicious behavior on some EN16931 fixtures. The 7/7 models scoring TP on XRECHNUNG_Einfach `issue_date` via factur-x (Probe 2 result) is empirically impossible via the sidecar. |
| Read GT from PDF's embedded factur-x XML attachment | **Accepted.** Implemented via `harness._extract_groundtruth_via_facturx(pdf)`, which delegates to `facturx.get_xml_from_pdf()` (ADR-010's canonical tool). Caching not necessary at this scale — extraction is sub-millisecond per invoice. |
| Hybrid: factur-x when present, sidecar fallback | **Rejected.** All 26 ZUGFeRD fixtures have embedded factur-x; no fallback path is reachable. The fallback would only matter on non-ZUGFeRD test corpora (future scope, separate ADR). |

### Axis 4 — Resume-safety protocol

| Option | Outcome |
|---|---|
| No resume: ctrl-c → start from scratch on re-run | **Rejected.** A 3-hour 26 × 7 sweep cannot tolerate restart-from-scratch as the default. The user-stated rule (handoff §3) "Cascade D is a long-running vertical with frequent terminal interruptions" makes resume-safety load-bearing. |
| Filesystem-based: hash the (cfg, model, invoice) tuple → check a marker file under `mlartifacts/` | **Rejected as primary.** Tightly couples the resume protocol to MLflow's artifact root layout; brittle if MLflow ever changes the layout (it has, between v2 and v3). MLflow's `search_runs` API is the stable abstraction. |
| MLflow `search_runs(parent_run_id, model_id, invoice_id, status=FINISHED)` → skip the tuple | **Accepted.** Uses MLflow's `tags.mlflow.parentRunId` (built-in) + harness-set `tags.model_id` + `tags.invoice_id` + `status` filter. Wrapped in try/except so a search-API hiccup falls through to re-running (correctness-preserving on the slow path). |

## Decision + integration thoughts

PR(c) ships:

- **`src/horus/eval/rasterize.py`** — `rasterize_pdf(pdf_path, output_dir, dpi)` → list of PNG paths, one per page. Cache-aware (re-uses prior renders when source mtime ≤ output mtime). Validates non-empty PDFs; errors on encrypted / unparseable files; tested across all 26 paired ZUGFeRD invoices in `tests/test_rasterize.py`.
- **`src/horus/eval/harness.py`** — `run_cohort(cfg, invoice_subset=None, model_subset=None)` → `HarnessRunResult`. Pure functions (`_strip_page_separators`, `_micro_f1_from_counts`, `_aggregate_per_field_scores`, `_invoice_profile`, `_model_slug`, `_filter_*`, `_extract_and_concat`, `_render_cohort_heatmap`) cover ~700 LOC and have isolated unit tests; the end-to-end `run_cohort` orchestrator is tested via 5 integration tests with `_MockExtractorForHarness` (no VLM dependency).
- **`src/horus/config.py`** — `RasterizerConfig` (dpi + output_dir + cache policy) + `CohortConfig` (corpus_root + working_models + parent_run_name + resume_on_existing_run) Pydantic sub-models added to `ExperimentConfig`. Both nullable at the parent config — they're only required for cohort runs (harness raises with a precise message if missing).
- **`configs/pilot-13.yaml`** — the single source of truth for the full pilot. 7 working models (filtered from ADR-009's 10 by Step 4 of PR(c) smoke); 26 paired invoices via `_list_paired_invoices`.
- **`scripts/run_pilot_13.py`** + **`make pilot-13`** — argparse + Makefile entrypoints.
- **`scripts/inspect_pilot_13.py`** — read-only MLflow inspector. Surfaces per-(model, invoice) grid, per-model aggregate, Probe 1 (MONEY-field TPs on EN16931_Einfach), Probe 2 (XRECHNUNG factur-x route DATE outcomes) from any pilot-13 parent run.
- **`scripts/ablation_threshold.py`** — offline re-scorer at arbitrary τ values.
- **`tests/test_scorer_integration_multipage.py`** — 4 regression tests pinning Step 7's empirical evidence (MinerU multi-page lift, due_payable_amount TP, XRECHNUNG factur-x-route TP, documented MONEY-field gap as regression baseline).

### Empirical results — full 26 × 7 sweep

Step 7 (parent_run_id `df6bce67369c47948d10dfa0d2624490`): **182 / 182 tuples completed, 0 failed**. Pooled cohort micro_F1 = **0.4908** (vs PR(b) ~0.20 page-1-only baseline → **2.45× lift**). Per-model best: MinerU2.5-Pro = 0.710 mean across 26 invoices. Full breakdown + lift table: `docs/retros/m2d.5-pilot-13-cohort-harness.md`.

Step 8 (threshold ablation): cohort Δ across τ ∈ [0.3, 0.7] = 0.0031 (0.3% absolute). Metric is τ-robust; literature default τ = 0.5 is empirically defensible.

### Known limitation deferred to a follow-up PR

The Layer 2 MONEY-field heuristics in `to_predicted_dict` (PR(b)'s adapter) were authored against page-1-only inputs. With PR(c)'s multi-page concat feeding the adapter, only `due_payable_amount` (BT-115, "Zahlbetrag") flips FN → TP on MinerU. The other 4 MONEY fields (BT-106, BT-109, BT-110, BT-112) remain FN even though the page-2 totals are visibly present in the archived transcripts (`docs/sources/transcripts-multipage/`). This is a PR(b) adapter heuristic gap, not a PR(c) harness gap — the regression test `tests/test_scorer_integration_multipage.py::test_multipage_money_field_gap_documented` captures the current state as the baseline. When the Layer 2 follow-up flips these to TP, the test will FAIL — the desired "limitation is gone" signal.

### Out of scope (explicit deferrals)

- **Layer 2 MONEY-field heuristic iteration** — separate PR, separate ADR. Captured as the canonical follow-up.
- **`delivery_date` (BT-72) systematic FN on XRECHNUNG_Einfach** — all 7 models output the visible date; GT mismatches. Could be a XRECHNUNG-specific BT-72 convention or a harness normalizer issue. Low priority, doesn't affect cohort ranking; future curiosity.
- **Per-page scoring (vs per-invoice)** — current harness scores at invoice granularity. Per-page scoring would let us see WHICH page each field lifts from; deferred until needed.
- **Cohort cloud-baseline comparison** (Brainstorm v2 §8.2) — post-pilot.
- **Field-weighted F1** (Brainstorm v2 §5.2) — supervisor-meeting-blocked.

## Source archival

Two new stubs land with this PR per `horus-source-archival`:

- `docs/sources/tools/pypdfium2.md` — pypdfium2 (Pure-Python PDFium binding), Apache-2.0 / BSD-3-Clause, GitHub: bblanchon/pdfium-binaries + pypdfium2-team/pypdfium2. Authored at Step 0b (pre-`/branch-start`). Captures the upstream's Apache-2.0 license metadata + the security-update cadence + the version pin rationale (`>=4.30,<5` — major-version-pinned to v4 line for API stability; v5 line carries breaking changes per the `pypdfium2-team/pypdfium2` CHANGELOG).
- (No paper stubs — PR(c) builds on PR(b)'s already-archived literature, not new theory. The ANLS metric stubs from ADR-013 carry over.)

Re-used sources (no new stub needed):

- `docs/sources/tools/mustangproject.md` (ADR-005) — Mustang's role in cross-tool factur-x XML validation; consumed transitively by `factur-x` Python lib.
- `docs/sources/papers/biten-2019-anls-iccv.md` (ADR-013) — ANLS metric + τ = 0.5 threshold rationale; consumed by PR(c)'s threshold-sensitivity ablation.

Empirical evidence saved as cited sources:

- `docs/sources/transcripts-multipage/` — 182 multi-page transcript files, one per `(model, invoice)` tuple from Step 7. Determinism-verified (only `# Extract: <s>` per-run timing differs across re-runs).

## Cross-references

- Predecessor ADRs: `docs/decisions/ADR-009-pilot-vlm-cohort.md` (Amendment 1 — evidence-base reframing), `docs/decisions/ADR-010-xml-extraction-script.md` (factur-x route), `docs/decisions/ADR-011-experiment-tracker-integration.md` (MLflow Tracker Protocol), `docs/decisions/ADR-012-cii-ground-truth-parser.md` (Probe 5 sidecar drift), `docs/decisions/ADR-013-vlm-prediction-scorer.md` (per-field F1 scorer + ANLS\* threshold).
- This ADR's retro: `docs/retros/m2d.5-pilot-13-cohort-harness.md` (empirical evidence summary + thesis-defense framing + cross-cutting learnings for `cascade-system` queue).
- Plan: `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §6 PR(c) breakdown (12-step authoring plan; superseded by this ADR + retro).
- Handoff: `~/Projects/cascade-system/docs/handoffs/cascade-d-master-thesis.md` (Cascade D vertical orientation; PR(c) is the closing PR of pilot #13's 3-PR split).
- Issue: [`ReebalSami/horus#13`](https://github.com/ReebalSami/horus/issues/13) — pilot #13 first data loop; closed by this PR.
