# 04 — Experiment phase (consolidation)

| Field | Value |
|---|---|
| **Phase** | 5/7 — `experiment` (per `.windsurf/phases.yaml`) |
| **Skill** | `@run-experiment` |
| **Milestone** | `experiments-validated` |
| **Status** | Closing — this document is the phase deliverable |
| **Date** | 2026-06-01 |
| **Scope** | Consolidates the experiments run across M2D.5 + the HND-0…HND-4 re-audit cycle (ADR-009 through ADR-033) into one phase-closing record. Authored retroactively: each experiment is already documented in its own ADR + (where applicable) retro; this doc is the index + the honest cross-experiment reading. |

> **READ THIS FIRST — what these numbers are and are not.**
> **Every F1 in this document is _in-sample / diagnostic_.** All experiments ran on the FeRD ZUGFeRD 2.2 **reference** corpus — clean, digitally-generated PDFs with regular layouts. Real firm documents (scans, skew, stamps, heterogeneous layouts) will score **materially lower**. **No number here may be cited as HORUS's real-world accuracy.** The canonical out-of-sample reporting surface is the held-out Belege split (#78 / HND-5) + cloud comparison (#80 / HND-6), both in the next phase. This caveat is inherited verbatim from ADR-028 §A / ADR-029 §"Threats to validity".

---

## 0. Executive summary (plain language)

The experiment phase set out to answer one practical question before any production code is written: **can small, local vision-language models (VLMs) read German e-invoices well enough to be worth building on — and which one?** We did not try to ship a product or maximise a score; we built the measuring apparatus, ran an honest bake-off, and characterised the failure modes.

What we found, in one breath:

- **A clear front-runner exists.** Of 7 working models, **MinerU-2.5-Pro (1.2 B)** is the most accurate on clean reference invoices (mean micro-F1 **0.710**, rising to **~0.917** after the MONEY-field fix), and **Granite-Docling-258M (MLX)** is the efficiency star — nearly as accurate on the totals that matter, **~134× faster**, in **1.3 GB** of memory.
- **The biggest single accuracy win was an engineering fix, not a better model.** Four invoice-total fields were silently scoring zero because the extractor searched for the *formal* EN16931 German labels while the invoices print *colloquial* ones. Fixing that label mismatch lifted the cohort from **0.49 → 0.67** with **zero new hallucinations**.
- **"Cleaner" output formats are not obviously better.** Forcing models to emit JSON did **not** beat free-form-plus-adapter; on the money totals it was markedly worse, and some models started **inventing** values for absent fields (the honesty axis). We carry both approaches forward rather than betting early.
- **The local-hardware story is half-proven.** 7 of 8 models fit comfortably in the 16 GB laptop; only MinerU overflows and swaps to disk. The "MLX is ≥3× faster than PyTorch" half of the claim could **not** be cleanly tested on this hardware, and we say so rather than fake a number.
- **We unlocked data and fixed the record.** 24 older-format (ZUGFeRD v1) invoices that were silently parsing to *empty* ground truth are now usable; and a hypothesis-label audit corrected several mislabels (including one fabricated citation) in the ADR trail.

The honest bottom line: **the experimental apparatus and the in-sample baselines are validated; the confirmatory hypotheses (local-vs-cloud, single-shot-vs-orchestrated, the retrieval layers) are deliberately deferred** to the implement phase, because they require the held-out real-document test set that does not yet exist.

---

## 1. Purpose & scope

The `experiment` phase validates hypotheses (and builds the tooling to test them) **before** the implement phase commits production code. For HORUS this meant:

