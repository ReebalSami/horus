# First-Supervisor Review — HORUS Master Thesis manuscript

**Role**: First-supervisor review pass (Data Science / Computer Vision professor persona), full audit: content, scientific method, repo evidence, rendered PDF, citations, formal compliance.
**Manuscript state reviewed**: working tree of 2026-08-15; clean build `make thesis-clean && make thesis` → `thesis/_build/main.pdf`, **101 pages**, 2 unresolved references, 0 unresolved citations.
**Verification depth**: every chapter read end-to-end; all 13 generated tables traced to committed evidence (`eval/`, `data/finetune/`); load-bearing citations and factual claims web-verified; PDF pages visually inspected.

---

## 1. Overall verdict

**Not submittable as it stands.** The manuscript is two theses stapled together: chapters 4–10 are a mature, unusually honest, well-evidenced piece of work that would grade in the top band; chapters 2, 3 and 11 are empty scaffolds, the abstract is half a placeholder carrying wrong numbers, and four of five appendices are blank pages — including the two appendices the body explicitly promises as evidence (the hypothesis register and the held-out datasheet). The printed submission date on the title page is 20 August 2026; the hard deadline in `preamble/header.tex` is 25.08.2026 14:00. Against that gate, the missing mass is the whole problem.

The deeper irony must be said plainly: this thesis dedicates an entire chapter to the discipline of checking claims against evidence — and then ships a reader-selection narrative that its own cited table does not support (§4.1), a bibliography entry whose author name is wrong despite an inline comment claiming it was "verified twice" (§7), and a second bibliography entry with a fabricated title (§7). The first examiner is FH Wedel's Ombudsperson für gute wissenschaftliche Praxis. He will look.

What is good is genuinely good: the measurement-validity chapter is a real contribution; the pre-registered conjunctive reader test and the precision-confound catch are textbook-grade methodology; every number I traced from a table to its committed evidence file matched exactly. The skeleton is strong. The flesh is missing in exactly the places a grader reads first (abstract, background, related work, conclusion).

---

## 2. Blocking issues (submission-preventing)

| # | Issue | Evidence |
|---|---|---|
| B1 | **Ch. 2 Background: zero prose.** Four section headings, body is 100 % TODO comments. Renders as a bare-headings page (PDF p. 7). | `chapters/02-background.tex` |
| B2 | **Ch. 3 Related Work: zero prose.** A master's thesis without a related-work chapter fails on formal grounds alone. Side effect: ~half of `references.bib` (Donut, LayoutLMv3, LoRA, HELM, CheckList, FUNSD, CORD, all legal statutes, …) is never cited and never prints — the printed bibliography is ~30 entries thin. | `chapters/03-related-work.tex`; `_build/main.bbl` |
| B3 | **Ch. 11 Conclusion: blank page** (PDF p. 85). A thesis whose central claims are this crisp has no excuse for an unwritten conclusion. | `chapters/11-conclusion.tex` |
| B4 | **Abstract is a placeholder with wrong numbers.** The bracketed block states "F1 of 0.96 on perfect transcripts but only 0.68 on real ones". The 0.68 is `overall_micro_f1 = 0.6771` — the **superseded survey reader on the synthetic sealed split**, not "real" invoices (real invoices scored 0.8825). The 0.96 is the superseded 0.9608 ceiling (current: 0.9719 4-bit / 0.9778 bf16). Both numbers are stale, and one is mislabeled in exactly the in-sample-versus-real way the manuscript forbids everywhere else. The placeholder's own trigger ("once the reader-selection results are in") has been satisfied for a week. | `chapters/00-abstract.tex:28-31`; `data/finetune/eval-zeroshot-val.json`; `eval/heldout-breakdown.json` |
| B5 | **Appendices A, B, C, E are TODO stubs rendering as blank chapters** while the body promises them as evidence: ch. 5 asserts "The register, with registration dates, is in Appendix B" (`app:hypotheses`) and the datasheet is "reproduced in Appendix C" (`app:heldout`). The pre-registration discipline is claimed loudly and its verification artifact is an empty page. The datasheet already exists in the repo (`docs/architecture/belege-heldout-datasheet.md`) — it just was never imported. | `appendix/appendix.tex`; `chapters/05-methodology.tex:82,444` |
| B6 | **Two unresolved references**: `\ref{app:registry}` (ch. 5, "The full registry is reproduced in Appendix~\ref{app:registry}") points at an appendix that does not even have a stub. | build log; `chapters/05-methodology.tex:253` |
| B7 | **Appendix A contradicts the body.** It is scheduled to present "the frozen one-page metric spec (field weights W=3/2/1)" — the compliance-weighted metric that ch. 1 and ch. 5 declare **abandoned** ("a headline number resting on an author-chosen weight vector is comparable to nothing"). Either present it explicitly as an abandoned design record or delete the appendix; as titled, it re-claims the metric the body disowns. | `appendix/appendix.tex:3-5` vs `chapters/01-introduction.tex:120-128`, `chapters/05-methodology.tex:337-343` |

