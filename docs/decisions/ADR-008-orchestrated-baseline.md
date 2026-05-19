# ADR-008 — Orchestrated-baseline document pipeline: dual-track (Docling primary + MinerU pipeline backend cross-check)

| Field | Value |
|---|---|
| **Status** | Accepted (smoke evidence captured 2026-05-13 — see §"Smoke evidence — captured transcript") |
| **Date** | 2026-05-13 |
| **Milestone** | M2D.5 step 4 — orchestrated-baseline enablement (issue #11) |
| **Authored by** | Cascade D (M2D.5 orchestrated-baseline session, plan `~/.windsurf/plans/horus-issue-11-orchestrated-baseline-adr-8006a7.md`) |
| **Issue** | `ReebalSami/horus#11` |
| **Forward-pointer resolution** | The "cohort ADR #14" forward-pointer (cohort selection for the orchestrated-baseline pipeline's MinerU-2.5-Pro VLM stage) is resolved by **ADR-009** (`docs/decisions/ADR-009-pilot-vlm-cohort.md`). ADR-009 includes MinerU-2.5-Pro VLM 1.2B as a **Cat 1 cohort entry** in single-shot mode; pilot #13's H1 single-shot-vs-orchestrated comparison pairs ADR-009's single-shot evaluation with this ADR's orchestrated-pipeline evaluation. Both ADRs co-exist; this ADR is NOT superseded. |
| **Supersession trigger** | (a) Docling lapses maintenance (no release ≥ 6 months AND issue tracker stalls AND a breaking upstream change remains unaddressed) → fallback: drop Docling, repromote MinerU pipeline backend or PaddleOCR PP-Structure as primary; OR (b) Brainstorm v2 §6 H2 directional-flip prediction is empirically falsified at pilot AND falsification persists at cohort-scale evaluation → orchestrated arm dropped per v2 §3 D6 reversibility clause + supersession follow-on; OR (c) Western-pretraining caveat for MinerU pipeline backend proves load-bearing on German invoices (verified at pilot #13 via German-corpus eval showing systematic Chinese-pretraining bias on Latin-script German content) → swap cross-check companion to `unstructured` OSS or PaddleOCR PP-Structure; OR (d) Linux Foundation Agentic AI Foundation re-licenses Docling away from Apache-2.0 → fallback: pin to last Apache-2.0 version, repromote alternative; OR (e) MinerU 3.x removes the `pipeline` backend in favor of VLM-only modes → swap cross-check to PaddleOCR PP-Structure or LayoutParser-replacement. |

## Context

Brainstorm v2 §6 hypothesis **H2** (Layer-1 architecture, directional-flip prediction) is the principal motivator of this ADR:

> *Single-shot end-to-end VLMs will outperform orchestrated specialist pipelines on clean structured invoices (ZUGFeRD); orchestrated pipelines will outperform single-shot VLMs on degraded real-world Belege where validator-driven retry can correct extraction errors.*

H2 is a **Layer-1 sub-question** — not the main thesis question. The main RQ is the three-layer cascade (doc-VLM → KG → analytical query) on German B2B accounting workflows under §203 StBerG. H2 sits inside Layer 1's architecture-comparison axis (v2 §1.1 — "the architecture comparison" between single-shot and orchestrated paths) and is explicitly enumerated in v2 §3 D6 ("Layer 1 expanded to four-stage pipeline … where the agentic vs single-shot comparison lives") with the reversibility clause "single-shot wins decisively → orchestrated dropped per ADR." This ADR enables H2 by selecting the **orchestrated arm's test instrument(s)**; the single-shot arm is the concern of cohort ADR #14 (also blocked-by issue #10).

H2 is locked-a-priori per v2 §4.1 (no HARKing — hypotheses fixed before seeing test results). The ADR does **not** lock the threshold parameters of H2 (the *X* and *Y* percentage-point quantifications); those belong in issue #17's first supervisor progress-check hypothesis-set deliverable per v2 §4.1 + brainstorm §4. This ADR locks the *tooling*; #17 locks the *hypothesis specification*.

### Literature anchor — Berghaus 2025

Berghaus et al. 2025 (Fraunhofer IAIS + Lamarr Institute, arXiv 2509.04469; archived at `docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md`) benchmarked native multi-modal cloud VLMs (GPT-5, Gemini 2.5, Gemma 3) against the **Docling library** as a text-based parsing baseline on invoice-extraction tasks. Verified key numbers:

- **Scanned Invoices**: native multi-modal **92.71%** vs Docling-parsed **64.03%** — ~29 pp gap.
- **Scanned Receipts**: native **87.46%** vs Docling-parsed **47.00%** — ~40 pp gap.

These numbers establish the literature prior for **H2's clean-document arm**: cloud single-shot beats Docling-the-library by a wide margin on clean scanned invoices. HORUS replicates this comparison on the **Oct-2025 local open-source cohort which Berghaus excluded** (no Granite-Docling / olmOCR-2 / Nanonets-OCR2 / dots.ocr / MinerU 2.5 in their candidate set). That replication is the literature gap the orchestrated-baseline ADR enables HORUS to test. **H2's degraded-document arm** (where orchestrated + validator-retry is predicted to overtake single-shot) is less established in literature and is where HORUS aims for the more original empirical contribution.

### Empirical-context anchor — ADR-007's 258M failure-mode taxonomy

ADR-007 §"Smoke evidence — interpretation" finding 3 documented Granite-Docling-258M's 4-prompt × 4-failure-mode capability gap on a clean fpdf2-rendered HORUS ZUGFeRD invoice (hallucinated boilerplate / false negation / page-as-screenshot / token-repetition loop — zero correct extractions). This taxonomy is **empirical context for what failure modes the orchestrated path may handle differently** — not a justification for needing the H2 comparison itself. The H2 framing predates ADR-007's smoke evidence (locked in v2 §6 dated 2026-05-06; ADR-007's smoke was captured 2026-05-12). Using ADR-007's taxonomy as the *reason* for the comparison would be post-hoc rationalization. Using it as forward-pointer evidence of *one specific way* the directional flip may manifest is honest.

### Discipline gate

Per `horus-decision-discipline` rule + ADR-001: every tool / library / framework / dataset choice in HORUS is a "significant decision" requiring an ADR with the 5 mandatory sections (Current-state survey / Options considered / Decision + integration thoughts / Source archival / Supersession trigger). Issue #11 acceptance criteria: ADR landed on `main` with 5 sections + chosen library installed (`uv add docling` or equivalent) OR explicit defer/skip with supersession-trigger; `make install && make test` passing; ≥ 1 source stub in `docs/sources/tools/`.

## Current-state survey (2026-05-13)

Survey methodology: PyPI version checks via `uv add`; HuggingFace Hub readme + benchmark cross-reference; `context7` MCP queries `/docling-project/docling` and `/opendatalab/mineru` for API confirmation; cross-check against brainstorm v2 §7.1 + §7.5 + §7.8 + §9.1 + §9.2; web verification of Berghaus 2025 numbers via `arxiv.org/html/2509.04469v1`; web verification of MinerU 2.5-Pro v1.6 score via `huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B`.

### Library / framework metadata (PyPI, 2026-05-13)

| Library | Latest installed | License | Architecture class | Notes |
|---|---|---|---|---|
| **docling** | 2.93.0 | Apache-2.0 | Orchestrated specialist (default `StandardPdfPipeline`) + optional VLM mode | IBM Research → Linux Foundation Agentic AI Foundation. Two pipeline classes: `StandardPdfPipeline` (orchestrated; layout + OCR + table-recognition stages) and `VlmPipeline` (single-shot, Granite-Docling-258M default). `PdfFormatOption(pipeline_cls=...)` selects mode; `PdfPipelineOptions(do_ocr=..., do_table_structure=...)` controls stage knobs. CLI: `docling <input> --to md --to json --no-ocr`. Ships `py.typed`. Pulled 37 deps including `docling-core==2.75.0`, `docling-ibm-models==3.13.2`, `docling-parse==5.11.0`, `pypdfium2==5.8.0` (then resolved down by MinerU's pin), `rapidocr==3.8.1`. |
| **mineru** | 3.1.11 | Apache-2.0 | **Dual-backend**: `pipeline` (orchestrated, this ADR's scope; 86.2 OmniDocBench v1.5) + `hybrid-auto-engine` / `vlm-auto-engine` (single-shot variants; 95.69 OmniDocBench v1.6 for MinerU2.5-Pro-VLM, OUT OF SCOPE here) | OpenDataLab. CLI-driven: `mineru -p <input> -o <output> -b pipeline -l latin` selects orchestrated mode with Latin-script OCR (German-friendly default; replaces MinerU's default `-l ch` Chinese). Pure-CPU compatible per OpenDataLab README. Does NOT ship `py.typed` — added override to `[tool.mypy.overrides]`. Pulled 40 deps including `mineru-vl-utils==0.2.7`, `modelscope==1.36.3`, `onnxruntime==1.26.0`, `pdfminer-six==20260107`, `pypdfium2==4.30.0` (downgraded from Docling's 5.8.0 to satisfy MinerU's pin — verified non-breaking via `make test` 16/16 pass). |

### MinerU 2.5-Pro (95.69 v1.6) — out of scope here, properly cohort ADR #14's concern

A factual nuance worth pinning: **MinerU2.5-Pro's 95.69 score on OmniDocBench v1.6** (April 2026, arXiv 2604.04771; HuggingFace `opendatalab/MinerU2.5-Pro-2604-1.2B`) is from the **VLM backend** (single-shot, 1.2B params), not the orchestrated pipeline. OpenDataLab's GitHub README explicitly distinguishes the two: *"The pipeline backend achieves a score of 86.2 on OmniDocBench (v1.5), surpassing the previous-generation mainstream VLM MinerU2.0-2505-0.9B."* The two backends belong in different ADRs:

- **MinerU pipeline backend, 86.2 v1.5** → orchestrated-baseline scope → THIS ADR.
- **MinerU2.5-Pro VLM backend, 95.69 v1.6** → single-shot cohort scope → cohort ADR #14 (forward-pointer).

This distinction is captured in the enriched `docs/sources/tools/mineru-2-5.md` source stub.

### `know-your-hardware` cross-check (M1 Pro / 16 GB / Metal 4 / 14 GPU cores / no CUDA)

Both libraries Apple-Silicon-compatible. Docling runs CPU + MPS via PyTorch backend. MinerU's `-b pipeline` flag explicitly targets pure-CPU compatibility per OpenDataLab README ("supports pure CPU"). Neither requires AWS escalation for M2D.5 pilot scope (≤ 50 invoices). The `hybrid-auto-engine` / `vlm-auto-engine` MinerU backends require ≥ 8 GB VRAM and are **not invoked** by this ADR — the `-b pipeline` flag is the load-bearing constraint; if a future cohort ADR considers MinerU's hybrid mode, that's a separate `know-your-hardware` evaluation.

## Options considered

| Option | Stack | Architecture class | License | Why considered | Outcome |
|---|---|---|---|---|---|
| **Docling library** (`StandardPdfPipeline`, IBM Research / LF AAIF) | Python, Apache-2.0 | Orchestrated specialist | Apache-2.0 | Issue #11 indicated; brainstorm v2 §7.8; Berghaus 2025 comparand at 64.03% on Scanned Invoices; MLX-aware; 2025–26 active development. Two pipeline classes (Standard + Vlm); selecting `StandardPdfPipeline` keeps orchestrated-only scope while `VlmPipeline`-with-Granite-Docling-258M is empirically excluded by ADR-007 | **Chosen primary — see Decision** |
| **MinerU pipeline backend** (`mineru -b pipeline`, OpenDataLab) | Python (CLI-driven), Apache-2.0 | Orchestrated specialist | Apache-2.0 | Independent codebase + research lab from Docling (Asia-Pacific OpenDataLab vs IBM Research); modern (2025–26 active dev; v3.1.11 current); 86.2 reported OmniDocBench v1.5 score on pipeline backend; pure-CPU-compatible per OpenDataLab README. Chinese-origin pretraining caveat documented (verification gate at pilot loop #13). | **Chosen cross-check companion — see Decision** |
| **PaddleOCR PP-Structure** (Baidu PaddlePaddle) | Python, Apache-2.0 | Orchestrated specialist (classical modular: detection + recognition + structure analysis as separate model stages) | Apache-2.0 | Mature, broadly deployed in Western + Asian production OCR pipelines; classical-pipeline reference; same Chinese-origin pretraining caveat as MinerU. Distinct from `PaddleOCR-VL` 1.5 (single-shot small VLM, covered in `paddleocr-vl.md`) | **Considered, fallback only.** Pre-Oct-2025-wave architectural lineage; classical CV models (CNN-era foundation). Preserved as fallback per supersession trigger (c) if MinerU pipeline backend proves to have install / Apple-Silicon friction or systematic Chinese-pretraining bias on German invoices. |
| **`unstructured` Python library** (Unstructured Technologies, OSS Apache-2.0 only) | Python, Apache-2.0 | Orchestrated ingestion library (parser-focused; extraction-light) | Apache-2.0 | Western-origin pretraining (no Chinese-pretraining caveat); §203-admissible (self-hosted only). Mature, broadly adopted in Western RAG-ingestion pipelines | **Considered, fallback only.** Weakness as H2 test instrument: Unstructured is more commonly an *ingestion-for-RAG* preprocessor than a key-value-extraction specialist. Less benchmarked on document-extraction tasks. Preserved as alternative supersession-trigger (c) fallback. |
| **Unstructured.io Serverless API + On-Prem hosted product** | Python SDK + proprietary cloud / hosted appliance | Orchestrated ingestion service | proprietary | (would otherwise be cloud-baseline candidate) | **Eliminated.** §203 StGB + §62a StBerG framing per brainstorm v2 §7.6 + `docs/sources/legal/stgb-203.md` + `docs/sources/legal/stberg-62a.md`: cloud routing of Mandantendaten is forbidden for Steuerberater. Self-hosted OSS only is admissible. |
| **LayoutParser** (Allen AI; Detectron2-based) | Python, Apache-2.0 | Orchestrated specialist (layout-detection-focused; pre-Oct-2025-wave) | Apache-2.0 | Issue #11 alternative; classical-CV reference | **Rejected.** Pre-Oct-2025-wave (last release 2022; Detectron2 = 2019-vintage). Brainstorm v2 §7.1 implication: building Layer 1 around pre-Oct-2025-wave tools "would be like building an NLP thesis around word2vec in 2023." Sets a clean pre-2025-wave exclusion precedent for follow-on cohort ADRs. |
| **LangChain document loaders + handcrafted extractors** | Python, MIT | Wrapper-library + DIY | MIT | Issue #11 alternative | **Rejected (out-of-scope).** LangChain document loaders are wrappers around other parsers (PyPDF / Unstructured / PDFMiner) — DIY infrastructure, not an orchestrated specialist pipeline. Different scope per the ADR-008 plan critique of issue #11's alternatives list. |
| **Skip orchestrated baseline entirely** | n/a | n/a | n/a | Issue #11 alternative #4 (AC explicit permission) | **Rejected.** H2 is locked-a-priori per v2 §4.1 + §6 (no HARKing — hypotheses fixed before testing). Skipping forfeits the directional-flip test that is a Layer-1 sub-question of the thesis. Supervisor progress check #17 needs concrete instruments on **both** arms (single-shot via cohort ADR #14; orchestrated via this ADR). Defer-and-skip is the worst path for scientific correctness. |
| **MinerU2.5-Pro VLM (1.2B, 95.69 v1.6)** | Python, Apache-2.0 | **Single-shot VLM** | Apache-2.0 | (would otherwise enter as "best-in-class single-shot") | **Out of scope here.** VLM backend = single-shot architecture → cohort ADR #14's concern. One-line forward-pointer: see `docs/sources/tools/mineru-2-5.md` for the dual-backend distinction. |

## Decision + integration thoughts

**Chosen: Dual-track orchestrated baseline — Docling 2.93.0 (`StandardPdfPipeline`, primary, Apache-2.0) + MinerU 3.1.11 (`-b pipeline`, cross-check companion, Apache-2.0).**

### Cross-check companion selection — trade-off table

The cross-check companion role required choosing between three Apache-2.0 self-hosted-OSS candidates. Evaluated explicitly:

| Cross-check candidate | For | Against | Verdict |
|---|---|---|---|
| **MinerU pipeline backend** | Modern (2025–26 active dev; v3.1.11 current); independent codebase + research lab from Docling; high reported OmniDocBench v1.5 score (86.2) on pipeline backend; pure-CPU-compatible | Chinese-origin pretraining caveat (verification gate at pilot #13) | **Chosen** |
| PaddleOCR PP-Structure | Mature production deployment; classical-pipeline reference | Pre-Oct-2025-wave architectural lineage (CNN-era foundation); same Chinese-pretraining caveat | Fallback per supersession (c) |
| `unstructured` OSS | Western-origin pretraining; no Chinese-pretraining caveat | Ingestion-RAG-focused, not extraction-specialist; weaker H2 test instrument for orchestrated-specialist class | Fallback per supersession (c) |

**Lean → MinerU pipeline backend wins** the cross-check role: modernity + lab-independence-from-Docling outweigh the Chinese-pretraining caveat for this milestone (the caveat is a verification gate, not a categorical exclusion; pilot #13 is the test). PP-Structure's classical lineage and `unstructured`'s ingestion-RAG focus both make them weaker H2 instruments for the *orchestrated-specialist* architectural class. Both preserved as supersession-trigger (c) fallbacks.

### Rationale (top-level)

1. **Mirror of ADR-005's scientific-correctness pattern.** ADR-005 chose `factur-x` (Python generator) + Mustang Project (Java validator) as a dual-track because *"a tool that generates AND validates its own output is a closed loop"* — the analogous concern here is *"a single orchestrated library that generates AND benchmarks its own architectural class is a closed loop."* If HORUS runs Docling-only and gets a number ~64%-Berghaus-shape, we cannot tell whether (a) orchestrated-as-a-class is underperforming single-shot, or (b) Docling-specifically has a failure mode that doesn't generalize. Pairing Docling with MinerU pipeline backend gives H2's orchestrated arm an *independent* second instrument — the same closed-loop-avoidance argument that justifies dual-track ground-truth in ADR-005.

2. **Independent lab + codebase.** Docling = IBM Research → Linux Foundation Agentic AI Foundation (Western, large-org, IP-vetted). MinerU = OpenDataLab (Asia-Pacific, university-spinoff lineage, modelscope-distributed). The two share no upstream model weights, no upstream training data, and no upstream architectural choices. A correlation between them (e.g., both fail on the same German invoice fields) is informative; a correlation between two IBM-derived libraries would not be.

3. **License hygiene.** Both Apache-2.0; both linking-only-friendly for academic non-distributed contexts. No new copyleft entries beyond fpdf2's LGPL-3.0+ already accepted in ADR-006. No license auditing surprises at writeup phase.

4. **Hardware fit (`know-your-hardware`).** Both run on M1 Pro / 16 GB / Metal 4 without AWS escalation: Docling via PyTorch backend with optional MPS; MinerU via `-b pipeline` flag for pure-CPU mode. The `hybrid-auto-engine` / `vlm-auto-engine` MinerU backends (which require ≥ 8 GB VRAM) are explicitly NOT invoked — pipeline backend is the binding constraint.

5. **H2 directional-flip framing.** Berghaus 2025 establishes the prior that single-shot wins on clean Scanned Invoices (92.71 vs 64.03 on Docling). H2's *clean-document* arm replicates this prior on the open-source cohort Berghaus excluded — expected outcome: orchestrated underperforms single-shot. H2's *degraded-document* arm is the more original empirical contribution, where orchestrated + validator-retry may overtake single-shot. Both arms need a credible orchestrated test instrument; Docling alone cannot be that instrument because Berghaus already characterizes its failure mode in the clean-document setting.

### Module / abstraction decisions deferred to follow-on ADRs

This ADR is **install-only + smoke-only** (matches ADR-007's pattern). No `src/horus/orchestrated/` runner abstraction is added; that's the natural concern of a future runner-abstraction ADR (likely emerging at pilot #13's design).

Specifically deferred:

- **Common-output normalization layer** (orchestrated output format vs single-shot VLM output format unification) → emerges at cohort comparison sub-issue under #13 / #14
- **Validator-retry stage** (the "+ validator" half of H2's degraded-document arm) → conditional per v2 §3 D11; decided on error analysis at pilot
- **Layer-1-architecture decision** (D6 reversibility — single-shot vs orchestrated as primary spine) → post-pilot Layer-1 ADR

### Forward link to issue #17 (supervisor progress-check agenda — H2 hypothesis-set lock channel)

This ADR enables H2 by selecting the orchestrated-arm test instruments. It does **NOT** lock H2's threshold parameters (the *X* and *Y* percentage-point quantifications). Threshold locking belongs in **issue #17's first supervisor progress-check hypothesis-set deliverable** per v2 §4.1 + brainstorm §4. Issue #17 explicitly carries scope item *"Hypothesis set (frozen v2 §3 or §4 — TBD via ADR if not already locked elsewhere)"* — H2's directional-flip prediction belongs there. Cross-link bidirectional: this ADR cites #17 as the formal hypothesis-lock channel; #17 will cite this ADR (and cohort ADR #14) as the tooling enablers.

### Integration with already-decided components (current state, post-this-ADR)

- **ADR-005** (factur-x + Mustang as ground-truth source) — the orchestrated baseline consumes Mustang-validated PDFs as input; ground-truth XML extracted via `factur-x` per `scripts/extract_zugferd_xml.py` (sub-issue #15) is the reference for compliance-aware F1 scoring.
- **ADR-006** (fpdf2 visual layer) — Docling and MinerU read the visual layer; the smoke evidence below uses the fpdf2-rendered `data/raw/smoke/invoice-001.pdf`.
- **ADR-007** (MLX-VLM + Transformers + MPS) — non-overlapping inference stacks. Orchestrated specialists do not route through ADR-007's stack. *Exception*: if Docling's optional `VlmPipeline`-with-Granite-Docling stage is later activated, that stage's VLM-inference call would route through ADR-007's stack — but ADR-007's smoke evidence empirically excluded Granite-Docling-258M for HORUS-style invoices, so this exception is moot until a 3B+ MLX-VLM is plugged into Docling's `VlmPipeline`. Out of scope for ADR-008.
- **`pyproject.toml`** — `docling >= 2.93.0` and `mineru >= 3.1.11` added to `[project] dependencies`. Both pulled by `uv sync`. `mineru.*` mypy override added (no `py.typed` shipped); `docling` ships `py.typed` since 2.x — no override needed.
- **`pypdfium2` constraint resolution**: Docling pinned `pypdfium2 >= 5.x`; MinerU pinned `pypdfium2 < 5.x`. `uv` resolved to MinerU's pin (4.30.0). Verified non-breaking via `make test` 16/16 pass (no Docling regression on the existing test surface). Captured to `cascade-system/queue/pending-review.md` for `@sprint-review` to consider as upstream-PR opportunity to either Docling (lower its `pypdfium2` floor) or MinerU (raise its `pypdfium2` ceiling).

### Forward links (work items unblocked by this ADR)

- **Issue #13** — first pilot data loop (now has both orchestrated baseline + Docling/MinerU dual-track ready as input); orchestrated-arm of the H2 test runs at #13.
- **Issue #14** — single-shot cohort selection ADR; pairs with this ADR to provide the single-shot arm of H2's test.
- **Issue #15** — XML-extraction script (factur-x); produces ground-truth for compliance-aware F1 scoring against orchestrated output.
- **Issue #16** — experiment tracker (MLflow indicated); will record orchestrated-arm metrics alongside single-shot-arm metrics.
- **Issue #17** — supervisor progress-check agenda; H2 hypothesis-set deliverable will cite this ADR + cohort ADR #14 as tooling enablers.

## Smoke evidence — methodology

Per `make-sure-it-works`, this ADR captures hands-on smoke evidence of the **chosen primary** library (Docling) running end-to-end on M1 Pro hardware against a real HORUS-generated ZUGFeRD invoice — mirrors the ADR-007 smoke pattern (single-backend smoke at install-ADR scope; full cross-backend comparison deferred to pilot #13). MinerU pipeline backend is install-verified (importable + CLI invocable; see "Library / framework metadata" above) but its on-invoice smoke is deferred to pilot #13 alongside the single-shot cohort to keep this PR scope-bounded.

1. **Pre-condition**: `data/raw/smoke/invoice-001.pdf` (Factur-X 1.08 BASIC profile, generated by `make zugferd-smoke` per ADR-005 + ADR-006).
2. **Backend — Docling `StandardPdfPipeline`**: load `DocumentConverter()` (default `StandardPdfPipeline`), call `converter.convert(pdf_path)`, capture model-load wall-time, conversion wall-time, output character count, output snippet (first ~500 chars from `result.document.export_to_markdown()`), structural counts (n_pages, n_tables, n_figures from `result.document` accessors).
3. **Cross-comparison reference (out-of-band)**: the ZUGFeRD XML embedded in the PDF (extracted via `factur-x` per ADR-005) is the ground-truth target. The smoke does NOT compute compliance-aware F1 — that's pilot #13's job. The smoke confirms (a) Docling installs + runs end-to-end on M1 Pro, (b) produces non-empty structured output on a real HORUS invoice, (c) captures forward-pointer evidence (output structure / failure modes) for pilot #13.
4. **Captured transcript** — see §"Smoke evidence — captured transcript" below.

## Smoke evidence — captured transcript (M1 Pro, 2026-05-13)

`make orchestrated-smoke` ran end-to-end on M1 Pro / 16 GB / Metal 4 / Python 3.14.3 / docling 2.93.0. The pre-step `make zugferd-smoke` produced `data/raw/smoke/invoice-001.pdf` (5,709 bytes; Factur-X 1.08 BASIC EN16931-compliant per Mustang validator output, 64 rules fired, 0 failed). Verbatim transcript from the first run (cold cache, model weights downloaded):

```
========================================================================
HORUS orchestrated-baseline smoke — ADR-008 evidence
========================================================================
Input PDF:      data/raw/smoke/invoice-001.pdf
Input size:     5,709 bytes

------------------------------------------------------------------------
Backend:        docling (StandardPdfPipeline, default)
Load wall-time:   0.01 s
Loading weights: 100%|██████████| 770/770 [00:00<00:00, 880.23it/s]
Convert wall-time: 116.32 s
Output length:  823 chars (markdown export)
Structure:      pages=2 texts=9 tables=1 pictures=0
Status:         ok

Output snippet (first 500 chars of markdown):

## RECHNUNG

## LIEFERANT

## RECHNUNGSEMPFÄNGER

HORUS Test Seller GmbH Teststraße 1 20095 Hamburg DE

USt-ID: DE123456789

HORUS Test Buyer GmbH DE

|   Pos. | Bezeichnung       | Menge Einheit          | Einzelpreis   | Gesamt     |
|--------|-------------------|------------------------|---------------|------------|
|      1 | Beratungsleistung | 1 C62                  | 100.00 EUR    | 100.00 EUR |
|        |                   | Zwischensumme (netto): |               | 100.00 EUR |
|
... [truncated; full length 823 chars]
------------------------------------------------------------------------

========================================================================
SUMMARY: Docling StandardPdfPipeline ran to completion
========================================================================
```

The first-run elapsed 116.32 s for `convert(...)` because of cold-cache model downloads — three OnnxRuntime models were downloaded inline by Docling's default OCR engine (`rapidocr` 3.8.1):

- `ch_PP-OCRv4_det_mobile.onnx` (4.53 MB) — text detection
- `ch_ppocr_mobile_v2.0_cls_mobile.onnx` (0.56 MB) — text-line classification
- `ch_PP-OCRv4_rec_mobile.onnx` (10.35 MB) — text recognition

Plus 770 layout-classifier weight tensors loaded from `docling-ibm-models`. **Cached re-run convert wall-time: 4.43 s** (a 26× speedup; first-run is dominated by network + model-load amortisation, not inference). Layout classifier load is now ~0.4 ms (1879 it/s) vs 1.1 ms cold (880 it/s); inference itself is the load-bearing cost.

The full 823-char markdown export (captured separately to verify completeness; not re-run via `make orchestrated-smoke` because the snippet truncation at 500 chars is by design):

```markdown
## RECHNUNG

## LIEFERANT

## RECHNUNGSEMPFÄNGER

HORUS Test Seller GmbH Teststraße 1 20095 Hamburg DE

USt-ID: DE123456789

HORUS Test Buyer GmbH DE

|   Pos. | Bezeichnung       | Menge Einheit          | Einzelpreis   | Gesamt     |
|--------|-------------------|------------------------|---------------|------------|
|      1 | Beratungsleistung | 1 C62                  | 100.00 EUR    | 100.00 EUR |
|        |                   | Zwischensumme (netto): |               | 100.00 EUR |
|        |                   | USt. 19 %:             |               | 19.00 EUR  |
|        |                   | Bruttosumme:           |               | 119.00 EUR |
|        |                   | Zahlbar:               |               | 119.00 EUR |

Datum: 11.05.2026

Generiert von HORUS - Synthetic ZUGFeRD invoice (ADR-006)
```

## Smoke evidence — interpretation

Three findings, each with relevance to the ADR + downstream work:

1. **Docling installs + runs end-to-end on M1 Pro hardware**, producing **substantively correct extraction** of the HORUS ZUGFeRD invoice. Successfully extracted seller block (HORUS Test Seller GmbH / Teststraße 1 / 20095 Hamburg / DE / USt-ID: DE123456789), buyer block (HORUS Test Buyer GmbH / DE), full line-item table with header row + position row + subtotal/VAT/Brutto/Zahlbar rows, and the document date. **This validates ADR-008's primary-tool choice (Docling) as a working orchestrated baseline on HORUS-style invoices.**

   Two framing caveats deliberately bound the evidence's scope:

   - **This is NOT evidence that H2's clean-document directional prediction is reversed.** Direct comparison vs ADR-007's Granite-Docling-258M smoke (0 correct extractions across 4 prompts on the same input) shows that on this single clean digitally-born ZUGFeRD invoice, Docling's orchestrated specialists outperform the smallest single-shot tier (258M parameters) — a tier ADR-007 has already empirically excluded from the H2 cohort. H2's prediction is about the *full* single-shot cohort (3B–7B+ parameter tiers from cohort ADR #14) vs orchestrated specialists; comparing Docling to the excluded 258M tier informs only **tier-dependent behavior**, not architecture-class direction. The most this smoke supports is *if* the H2 directional flip exists, it is parameter-tier-dependent — pilot #13 should test this systematically against the full single-shot cohort.
   - **The Berghaus 2025 prior is not directly comparable to this smoke result.** Berghaus measured Docling at 64.03% on **scanned (rasterized) invoices** — Docling's OCR-pipeline path on bitmap input. The HORUS smoke ran on a **digitally-born fpdf2 PDF with embedded text layer** — Docling's text-layer-extraction path (with `rapidocr` engaged for any image regions, but the bulk of the extraction draws from the embedded text layer). These are **different input modalities**; comparing the 64.03% scanned prior to a digital-input smoke conflates input-modality differences with model-quality differences. Pilot #13 must evaluate on **both modalities** (digital ZUGFeRD AND scanned/photographed Belege) to honor v2 §6 H2's clean-vs-degraded split.

   Caveat: N=1; the pilot batch (10–50 invoices, #13) is what produces statistically meaningful evidence on either modality.

2. **Docling's bundled OCR engine is `rapidocr` running PP-OCRv4** (Chinese-origin text-detection / classification / recognition models). This is a **non-trivial dependency observation**: ADR-008's framing of "Docling = Western IBM-Research origin (no Chinese-pretraining caveat)" is technically incomplete — the *parser* is Docling's, but the *OCR layer underneath* is PaddleOCR's. The Western-vs-Chinese-pretraining caveat we documented for MinerU pipeline backend also applies (transitively) to Docling's default configuration. **Mitigation**: Docling's `PdfPipelineOptions(do_ocr=False)` knob disables OCR entirely for digitally-born PDFs (which all ZUGFeRD synthesised invoices are — the text layer is embedded). Pilot #13 should validate that `do_ocr=False` produces equivalent or better results on ZUGFeRD-style PDFs (no rasterisation needed), which would moot the Chinese-OCR caveat for the Mustang/factur-x synthetic-corpus arm of the experiment matrix. For the *real-world Belege* arm (degraded scans), OCR is unavoidable and the caveat applies — verification gate at pilot.

3. **Forward-pointer evidence for pilot #13** — the smoke surfaces three substantive observations. **Two are verified Docling failure modes** (pypdfium2 cross-check confirms the source-PDF text layer contains the dropped/reordered content) and one is a **verified generator-side artefact** (NOT a Docling failure mode):
   - **The invoice number ("Nr. HORUS-SMOKE-001") is missing from the extracted output (verified Docling failure).** Independent pypdfium2 dump of the source PDF confirms `"RECHNUNG Nr. HORUS-SMOKE-001"` is present in the page-1 text layer, but Docling's `export_to_markdown()` returned only `"## RECHNUNG"` — the `"Nr. HORUS-SMOKE-001"` portion was dropped. This is a W=3 critical field per v2 §5.2 (required for Vorsteuerabzug). Pilot #13 should treat Rechnungsnummer extraction accuracy as a **measurable known-weakness line item** in the compliance-aware F1 matrix.
   - **Reading order placed "Datum: 11.05.2026" at the *bottom* of the markdown output (verified Docling failure).** pypdfium2 confirms the source-PDF page-1 text layer has `"Datum: 11.05.2026"` second-from-top (right after `"RECHNUNG Nr. HORUS-SMOKE-001"`); Docling's markdown export places it after the table + before the page-2 footer. This is a **layout-reading-order failure mode** on multi-block top-of-page layouts; pilot #13 should record per-field positional accuracy alongside extraction accuracy.
   - **Structural counts (`pages=2 texts=9 tables=1 pictures=0`) report 2 pages — and the source PDF actually has 2 pages (verified generator-side observation, NOT a Docling failure mode).** Independent pypdfium2 cross-check (`len(PdfDocument(pdf_path)) == 2`) confirms the source PDF has 2 visual pages: page 1 contains the invoice content; page 2 contains only `"Generiert von HORUS - Synthetic ZUGFeRD invoice (ADR-006)"`. fpdf2's auto-page-break pushed the intended-page-1 footer onto a new page when the table + spacing exhausted page 1's vertical budget. **This is a forward-pointer for ADR-006 supersession candidates** (visual layout could be tightened to keep the footer on page 1), not a pilot-#13 task. Pre-merge note: the first commit on this branch speculated `pages=2` was a Docling PDF/A-3-attachment quirk; pypdfium2 verification before merge corrected the attribution.

   None of these three findings invalidate ADR-008's tool choice; the two verified Docling failures (3a + 3b) are forward-pointer evidence pilot #13 should systematically test, and 3c routes to ADR-006 generator-side work.

## Source archival

Per `horus-source-archival` rule + ADR-002:

- `docs/sources/tools/docling-library.md` — **enriched** (this PR). Apache-2.0 + LF Agentic AI Foundation membership noted; `StandardPdfPipeline` vs `VlmPipeline` distinction documented; ADR-007 cross-reference for 258M empirical exclusion; H2 framing.
- `docs/sources/tools/mineru-2-5.md` — **enriched** (this PR). Pipeline-vs-VLM-backend distinction (86.2 v1.5 vs 95.69 v1.6) documented as critical scope-disambiguation; Chinese-origin pretraining caveat; pure-CPU compatibility on M1 Pro.
- `docs/sources/tools/paddleocr-pp-structure.md` — **NEW** (this PR). Distinct from existing `paddleocr-vl.md` (single-shot). Fallback candidate per supersession (c).
- `docs/sources/tools/unstructured-io.md` — **NEW** (this PR). OSS Apache-2.0 only; cloud product tiers eliminated on §203 grounds.
- `docs/sources/tools/layoutparser.md` — **NEW** (this PR). Pre-Oct-2025-wave; rejected on staleness grounds.
- `docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md` — **enriched** (this PR). Verified key numbers (92.71/64.03 on Scanned Invoices; 87.46/47.00 on Scanned Receipts) embedded; full author list (Berghaus, Berger, Hillebrand, Cvejoski, Sifa); H2 clean-arm framing.
- `docs/sources/legal/stgb-203.md` — **existing** (M2D.4 brainstorm). Cited for Unstructured.io cloud-tier elimination.
- `docs/sources/legal/stberg-62a.md` — **existing** (M2D.4 brainstorm). Same.

LangChain document loaders + skip-entirely option — **eliminated-by-reference** (no positive citation in Decision text). Per `horus-source-archival` §"When the rule does NOT fire": no stub required for alternatives considered-and-rejected with no positive citation. Same shape as ADR-007's vLLM-canonical / Apple Core ML elimination pattern.

## Consequences

- **Positive**: H2's orchestrated arm has two independent test instruments (Docling primary + MinerU pipeline backend cross-check); §203-clean stack throughout (no cloud routing, only OSS self-hosted Apache-2.0 libraries); first HORUS-internal data point on Docling extraction quality on a HORUS-generated ZUGFeRD invoice; smoke evidence captured per `make-sure-it-works`. Supervisor progress check #17 has concrete tooling on the orchestrated arm to discuss alongside the single-shot cohort (ADR #14).
- **Negative**: heavy install footprint — Docling pulls 37 deps (including layout/table-recognition models from `docling-ibm-models`, `rapidocr` engine, `pypdfium2` PDF backend, latex/markdown renderers); MinerU pulls another 40 deps (including `modelscope`, `onnxruntime`, `boto3`, `pdfminer-six`). First-time `uv sync` after this PR will pull substantial wheel volume (~hundreds of MB). Both libraries cache model weights to disk on first `convert(...)` / `mineru` invocation (additional download on first smoke run; subsequent runs cached). The `pypdfium2` constraint conflict between Docling (pin ≥ 5.x) and MinerU (pin < 5.x) resolved to MinerU's pin (4.30.0) — verified non-breaking but is a fragility surface for future Docling upgrades; captured to `cascade-system/queue/pending-review.md` for upstream-PR-opportunity sprint review. **Chinese-origin pretraining caveat** for MinerU pipeline backend is the load-bearing risk — pilot #13 is the verification gate; if systematic German-content underperformance emerges, supersession (c) fallback to PP-Structure or `unstructured` OSS.
- **Neutral**: orchestrated baseline output format (Docling's `DoclingDocument` / MinerU's content_list_v2.json) differs from single-shot VLM output format (raw markdown / DocTags); cohort comparison sub-issues under #13 / #14 will define a common-output normalization layer — that's a downstream concern. The `make orchestrated-smoke` Makefile target downloads model weights on first run (`docling-ibm-models` + MinerU's modelscope artefacts) — cached in `~/.cache/` per upstream defaults; not committed.

## Related ADRs

- **ADR-001** — tool-decision discipline (this ADR follows the 5-section mandate)
- **ADR-002** — source-archival convention (this ADR's §"Source archival" cites)
- **ADR-005** — synthetic ZUGFeRD generator (`scripts/generate_zugferd_smoke.py` produces the smoke input PDF; dual-track precedent that motivates this ADR's dual-track cross-check pattern)
- **ADR-006** — visual PDF renderer (the `data/raw/smoke/invoice-001.pdf` visual layer is fpdf2-rendered; Docling and MinerU read the visual layer)
- **ADR-007** — local-VLM inference framework (non-overlapping inference stacks; cited for 258M empirical exclusion finding)
- **Cascade-system ADR-013** — `/commit` workflow (used for commits in this PR)
- **Cascade-system ADR-018** — `@release-manager` discipline (this PR lands via `@release-manager`; artifact-review gate at step 4 fires on the smoke transcript before push)

## Provenance

- Plan: `~/.windsurf/plans/horus-issue-11-orchestrated-baseline-adr-8006a7.md`
- Issue: `ReebalSami/horus#11`
- Brainstorm refs: `docs/prompts/stages/02-brainstorm.md` §1 (working frame) + §5 (open Layer-1 architecture decision) + §7 D6 (Layer-1 four-stage pipeline reversibility) + v2 §1.1 (architecture comparison axis) + v2 §6 H2 (directional-flip prediction) + v2 §7.5 (Berghaus literature gap) + v2 §7.8 (Docling baseline) + v2 §9.1 (MinerU 2.5-Pro v1.6 95.69 — VLM, out of scope) + v2 §9.2 (MinerU pipeline backend forward-reference)
- Workspace rules applied: `horus-decision-discipline.md`, `horus-source-archival.md`, `know-your-hardware.md`, `make-sure-it-works.md`, `context7-and-docs-first.md`, `branch-and-pr-required.md`
