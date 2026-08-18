# Fifth-Pass Review — adversarial pre-submission audit (the "Zweitgutachter argues 2.0" pass)

**Role**: Independent fifth full pass, requested as the final audit before submission, run as the hostile second examiner whose job is to find every defensible argument against a 1.0. Read-only — no manuscript edit was made; every finding below awaits discussion and an approved fix plan.
**Manuscript state on entry**: working tree of 2026-08-18 (identical sources to the user-provided build `thesis/_build/main.pdf`, built 2026-08-17 19:20, 138 pages, after the fourth-pass repairs of PR #130).
**Verification depth**: all twelve chapters, the abstract, the preamble and all six appendices read end-to-end from source; all 17 generated tables read and re-derived against the committed evidence (`data/finetune/*.json`, `eval/heldout-breakdown.json`, training-provenance files, split seal, McNemar artefact, findability audit); the full bibliography (80 entries) re-read and the citation graph recomputed (72 cited keys, zero broken, 8 deliberately dormant tooling entries); every load-bearing external claim re-verified against primary sources on the live web (arXiv, HF model cards, GI digital library, gesetze-im-internet.de, dejure.org, BMF, EDPB-via-third-pass, vendor contract documents); the rendered PDF inspected page-by-page visually (title, contents, abstract, results, figures, registry, declaration) and its build log re-analysed; the GitHub issue tracker cross-read against the manuscript's claims. The four prior review records were read first and their "verified" claims treated as claims to be checked, not as ground truth — several were re-derived independently (McNemar p-value, precision-confound factor, dev-loss ratios, channel arithmetic).

---

## 1. Verdict

**The manuscript is not yet submission-clean, but nothing found questions the science.** Every measured number I traced reconciles exactly with committed evidence; every externally checkable claim I re-verified (papers, statutes, standards, model cards, vendor contracts) holds, including the fourth pass's Krieger/Thiée repair. What remains is a small set of precision defects: one sentence in the flagship chapter misstates what the project's own audit found, two bibliography entries carry wrong or invented metadata of exactly the defect class this project has already repaired three times, two appendix statements contradict the project's own decision records, and the statutory-declaration wording is — by the project's own archive record — still not verified against the prescribed source. The hostile examiner's strongest ammunition is not any single finding; it is the pattern: a thesis whose central contribution is "validate the instrument" currently contains an instrument-validity chapter with a misstated mechanism and a bibliography whose header asserts verification that two entries contradict. All repairs are cheap (one sitting). The declaration check is the only true gate and requires the internal Richtlinie PDF the author holds locally.

| Severity | Count | Blocking? |
|---|---|---|
| Critical (factual, would embarrass in a defence) | 0 | — |
| Major (factual/precision, must fix before submission) | 5 (F1–F5) | yes, cheaply |
| Moderate (record/standards precision) | 2 (F6–F7) | strongly advised |
| Minor / cosmetic / judgment calls | 6 (F8–F12, plus D-notes) | no |

---

## 2. Major findings

### F1 — CERTAIN — Chapter 6 misstates the mechanism its own audit record documents

**Site**: `thesis/chapters/06-measurement-validity.tex`, §Class Three.

**Verbatim**: *"Two fields that had been scoring zero on perfect text turned out to be scoring zero because the renderer never rendered them; after repair they score near the top of the range."*

**What the record shows**: the count of two is right (in `data/finetune/eval-oracle-tier1-val.json`, exactly `allowance_total_amount` and `charge_total_amount` sit at F1 0.000). The mechanism is wrong. The project's own audit states, verbatim: *"check_oracle_transcript_labels proved all 6 allowance cases had `Summe Nachlässe: <value>` in the input while the model emitted `null`, i.e. a glossary gap"* (`eval/field-prompt-audit.md`, ADR-058). The renderer **did** render those fields — under the canonical EN 16931 label that no invoice prints and that the prompt never named — and the repair (corpus-grounded `printed_label`, ADR-059) changed the **label**, not the presence. "The renderer never rendered them" is contradicted by the audit's own evidence sentence.

**Why it matters here more than anywhere else**: this is the chapter whose entire claim is precision about what broke. An examiner who opens the repo — which the appendix invites — finds the audit record contradicting the chapter in one hop.

**Repair**: reword to the true mechanism, e.g. *"Two fields had been scoring zero on perfect text because the renderer showed them under a label no invoice in the corpus prints and the field specification never named; after repair they score near the top of the range."*

### F2 — CERTAIN — `deepseekocr2026` carries an invented title; both DeepSeek entries carry a corporate author

**Site**: `thesis/references.bib`, `@online{deepseekocr2026}` (cited in §3.1.1).

**Verbatim**: `title = {{DeepSeek-OCR-2}: Improved Contexts Optical Compression}`

**What is true** (verified against arXiv 2601.20552, the official GitHub repo's BibTeX, and the HF papers page): the paper's title is **"DeepSeek-OCR 2: Visual Causal Flow"**, and its authors are **Wei, Haoran and Sun, Yaofeng and Li, Yukun** — not "DeepSeek AI". "Improved Contexts Optical Compression" appears nowhere in the work; it is a descriptive paraphrase — the same defect class as the invented `krieger2021german` title and the `fatura2` author that the third pass repaired and the bibliography's own honesty note claims were the complete set ("All four are repaired in place"). A fifth instance survived: this entry was added later and never re-checked. The sibling entry `deepseekocr2025` has the correct title but the same corporate-author substitution ("DeepSeek AI" instead of Wei, Sun, Li).

**Repair**: real title + named authors for both entries; add the papers' archive records (the `docs/sources/tools/deepseek-ocr*.md` stubs cover the tools, not the papers); then re-check the honesty note's completeness claim — its "all four" enumeration is now itself stale.

### F3 — CERTAIN — `real5omnidocbench` is attributed to the wrong organisation and carries a descriptive title

**Site**: `thesis/references.bib`, `@online{real5omnidocbench}` (cited in §3.1.2).

**Verbatim**: `author = {{OpenDataLab}}` and `title = {{Real5-OmniDocBench}: real-world extension with five physical capture conditions}`

**What is true** (verified against arXiv 2603.04205 and the dataset page `huggingface.co/datasets/PaddlePaddle/Real5-OmniDocBench`): the authors are **Zhou, Gao, Wang, Gao, Cui, Tang & Liu** (PaddlePaddle), and the title is **"Real5-OmniDocBench: A Full-Scale Physical Reconstruction Benchmark for Robust Document Parsing in the Wild"**. OpenDataLab authored the parent OmniDocBench, not this extension — the entry conflated the parent benchmark's organisation with the extension's authors. The in-text claim ("extends it with five physical capture conditions") is accurate; only the bibliography metadata is wrong.

**Repair**: correct author list + real title; complete the archive record (`docs/sources/datasets/real5-omnidocbench.md` exists — verify it carries the corrected metadata).

### F4 — CERTAIN — Appendix B's H8 disposition is contradicted twice by the decision record

**Site**: `thesis/appendix/appendix.tex`, Appendix B, H8 entry.

**Verbatim**: *"Disposition: instrumentation was delivered; the confirmatory sweep was not run within scope --- not evaluated. The memory-envelope clause is consistent with every local run reported, but no dedicated sweep is claimed."*

**What the record shows** (ADR-032, the efficiency-sweep record): a sweep **was** run — 8 models × 1 invoice, `dev_only`, `configs/h8-efficiency.yaml` — and it produced a two-clause verdict: the decode-speed clause was *"not cleanly evaluable"* (no MPS decode-side numbers exist), and the memory clause **failed for one of eight models**: MinerU peaked at 13.40 GB = 105.4 % of the working set and swapped. Two misstatements follow: (a) "the confirmatory sweep was not run" — a diagnostic sweep ran and could not decide the hypothesis, which is a richer and more honest statement than "not run"; (b) "consistent with every local run reported" — directly contradicted by the documented MinerU breach. Chapter 1's RQ-map sentence (*"the confirmatory comparison was not run"*) inherits the first half of the problem.

**Why it matters**: Appendix B is the pre-registration exhibit; its dispositions must be the most carefully worded sentences in the document. As written, an examiner comparing the register against the decision trail finds the register misreporting the trail.

**Repair**: restate the H8 disposition as: instrumentation delivered; a diagnostic sweep ran (8 models, dev-only) and the ≥3× clause proved not cleanly evaluable on this hardware pairing (documented final position, not a TODO); the memory clause held for 7 of 8 models with one documented breach.

### F5 — CERTAIN — "Six registered hypotheses" miscounts the register both ways

**Site**: `thesis/chapters/10-limitations-future-work.tex`, §Pre-Registered but Unevaluated Hypotheses.

**Verbatim**: *"Six registered hypotheses were consequently never tested."*

**What the register itself says** (Appendix B): H7 is *"floated, never locked … never registered"*, yet template shift is counted as one of the six; and H8 **is** registered (formalised 2026-05-31) and unevaluated, yet is not among the six. So of the six items listed, one was never registered, and one registered-but-unevaluated hypothesis is missing from the count. Both the number and the adjective are off in the same sentence.

**Repair**: reword to name the sets precisely, e.g. *"Five registered hypotheses were consequently never tested; a sixth, floated but never locked, is reported alongside them; H8, registered later and found not cleanly evaluable on the project's hardware, is dispositioned in Appendix B."* (If F4's repair lands first, mirror it here.)

---

## 3. Moderate findings

### F6 — LIKELY — the registry presents a flat `tax_rate` as business term BT-119, which the standard defines only inside the VAT breakdown

**Site**: `thesis/tables/field-registry.tex` (Appendix A), row `tax_rate & BT-119 & Umsatzsteuersatz & rate`; framing sentence in §4.2.2: *"It is an alignment to EN~16931 … so every extracted field has a defined legal meaning"* (§2.2.2).

**What the standard says** (EN 16931-1, verified against the Peppol/invoice-converter term references): BT-119 is *"VAT category rate"*, a term of group **BG-23 (VAT breakdown)** with no document-level counterpart — the standard deliberately carries the rate per category, not per invoice. The registry uses BT-119 twice: correctly inside `vat_breakdown.rate_percent`, and again for the flat document-level `tax_rate`, which is **not** a business term of the standard. Chapter 6 is candid about the flat field being a design choice ("inherited from the era when an invoice had one"), but the appendix table presents it as a BT alignment, and §2.2.2's "every extracted field has a defined legal meaning" is thereby overstated for this one field. A standards-literate examiner (or the auditing-side examiner the archive warns about) can stand on this.

**Confidence note**: LIKELY rather than CERTAIN because a lenient reading ("aligned to" = "named after the closest term") is defensible; the table's own protocol note says the German label is the canonical term. The risk is the over-claim, not the design.

**Repair**: mark the row as derived, e.g. `BT-119 (BG-23, derived)` — one parenthetical that converts an over-claim into an honest derivation.

### F7 — CERTAIN — the bibliography's "every entry is archived" assertion fails for two cited entries, and one archive record is stale against its own entry

**Site**: `thesis/references.bib` header: *"Every entry below is backed by a record under docs/sources/<type>/"*.

**What the archive shows**:
- `edge2024graphrag` (Edge et al. 2024, arXiv 2404.16130 — cited in §2.3 and §3.4): **no record exists**. `docs/sources/tools/microsoft-graphrag.md` is about the GraphRAG *library* as a Layer-3 baseline candidate, status `stub`, and is not the paper.
- `dsgvo28` (Art. 28 DSGVO, cited in §1.1): **no record exists** — `docs/sources/legal/dsgvo-art-32.md` covers Art. 32 only.
- That same Art. 32 record still points at `dsgvo-gesetz.de` — the private commentary site the third pass deliberately re-pointed away from to EUR-Lex. The bib was repaired; its archive record was not, so the two have drifted apart — precisely what the header comment claims cannot happen.

**Why it matters**: the thesis's appendix states *"Literature citations were verified against the cited sources; the bibliography records per-entry verification notes"* (Appendix E), and the project's own archival rule says a citation without a completed record is "a citation this project is not entitled to make". This is process, not printed content — but the repository is part of the submission's evidence trail.

**Repair**: create/complete the two records, update the Art. 32 record's URL to the EUR-Lex target, and note the repair in the bib header's honesty note.

---

## 4. Minor findings and cosmetic notes

### F8 — CERTAIN — the committed datasheet contradicts the appendix on the answer-key schema version

**Site**: `docs/architecture/belege-heldout-datasheet.md` line 9: *"GT schema version: 1"* — versus `thesis/appendix/appendix.tex`, Appendix C: *"ground-truth schema version~2 (the provenance-carrying schema)"*.

The appendix is the correct side (`src/horus/eval/promotion.py` writes `PROMOTED_SCHEMA_VERSION = 2` into every signed-off document); the datasheet generator (`scripts/heldout_manifest.py`) prints the *draft-tree* constant (`GT_SCHEMA_VERSION = 1`). The datasheet the appendix's tables are converted from therefore describes the superseded draft tree's schema, not the signed-off key it now reports on. No wrong number reaches the PDF (none of the three converted tables carries the version), so this is a repo-artifact inconsistency — but it sits exactly where an examiner verifying Appendix C would look.

**Repair**: regenerate the datasheet reading the version from the promoted tree (or strike the line from the datasheet), so the two cannot disagree.

### F9 — CERTAIN — Chapter 8's test-suite composition claim does not match the suite

**Site**: `thesis/chapters/08-implementation.tex`: *"the two largest files cover the scoring rules and the typed schema with its repair pass, and the value normalisers and reference extraction follow closely"*.

Measured (`wc -l tests/*.py`): the two largest are `test_scorer.py` (1,337 lines) and **`test_harness.py` (1,190)** — the orchestration harness, not the schema. `test_ground_truth.py` (911) and `test_schema.py` (864) follow. And there is no dedicated normaliser test file at all — normaliser tests live inside other files. The risk narrative is right; the file ranking is wrong.

**Repair**: one sentence: *"the two largest files cover the scoring rules and the orchestration harness, with the reference extraction and the typed schema with its repair pass close behind."*

### F10 — CERTAIN — the final build has 14 overfull boxes; the "zero overfull" claim no longer holds

The post-repair build (138 pp) logs 14 `Overfull \hbox` warnings: twelve are TOC/LOF/LOT page-number columns protruding 1.6 pt (three-digit page numbers against the widened number columns) plus the abbreviations entry at 3.2 pt, two are subsection-number entries ("10.1.10.", "10.3.10.") at 1.6 pt, and one is a 0.4 pt paragraph in Appendix B. Worst case ≈ 1.1 mm — invisible in print; visually confirmed on the affected pages. Cosmetic only, but the fourth pass's "zero overfull boxes" and the README's status line are now stale, and the fix is mechanical (widen `numwidth` once more or accept and record).

### F11 — CERTAIN — "CI runs on every push" overstates the trigger

**Site**: `thesis/chapters/08-implementation.tex`: *"Continuous integration runs on every push and every pull request"*.

`.github/workflows/ci.yml` triggers on push **to `main`** and pull requests **against `main`** — a push to a feature branch does not run CI. One-word-class repair: *"on every push to the main branch and every pull request against it"*.

### F12 — LIKELY — the known-defects section presents itself as exhaustive but omits a third known, deferred defect

**Site**: `thesis/chapters/10-limitations-future-work.tex`, §Two Known Defects Remain Open: *"Reported here so that the apparatus is not represented as cleaner than it is."* The section lists exactly two (the supplier-article-number regression; the stale config default).

The tracker holds a third known, deliberately deferred apparatus defect: issue #118 — the date normaliser rejects English long-form, two-digit-year and US-order dates. It produced no error on the measured corpora (which is presumably why it was deferred), but the section's framing claims exhaustiveness, and an examiner reading the repo can find the open issue. Repair: either one clause disclosing it ("a third deferred gap, which fired on no measured document, is tracked as issue #118") or a stated criterion for what the section lists.

---

## 5. Discussion points (defensible as-is; listed so they don't surprise in the defence)

- **D1 — McNemar independence.** §7.2's exact McNemar over 963 paired *per-cell* outcomes treats cells as independent although they are nested within 29 invoices. The reported conclusion (no separation; p = 0.71, independently recomputed: correct) is the conservative direction — intra-invoice correlation would shrink effective sample size and push p further from significance — so the finding is safe, but a statistically trained examiner can raise it. One clause acknowledging the nesting would close it.
- **D2 — the headline mixes languages under a German-titled question.** The 0.88 headline pools 11 English + 28 German invoices; the abstract's question is about *German* B2B invoices. Everything is disclosed per-channel in Table 7.11, so this is framing, not concealment — but stating the German-only figure (or one clause in the abstract pointing at the mixed composition) pre-empts the obvious defence question.
- **D3 — "Scaling factor 16.0"** (Table 7.8) is `lora_alpha`; the effective LoRA scaling is alpha/r = 2. Common shorthand, but a picky reader of the adaptation chapter may ask. Optional: relabel "LoRA alpha".
- **D4 — vendor diversity of the held-out corpus is undocumented.** The limitations cover size and single-annotator; the defence may ask how many distinct vendors the 39 invoices span. The datasheet cannot answer today. Consider one sentence if the number is good.
- **D5 — `README.md` status block is stale** ("Green build verified: 128 pp" — the current build is 138 pp; "zero overfull boxes" — now 14). Repo hygiene only.

---

## 6. The one true gate (UNVERIFIED — artifact named)

**U1 — the statutory declaration's wording has never been verified against the prescribed source, by the project's own record.** `docs/sources/legal/fh-wedel-thesis-richtlinie.md` is still a stub carrying an open TODO: *"Verify the EXACT declaration wording + AI-clause text against the official Richtlinie 3.0; update `thesis/preamble/declaration.tex` if it differs."* The Richtlinie is Moodle-internal and not checkable from the public web (confirmed — the FH's own site directs to the Moodle course). The declaration's German ("an Eides Statt" vs. reformed "an Eides statt"; the exact AI-clause wording) is the single formal item whose defect can fail a submission rather than a grade. **Artifact needed**: the Richtlinie 3.0 PDF the author holds at `~/Projects/FH-Wedel/SS26/Master-Thesis/anmeldung-und-richtlinien/`. The same document settles the two related open items: the Kurzfassung-omission decision (README flags it for Prüfungsamt re-confirmation) and the 80–120-page window the fourth pass cites. Until that five-minute check happens, "submit" rests on an unverified formal assumption — the only finding in this audit the author cannot delegate.

**U2 — the 1,265-test count** (Chapter 8) was re-collected by the fourth pass on the main checkout; this worktree has no environment, so I verified a floor instead: 1,123 `def test_` functions by grep, consistent with 1,265 after parametrisation. Tag: consistent-with-evidence, re-run `pytest --collect-only -q | tail -1` once on the main checkout if you want it CERTAIN.

---

## 7. What was checked and found correct (inventory)

**Numbers — every traced figure reconciles exactly with committed evidence, several independently re-derived:**
- Held-out headline: 0.8825 mean / 0.8987 pooled / P 0.9530 / R 0.8503 / TP 568 / FP 28 / FN 100 — recomputed P = 568/596, R = 568/668, pooled F1 from P and R, channel sums (151+286+131, 3+14+11, 16+44+40), and the 12.6-point channel gap (0.9148 vs 0.7889) — all exact against `eval/heldout-breakdown.json`. "Four errors in five" = 100/128 ✓. Prior-ruler 0.8767 ✓.
- Sealed arms (0.8480/0.9778 bf16; 0.8257/0.9719 4-bit), the 2×2 grid (all four deltas negative; spurious 0.2012 the highest arm), the precision confound (−0.0011 vs −0.0234, factor 21.3; full precision +0.0223) — all exact against the six eval JSONs.
- Dev-loss table and both "rises 2.00×/3.21× at epoch 2" claims recomputed from the two training-provenance files; hyperparameter table matches the same files row for row; checkpoint-13 = end of epoch 1 under the registered rule ✓.
- Attribution: 304+201+92 = 597 (50.9/33.7/15.4 % recomputed); cluster table including both FN splits and the oracle-side figures; the 0.6771/0.9608 decomposition (0.3229/0.2837/0.0392) ✓.
- Reader lineage 0.6771/0.7829/0.8335/0.8257 ✓; corrected findability 0.995/0.976/0.970/0.965/0.925/0.753 with miss counts 3/13/16/19/40/129 ✓; McNemar 963 = 931+16+13+3, **p = 0.7111 independently recomputed** from the binomial tail ✓; the 52-miss audit's 19/6/27 classification and 23 exclusions ✓.
- Corpus: 117+29 = 146, seed 42, sealed hash prefix `9596cc2f…` matches `split.json`; dev slice 17 with its own hash; 100 fitting + 17 dev = 117 ✓.
- Adjudication: 1,326 = 34×39; 463 warranted + 248 by-hand; 8 unlocatable cells with TP/FP unmoved ✓. The Chapter 5 failure narrative (wrong month, blended total, missing digit, printed-but-absent) matches the ADR-060 evidence table verbatim.
- Registry: 34 flat fields + 3 groups confirmed from `src/horus/eval/ground_truth.py`; the held-out presence table matches the datasheet row for row; freeze-table page counts sum to 58 ✓.

**External facts — verified against primary sources this pass:**
- MDPBench (arXiv 2603.28130): 3,400 documents, 17 languages, 17.8 % photographed-drop, private split, author list — exact ✓ (this is the thesis's key external corroboration and it is solid).
- MinerU2.5-Pro (arXiv 2604.04771): title, authors, 95.69 OmniDocBench v1.6 ✓. DeepSeek-OCR (2510.18234) title ✓ (but see F2 on its sibling). Real5-OmniDocBench five conditions ✓ (but see F3 on attribution).
- Berghaus et al. (IEEE BigData 2025, arXiv 2509.04469): eight models, three families (3×GPT-5, 3×Gemini 2.5, 2×Gemma 3), three datasets, native > parse-first, and the SmolDocling control ("results were almost identical so we do not report them") — the §3.1.3 reconciliation passage is accurate, including the hard-won concession ✓.
- Thiée, Krieger & Funk (INFORMATIK 2023, DOI 10.18420/inf2023_180, LNI, pp. 1777–1792): the GI record and full text confirm the 977/494/531 German corpus with 60+ rule-annotated classes and its own comparison line "1129 (277/1)" for Krieger 2021 — the fourth pass's two-paper repair is correct in both directions ✓.
- FATURA (arXiv 2311.11856): 10,000 invoices, 50 templates, 24 classes, Limam/Dhiaf/Kessentini 2023 ✓.
- Both 2026 hallucination papers verified with author lists, venues, and the load-bearing quotes: "implicitly rewards always responding" (Uluoglakci & Taskaya Temizel, 800 LoRA runs incl. Gemma3-4B — the "predecessor generation" claim is accurate) and freezing-parameter-groups (Kaplan et al., arXiv 2604.15574) ✓.
- Legal: § 62a StBerG heading and all five Absätze as the Chapter 1 footnote paraphrases them ✓; § 27 Abs. 38 UStG phase-in (all 2026 → ≤ €800k 2027 → 2028) ✓; § 33 UStDV €250 ✓ (third-pass verification stands); Microsoft Zusatzvereinbarung exists, names § 203 StGB, expires after 36 months without renewal clause; Google NDA-gated; AWS individual — the narrowed provider claims hold ✓.
- Models: `Qwen/Qwen3-VL-4B-Instruct` exists (Apache-2.0, multilingual incl. German) ✓; `google/gemma-4-E4B-it` exists (natively multimodal; 4.5 B effective via Per-Layer Embeddings — note: the *repo comment*'s "Matformer" mechanism name is Gemma 3n-era and wrong for Gemma 4, but nothing in the manuscript repeats it) ✓; olmOCR-2 = Qwen2.5-VL-7B fine-tune, English-focused ✓; granite-docling-258M Idefics3 ✓.
- Standards: ZUGFeRD acronym expansion ✓; profile ladder incl. MINIMUM/BASIC WL as booking aids ✓; EN 16931 BT-mappings in the registry — all correct **except** the flat-tax-rate row (F6).

**Language and register**: zero contractions and zero first-person pronouns in the body (full-corpus grep); British spellings consistent ("artefact", "-isation" throughout; the only "artifact" is a code comment); quotation marks are proper LaTeX quotes throughout; heading capitalisation follows a consistent two-level convention (title case for `\section`, sentence case below); no colloquialisms found in the full read; hedging is calibrated and the diagnostic/sealed labelling discipline is upheld everywhere I checked.

**Form and look** (rendered 138-page PDF inspected visually): title page complete and clean (logo, department, title + HORUS subtitle, date, author, matriculation, both examiners with correct addresses); part order per the Richtlinie convention; TOC/LOF/LOT render correctly; abstract self-contained on one page; figures and protocol-note tables render professionally (defect chronology, held-out headline, channel table + chart all checked visually); declaration present in German with the AI clause and sign-off block. No unresolved references or citations in the build log; no LaTeX errors; the only boxes issues are the 14 sub-1.2 mm overfulls of F10.

**Coherence**: the four sub-questions map point-by-point to §9.1 answers with no overclaim; every forward promise I followed resolves; terminology is stable across chapters; the conclusion's numbers all appear in Chapter 7's tables; the abstract's every number traces to a committed artefact; the "what this thesis does not claim" section matches the scope-freeze record exactly.

---

## 8. Recommended fix order

1. **U1** (declaration wording + Kurzfassung + page window against the Richtlinie PDF) — five minutes with the author's local document; the only item that gates the act of submission rather than the grade.
2. **F1** (one sentence in Chapter 6) → **F4 + F5** (three sentences across Appendix B and Chapter 10) → **F2 + F3** (bibliography metadata + archive records) → **F7** (two archive records + one URL) → **F6** (one parenthetical).
3. **F8, F9, F11, F12, D5** — single-sentence repairs; **F10** — one `numwidth` widening or a recorded acceptance.
4. Rebuild (`make thesis-clean && make thesis`), re-run the float/overfull glance, and re-check the two repaired bibliography entries render correctly under `authoryear`.

All fixes belong on one branch via the release flow; none touches a measured number, so no table regeneration is required (the only executable change would be the datasheet line of F8, which regenerates from unchanged data).

---

## 9. Note on method

This pass deliberately treated the four prior reviews as exhibits, not as authority: their "verified" claims were re-derived where load-bearing (the McNemar p-value, the confound factor, the epoch ratios, the channel arithmetic, the Krieger/Thiée corpus facts), which is how F1–F5 surfaced — every one of them is a place where a prior pass verified the *metadata* of a claim but not its *content*, the exact failure pattern the fourth pass named for the Krieger conflation. The pattern is now the thesis's own best argument, applied to itself.

---

## 10. Disposition (added 2026-08-18, correction pass)

Every finding above was actioned in a single correction pass on branch
`docs/fifth-pass-audit-corrections`. **No measured number moved**:
`eval/heldout-breakdown.json` is byte-identical before and after, and the only
regenerated-table diffs are label-only (`field-registry`, `hyperparameters`).

| # | Disposition |
|---|---|
| **F1** | **Fixed.** Reworded in ch. 6 §Class Three *and* a second site in ch. 9 that carried the same misattribution. ADR-072 records the correction: ADR-059's own finding is *mislabelling*, not omission. |
| **F2** | **Fixed**, and wider than reported. Verified against the HF papers record: the real title is **"DeepSeek-OCR 2: Visual Causal Flow"** (space, not hyphen) and the contribution is DeepEncoder V2 token *reordering* — not a compression increment. Repaired in the bib **and** in four archive records that carried the same invented descriptor (`papers/deepseek-2026-*`, `papers/deepseek-2025-*`, `tools/deepseek-ocr-2`, `tools/deepseek-ocr`). The audit's claim that only tool stubs existed was incorrect — paper records existed and were also wrong. One consequence not in the finding: the ch. 3 prose described both papers as "optical context compression", which the corrected title would have visibly contradicted; reworded. |
| **F3** | **Fixed.** Authors + title corrected against arXiv 2603.04205 (Zhou et al., PaddlePaddle). `datasets/real5-omnidocbench.md` also had **invented condition names** ("lighting, angle, blur, glare, paper quality"); replaced with the paper's actual five (Scanning, Warping, Screen-Photography, Illumination, Skew). |
| **F4** | **Fixed.** H8 disposition restated: instrumentation delivered; diagnostic sweep ran (8 models, dev-only); decode clause not cleanly evaluable; memory clause held 7 of 8 with one documented MinerU breach. ch. 1 RQ-map sentence corrected too. |
| **F5** | **Fixed.** Five registered, plus template shift reported as floated-never-registered. |
| **F6** | **Fixed.** Registry table header is now `BT / BG`, `tax_rate` carries a dagger, and the protocol note explains the BG-23 scoping. ch. 2's "every extracted field has a defined legal meaning" qualified. |
| **F7** | **Fixed.** Created `papers/edge-2024-graphrag.md` and `legal/dsgvo-art-28.md`; re-pointed `legal/dsgvo-art-32.md` from the private commentary site to the EUR-Lex CELEX text the bib already used. The bib's blanket provenance claim and its stale "all four are repaired" enumeration are replaced by a cumulative three-pass correction log. |
| **F8** | **Fixed** at the generator, not the artefact: `heldout_manifest.py` now prints **both** schema versions with their trees named (1 in `gt/`, 2 in `_promoted/`), so the two cannot disagree again. Datasheet regenerated. |
| **F9** | **Fixed.** Ranking corrected to scorer → harness → ground truth → schema; the claim of a dedicated normaliser test file removed (there is none). |
| **F10** | **Fixed — now zero.** Root causes were TOC `pagenumberwidth` (too narrow for bold three-digit arabic and four-character roman page numbers) and a missing `subsection` tocline style (ch. 10 reaches `10.1.10.`). The residual 0.38 pt in Appendix B was absorbed by raising that block's existing local `\emergencystretch` from 2em to 3em. Two *underfull* warnings remain; they pre-date this pass. |
| **F11** | **Fixed** at both sites. |
| **F12** | **Fixed, and superseded by a larger finding.** Disclosing #118 led to auditing the exclusion mechanism, which found the count is **30 excluded cells = 8 ratified + 22 parser-rejected across five date fields** — not the 8 `issue_date` the tracker recorded. ADR-072 + `make audit-heldout-exclusions`. |
| **D1** | **Addressed.** ch. 7 now states the per-cell independence assumption, that cells nest within 29 invoices, and that the bias runs conservative — a test ignoring nesting cannot manufacture a null. |
| **D2** | **Addressed with numbers.** ch. 7 now gives the German-only figures derived from the per-channel counts (TP 417 / FP 25 / FN 84 → pooled F₁ 0.884, per-invoice mean 0.862 over 28 invoices) and notes that pooling *flatters* German rather than the reverse, since English email is the best-read channel. |
| **D3** | **Fixed** in the generator: "Scaling factor" → "LoRA alpha". |
| **D4** | **Declined, with reason.** Vendor diversity would need a fresh derivation over the private corpus, and the ceiling is 39 — too small to support a generalisation claim in either direction. Stating it invites a stronger reading than the corpus can carry, and the limitations section already discloses size and single-annotator. Recorded as an optional post-submission addition rather than silently dropped. |
| **D5** | **Not applicable.** Verified against `README.md`: it contains no build-status block, no "128 pp" and no "zero overfull" claim. The finding does not reproduce. |
| **U1** | **Fixed — and the audit's premise was wrong.** The Richtlinie *is* reachable: `Richtlinie 3.0 (Stand 25.04.2024).pdf` is held locally and `pdftotext` is installed. Extraction found a **real defect**: the declaration read "in ähnlicher Form" where §3.9/Abb. 2 prescribes "in gleicher **oder** ähnlicher Form", narrowing a legal assurance. Corrected verbatim; ADR-073. The two bundled questions are also closed — Kurzfassung is `Fallweise` (not obligatory) per Tab. 1, and the body is 115 Textseiten against the prescribed 80–120. Margins, 12 pt, `onehalfspace`, title-page geometry and Tab. 1 part order were additionally verified against FH Wedel's own **LaTeX** template and are all correct; the Richtlinie's prose margin figures describe the Word template, and "correcting" the geometry to match them would have been a regression. |
| **U2** | **Verified CERTAIN.** `make test` → 1,265 passed. |

### Findings this audit missed

Recorded so the next pass does not treat this one as authority either:

1. **olmOCR-2 parameter count.** The sibling zweitgutachter audit *explicitly cleared* this as "the thesis uses the model name only and never claims a literal seven billion". False: ch. 3 said "a seven-billion-parameter transcription model" and ch. 7 "at seven billion". The card reports 8,292 M. Both corrected, with a footnote on the naming convention.
2. **German prior-art bundling.** Both fifth-pass audits declared the Krieger/Thiée repair complete. But ch. 1 and ch. 3 still cited `krieger2021german` *inside German-corpus claims*, when the bibliography's own note records it as 1,129 **English** invoices. Only `thiee2023invoices` supports the German claim.
3. **Corpus provenance in the asset generator.** `scripts/thesis_assets.py` described the held-out inputs as "client documents" — the same defect the zweitgutachter caught in Appendix C, in a second location neither audit checked.
4. **`quantity` typed *money*.** The registry table gave no reason why an invoiced count carries a money comparator; a reader would read it as a type error. Protocol note now explains it denotes the comparison rule, not the business meaning.
5. **Issue #48's actual content.** The zweitgutachter said the OCR-free terminology note "has landed in ch. 1 §Scope" and advised closing the issue. It had not: ch. 2 defines OCR-free architecturally, but nothing anywhere reconciled it with the OCR-*named* models the thesis evaluates, which is precisely what #48 asks for. The note was written in this pass.
6. **`AGENTS.md` bibliography style.** Claimed `alphabetic`; the build has used `authoryear` since the 2026-08-16 pass.
