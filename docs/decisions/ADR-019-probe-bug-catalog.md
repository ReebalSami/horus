# ADR-019: Structured-output probe — bug catalog

**Status**: Proposed
**Date**: 2026-05-21
**Parent**: ADR-018 (structured-output prompting probe)
**Children (forthcoming)**: ADR-020 (rescore methodology), ADR-021 (probe verdict matrix — threshold + denominator amendments)

---

## Context

The structured-output probe ratified in ADR-018 was executed on `feat/issue-53-structured-output-probe` and committed at `d01afd1` with verdict **DEFER #54**. Post-merge audit by Cascade D (this session, 2026-05-21) reading every transcript end-to-end uncovered that the verdict is **invalid**: the metric harness silently discarded valid model output. Most prominent example: Gemma-4-E4B-it emitted a perfect 16-key JSON object on each page in BOTH arms, but the JSON adapter's `to_predicted_dict` returned all-None because the harness concatenates per-page outputs into a single text string and the adapter cannot parse the resulting `{<dict-1>}\n{<dict-2>}` shape.

Locking the catalog of every confirmed bug BEFORE any fix is the entry gate for a defensible re-verdict. The catalog is the per-bug evidence record that future work cites, and the fix-wave roadmap that the post-audit branch executes against.

This ADR ratifies the catalog. It does NOT amend the threshold criterion (ADR-021 does), does NOT redesign the rescore pipeline (ADR-020 does), and does NOT modify any source code (Phase 3 fix waves do, each with its own commit + regression test).

---

## Current-state survey

### What was committed at `d01afd1`

- `src/horus/eval/adapters_json.py` — Layer-2 JSON adapter with permissive 5-step JSON-recovery ladder; sibling to `adapters.py` (regex). Public surface `(preprocess, to_predicted_dict)`.
- `src/horus/eval/harness.py` — `_score_single_invoice` dispatches per `cohort.adapter_mode` ∈ `{regex, json}`. `_strip_page_separators` runs at line 408 BEFORE the adapter receives the text.
- `configs/pilot-13-structured-probe-uniform.yaml` — Arm A overlay (cohort-uniform JSON prompt for all 7 working models).
- `configs/pilot-13-structured-probe-native-json.yaml` — Arm B overlay (per-model native task prefix + JSON suffix).
- 14 saved transcripts under `docs/sources/transcripts-structured-probe-{uniform,native-json}/<model>__EN16931_Einfach.txt`.
- 2 MLflow parent runs: `f9273a9d196742cdaa0831d7dcaa8608` (Arm A, experiment `structured-output-probe-uniform`) and `fced15055ae244e095cf5347760daf25` (Arm B, experiment `structured-output-probe-native-json`).
- Verdict text in commit body: "DEFER #54 — 0/7 models passed `(json_validity=1, canonical_keys≥12)`".

### What the post-merge audit found

A per-transcript end-to-end read (per `no-half-knowledge`) revealed that the underlying harness + adapter pipeline silently dropped extractable data. The verdict text is mathematically derived from the 0-of-7 count, but the count itself is wrong. The verdict cannot stand without re-scoring against the saved transcripts using a fixed adapter.

### Per-transcript annotation (locked from full read)

