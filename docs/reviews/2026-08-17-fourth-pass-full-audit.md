# Fourth-Pass Review — full audit: rendering, typography, language, facts, sources, coherence

**Role**: Fourth full pass, requested as a pre-submission "check everything" audit: content, format, language, tone, facts, rendering, sources, integration. Read-only — no manuscript edit was made in this pass; every finding below awaits discussion and an approved fix plan.
**Manuscript state on entry**: working tree of 2026-08-17, clean `git status`, committed build 137 pages (`make thesis-clean && make thesis`), zero LaTeX errors, zero unresolved references, zero unresolved citations, zero biblatex/biber warnings, zero overfull boxes, one underfull hbox (badness 1173, p. 86) — cosmetic.
**Verification depth**: all twelve chapters plus all six appendices read end-to-end; all twelve generated tables re-read and **regenerated from committed evidence** (`make thesis-assets` → zero `.tex` diffs; PDFs differ only by embedded timestamps — the "no number typed by hand" guarantee holds); the full bibliography (79 entries) read and cross-checked against the citation graph (70 cited keys, zero broken); the test count re-collected (`pytest --collect-only` → exactly 1,265, matching Chapter 8); the field registry imported from source (`horus.eval.ground_truth`: 34 flat + 3 groups, matching Appendix A and every "34 fields" claim); float placement audited programmatically over the built PDF (32 floats); the reader-selection, adjudication, scope-freeze and attribution decision records re-read; the McNemar artifact, both finalist eval JSONs, and the per-miss audit document re-traced; German statutes, the e-invoicing timeline, EN 16931 business terms, ZUGFeRD profile semantics, and six external papers re-verified against primary sources on the live web.

---

## 1. Verdict

The manuscript is in strong shape: every internally generated number I traced reconciles exactly with its committed evidence, the argument is coherent from research questions through conclusion, the register is uniformly formal (zero contractions, zero first-person pronouns in the body), and the build is clean. **One finding is blocking**: a related-work paragraph attributes another paper's corpus to the closest published prior work, and the error survived the third pass's "deep-read" because the deep-read verified the bibliographic metadata but not the corpus description. Everything else is rendering polish, staleness, or judgment calls.

| Severity | Count | Blocking? |
|---|---|---|
| Critical (factual) | 1 | yes — F1 |
| Major (rendering / staleness) | 4 | no, but should be fixed |
| Minor / judgment calls | 6 | discussion items |

---

## 2. F1 — CRITICAL: the German-invoice prior-work paragraph conflates two different papers

**Site**: `thesis/chapters/03-related-work.tex`, §"German invoices have been extracted before, and by whom" (the `krieger2021german` paragraph and the comparison paragraph that follows it).

**What the thesis says**: Krieger, Drews, Funk & Wobbe (2021) "assemble 977 real German invoices from 494 vendors, annotated over more than sixty classes, and extract from them with a graph neural network over OCR output, reporting a macro-averaged F$_1$ of 0.8753 on a deliberately layout-diverse set" — framed by the section as "the closest published work on German invoices", which is the load-bearing language claim.

**What is actually true** (verified against the Springer full text, the WI 2021 proceedings page, and the GI digital library):

- **Krieger et al. 2021** (WI 2021, Springer LNISO, DOI 10.1007/978-3-030-86797-3_1): corpus = **1,129 English one-page invoices from 277 vendors, one recipient** (an audit firm), **hand-annotated** for **three key items** (invoice number, invoice date, total amount) plus an "unlabeled" class. Macro-F$_1$ **0.8753** is over that task. OCR engine: Tesseract. The layout-variety contrast against prior single-vendor datasets is the paper's point — that part of the thesis's framing is right.
- The **977-invoice German corpus** (494 vendors / 531 recipients, rule-based annotations over 60+ classes, Abbyy OCR) belongs to a **different paper**: a GI-published design-science study by the same research group (Thiée, Krieger & Funk, "Extraction of Information from Invoices — Challenges in the Extraction Pipeline", INFORMATIK 2023, DOI 10.18420/inf2023_180 — the GI full text contains the 977/494/531 table verbatim, compares itself against "1129 (277/1)" for Krieger 2021, integrates German-BERT into Krieger's GCN, and reports **F$_1$ 0.823** on the same three labels).

So the thesis merges two papers into one citation: corpus and class count from the 2023 GI study, F$_1$ and authorship from the 2021 WI paper. Three claims break:

1. "977 real German invoices from 494 vendors" — wrong paper.
2. "annotated over more than sixty classes … reporting a macro-averaged F$_1$ of 0.8753" — the 0.8753 is over **three** key items on the **English** corpus; the 60+-class German corpus scored **0.823**.
3. the framing "closest published work on German invoices" — Krieger 2021's corpus is English ("we only used English invoices", the paper's own limitations section).

