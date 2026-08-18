# Fifth pass — Zweitgutachter audit (2026-08-18)

**Auditor stance**: second examiner, German M.Sc. standards, adversarial ("find every point
a 2.0-advocate could stand on"). Every finding quote-anchored and tagged
CERTAIN / LIKELY / UNVERIFIED. Baseline: fourth pass (2026-08-17) verified and not
re-reported; this pass re-verified its fixes on the rendered PDF.

**Build audited**: `thesis/_build/main.pdf`, 138 pages, A4, built clean in this worktree
(`make thesis`, zero errors; benign `\input@path` info lines only).

**Verdict**: **submit after two small text fixes** (findings 1–2). Finding 1 is the only
substantive gap: an exclusion class on the headline result that the repo's own issue
tracker documents but the manuscript does not disclose. It is a disclosure gap, not a
scoring trick — the fix is a few sentences, in the same voice the thesis already uses for
its other defects. Everything else verified across five passes is listed in the clean
inventory. No finding here supports a 2.0 on substance; finding 1 unfixed would hand a
picky examiner a legitimate consistency objection against the thesis's own strongest
claim (measurement completeness).

---

## Finding 1 — Undisclosed exclusion class on the headline result (date-normalizer-rejected GT cells)

**Tag**: CERTAIN (mechanism, code + tracker); UNVERIFIED (exact cell count on the final
signed-off key — needs `uv run python scripts/audit_heldout_evidence.py` against the
private corpus, which is not in this worktree).

**The thesis promises a complete exclusion inventory.** Ch. 5:

> "Chapter~\ref{ch:measurement-validity} states exactly which cells were excluded, on what
> recorded warrant, and what the exclusion was worth --- including the discipline that a cell
> may only be excluded on a criterion declared in advance and applied by a rule, never
> case-by-case after seeing whether the model got it right."
> (`thesis/chapters/05-methodology.tex:341-344`)

Ch. 6 then inventories: multi-rate `tax_rate`, zero-rate `tax_rate` ("Both exclusions are
rule-driven on a declared criterion", `06-measurement-validity.tex:97-98`), optional-zero
totals, and the repaired reference-data classes. Ch. 10 closes the books:

> "\subsection{Two Known Defects Remain Open} ... Reported here so that the apparatus is
> not represented as cleaner than it is."
> (`thesis/chapters/10-limitations-future-work.tex:170-173`)

listing exactly two: the supplier-article-number regression and the stale configuration
default.

**The repo knows a third.** Open issue #118 ("Date normalizer rejects English long-form,
2-digit-year and US-order dates (deferred)", filed 2026-08-04) documents that
`_normalize_predicted_date` (`src/horus/eval/normalizers.py:118`) cannot parse three date
renderings **that occur in the held-out corpus**, and measures the blast radius:

> "Measured blast radius: **8 `issue_date` values** across the 39 held-out invoices ...
> Concentrated in the 11 English invoices ... Held-out GT is normalized through
> `validate_and_repair` and predictions through `_normalize_predicted_date`, so for an
> English invoice both sides become `None`: GT is `is_present=True` with
> `normalized_value=None`, and a correct model answer cannot be credited as a match."

The scorer maps that GT state to a silent neutral. `src/horus/eval/scorer.py`:

```
normalizer_rejected  EXCLUDED       EXCLUDED      EXCLUDED     (line 23)
if gt_field.normalized_value is None: return "normalizer_rejected"   (line 280-281)
```

So up to 8 `issue_date` cells drop out of the headline denominators (568 TP / 28 FP /
100 FN, Table 7.10) — an exclusion class the manuscript never names. It is rule-driven
and symmetric (satisfies the "applied by a rule" discipline mechanically), but it is
**not disclosed**, which contradicts the ch. 5 promise verbatim. Worse for the record:
issue #118's own deferral condition —

> "Revisit when the held-out English subset actually needs to be scored."

— was met when the held-out corpus was scored (2026-08-06 lineage, ADR-063/065) and the
issue was never revisited. The English channel row (0.9345, Table 7.11) is reported with
per-channel commentary while ~8 of its date cells are invisibly neutral.

**Direction of bias**: mixed per cell (excluding a likely-correct date removes a TP →
deflates; excluding a misread removes an FN → inflates). Given `issue_date` is a
high-accuracy field, the net effect most plausibly *understates* the English score
slightly — this is not score inflation. The defect is inventory completeness, and it
collides with the thesis's own flagship claim (measurement validity as contribution).

**Fix (pre-submission, small)**: disclose, do not repair. (a) Add the
`normalizer_rejected` class to ch. 6's exclusion inventory with the audited count on the
signed-off key; (b) extend §10 "Two Known Defects Remain Open" to three, citing the date
normalizer's three unhandled renderings; (c) optionally one clause in the Table 7.10
protocol note. Re-run `scripts/audit_heldout_evidence.py` first to replace the "8" from
the 2026-08-04 draft-key audit with the current count on the promoted key (adjudication
may have changed stored renderings; count could be 0–8 — if 0, the ch. 10 entry still
belongs, as the normalizer gap itself remains). Repairing the normalizer now is the wrong
move — #118 is right that it moves published ZUGFeRD-corpus figures and needs its own
regression pass + ADR (post-submission).

## Finding 2 — Appendix datasheet contradicts the methodology on corpus provenance

**Tag**: CERTAIN.

Appendix C (held-out datasheet) opens:

> "The held-out corpus of 39 real invoices is private by design (client documents;
> \S\ref{sec:method-data})."
> (`thesis/appendix/appendix.tex:91-92`)

Ch. 5 says the opposite, twice:

> "39 real invoices collected from the author's own business" (`05-methodology.tex:100`)
> "the author's own collected invoices --- no client document and no third [party's] ..."
> (`05-methodology.tex:534`)

and §10.1's cloud-GT limitation depends on the distinction ("a practitioner bound by
professional secrecy could not construct this answer key from their own client
documents", `10-limitations-future-work.tex:189-193`). "Client documents" in the appendix
accidentally claims the author held protected client data — the exact thing the
methodology denies and the privacy argument requires denying. Two-word fix:
"(personal business correspondence; ...)" or "(the author's own received invoices; ...)".

## Finding 3 — Under-filled float page for the headline table

**Tag**: LIKELY (cosmetic; one instance verified on the rendered PDF).

PDF p. 87 (Table 7.10 + protocol note) renders as a float page with ~40% dead white space
above the table. Verified visually on the render; the headline result of the thesis sits
below a large blank block. A `[t]`-placed float or a `\afterpage` nudge fixes it. Not
checked exhaustively for siblings; if one table is worth polishing, it is this one.

---

## Minor notes (no action required, or action optional)

- **Title page** (CERTAIN, template-locked): "Master Thesis" and German-format date
  "20. August 2026" on an otherwise-English title page follow the FH Wedel template;
  noted only so the choice is conscious.
- **"the two largest files cover the scoring rules and the typed schema"** (ch. 8)
  (LIKELY fine): true by test-function count (`test_scorer.py` 106 defs,
  `test_schema.py` 46 defs — the two largest); by byte size the second-largest is
  `test_harness.py`. Defensible as written; "largest by test count" would be unambiguous.
- **Repo hygiene, not manuscript** (CERTAIN): tracker issue #48 (OCR-free framing in
  ch. 1) is still open although the terminology note has landed in ch. 1 §Scope — close
  or re-scope the issue.