---

## 3. Scientific-method audit — where the evidence does not carry the prose

### M1 (major). The reader-selection inversion story is misattributed — and the cited table cannot show it

Ch. 7 §7.3.1, ch. 6 §6.8, and ch. 9 (RQ 1) all tell the same story: the two finalists "finished **within a point** of each other **on end-to-end score**", the ruler corrections were applied, "the **ordering inverted** while staying inside the same margin", and "Table 7.1 shows the relevant rows."

The committed evidence (ADR-057, chronology §Context) says otherwise:

- The within-a-point margin and the inversion happened on the **findability/answerability ruler**: raw 0.777 (Qwen) vs 0.774 (olmOCR), fixed ruler 0.906 vs 0.913 — order inverted within noise. That is instrument two, not end-to-end score.
- **End-to-end** scores were never within a point: olmOCR 0.8335 vs Qwen 0.7829 raw / 0.8118 blank-page-guarded — a 2.2–5.1 point gap, olmOCR ahead.
- olmOCR was **never re-scored end-to-end under the corrected ruler** (no `eval-zeroshot-olmocr-adr059-val.json` exists). An end-to-end inversion is therefore not established by any committed artifact.
- Table 7.1 (`tables/reader-lineage.tex`) contains three old-ruler rows and one corrected-ruler row for one model. It cannot show an inversion, and its own protocol note correctly claims only "the gap between rows two and four is instrument, not model."

The **conclusion survives** — the instruments genuinely do not separate the finalists, and the decision was correctly forced onto per-miss adjudication. But the narrative as printed is factually wrong three times over, in the thesis whose stated contribution is not doing exactly this. Fix: retell §7.3.1 on the findability ruler (where the within-noise inversion actually happened, 0.906 vs 0.913), state plainly that end-to-end favoured olmOCR before corrections and was not re-measured for it afterwards, and re-scope what Table 7.1 is cited for.

### M2 (major). The attribution decomposition is stated three incompatible ways

- Ch. 7 §7.4 prose: "Of the total gap between the achieved score and the perfect-text ceiling, the **substantial majority is reading-induced** and the remainder is structuring capability."
- Table 7.4's protocol note: "of the 0.2837 gap the reading stage accounts for **roughly 0.14** and the structurer for the remainder" — i.e. ~50/50, matching the per-miss split printed directly above it (304 vs 293; 50.9 % / 49.1 %).
- `eval/finetune-attribution-audit.md`: "of the 0.32 total gap, **~0.28 is reading-induced, ~0.04 is structurer capability**" — a different denominator (gap to 1.0, using the oracle bound, which the audit argues is the honest one because string-findability understates the reader's share).

Three surfaces, three arithmetic stories, one adjective ("substantial majority") that only the third supports. A reader who checks Table 7.4 against the sentence above it finds a coin flip labelled a majority. Pick one decomposition, state its denominator, and carry it through prose, protocol note and audit identically. The audit's own argument (readable-but-mangled counts as structurer under the per-miss test) belongs in the chapter — it currently exists only in the repo.

### M3 (major). The one paper this thesis positions itself against is never engaged on its contradicting finding

Berghaus et al. benchmark two processing strategies and their headline result is: "**native image processing generally outperforms structured approaches**" (direct-vision beats parse-to-markdown-then-structure). This thesis's RQ 2 answer is the opposite arrangement won on its corpus. That is not a contradiction to hide from — their models are cloud-frontier-scale and their parse stage is Docling-to-markdown, not a VLM transcriber; the reconciliation is genuinely interesting (scale-dependent, and the thesis's decisive argument is measurability, not accuracy). But the manuscript cites `berghaus2025` three times, exclusively as gap evidence, and never once mentions that its headline finding points the other way. Ch. 3 — where this discussion belongs — is empty. A grader who reads the cited paper's abstract (I did) finds this in thirty seconds.