**How it got in**: the brainstorm-era stub `docs/sources/papers/gi-2021-german-invoices.md` described "a GI 2021 paper, 977 German PDFs, 60+ classes, authors TBD". The third pass resolved "authors TBD" to the nearest matching paper — Krieger's WI 2021 GNN paper — and transplanted the stub's corpus description onto it. `krieger-2021-invoice-gnn.md` now carries `status: verified` over a corpus description that the verified paper contradicts. The lesson is the one the bibliography's own honesty note states: *a claim of verification is itself a claim to be checked*.

**Why it matters**: this is the exact passage an examiner from the auditing side will probe (the archive record itself says so), and the "both round to roughly 0.88" comparison is one of the thesis's positioning anchors.

**Recommended repair** (one coherent path, no menu):
1. Rewrite the paragraph to describe Krieger 2021 accurately: 1,129 real invoices in English from 277 vendors and a single recipient, three key items, GNN over OCR output, macro-F$_1$ 0.8753.
2. Add the GI 2023 design-science study as a second citation carrying the German-language angle: 977 real German invoices, 494 vendors, 60+ rule-annotated classes, F$_1$ 0.823 on the same three labels with a German-BERT-augmented variant of Krieger's model. This *strengthens* the section: the German-language prior is weaker (0.823 on 3 fields) than the English prior, which makes the thesis's 0.88 over 34 EN 16931 terms on unseen real documents a sharper contrast.
3. Rework the comparison paragraph: attribute the German-language angle to the 2023 study; the incomparability reasons (corpus scale/realism, kind of ground truth, hardware setting, class inventory) all survive and get stronger.
4. Repair the archive: fix `krieger-2021-invoice-gnn.md` (corpus description + status note), create a verified record for the GI 2023 paper, update the supersession note in `gi-2021-german-invoices.md`, add the new bib entry.
5. Chapter 1's one-line mention ("addressed with recognition-plus-layout models on a restricted real corpus") needs its citation widened to both papers and its noun pluralised — as a German-prior claim it cannot rest on the English-corpus citation alone. (Implementation note, 2026-08-17: the same holds for the Chapter 3 positioning summary, whose "German invoice extraction has been studied" cited `krieger2021german` and `krieger2023longtail` — the latter's corpus is the audit firm's primarily-English collection per Krieger's dissertation — so `thiee2023invoices` was added there; the long-tail archive record's `german` tag was likewise a conflation residue and was corrected.)

---

## 3. Major findings

### F2 — "HELM! (HELM!)" in §3.2.2

`\ac{HELM}` is used at `03-related-work.tex:200` but `HELM` was never added to `preamble/acronyms.tex`. The `acronym` package renders an undefined key as the key with exclamation marks — hence the "HELM! (HELM!)" the author spotted in the PDF. This is the only undefined acronym key in the manuscript (all other `\ac` keys resolve).
**Repair**: add `\acro{HELM}{Holistic Evaluation of Language Models}` to the acronym list (first use will render "Holistic Evaluation of Language Models (HELM)", matching the cited `liang2022helm`). One line.

### F3 — Appendix E understates the review-pass count

`appendix.tex` ("AI-Tool Usage Documentation") says "Two review passes (one adversarial, documented in the repository) checked the manuscript's claims…". Three passes exist on disk (2026-08-15, 2026-08-16 ×2), and this fourth pass makes four. A statutory-declaration support document that is itself stale undercuts its purpose.
**Repair**: replace the fixed count with un-versioned wording — "Multiple review passes, documented under `docs/reviews/` in the repository, checked the manuscript's claims against the committed evidence and the cited sources, including one adversarial re-audit of a prior pass." No future re-staling.

### F4 — Two floats land far from their first mention

Programmatic float audit over the built PDF (all 32 floats; landing page from `.aux`, first prose mention from per-page text extraction):

| Float | First mention | Lands | Drift |
|---|---|---|---|
| `tab:corpus-composition` (Table 5.1) | p. 37 (§5.2, data) | p. 47 | **+10 pages** |
| `fig:gt-adjudication` (Figure 5.2) | p. 37 (§5.2) | p. 42 | **+5 pages** |