| Model | Arm | Output mode | Per-page JSON validity | Real-value content | Adapter outcome (current bug) |
|---|---|---|---|---|---|
| **olmOCR-2-7B** | A | unfenced p1 + ` ```json``` ` p2 | both valid 16k | p1: 11 real (header), 5 null; p2: 11 string-"null" + 5 real (footer money) | ALL-NONE (concat of 2 dicts unparseable) |
| **olmOCR-2-7B** | B | ` ```json``` ` per page | both valid 16k | p1: 11 real header; p2: 16 page-2 hallucinations ("seller_name": "Joghurt Banane" from line-item table) | First-fence captured → ~11 real (p1) — partial recovery via fence |
| **gemma-4-E4B-it** | A | unfenced single-line per page | both valid 16k | p1: 5 real (invoice_number, issue_date, currency, delivery_date, seller_name), 11 null; p2: 14 null + 2 real (grand_total, due_payable) | ALL-NONE (concat of 2 dicts unparseable) — **load-bearing example** |
| **gemma-4-E4B-it** | B | identical to Arm A (per overlay design) | identical | identical | ALL-NONE |
| **paligemma2-3b-mix-448** | A | refusal text | NO JSON | "Sorry, as a base VLM I am not trained..." × 2 | ALL-NONE |
| **paligemma2-3b-mix-448** | B | partial cooperation | NO JSON | p1: "OK<eos>"; p2: comma-separated key list (no values) | ALL-NONE |
| **granite-docling-258M** | A | repeated unfenced placeholder dicts | each dict valid | 16 placeholder keys (`<BT-N>` strings) × 8 dicts × 2 pages | ALL-NONE (concat of 16 dicts unparseable) |
| **granite-docling-258M** | B | DocTags (no JSON) | NO JSON | DocTags layout p1 + p2 (real values inside DocTags) | ALL-NONE (DocTags is the model's NATIVE format; Cat-1 task-prefix lock; JSON suffix ignored) |
| **mineru2.5-Pro** | A | malformed pseudo-JSON (table-wrapped) | NO JSON | repeated `"value_type":` token sequence | ALL-NONE (decoder-loop on JSON OOD prompt; 1970s wall-clock = 33 min cap-hit) |
| **mineru2.5-Pro** | B | DocTags-table format | NO JSON | DocTags p1 + p2 with real values | ALL-NONE (Cat-1 task-prefix lock) |
| **paddleocr-vl** | A | corrupted Chinese-mixed pseudo-JSON p1 + 1024 lines of `0` p2 | NO JSON | none | ALL-NONE (decoder-collapse; quant + JSON-OOD) |
| **paddleocr-vl** | B | clean OCR p1 + integers 1-575 p2 | NO JSON | p1 has correct invoice text; p2 decoder-collapse | ALL-NONE (Cat-2 task-prefix lock) |
| **glm-ocr** | A | ` ```json``` ` per page (placeholder) | both valid 16k | 16 placeholder keys (`<BT-N>`) per page | First-fence captured → 16 placeholder values; **PASSES pre-registered threshold with F1=0** |
| **glm-ocr** | B | ` ```json``` ` per page | both valid 16k | p1: 6 real, 9 empty; p2: 4 wrong-context line-item names + 6 empty | First-fence captured → ~7 real (p1) — partial recovery via fence |

### Mechanism of the load-bearing bug (B1+B2+B3)

For Gemma-4 Arm A input — after harness's `_strip_page_separators` runs at line 408:

```
{<page-1 dict with real values>}
{<page-2 dict with real values>}
```

`adapters_json.preprocess`:
1. `text.strip()` — no change
2. `_FENCE_RE.search(text)` — no match (Gemma-4 doesn't use markdown fences)
3. chat-artifact strip — no change
4. NFC normalize → returns the 2-dict concat verbatim

`adapters_json.to_predicted_dict` → `_try_parse_json`:
1. `json.loads(text)` → `JSONDecodeError` (extra data after first `}`)
2. Substring branch: `first_lbrace = 0`, `last_rbrace = end-of-page-2-dict`. `substring = text[0:last_rbrace+1]` = WHOLE concat (still 2 dicts) → fails
3. Trailing-comma sanitize → still 2 dicts → fails
4. Returns `None`
5. `to_predicted_dict` returns all-None

**Same mechanism, fence-asymmetric**: GLM-OCR Arm B emits `\`\`\`json\n{p1}\n\`\`\`\n\`\`\`json\n{p2}\n\`\`\``. Non-greedy `_FENCE_RE` captures the FIRST fence (page 1), `preprocess` returns just `{p1 dict}`, `to_predicted_dict` parses cleanly → 11 real values recovered. Gemma-4 emits the same per-page-valid-JSON shape but unfenced, so the adapter can't isolate page 1 → all-None. **The scoring outcome differs purely by whether the model emitted markdown fences, not by the model's underlying JSON adherence.**

### Threshold-design gap (B4)

GLM-OCR Arm A: 16 valid keys all containing placeholder strings (`<BT-1>`, `<BT-2 ISO 8601>`, etc. — verbatim echoes of the prompt schema). F1 against ground truth = 0.0 (zero matches). Yet `(json_validity=1, canonical_keys=16 ≥ 12)` is satisfied. Granite Arm A would also pass under this threshold after the B1 fix recovers any one of its 16 placeholder dicts.

The pre-registered threshold conflates **schema conformance** (does the output have the right keys?) with **value-extraction quality** (do the keys carry the right values?). Schema-mimicry without extraction was not a failure mode anticipated in ADR-018 §"Predicted outcomes". This is a methodology-discovery, NOT a moving-the-goalposts amendment.

### PaliGemma2 pre-registration error (B8)

PaliGemma2 is documented on its HF model card as a **base VLM**, not instruction-tuned. It is fine-tuned on the `mix-448` instruction set which does not include JSON extraction. Including it in the threshold tally for an instruction-following probe was knowable at probe-design time (ADR-009 §smoke evidence already showed PaliGemma's chart-recognition refusal loop on free-form prompts). The Arm A transcript ("Sorry, as a base VLM I am not trained...") is the structurally-correct output for a base model on this prompt — the model is honestly reporting its own training scope. Counting this as one of the 7 in the denominator inflates the threshold's stringency by 1/7 = 14% in a way that has nothing to do with the probe's actual question (does instruction-tuned JSON prompting work?).

### Decoder-loop / decoder-collapse signature classes (B6, B7, B11)

Three Arm-A models exhibit pathological generation: Granite (8 identical placeholder dicts × 2 pages), PaddleOCR-VL (1024-line monotone-`0` collapse on page 2), MinerU (33-minute extraction with `"value_type":` token sequence repetition). All three are Cat-1 (Granite, MinerU) or Cat-2 (PaddleOCR) task-trained models — purpose-fine-tuned on document parsing (DocTags, OCR), not on JSON. The JSON instruction is out-of-distribution; the model cannot stop because the EOS token never wins against the most-likely-continuation distribution learned at pretrain.

**Important**: this is a **model-behavior** failure, NOT a `vlm_extractor.py` extractor bug. The extractor correctly applies the chat template, generates with `do_sample=False` (deterministic), and respects `max_new_tokens` and the model's tokenizer EOS. No code change in `vlm_extractor.py` would alter these transcripts. Re-inference would NOT recover real data because the model fundamentally cannot do JSON. The classification is "diagnose, document, do not 'fix'".

---

## Options considered

**Option 1 — Catalog every bug now in ONE consolidated ADR (this one) + per-row supersession trigger.**

- Pros: single sign-off gate; one place to read the audit; cross-references trivial; consistent severity/wave classification.
- Cons: longer ADR; some rows are not "decisions" but "observations" (B6/B7/B11 model-behavior diagnostics).

**Option 2 — One ADR per bug.**

- Pros: per-bug separation cleaner for `horus-decision-discipline` strict reading; easier to supersede individually.
- Cons: 9+ ADRs reserved at once; INDEX bloat; cross-reference fan-out; the catalog VALUE is in seeing all bugs together (asymmetric fence-bias only makes sense if you read B1 + B2 + B3 in sequence).

**Option 3 — Defer the catalog; fix the highest-severity bug (B1) first, then iterate.**

- Pros: faster time-to-first-commit.
- Cons: violates `make-sure-it-works` (no evidence the fix is COMPLETE without the full catalog); fixes one bug while others silently invalidate the verdict; user instruction was explicit: "no skipping, no do it later".

**Decision**: Option 1. The catalog IS the audit record; reading it as a single document is the value. Per-row supersession triggers (each row's "Fix wave" column points to the commit that supersedes the row) preserve the per-bug finality without fragmenting the audit.

---

## Decision + integration thoughts

### The catalog (locked; mechanism cited from saved transcripts)

| # | Location | Confirmed evidence | Severity | Disposition / Fix wave |
|---|---|---|---|---|
| **B1** | `adapters_json._try_parse_json` | Gemma-4 Arm A + B emit `{<16-key dict, real values>}\n{<16-key dict, real values>}` after harness strips `===== PAGE N =====`. `json.loads(text)` fails (extra data). Substring `text[first_lbrace:last_rbrace+1]` = whole concat → still invalid. Returns all-None. **Discards the model's correct prediction.** | **HIGH (load-bearing)** | **Wave 3.1** — fix multipage path |
| **B2** | `adapters_json._FENCE_RE` × multipage | Non-greedy regex captures first fence only. GLM-OCR Arm B fenced (page 1 captured → real values recovered); Gemma-4 unfenced (both lost). Same model-behavior class (per-page valid JSON), different score purely from fence presence. | **HIGH (introduces fence bias)** | **Wave 3.1** (joint with B1) |
| **B3** | `adapters_json` × Granite-shape repetition | Granite Arm A: 8 identical placeholder dicts per page × 2 pages = 16 dicts concatenated. Concat unparseable. GLM-OCR Arm A (2 placeholder dicts, fenced) → first dict captured, 16 placeholder keys "passes" `canonical_keys≥12` threshold. Asymmetric purely from fence presence. | **MEDIUM (downstream of B1+B2)** | **Wave 3.1** (joint) |
| **B4** | Pre-registered threshold `(json_validity=1, canonical_keys≥12)` | GLM-OCR Arm A passes pre-registered threshold with 16 placeholder keys, F1=0. Granite Arm A would also pass post-B1-fix, F1=0. Threshold measures schema conformance, not value extraction. **Schema-mimicry was not anticipated in ADR-018 §"Predicted outcomes".** Methodology-discovery, not goalpost-move. | **MEDIUM (methodology)** | **Wave 3.2** — verdict matrix module + dual-threshold reporting |
| **B5** | `tests/test_adapters_json.py` (multipage coverage) | 17 single-input tests; ZERO multi-page. The B1 bug would have been caught pre-merge by a 5-line test. Parity gap with `tests/test_scorer_integration_multipage.py` (regex adapter has multipage coverage). | **HIGH (preventive)** | **Wave 3.1** (TDD-first; tests written before B1 fix) |
| **B6** | Granite Arm A — decoder-loop on JSON OOD prompt | Arm A: 8 identical placeholder dicts per page; 18.61s extract; `max_tokens=1536`. Token cap likely hit. Granite is fine-tuned on DocTags (Cat-1 task-trained); JSON is OOD; EOS token loses to repetition. Arm B (DocTags prompt) emits clean DocTags with real values. **Not an extractor bug — model-behavior failure.** | **DIAGNOSTIC (model-behavior)** | **No code change.** Document in §"Caveats" of ADR-018; cite HF model card. |
| **B7** | PaddleOCR-VL Arm A — decoder-collapse on JSON OOD prompt | Arm A: corrupted Chinese-mixed pseudo-JSON p1 + 1024 lines of literal `0` p2. PaddleOCR-VL is 4-bit quantized, fine-tuned for `OCR:` task prefix (Cat-2). JSON instruction → degenerate-most-likely-token sampling loop. Arm B (`OCR:` prefix + JSON suffix) → clean OCR p1 + integers 1-575 p2 (page-2 still collapses). **Not an extractor bug — quant × OOD-prompt model failure.** | **DIAGNOSTIC (model-behavior)** | **No code change.** Document in §"Caveats". |
| **B8** | PaliGemma2 base-VLM in 7-of-7 denominator | HF model card: base VLM, not instruction-tuned. Arm A: explicit refusal ("Sorry, as a base VLM I am not trained..."). Arm B: partial cooperation ("OK<eos>" + key list, no values). Inclusion in instruction-following probe denominator was a pre-registration error (HF card knowable at probe-design time per ADR-009 §smoke). | **LOW (methodology)** | **Wave 3.2** — verdict matrix BOTH-denominators dimension (N-of-7 + N-of-6) |
| **B11** | MinerU Arm A — decoder-loop on JSON OOD prompt | Arm A: 1970.14s extract (33 min), `"value_type":` token-sequence repetition + table-wrapped pseudo-JSON. MinerU is fine-tuned on DocTags (Cat-1). Same task-prefix lock + JSON-OOD failure mode as Granite (B6). Arm B emits clean DocTags with real values. **Not an extractor bug — model-behavior failure.** | **DIAGNOSTIC (model-behavior)** | **No code change.** Document in §"Caveats". |
| **B9** | `scripts/inspect_pilot_13.py` hardcoded experiment | Hardcoded `experiment_name='pilot-13-full'`; silently returns "0 nested runs" for non-pilot-13 experiments. Already captured in `cascade-system/queue/pending-review.md`. | **LOW (out-of-scope)** | **Out-of-scope** — file as separate HORUS issue post-merge. |

### Bug numbering note

B10 is intentionally unused (the pre-audit plan reserved it for "Phase 1 surfacing" — Phase 1 surfaced B11, no row claimed B10). Future post-audit-discovered bugs should reuse B10 before allocating B12+ to keep the catalog dense.

### Architectural decision: Wave 3.1 fix path

**Path B locked** (per parent plan §0). The new public function `to_predicted_dict_multipage(per_page_texts: list[str], model_id: str)` in `adapters_json.py` accepts a list of per-page strings (which the harness already has in `per_page_results`), parses each independently, and merges with **first-non-null-wins** (page 1 dominant — page 2 only fills fields page 1 left null; defends against page-2 hallucinations like olmOCR Arm B "Joghurt Banane"). Mirror the function in `adapters.py` (regex) for public-surface parity — the regex adapter's mirror just joins with `\n` and delegates to existing `to_predicted_dict` (regex-based extraction is robust to multi-page concat by construction). Backward compat: existing single-input `to_predicted_dict(text, model_id)` stays for the existing 17 + 22 test cases.

### Architectural decision: Wave 3.2 verdict reporting

New module `src/horus/eval/probe_verdict.py` exposes `compute_verdict_matrix(per_model_scores, *, paligemma_model_id) -> VerdictMatrix`. The matrix has 4 cells crossing 2 thresholds (pre-registered `(json_validity=1, canonical_keys≥12)` × amended `(... ∧ micro_F1≥0.1)`) by 2 denominators (N-of-7 PaliGemma counted × N-of-6 PaliGemma flagged). NO modification of any existing threshold logic; the matrix is purely additive. Pre-registration discipline preserved.

### Architectural decision: Phase 4 rescore reuses `scripts/rescore.py`

`scripts/rescore.py` already implements the adapter A/B rescore pattern (ADR-016) with `load_adapter_pair`, transcript parsing, GT cache, per-field outcome counts, opt-in MLflow logging. Re-using it (with one new flag `--baseline-adapter-module` to swap `horus.eval.adapters` ↔ `horus.eval.adapters_json`) is cleaner than building a parallel `scripts/rescore_probe.py`. The probe's evidence is canonical — re-scoring against the saved transcripts using the post-fix `adapters_json` IS the rescore.

### What this ADR does NOT decide

- The threshold amendment itself (ADR-021 ratifies the amended threshold + the dual-verdict matrix; this ADR documents the GAP that motivates it).
- The rescore methodology details (ADR-020 ratifies the offline-rescore-from-transcripts policy + `rescore_of` MLflow tag convention).
- The model-behavior caveats narrative for ADR-018 (Phase 6 docs update).
- Whether to file the model-behavior bugs (B6/B7/B11) as upstream issues with HF / mlx-vlm. Out-of-scope per parent plan §9.

---

## Source archival

### Saved transcripts (canonical evidence)

- `docs/sources/transcripts-structured-probe-uniform/<model>__EN16931_Einfach.txt` — 7 files, Arm A.
- `docs/sources/transcripts-structured-probe-native-json/<model>__EN16931_Einfach.txt` — 7 files, Arm B.

These 14 files are the audit substrate and are NEVER mutated post-audit. Any re-inference (none required for this catalog) would land in `*-r1/` directories per parent plan D1.

### Buggy MLflow runs (preserved as audit trail; never mutated)

- Arm A parent: `f9273a9d196742cdaa0831d7dcaa8608` (experiment `structured-output-probe-uniform`)
- Arm B parent: `fced15055ae244e095cf5347760daf25` (experiment `structured-output-probe-native-json`)

### Cross-references

- ADR-018 (parent — the probe being audited)
- ADR-013 (sibling regex adapter `adapters.py` — Wave 3.1 mirrors `to_predicted_dict_multipage` here for public-surface parity)
- ADR-014 (multi-page rasterizer + harness — `_strip_page_separators` line 408 is the dispatch site)
- ADR-016 (`scripts/rescore.py` adapter A/B substrate — Phase 4 reuse)
- ADR-009 §"Per-model native prompt strategy" + Amendment 1 (PaliGemma base + Cat-1/Cat-2 task-prefix-lock empirical evidence — the priors that B6/B7/B8/B11 confirm)

### External sources cited

- Google "Rules of Machine Learning" §24 ("Measure the delta between models") — already archived under `docs/sources/papers/google-rules-of-ml.md` per ADR-016.
- HF model cards for PaliGemma2 / Granite-Docling / PaddleOCR-VL / MinerU (Phase 6 will archive each per `horus-source-archival` when the per-model diagnosis paragraphs are authored in ADR-018's §"Empirical evidence" amendment).

---

## Supersession trigger

Each row of the catalog supersedes when its "Fix wave" column closes:

- B1, B2, B3, B5 → Wave 3.1 commit (multipage adapter + 7+ TDD tests)
- B4 → Wave 3.2 commit (verdict matrix module + dual-threshold reporting)
- B8 → Wave 3.2 commit (matrix supports BOTH denominators; no separate code path)
- B6, B7, B11 → ADR-018 §"Caveats" amendment (Phase 6 commit; ADR-019 is itself the canonical record — these rows close when Phase 6's cross-reference back to this ADR lands)
- B9 → separate post-merge HORUS issue filed (closes when issue is filed; cascade-system queue entry already drains via `@sprint-review`)

This ADR as a whole is **superseded by the closure of the post-audit branch's PR** (the entire branch's `@release-manager` flow). The bug catalog stays on disk as the immutable audit record per `document-as-you-go` "supersession over deletion".