- **In scope:** select a defensible model cohort; build a reproducible extraction + scoring harness; establish in-sample baselines; expand the evaluation metric surface; diagnose extraction failure modes; pre-register and (where feasible) test the §6 hypotheses; characterise local-hardware feasibility.
- **Out of scope (→ implement phase):** the held-out real-document (Belege) test set (#78), the cloud-vs-local comparison (#80), fine-tuning (#55), the Layer-2/3 knowledge-graph + retrieval experiments (#49/#50), and the production extraction build (#81) + prototype (#82).

The phase is governed by `horus-decision-discipline` (every tool/model/dataset choice → a numbered ADR with 5 mandatory sections) and the no-HARKing convention (`02-brainstorm.md` §12): every experiment cites a §6 hypothesis **or** is marked exploratory.

---

## 2. Data substrate

| Item | Detail |
|---|---|
| Primary corpus | FeRD **ZUGFeRD 2.2 reference invoices** (EN16931 + XRECHNUNG profiles); clean, digitally-generated PDFs with embedded Factur-X XML |
| Ground truth | The PDF's **embedded Factur-X CII XML**, read via `facturx.get_xml_from_pdf()` — NOT the FeRD-shipped `.cii.xml` sidecar (which carries 2024-era release-date stamps; ADR-012 "Probe 5" caught this silent drift) |
| Field set | **16 EN16931-anchored fields** (invoice no., dates, seller/buyer identity + tax IDs, currency, 5 MONEY totals) — `src/horus/eval/ground_truth.py` `FIELDS` |
| Schema coverage | CII **v2** (`CrossIndustryInvoice`) since ADR-012; CII **v1** (`CrossIndustryDocument`) added in ADR-033 — unlocking 24 previously-unusable `ZUGFeRDv1/` PDFs |
| Rendering | `pypdfium2` rasterisation, **every page** (ADR-014); page-1-only rendering in early smokes hid the page-2 totals block on 25/26 invoices |

Other datasets (fatura2, FUNSD, CORD-v2, OmniDocBench, etc.) are characterised in the EDA Quarto Book (ADR-024/025) but were **not** used for the extraction experiments here.

---

## 3. Model cohort

Selected in **ADR-009**: a 10-model, 3-category single-shot bake-off, mixed-quantised to fit the M1 Pro / 16 GB envelope.

| Category | Hypothesis it probes | Members | Deployed in pilot-13 |
|---|---|---|---|
| **Cat 1** — purpose-trained document-VLMs | purpose-training is the dominant lever at small param counts | Granite-Docling-258M, MinerU-2.5-Pro 1.2 B, olmOCR-2-7B | ✅ all 3 |
| **Cat 2** — architecturally innovative | the architectural lever can match purpose-training | DeepSeek-OCR-2, PaddleOCR-VL, GLM-OCR | ✅ 2 (DeepSeek-OCR-2 blocked) |
| **Cat 3** — general-purpose multimodal | scale + general training compensates for absent doc-training | Gemma-4-E4B-it, Qwen3-VL-4B, PaliGemma-2-3B, Molmo-7B-D | ✅ 2 (Qwen3-VL-4B + Molmo-7B-D blocked) |

**7 of 10 became the "working cohort."** Three did not deploy on this hardware and are honestly excluded with cause (ADR-009 §"Smoke evidence"): **DeepSeek-OCR-2** (Type-B ABI conflict — model remote-code imports a symbol removed in `transformers ≥4.45`), **Qwen3-VL-4B** (triple-fail across 4-bit/8-bit/bf16 — M1 Pro 16 GB ceiling), **Molmo-7B-D** (MLX `metal::malloc` buffer-size bug).

> **Non-comparability footnote (ADR-009, load-bearing):** the cohort is mixed-quantisation (bf16 for ≤2 B; MLX 4-bit for ≥3 B), so raw latency is **not** cross-model comparable. Quality F1 is comparable (XML-grounded, exact-match); raw tokens/sec is not.

---

## 4. Evaluation methodology

- **Scorer (ADR-013):** per-field micro/macro F1; exact-match on normalised values for MONEY/DATE/CODE/ID; ANLS\* fuzzy match for the 2 STRING name fields. Threshold τ=0.50 (literature default; ADR-014 ablation showed F1 is **τ-robust** across [0.3, 0.7], Δ=0.0031).
- **Harness (ADR-014):** loads each model once, rasterises every page, extracts per-page + concatenates, parses via a 2-layer adapter, scores against Factur-X GT, logs parent + nested MLflow runs. Resume-safe.
- **Metric expansion (ADR-027, HND-0):** four additive metrics on top of micro-F1, all derived offline from logged per-field outcomes — **per-canonical-label F1**, **presence-conditional F1** (recall-faithful), **group-level F1** (KIEval all-or-nothing over seller/buyer/totals groups, arXiv 2503.05488), and **spurious-emission rate** (the hallucination-on-absent-fields honesty axis). (2)+(4) decompose F1 into recall/precision and fix the asymmetry that was penalising models for honest nulls.

---

## 5. Experiment 1 — Pilot cohort comparison ("pilot-13")

**ADR-014** · retro `docs/retros/m2d.5-pilot-13-cohort-harness.md` · MLflow `pilot-13-full` (`df6bce67…`) · **182/182 tuples (7 models × 26 invoices), 0 failures.**

Per-model mean micro-F1 (n=26), ranked:

| Rank | Model | Cat | mean micro-F1 |
|---:|---|:---:|---:|
| 1 | MinerU-2.5-Pro-1.2B | 1 | **0.710** |
| 2 | GLM-OCR | 2 | 0.521 |
| 3 | Granite-Docling-258M-mlx | 1 | 0.463 |
| 4 | PaddleOCR-VL | 2 | 0.463 |
| 5 | olmOCR-2-7B | 1 | 0.442 |
| 6 | Gemma-4-E4B-it | 3 | 0.437 |
| 7 | PaliGemma-2-3B-mix-448 | 3 | 0.298 |

**Pooled cohort micro-F1 = 0.4908.** Key findings:

- **Multi-page rasterisation was a 2.45× lift** over page-1-only (0.20 → 0.49). The page-2 totals block was previously invisible.
- **MONEY fields were the cohort's weak spot.** Probe 1 (≥3 of 5 MONEY fields correct on the simplest invoice) returned **PARTIAL**: MinerU 1/5, all others 0/5 — even though the totals were present in the transcript. → diagnosed + fixed in Experiment 2.
- **The Factur-X GT route is validated** (Probe 2): 7/7 models score TP on the XRECHNUNG `issue_date` via `facturx`, impossible against the drifted sidecar.

---

## 6. Experiment 2 — MONEY-field recovery (Belegsummen adapter)

**ADR-028 (HND-2)** · issue #41 · offline A/B re-score over the 182 cached transcripts (no VLM re-run).

**Root cause:** the Layer-2 extractor searched for each field's *formal* EN16931 `german_label`, but the FeRD "Belegsummen" totals block prints *colloquial* display labels. Only `due_payable_amount` ("Zahlbetrag") matched verbatim; the other four scored a silent FN despite being present in the text.

| Field | BT | formal label searched | label invoices actually print |
|---|---|---|---|
| `line_total_amount` | BT-106 | Summe Nettobeträge | **Positionssumme** |
| `tax_basis_total_amount` | BT-109 | Steuerlicher Bemessungsbetrag | **Rechnungssumme ohne USt.** |
| `tax_total_amount` | BT-110 | Umsatzsteuer gesamt | **Steuerbetrag** |
| `grand_total_amount` | BT-112 | Bruttobetrag | **Bruttosumme** |

**Fix:** a section-scoped, shape-tolerant fallback that normalises the Belegsummen window across the 4 transcript shapes (MinerU cells / Granite DocTags / PaddleOCR split-lines / Gemma markdown), section-anchored to dodge the "Steuerbetrag" VAT-header collision.

**Result — cohort micro-F1 `0.4908 → 0.6729` (Δ +0.182), with ZERO new false positives** (spurious-emission unchanged at 0.0317; the fallback only flips FN→TP, never invents values). Per-label: `line_total` 0.000→0.681, `tax_basis` 0.000→0.676, `tax_total` 0.000→0.705, `grand_total` 0.000→0.736. Per-model, **all 7 improved** (MinerU 0.718→0.917).

---

## 7. Experiment 3 — Structured-output JSON baseline (HND-1)

**ADR-029** · issue #54 · MLflow `json-baseline` (`0f934104…`) · 3 JSON-capable models × 6 invoices (18 tuples).

The structured-output probe (ADR-018/019/021) established that **only 3 of 7 models can emit usable JSON at all** (Gemma-4, olmOCR-2, GLM-OCR); the other 4 are structurally incapable (DocTags models ignore the instruction; PaddleOCR collapses; PaliGemma refuses). We ran the 3 capable ones and cited the evidence for the other 4 rather than burning ~22 min/page re-confirming known zeros.

| Model | mean micro-F1 | presence-cond. F1 | spurious-emission |
|---|---:|---:|---:|
| **Gemma-4-E4B-it** | **0.707** | 0.706 | **0.000** |
| olmOCR-2-7B | 0.660 | 0.706 | 0.875 |
| GLM-OCR | 0.475 | 0.496 | 0.500 |

**Findings (the inputs to Experiment 4):**

1. **Honest-null vs hallucinate-on-absent is the headline axis.** olmOCR and Gemma have *identical* recall on present fields (0.706) — yet olmOCR **invents** values for absent fields (spurious 0.875) while Gemma emits `null` (0.000). For a tax tool, a wrong number is worse than a missing one, so this matters enormously. **Gemma-4 is the standout JSON model** (best F1, fastest, zero hallucination).
2. **Prompt-only JSON under-recovers the MONEY totals** (`line_total` 0.105 vs ADR-028's ~0.68). "Switch to JSON" does **not** obviously beat "free-form + adapter".
3. **Group-level correctness is near zero** (KIEval 0.019) — almost no invoice yields a fully-correct business group.

---

## 8. Experiment 4 — Reading-ceiling & approach comparison (HND-3)

**ADR-030** · `eval/reading-ceiling-and-approach-comparison.md` · **exploratory** (not a §6 hypothesis test; arXiv 2503.08124 exploratory→confirmatory stance).

This reframed the "JSON vs free-form, pick a winner now" question into "diagnose both honestly, carry both forward; defer the final Layer-1 pick to post-fine-tuning." Two diagnostics:

- **Reading ceiling vs parser-loss.** For each present field: is a surface form of the value *in the raw transcript* (ceiling) and did the adapter *extract* it? The gap is split into **parser-loss** (readable but dropped — an adapter problem, cheap to fix) vs **read-miss** (absent from raw — a model problem). Cohort free-form: ceiling **0.81**, extracted **0.51**, parser-loss **0.30**, read-miss **0.19**. **Granite-Docling and MinerU are near-ceiling on MONEY** (0.97 / 0.96 extracted) — they *read* the totals; weaker models *miss* them.
- **Same-tuple free-form vs native-JSON** (3 models × 6 shared invoices, same scorer): cohort free-form micro-F1 **0.607** (spurious **0.000**) vs native-JSON **0.614** (spurious **0.458**). Statistically a wash on F1 — but free-form is dramatically more honest. Determinism cross-check reproduces the ADR-029 numbers exactly.

**Verdict: diagnostic, not a decision.** Both approaches are carried forward; the final Layer-1 choice is made post-fine-tuning with out-of-sample evidence.

---

## 9. Experiment 5 — Efficiency sweep (H8)

**ADR-032 (HND-4)** · issue #77 · MLflow `h8-efficiency` (`316ca04c…`) · 8 model-variants × 1 invoice; `dev_only` (kept out of the thesis F1 lineage).

The first dedicated measurement of speed + memory (the `pilot-13-full` run predated the ADR-017 instrumentation). **Two-clause verdict:**

- **Memory-fit — HOLDS for 7/8.** Peak 1.31–8.40 GB (≤ 66 % of the 12.71 GB recommended MPS working set). **MinerU alone breaches** at 13.40 GB = 105.4 % → it swaps to disk (1314 s wall vs seconds for the fast models), independently reproducing the ADR-028 observation.
- **Decode-≥3× — NOT cleanly evaluable on this hardware.** Three confirmed reasons: PyTorch-MPS exposes no decode-only tokens/sec (0.0 sentinel); the one deliberate same-model MLX-vs-MPS controlled pair broke on the MPS side (Granite-MPS emitted 0 tokens → F1 0.000 vs MLX 0.800, filed as **#99**); and the end-to-end proxy is model⊥backend-confounded. **Honestly bounded as a final position, not a TODO.**

**Efficiency–accuracy frontier:** Granite-Docling-258M (MLX) reaches F1 0.800 in 9.83 s — **~134× faster wall-clock than MinerU** at near-equal quality on the totals. This is the strongest "HORUS can run locally" data point.

---

## 10. Auxiliary — ground-truth coverage (ZUGFeRD v1 unlock)

**ADR-033** · issue #75. The CII parser only understood v2; v1 invoices silently parsed to *empty* ground truth, making 24 `ZUGFeRDv1/` PDFs unusable. Extending `parse_cii_xml` to auto-detect + parse both schemas (the 16 EN16931 leaf paths proved byte-identical across v1/v2) **unlocked those 24 invoices** as GT-parseable for baselines + the fine-tuning pool. The ADR-014 harness benefits automatically.

---

## 11. Hypothesis status (§6 H1–H8)

Per **ADR-031** (which reconciled every hypothesis label against the locked brainstorm §6 and pre-registered H8). "Tested" = a result exists; "substrate ready" = the apparatus + in-sample data exist but the confirmatory comparison has not run.

| H | Layer | Claim (abbrev.) | Status after this phase |
|---|---|---|---|
| **H1** | L1 | local VLMs within X pp of cloud SOTA | **Substrate ready** — local cohort baselines exist; cloud arm + held-out split deferred → #80 |
| **H2** | L1 arch | single-shot vs orchestrated (clean↔degraded flip) | **Substrate ready** — single-shot cohort (ADR-009) + orchestrated baseline (ADR-008) both exist; head-to-head + degraded Belege deferred |
| **H3** | L2 | compliance-F1 predicts KG pass-rate | **Not reached** — Layer-2/KG is future → #49 slot |
| **H4** | L3 | graph beats vector retrieval (multi-hop) | **Not reached** — Layer-3 future → #49 slot |
| **H5** | L3 | feature-only router ≈ oracle router | **Not reached** — Layer-3 future |
| **H6** | cond. | validator-retry closes the cloud gap | **Not reached** — conditional → #50 slot |
| **H7** | — | transfer-learning / template-shift robustness | **Floated**, not locked (candidate) |
| **H8** | L1 | MLX ≥3× MPS decode + 16 GB fit | **Tested (partial)** — memory-fit holds 7/8; decode-ratio not cleanly evaluable (ADR-032) |

Exploratory work outside §6 (per the cite-or-mark convention): the metric expansion (ADR-027), the MONEY-field engineering fix (ADR-028), the JSON baseline (ADR-029), and the reading-ceiling diagnostic (ADR-030).

**No-HARKing note for the writeup:** H1–H6 were pre-registered 2026-05-08; H8 was formalised 2026-05-31 (after instrumentation, before the efficiency test ran) — transparent late-formalisation, not retro-fitted confirmation. Pre-registration ≠ commitment to run every test; untested hypotheses are reported honestly as "not evaluated within thesis scope."

---

## 12. Conclusions & bridge to the implement phase

**What is validated:**

- The **measurement apparatus** (harness, scorer, 4-metric surface, Factur-X GT route, MLflow tracking, resume safety) — reproducible and tested (705 passing tests).
- **In-sample baselines** for 7 models, with MinerU the accuracy leader and Granite-Docling-MLX the efficiency leader.
- **H8 (efficiency)** to the extent the hardware permits an honest answer.
- The **failure-mode map**: MONEY-label mismatch (fixed), the honesty axis on JSON, parser-loss vs read-miss, and the swap ceiling for the largest model.

**What is deliberately deferred** (the experimental record is honest that these are NOT done):

- **Every accuracy number is in-sample.** Generalisation is unproven until the held-out real-document set exists.
- **H1, H2** await the cloud arm + degraded Belege; **H3–H6** await Layers 2–3.

**The bridge:** the single highest-leverage next step is **#78 — the held-out Belege test set**. It converts every in-sample finding above into a defensible, generalisable thesis result, and gates the cloud comparison (#80) and fine-tuning (#55). It is the first issue of the `feature-complete` (implement) phase and carries a real-world dependency: it needs genuine private invoices, which only the project owner can supply (with a circularity guard so fine-tuning never sees the test set).

---

## 13. Sources

**ADRs (this phase):** ADR-007 (inference dual-track) · ADR-008 (orchestrated baseline) · ADR-009 (cohort) · ADR-010/012/033 (GT parsing) · ADR-013 (scorer) · ADR-014 (harness) · ADR-016 (fast-dev config) · ADR-017 (instrumentation) · ADR-018–021 (structured-output probe) · ADR-027 (metric expansion) · ADR-028 (Belegsummen) · ADR-029 (JSON baseline) · ADR-030 (reading-ceiling) · ADR-031 (hypothesis reconciliation + H8) · ADR-032 (efficiency).

**Retros:** `docs/retros/m2d.5-pilot-13-cohort-harness.md` · `…-structured-output-probe.md` · `…-step3-dataset-acquisition.md` · `…-mid-heartbeat-2026-05-19.md`.

**Generated reports:** `eval/reading-ceiling-and-approach-comparison.md` · `eval/probe-verdict-matrix.md` · `docs/sources/json-baseline-metrics.txt`.

**Evidence archives:** `docs/sources/transcripts-multipage/` (182) · `docs/sources/transcripts-json-baseline/` (18).

**Methodology anchors:** Kerr 1998 (no-HARKing) · KIEval arXiv 2503.05488 (group-level F1) · arXiv 2503.08124 (exploratory→confirmatory) · brainstorm v2 §6 (hypothesis registry).