### M4. "Statistically tied" with no statistics

Ch. 7 §7.3.2: "The two finalists are **statistically tied** on corrected reading quality" (0.970 vs 0.965). No test, no interval, anywhere — and ch. 9 explicitly concedes no variance estimates exist under greedy decoding. Either run the cheap test that the per-document scores permit (bootstrap or McNemar over the 29 documents) or delete the word "statistically". As written it borrows authority the apparatus does not have.

### M5. The capture channel is misdescribed

The datasheet says the degraded channel is `iphone-pdf-scan` (10 documents) — scan-app output: perspective-corrected, contrast-enhanced. The manuscript calls it "photographed with a phone" (ch. 5), "photographed rather than exported" (ch. 7), "phone photograph" (Table 7.7 row label). A processed scan is a materially milder degradation than a raw photograph; this affects both the interpretation of the 11–13-point gap and the MDPBench comparison (whose photographed condition is printed-then-photographed under varied controlled conditions). One honest sentence fixes it — and arguably strengthens the finding (even scan-app-cleaned captures cost double digits).

### M6. The structurer is called "a second, text-only model" — it is not one

`google/gemma-4-E4B-it` is natively multimodal (text + image + audio input; ~150 M-parameter vision encoder per its model card). It is *used* text-only, which is a different statement — and an interesting one, since the training code explicitly freed the vision/audio towers (ADR-068). Also: the structurer's identity and size appear **only in table protocol notes**, never in prose; and the adaptation chapter never states in prose that only the text tower was adapted (it is in a protocol note). For reproducibility from the manuscript alone, name the models in the running text at first mention.

### M7. The "52 misses" audit is described imprecisely

The 52 hand-judged misses were the olmOCR candidate's residual list; Qwen's residual list got a separate symmetric pass afterwards (`eval/reader-findability-audit.md` §"Symmetric judge pass"). Ch. 7 §7.3.2 reads as if one 52-item audit covered both finalists. Small, but this chapter is the thesis's showpiece of per-miss rigour; describe the protocol exactly.

### Verified sound (credit where due)

- **Every table-to-evidence trace I ran matched exactly**: held-out headline and channel tables ↔ `eval/heldout-breakdown.json` (all twelve numbers, including the superseded 0.8767); 2×2 grid ↔ `data/finetune/eval-*-val.json`; dev-loss table ↔ both `horus_training_provenance.json` files; lineage rows ↔ the four zero-shot reports; precision-confound arithmetic (−0.0011 vs −0.0234, ×21) exact. The "no number is hand-copied" claim is real, not aspirational.
- Notably, the thesis dev-loss table is **correct where the repo's own eval report is wrong**: `eval/structurer-lora-2x2-results.md` §"Selection behaved exactly as designed" prints the oracle arm's curve (0.0965 …) labelled "reader arm". The provenance JSONs adjudicate for the thesis. Fix the eval report.
- Internal arithmetic: P/R/F1 from TP/FP/FN consistent everywhere checked; 34×39 = 1,326 cells; 463 + 248 accounting consistent; 10/39 ≈ "roughly a quarter"; corpus 117 + 29 = 146.
- Ch. 8's "1,265 tests" claim: exact (`pytest --collect-only` → 1265).
- The scope discipline holds: Layers 2–3 are marked design-only at every appearance I checked (ch. 4 headers, italic disclaimers, ch. 9, ch. 10). No result is claimed for them. ADR-054 compliance: clean.

---

## 4. Chapter-by-chapter