Root cause is source order, not LaTeX float drift: both are first *referenced* in §5.2 but *declared* in the later sections that discuss them in depth (`corpus-composition` at `05-methodology.tex:390` in the splits section; the adjudication figure in the ground-truth section). `[htbp]` cannot place a float before its declaration. All other 28 body floats land on the mention page or the page after (two at +2 — acceptable). Appendix floats are covered under F5.
**Repair**: for the table, either move the `\input` to just after the first reference in §5.2 (the caption already describes both corpus and split, so it works there) or reword the §5.2 sentence to point at the section instead of the table number. For the figure, the same choice. My recommendation: move both declarations to the first-reference point — the reader meets the numbers where they are promised.

### F5 — Four appendix floats are never referenced by number

`tab:field-registry` (A.1), `tab:heldout-presence` (C.2), `tab:heldout-freeze` (C.3) have no `Table~\ref{…}` anywhere; the appendix prose introduces them as "The registry below" / "All three tables". `tab:heldout-composition` (C.1) is referenced — but only from Chapter 5, not from its own appendix. The general convention (and examiner expectation) is that every float is referenced by number at least once.
**Repair**: three small prose edits in `appendix.tex` naming the tables (e.g., "…composition counts (Table~\ref{tab:heldout-composition}), per-field presence in the signed-off answer key (Table~\ref{tab:heldout-presence}), and the cryptographic freeze table (Table~\ref{tab:heldout-freeze})"; "The registry (Table~\ref{tab:field-registry}) is reproduced…").

---

## 4. Minor findings and judgment calls

### F6 — Stale style comment in the bibliography

`references.bib:1` says "biblatex + biber; **alphabetic** style" — the manuscript switched to `authoryear` (Richtlinie conformance, 2026-08-16, per `preamble/header.tex`). Comment-only; zero rendering effect. One-word fix.

### F7 — Nine bibliography entries are never cited (dormant)

`anthropicsdk`, `doclinglib`, `fpdf2`, `granitedoclingmlx`, `huggingfacetransformers`, `peftlib`, `trllib`, `streamlit`, `fhwedelrichtlinie`. Under biblatex, uncited entries do not print — the rendered bibliography is clean, so this is not a defect. Two of them deserve promotion rather than deletion:
- `fhwedelrichtlinie` — Appendix E invokes "the FH Wedel guidance on AI use in academic work" without citing it; citing the Richtlinie there closes the loop.
- The tooling entries — Appendix F (reproducibility) names the package manager, MLX, MLflow and the build chain; if the implementation-tooling entries are wanted in the printed bibliography, a `\nocite` block or explicit cites in Appendix F would do it. Otherwise leave them dormant (they cost nothing).

### F8 — An archived methodological anchor is uncited

`docs/sources/papers/raman-2025-invoice-extraction-arxiv-2510-15727.md` archives the paper that anchored the header-fields-vs-line-items metric separation (the early ground-truth decision record cites it as the scientific precedent for scoring the two separately). The thesis now makes exactly that separation load-bearing (§5 metrics; §10 limitations) without citing any precedent for it. Optional: one sentence + citation in the metrics section. Counter-argument: the DocILE benchmark lineage could be cited instead as the origin of the separation; the archived record is a stub (authors unverified). If cited, the record must be completed first — per the archival rule, "a citation whose archive record says authors TBD is a citation this project is not entitled to make."

### F9 — The McNemar paragraph's counts do not visibly sum