- **olmOCR-2-7B parameter count** (CERTAIN, no defect): the HF card reports 8.29 B
  parameters (the "7B" names the Qwen2.5-VL-7B base's LLM size). The thesis uses the
  model *name* only and never claims a literal seven billion — verified clean, recorded
  here because an examiner might ask.

---

## External verification — fifth-pass additions (all clean)

| Claim in thesis | Primary source checked | Result |
|---|---|---|
| Krieger 2021: 1,129 English one-page invoices, 277 vendors, one audit-firm recipient, 3 key items, macro-F1 0.8753 | Springer DOI 10.1007/978-3-030-86797-3_1 (full text) | exact match, incl. 0.8753 = macro-avg excl. unlabeled |
| Thiée 2023: 977 German PDFs, 60+ classes, rule-based labels, builds on Krieger's graph model | GI DL DOI 10.18420/inf2023_180 (abstract + text excerpt; pp. 1777–1792) | match (494 vendors + F1 0.823 verified in pass 4 from the GI PDF) |
| Berghaus 2025: 8 models / 3 families / 3 datasets, native image beats Docling parse-first, SmolDocling "almost identical", IEEE BigData 2025 | arXiv 2509.04469 + Lamarr/Fraunhofer IAIS record | exact match, verbatim SmolDocling clause found |
| FATURA: 10,000 invoices, 50 layouts, 24 field classes | arXiv 2311.11856 + Zenodo record 8261508 | exact match ("24 different classes") |
| KIEval: ICDAR 2025, LNCS 16025, pp. 270–286, correction-cost framing | Springer DOI 10.1007/978-3-032-04624-6_16 + official BibTeX | exact match |
| Ghosh 2024: LoRA learns style/response-initiation, not knowledge; ICML, pp. 15559–15589 | PMLR v235 (ghosh24a) | exact match |
| Cai & O'Connor: KG extraction errors bias downstream graph analyses | Applied Network Science 10(1):64, DOI 10.1007/s41109-025-00749-0 | exact match |
| Tam 2024: format restrictions degrade reasoning; EMNLP Industry pp. 1218–1236 | ACL Anthology 2024.emnlp-industry.91 | exact match |
| MDPBench: 3,400 docs, 17 languages, public+private splits, open-source −17.8 % on photographed | arXiv 2603.28130 + HF dataset card (live) | exact match |
| E-invoicing law: receive-duty 2025 without transition; issuer duty 2027 (> €800k prior-year turnover) / 2028 (rest); §27 Abs. 38 UStG; ≤ €250 (§33 UStDV) and Kleinunternehmer (§34a UStDV) exempt | BMF FAQ + BMF-Schreiben 2025-10-15 + Finanzamt NRW | exact match |
| §33 UStDV: small-amount invoice may omit recipient identity + separate tax amount | UStAE 14.6 / gesetze-im-internet | exact match |
| ZUGFeRD: five profiles + XRECHNUNG reference profile; MINIMUM and BASIC WL are booking aids, not UStG-complete invoices | FeRD FAQ (ferd-net.de) | exact match |
| §203 StGB 2017 reform: "mitwirkende Personen" (Abs. 3), criminal liability of provider + professional who fails to bind them (Abs. 4) | gesetze-im-internet §203 + BT-Drs. 18/11936 | exact match |
| §62a StBerG / §43e BRAO / §50a WPO "Inanspruchnahme von Dienstleistungen"; §57 StBerG "Allgemeine Berufspflichten" | gesetze-im-internet (statute headings vs. bib titles) | exact match |
| EDPB Opinion 22/2024: contract wording "does not release the processor"; Recommendations 01/2020 v2.0: contractual clauses cannot bind third-country authorities | EDPB originals (PDF) | exact match, near-verbatim |
| Model IDs: `Qwen/Qwen3-VL-4B-Instruct` (4.4 B, Apache-2.0), `Qwen/Qwen3-VL-8B-Instruct`, `allenai/olmOCR-2-7B-1025` (fine-tune of Qwen2.5-VL-7B-Instruct), `ibm-granite/granite-docling-258M` (257.5 M, Idefics3 arch), `google/gemma-4-E4B-it` (Gemma-4 E-series, Apache-2.0) | live Hugging Face Hub cards | all exist; lineage + sizes match thesis |

## Repo verification — fifth-pass additions (all clean)

- **Registry pins**: `len(FIELDS) == 34` asserted in `tests/test_ground_truth.py:487`;
  exactly 3 repeating groups in `REPEATING_GROUPS` (`ground_truth.py:1391-1395`).
- **Ch. 4 recovery-ladder description matches the code** rung for rung
  (`adapters_json.py:260-330`: direct parse → first balanced dict → greedy substring →
  trailing-comma sanitize → structural repair; top-level shape gate included).
- **First-non-None-wins multipage merge** as described (`structurer.py:216-237`,
  `adapters_json.py:177-241`); **single-rate tax backfill is the only cross-field
  repair**, import-time-guarded (`structurer.py:129-189`).
- **CI**: lint + typecheck + full suite on push to main + PRs (`.github/workflows/ci.yml`);
  Mustang JAR SHA-256-pinned (`Makefile:142`).
- **Fourth-pass fix confirmed in repo**: the dev-loss mislabel in
  `eval/structurer-lora-2x2-results.md` now carries the 2026-08-15 correction note; both
  curves re-read from `horus_training_provenance.json`.
- **Attribution + findability audit artifacts** (`eval/finetune-attribution-audit.md`,
  `eval/reader-findability-audit.md`) match every number the thesis reprints (0.6771 /
  0.9608 / 304–201–92 / corrected ceiling 0.9719 / 52 = 19 R + 6 V + 27 P / 23 exclusions /
  8B decode-collapse 1/29 / endpoint 0.8335 vs 0.8118).
- **Open issues consistent with thesis honesty claims**: #129 (floor unmeasured) and
  #127 (olmOCR end-to-end not taken; transcripts retained) are both disclosed in the
  manuscript in matching terms. #118 is the exception — Finding 1.
- **Rendered pages spot-checked**: title, Contents, Abstract, Table 7.10 page,
  Bibliography, Eidesstattliche Erklärung — all clean apart from Finding 3; statute
  bibliography titles match gesetze-im-internet headings; declaration carries the
  AI-disclosure clause matching Appendix E.

## Clean-sections inventory (cumulative, five passes)

Abstract; ch. 1–4 (fully re-read this pass, no new findings); ch. 5 (modulo Finding 1's
promise sentence); ch. 6 (modulo Finding 1's inventory); ch. 7 numbers (all recomputed
against committed JSON in pass 4; spot-re-verified here); ch. 8; ch. 9; ch. 10 (modulo
Finding 1's "two defects"); ch. 11; appendices A, B, D, E, F (modulo Finding 2 in C);
bibliography (every entry now verified against a primary source across passes 3–5);
declaration; typography and front matter.

## What a 2.0-advocate could still argue, and why it fails

1. *"The held-out corpus is 39 invoices, single-annotator."* Disclosed at length
   (§10.1.2), quantified (three-channel adjudication, 285 → 178 → 463 verdicts), and the
   thesis never claims population-level generalization. Sample-size honesty is graded as
   maturity, not weakness, under German standards.
2. *"Two of three layers were never built."* Pre-registered as descoped (ADR-054 lineage,
   §1.5, App. B); hypotheses reported as unevaluated rather than silently dropped. The
   depth of Layer 1 (measurement-validity chapter, negative fine-tuning result with
   matched-precision re-baseline) is where the thesis earns its grade.
3. *"The adaptation result is negative."* Pre-registered, published as promised, with the
   quantization confound caught and quantified (−0.0234 vs the −0.0011 the naive
   comparison would have shown). This is the strongest methodological material in the
   thesis.
4. *"Measurement apparatus needed repairs mid-flight."* The repairs are the contribution;
   frozen-generation re-scoring makes them attributable. Finding 1 is the one loose end
   in that story — fix it and the argument is airtight.

## Submit / don't-submit

**Submit after Findings 1–2 are fixed** (both are localized text edits plus one audit-script
run on the main checkout; no numbers move, no experiments re-run). Finding 3 optional.

---

## Disposition (added 2026-08-18, correction pass)

All three findings and all four minor notes actioned on branch
`docs/fifth-pass-audit-corrections`, together with the sibling camshaft audit's
F1–F12 / D1–D5 / U1–U2. **No measured number moved** — `eval/heldout-breakdown.json`
is byte-identical.

| Finding | Disposition |
|---|---|
| **1 — undisclosed exclusion class** | **Fixed, and the blast radius is ~3× the estimate.** This finding was correct in mechanism and materially low in magnitude. It estimated "up to 8 `issue_date` cells" from the 2026-08-04 tracker note and proposed `scripts/audit_heldout_evidence.py` to confirm — the wrong instrument, since that script audits ground truth against *printed evidence* and never touches `_gt_state`. A purpose-built read-only census (`scripts/audit_heldout_exclusions.py`, `make audit-heldout-exclusions`) classifies every header cell by the scorer's own predicate and finds **30 exclusions: 8 ratified neutralisations (ADR-065, `payment_means_text`) and 22 parser-rejected across five date fields** — `issue_date` 8, `billing_period_end` 4, `payment_due_date` 4, `billing_period_start` 3, `delivery_date` 3. Disclosed in ch. 6's Class One inventory, in its defect chronology ("Two items" → "Three"), and in ch. 10 ("Two Known Defects" → "Three"). Ratified as ADR-072. The bias-direction reasoning here was right and is preserved: 17 of 22 fall in English email, the best-read channel, so the omission understates rather than flatters. |
| **2 — corpus provenance** | **Fixed**, and in a second location this audit did not check: `scripts/thesis_assets.py`'s module docstring carried the same "client documents" mischaracterisation. Both now match ch. 5's verbatim "the author's own business correspondence". |
| **3 — under-filled float page** | **Fixed generally rather than per-table.** Root cause was LaTeX's default `\@fptop` (`0pt plus 1fil`), which vertically centres float-only pages. Zeroed with the slack pushed to `\@fpbot`, so *every* deferred float top-aligns and the 17 generated tables stay consistent instead of each needing hand-tuned placement. |
| **Minor — title page** | No action, as advised. The German-format date and "Master Thesis" follow the FH Wedel template; now additionally confirmed against Tab. 1 and the template's own title page. |
| **Minor — "two largest files"** | **Fixed** (the camshaft audit's F9 disagreed with this note's "defensible as written"). Corrected to the line-count ranking: scorer → harness → ground truth → schema. This note's defence rested on test-function count, which is a second metric the sentence never named; the claim of a dedicated normaliser test file was wrong under either metric, since no such file exists. |
| **Minor — issue #48** | **The advice was wrong, and the issue is now genuinely closed.** This note stated "the terminology note has landed in ch. 1 §Scope". It had not. ch. 2 §2.1 defines OCR-free architecturally, but no site anywhere reconciled that claim with the OCR-*named* models the thesis evaluates — which is exactly what #48 asks for. The note was written in this pass (ch. 2, after the OCR-free definition), so the issue can close on substance rather than on a mistaken belief that it was already done. |
| **Minor — olmOCR-2 parameter count** | **This clearance was incorrect.** The note says "the thesis uses the model *name* only and never claims a literal seven billion — verified clean". The manuscript did claim it, twice: ch. 3 "a seven-billion-parameter transcription model" and ch. 7 "at seven billion". Corrected to the card's 8,292 M, with both finalists now carrying true checkpoint sizes (4.4 B / 8.3 B) and a footnote on the naming convention. |

### On this audit's verdict

Its bottom line — "submit after two small text fixes" — was too optimistic, though not
because its own findings were weak. The sibling camshaft pass, run independently against the
same tree, additionally found an invented bibliography title, two corporate-author
substitutions, a benchmark attributed to the wrong organisation, two missing archive records,
a stale archive URL, a misstated defect mechanism in the flagship chapter, two contradicted
appendix dispositions, and — decisively — that the statutory declaration had never been checked
against the Richtlinie, where a real defect was waiting ("in ähnlicher Form" for the prescribed
"in gleicher oder ähnlicher Form"). Neither pass alone was sufficient.

The two clearances above that proved false (`olmOCR-2` parameters, issue #48) are both cases
where this pass checked one facet and reported the whole claim as verified — the same pattern
the fourth pass named for the Krieger conflation, and the reason the correction pass re-derived
every metadata claim from the primary source instead of accepting either audit's word for it.