| Ch | Verdict | Notes |
|---|---|---|
| Abstract | **Rewrite** (B4) | Write last, but write: wrong numbers in a placeholder still anchor a reader. Kurzfassung question still open. |
| 1 Introduction | **Good** | Motivation is honest and correctly softened; the SUPERVISOR-GATE legal paragraph is accurate per my check (§6) — I sign it off with one change: cite the statutes, not only the BStBK FAQ. The named non-contribution (abandoned weighted metric) is exemplary practice. Structure section will need updating once ch. 2/3/11 exist. |
| 2 Background | **Missing** (B1) | The plan in comments is right-sized (keep KG short). Write it. |
| 3 Related Work | **Missing** (B2) | Must carry the Berghaus engagement (M3) and the measurement-validity positioning — the thesis's methodological novelty claim ("what we add") lives or dies here, and it is currently an empty room. |
| 4 System Design | **Strong** | The honest-null contract and the transcript-as-measurement-surface argument are the best-written design rationale I have seen in a master's thesis. The "what the split costs" paragraph pre-empts the obvious objection. Minor: "text-only model" (M6). |
| 5 Methodology | **Strong, with broken promises** | Three-channel GT adjudication, sealed splits with hashes, per-field symmetric normalisation — all defensible and evidenced. But it promises three appendices that don't exist (B5, B6) and describes the scan channel as photographs (M5). The privacy-cost admission (cloud GT channels) is honest and necessary. |
| 6 Measurement Validity | **The contribution** | Justifies its promotion to a chapter. The repair-versus-inflation discipline (§6.2) and the self-inflicted asymmetric-fix confession (§6.7) are exactly right. Weakness: it repeats the inversion misattribution (M1) in §6.8, and its effect-size claims lean on Table 7.1's incomplete lineage. |
| 7 Results | **Good, two defects** | M1 and M2 live here. The adaptation section (grid design, matched-precision baseline, dev-loss turn) is exemplary negative-result reporting. Summary list (§7.8) is crisp — items 1 and 5 need re-wording after M1/M2 fixes. |
| 8 Implementation | **Good** | Claims verified (1,265 tests; five app surfaces; CI on push/PR; hash-pinned Java validator). The deployment honesty ("what does not exist") is the right call. |
| 9 Discussion | **Good** | The four-mechanism literature engagement on the adaptation failure (Uluoglakci, Ghosh, Kang, Kaplan — all four verified, two verbatim quotes exact) is the strongest literature work in the manuscript; it belongs in ch. 3 too. RQ 1's answer repeats M1. Threats-to-validity section is unusually complete — the residual-leak admission (author read val documents during defect investigations) is the kind of sentence most students would delete; keep it. |
| 10 Limitations & Future Work | **Strong** | The structurer-was-never-selected admission (§10.1.4) and the registered-but-unevaluated hypothesis list are exactly how scope narrowing should be reported. Future-work ordering follows the evidence. |
| 11 Conclusion | **Missing** (B3) | — |
| Appendices | **Missing ×4** (B5–B7) | Only the AI-usage appendix has content, and it is generic + carries a TODO comment (F6). |

---

## 5. Formal compliance (FH Wedel)

| Check | Status |
|---|---|
| Part order (cover → ToC → LoF → LoT → abbreviations → body → appendix → bibliography → declaration) | ✅ verified in `main.tex` and rendered PDF |
| Declaration wording verbatim + inline AI clause, German, hand-signature space | ✅ (PDF p. 93) |
| Title page: matriculation, e-mails, both examiners | ✅ complete; examiners verified real (Säring, Bohn — FH Wedel faculty pages) |
| Undefined references/citations | ❌ 2 (`app:registry` ×2) — must be zero |
| Overfull boxes | ❌ `finetune-grid` table 58.7 pt and `precision-confound` table 48.5 pt into the margin (PDF pp. 55–57) + 3 minor. Visibly protruding; fix (abbreviate row labels or `\small`) |
| AI-usage appendix | ⚠️ present but generic, carries a TODO. The declaration legally asserts AI content is "kenntlich gemacht"; this appendix is the mechanism. Name the tools, the scopes, the verification practice, specifically. |
| Citation style | ⚠️ biblatex `alphabetic` is an acceptable short-reference form; formally confirm with supervisor per Richtlinie (do it in the next meeting, note the confirmation) |
| Kurzfassung (German abstract) | ⚠️ unresolved stub — confirm with Prüfungsamt; do not leave to the final week |
| Length | 101 pp. total, ~85 body — appropriate *after* ch. 2/3/11 land |