§7.2 gives 963 paired cells, 931 both-find, 16 vs 13 discordant — leaving 3 both-miss cells unstated (the artifact confirms `both_missed: 3`, and they coincide with the text-layer ceiling's own 3 misses). Adding half a sentence ("…and three that neither finds, which are the three the embedded text layer itself lacks") completes the arithmetic and quietly explains the ceiling row.

### F10 — Bold run-in lead-ins: consistent house style, keep

The manuscript uses `\textbf{…}` as paragraph lead-ins ~180 times across all chapters (the pattern the author asked about). Assessment: this is a deliberate, uniformly applied convention (run-in paragraph headings), common in German-tradition theses and consistent here — including inside protocol notes and the limitations chapter. It is not wrong, and un-bolding selectively would create inconsistency. A handful of *mid-sentence* emphasis bolds exist (e.g., "should therefore be read as an upper bound", "was not chosen at all"); those carry argumentative weight and are defensible, but `\emph` would be the more conventional register for mid-sentence stress. Recommendation: keep the lead-in convention untouched; optionally convert the ~8 mid-sentence bolds to `\emph`. This is a pure style call for discussion.

### F11 — Cosmetic rendering notes (no action urged)

- One underfull hbox (badness 1173) on p. 86 — invisible in print.
- `tab:precision-confound` and `fig:heldout-pr` land +2 pages after first mention — normal float behavior at chapter density.
- Cross-chapter forward references (Ch. 1 → Table 7.5; Ch. 6 → Tables 7.1/7.9/7.10) are intentional narrative devices and resolve correctly.

---

## 5. What was checked and found correct (inventory)

**Numbers** — every one of the following was traced to committed evidence and reconciles exactly:
- Held-out headline: 0.8825 mean per-invoice / 0.8987 pooled / P 0.9530 / R 0.8503; TP 568, FP 28, FN 100 → 100/128 = 78 % ≈ "four errors in five are omissions"; 39/39 scored; prior-ruler 0.8767 note.
- Channel split: 11+18+10 = 39; email-mean 0.9148 vs scan 0.7889 = 12.6 pt; German email − German scan = 11.4 pt ("more than eleven points" is conservative and correct).
- Sealed-split arms: 0.8480/0.9778 (bf16), 0.8257/0.9719 (4-bit); "exceeds 0.97 on perfect transcripts…reaches 0.85 at matched precision" ✓.
- Adaptation grid: all four deltas negative (−0.0234/−0.0196/−0.0126/−0.0476); spurious rises to 0.2012 (highest of any arm) ✓; precision confound −0.0011 vs −0.0234 → "factor of 21" ✓; full precision worth +0.0223 ✓.
- Attribution: 304+201+92 = 597; 50.9 %/49.1 %; pipeline 0.6771 vs oracle 0.9608 → 0.3229/0.2837/0.0392 decomposition ✓ (matches the scope-freeze decision record verbatim).
- Reader selection: 0.777/0.774 → 0.906/0.913 inversion ✓ (decision records); "two to five points" = 2.1–5.1 pt across the three aggregations in the two eval JSONs ✓; 52 hand-judged misses → 19 real / 6 ruler / 27 unfindable, 23 exclusions ✓; McNemar 963/931/16+13/p = 0.7111 ✓; 8B sibling decode-collapse on 1/29 ✓.
- Corpus and splits: 117+29 = 146 ✓; 100 fitting + 17 dev = 117 ✓; dev-loss minimum at epoch 1 in both arms, budget 6 ✓; hyperparameters match the training provenance files ✓.
- Adjudication: 285+178 = 463 warranted + 248 by-hand = 711 decided ✓; 1,326 = 34×39 ✓; 8 unlocatable cells, TP/FP unchanged ✓.
- Implementation: 1,265 tests (exact, re-collected); 34 flat fields + 3 repeating groups (imported from `horus.eval.ground_truth`); five app surfaces ✓.

**Regeneration**: `make thesis-assets` reproduces every table byte-identically from committed evidence — the "no measured number typed by hand" claim in the conclusion and Appendix F is *demonstrated*, not asserted.

**External facts** (live-web verified): Berghaus et al. — eight models, three families (GPT-5/Gemini 2.5/Gemma 3), three datasets, native-vision beats parse-first, IEEE BigData 2025, authors/title exact ✓. FATURA — Limam/Dhiaf/Kessentini 2023 ✓. Krieger 2023 long-tail — LayoutLM vs Chargrid/random-forest generalization gap ✓. Donut ECCV 2022, LayoutLMv3 ACM MM 2022, ViT ICLR 2021, Attention NeurIPS 2017, LoRA ICLR 2022, CheckList ACL 2020, Kerr 1998 (PSPR 2(3) 196–217), Gebru datasheets, Biten ANLS ICCV 2019, ANLS* 2402.03848, KIEval ICDAR 2025 (LNCS 16025), Tam et al. EMNLP 2024 Industry (format restrictions degrade performance) ✓. Ghosh et al. ICML 2024 quote "limited to learning response initiation and style tokens" ✓. Kang et al. 2403.05612 ✓.
**Legal/timeline** (against gesetze-im-internet.de and chamber FAQs, as re-verified in pass three and spot-rechecked): receive-obligation 2025; issuance 2027 (> €800k turnover) / 2028 (all); §33 UStDV €250 small-amount relief; §203 StGB + §62a StBerG / §43e BRAO / §50a WPO service-provider provisions from the same 2017 act; EN 16931 BT numbers (BT-1/2/5/27/31/44/72/112/115 all correctly mapped); ZUGFeRD profile ladder with MINIMUM/BASIC WL as booking aids, not EN-conformant invoices ✓.

**Language and tone**: zero contractions, zero first-person pronouns, no colloquialisms found in a full read; spelling is consistent British-academic ("colour" not used; "-ise/-ize" consistent as "-ise"? — both chapters use "-isation/-ise" spellings consistently); hedging is calibrated (claims labeled diagnostic vs. confirmatory throughout); the "honest ruler" chapter's confessional register is unusual but deliberate, consistent, and the thesis's strongest asset.

**Structure and compliance**: part order matches the template (title → abstract → TOC → body → bibliography → declaration → appendices with LOF/LOT); the statutory declaration is present in German with the AI clause and backed by Appendix E; body page count (110 printed pages) sits inside the 80–120 window; abstract is self-contained (no undefined acronym use, no citations); hyperref metadata present; TOC/LOF/LOT render correctly.

**Coherence**: the four sub-questions of §1.3 are answered point-by-point in §9.1 under the same numbering and no answer overclaims its evidence; every chapter's forward promises ("§X states…") were spot-verified to resolve; terminology is stable (reading/structuring, target class/floor, fitting/sealed, signal-bearing, honest-null) across all twelve chapters; the conclusion's numbers all appear in Chapter 7 tables; the unevaluated-hypotheses register (Appendix B) matches §10.2's six items and the label-reconciliation history it cites.

---

## 6. Recommended fix order

1. **F1** (Krieger conflation) — factual, blocking, touches ch. 3 + bibliography + two archive records + one new archive record.
2. **F2** (HELM acronym) — one line.
3. **F3** (review-pass count) — one sentence.
4. **F5** (appendix float references) — three sentences.
5. **F4** (float placement) — two declaration moves, then a clean rebuild to confirm landings.
6. **F6** (bib comment) — one word.
7. **F7–F10** — as decided in discussion.

All fixes belong on one branch via the release-manager flow, followed by `make thesis-clean && make thesis` and a re-run of the float audit to confirm the placement repairs.

---

## 7. Disposition (2026-08-17, implemented on branch `docs/fourth-pass-fixes`)

| Finding | Disposition |
|---|---|
| F1 | **Fixed** — two-paper repair. A deeper re-verification against the papers' own texts confirmed the conflation and extended it: the ch. 1 citation, the ch. 3 positioning summary, the `krieger2023longtail` record's `german` tag, and the dataset record's chimera citation were all conflation residue. New verified record `thiee-2023-invoice-extraction-pipeline.md`; `thiee2023invoices` added to the bibliography. |
| F2 | **Fixed** — `HELM` added to the acronym list. |
| F3 | **Fixed** — un-versioned wording ("Multiple review passes, documented under `docs/reviews/`…"). |
| F4 | **Fixed** — `tab:corpus-composition` moved to its first prose promise in §5.2; the two page-37 pointers to `fig:gt-adjudication` (corpus-map caption + TikZ node) retargeted to `\S\ref{sec:method-heldout-gt}`, so the figure now lands beside its discussing section instead of trailing a far-forward promise. |
| F5 | **Fixed** — all four appendix tables now referenced by number from their own appendix prose. |
| F6 | **Fixed** — "authoryear". |
| F7 | **Partially adopted** — `fhwedelrichtlinie` is now cited in Appendix E, closing the statutory-declaration loop. The eight tooling entries stay dormant deliberately: a `\nocite` block would print implementation-tool manuals in the bibliography with no in-text warrant. |
| F8 | **Declined** — the archived record is a stub with unverified authors; per the archival rule the citation is not available until the record is completed, and the metric-separation precedent is already carried in-text by the KIEval citation. Record retained for provenance. |
| F9 | **Fixed** — the 3 both-miss cells are now stated, with their coincidence with the text-layer ceiling's own misses; 931 + 16 + 13 + 3 = 963 sums visibly. |
| F10 | **Adopted with a uniform rule** — bold is retained only for paragraph-initial run-in lead-ins and definitional first introductions; every in-paragraph stress bold (19 instances — the "~8" above undercounted the same class) converted to `\emph`. |
| F11 | **No action**, as recommended. |