---

## 6. Legal-framing check (the SUPERVISOR-GATE paragraph, ch. 1)

Verified against public sources: §203 StGB covers Steuerberater/Wirtschaftsprüfer as Berufsgeheimnisträger; the 2017 amendment regime (§203 Abs. 3–4 StGB with §62a StBerG) requires text-form confidentiality obligations for mitwirkende Personen and a comparable-protection test for foreign providers; a major cloud provider (Microsoft) does offer a Berufsgeheimnisträger-specific contractual amendment; US extraterritorial access (CLOUD Act) is the standard residual-risk argument. The softened framing — "local inference removes the question rather than managing it" as an operational premise, not a legal verdict — is correct and defensible. **Sign-off granted, with one required change**: the paragraph cites only the BStBK FAQ (`bstbk2026`). The statute entries (`stgb203`, `stberg62a`, `dsgvo32`) exist in `references.bib` and are **never cited** — cite the statutes where they are asserted; a legal claim resting solely on a professional body's FAQ is weaker than the bibliography you already built for it. (This resolves issue #96.)

---

## 7. Citation & factual-accuracy audit

Web-verified this pass:

| Key | Verdict |
|---|---|
| `berghaus2025` | ❌ **Wrong first author**: bib says "Berghaus, Marco"; the paper is by **David** Berghaus (Fraunhofer IAIS). Title truncated: actual is "…: **Benchmarking LLM Strategies** for Invoice Processing". Now published at IEEE BigData 2025 (upgrade from `@online` possible). The bib's own comment claims "Verified 2026-05-13 … re-confirmed 2026-08-09" — the verification process failed on the thesis's single most load-bearing positioning citation. Also ch. 1's characterization "benchmarked large cloud models" is imprecise: they also benchmarked open-weights Gemma 3 (12B/4B); the accurate gap statement is "no recent specialised open-weights *document* VLMs" — keep that half only. |
| `cai2025` | ❌ **Fabricated title**: bib title "Evaluating Knowledge Graph Construction at Two Levels: …" is a paraphrase of the abstract. Actual title (arXiv 2506.12367): "Understanding the Effect of Knowledge Graph Extraction Error on Downstream Graph Analyses: A Case Study on Affiliation Graphs". The claim cited to it (edge-level vs structural-level evaluation) is supported; the entry must be corrected — and re-verify the author list while at it. |
| `mdpbench2026` | ✅ exact: 3,400 documents, 17 languages, 17.8 % average drop on photographed documents for open-source parsers; private split for contamination — all as claimed. |
| `uluoglakci2026humility` | ✅ exact: "implicitly rewards always responding" verbatim; 800 controlled LoRA runs; Llama3.1-8B + Gemma3-4B (predecessor family of the structurer, as the bib comment honestly notes). |
| `ghosh2024limitations` | ✅ verbatim: "LoRA fine-tuning is limited to learning response initiation and style tokens" (ICML 2024). |
| `kaplan2026why` | ✅ freezing-parameter-groups claim matches abstract; author list matches. |
| `kang2024unfamiliar`, `tam2024format`, `kieval2025`, `kim2022donut`, `huang2022layoutlmv3`, `biten2019anls`, `peer2024anlsstar`, `kerr1998`, `gebru2018datasheets`, `edge2024graphrag`, `han2025` | ✅ exist; claims match. `kieval2025`: cite the ICDAR 2025 version (Springer LNCS 16025, pp. 270–286) instead of bare arXiv. |
| `gemma4e4b`, `qwen3vl`, `olmocr2` | ✅ models exist as described; note E4B is 4.5 B effective / 8 B with embeddings and natively multimodal (feeds M6). These model entries are currently **uncited** — they should be cited at first prose mention of each model (M6 fix). |
| `en16931` | ⚠️ cites mustangproject.org — a third-party tool vendor's portal — for a CEN standard. Cite EN 16931-1:2017 (CEN/DIN or the EU eInvoicing portal). |
| `fhwedelrichtlinie` | ⚠️ URL is the university homepage; point at the actual document or mark it institutional-internal. |
| Legal statute entries | ⚠️ all uncited (see §6). |

Repo-side evidence hygiene (not manuscript, but graders clone repos): `eval/structurer-lora-2x2-results.md` mislabels the dev-loss arms (§3, "Verified sound"); `thesis/README.md` and `docs/prompts/stages/05-writeup.md` still describe the pre-2026-08-09 11-chapter map ("06-results") — stale against the 12-chapter reality.

---

## 8. Language & style

1. **The anonymized-model affectation.** The prose never names a model ("a general-purpose vision-language model at four billion parameters", "a purpose-built document transcription model at seven billion") while the tables two inches below print `Qwen3-VL-4B-Instruct` and `olmOCR-2-7B`. This buys nothing — the names are on the same page — and costs precision, reproducibility-from-prose, and the citations the model authors are owed. Name them at first mention, cite the model cards, use short names after.
2. **The "X rather than Y" tic.** "stated rather than omitted", "recorded rather than hidden", "reported as one rather than dropped", "an instrument, not a product" — the construction is effective the first five times; it appears several dozen times across ch. 4–10. Same for "load-bearing". Vary or cut.
3. **The honest-null contract is justified in full at least four times** (ch. 4 §honest-null, ch. 5 §metrics, ch. 7 §error-profile, ch. 9 RQ 1). Justify once, reference after.
4. **Em-dash density.** Multiple sentences carry two or three em-dash insertions each; combined with `parskip=full` the page reads breathless. Prune the second dash as a rule.
5. What is *not* wrong: the register is consistent, hedging is calibrated (claims are sized to their evidence), and the recurring protocol notes under tables are a genuinely good device. Keep those.

---

## 9. Prioritized action list

**Blocking (submission-preventing):**

1. Write ch. 3 Related Work — including the Berghaus engagement (M3) and the measurement-validity positioning. Highest-value writing in the remaining budget.
2. Write ch. 2 Background (keep KG short, per its own comments) and ch. 11 Conclusion.
3. Write the abstract from current numbers (0.8825 mean per-invoice held-out; 0.9719/0.9778 ceiling; channel gap; adaptation negative). Delete the placeholder. Resolve Kurzfassung.
4. Fill appendices: hypothesis register (B — from ADR-031/054 lineage, with dates), held-out datasheet (C — import `docs/architecture/belege-heldout-datasheet.md`), field registry (fix `app:registry`, B6), reproducibility pointers (E), AI-usage specifics (D). Resolve the Appendix-A contradiction (B7): reframe as abandoned-design record or delete.
5. Fix M1 — retell the reader-selection inversion on the instrument where it happened; state end-to-end was not re-measured for olmOCR. This is a factual-accuracy defect in the thesis's showpiece argument.

**Major (grade-relevant):**

6. Reconcile the attribution decomposition (M2) — one denominator, all three surfaces, and bring the audit's understatement argument into ch. 7.
7. Fix both bibliography defects (Berghaus author+title; Cai title) and re-run the claimed verification pass over every entry — two hits in one sampled pass is a rate, not bad luck.
8. Name the models in prose; fix "text-only model" (M6); describe the capture channel as scan-app processed (M5); delete or substantiate "statistically tied" (M4); precise-up the 52-miss protocol description (M7).
9. Cite the statutes in ch. 1 (§6); fix `en16931` and `fhwedelrichtlinie` entries.

**Minor (polish):**

10. Fix the two overfull tables and the `app:registry` refs → zero warnings; style pass on the tics (§8); update `thesis/README.md` + `05-writeup.md` chapter maps; fix the mislabeled dev-curve in `eval/structurer-lora-2x2-results.md`.

---

*Every claim in this review cites its evidence: repo paths, build log lines, rendered pages, or web sources checked on 2026-08-15. Where I verified numbers, I recomputed them from the committed JSONs rather than trusting either the tables or the eval reports.*
