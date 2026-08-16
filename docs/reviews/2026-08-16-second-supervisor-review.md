# Second-Pass First-Supervisor Review — HORUS Master Thesis manuscript

**Role**: First-supervisor review, second full pass (Data Science / Computer Vision professor persona). Scope: regression check of the 2026-08-15 review's fixes, fresh audit of the chapters written since (2, 3, 11, appendices), evidence re-trace, formal compliance, and the author's six pre-submitted concerns.
**Manuscript state reviewed**: working tree of 2026-08-16; committed build `thesis/_build/main.pdf`, **125 pages** (body pp. 1–99, appendices pp. 100–111, bibliography pp. 112–116, declaration p. 117), zero unresolved references and citations per `thesis/README.md` status.
**Verification depth**: all twelve chapters and all six appendices read end-to-end; all 17 generated tables inspected; held-out headline, channel table and reader-selection numbers re-traced to `eval/heldout-breakdown.json` and `eval/finalist-significance.json`; the McNemar p-value recomputed by hand; model-architecture claims verified against the three Hugging Face model cards; KIEval authorship verified against Springer/arXiv; FH Wedel AI guidance verified against the university's published "Lernen mit KI" page.

---

## 1. Overall verdict

**Submittable after one focused polish pass — and no longer for reasons of substance.** The 2026-08-15 review found a manuscript with empty load-bearing chapters and three factual misattributions in its showpiece argument. None of that survives: every blocking issue (B1–B7) and every major methodological defect (M1–M7) is verifiably fixed, and the chapters written since — Background, Related Work, Conclusion — are not filler; the Berghaus engagement in §3.1.3 is now the single best piece of positioning writing in the manuscript, because it states the contradicting headline finding of the closest prior work and reconciles it instead of hiding from it.

What remains is presentation-layer, and I will be blunt about it because the content now deserves better packaging than it has. This is a **computer-vision thesis with eight figures in 125 pages**, five of which are bar charts. Chapters 2, 3, 5, 8, 9, 10 and 11 contain not a single visual element. The thesis compares vision-language models whose internal differences it never draws, describes a three-channel ground-truth adjudication protocol — arguably its most original data work — entirely in prose, and dedicates a chapter to instrument repair whose chronology the reader must assemble in their head. A grader reads pictures first. Right now there is nothing to read first.

Second, the citation apparatus is formally acceptable and contextually wrong: biblatex `alphabetic` prints `[BBH+25]` labels, while both prior graded works under the same supervisor (WS25 seminar, SS25 deep-learning project) used `authoryear` with `\parencite` — `(Berghaus et al. 2025)`. The Richtlinie prescribes the short-reference method and defers details to the supervisor; the supervisor's established preference is on record twice. Switch it.

Third, the prose still carries the tics the first review named: "rather than" appears **89 times**, one sentence about vanishing hypotheses appears **verbatim three times** (ch. 4, 5, 10), the honest-null justification is argued in full in at least four places, and 277 em-dash pairs across 99 body pages produce a breathless register in the dense chapters. The fix list (§5) is mechanical.

The grade trajectory: the 2026-08-15 state was not submittable. The current state is a solid pass. The state after this polish pass — figures, citations, deduplication — is the thesis this work has earned. The evidence discipline underneath is, and I do not say this lightly, the strongest I have seen in a master's manuscript: I re-derived the McNemar p-value from the committed discordant counts and got 0.7111 exactly; I re-traced the headline table to `eval/heldout-breakdown.json` and all nine numbers match to four decimals; the claimed channel gap (0.9027 email-native German vs. 0.7889 phone-scanned) is 11.38 points, exactly as prose'd.

---

## 2. Regression check — 2026-08-15 review items

| Item | Status | Evidence |
|---|---|---|
| B1 Background empty | ✅ written | `02-background.tex`: 4 sections, tutorial register, KG section correctly kept short |
| B2 Related Work empty | ✅ written | `03-related-work.tex`: 4 bodies of work + positioning section; per-section "what this thesis adds" |
| B3 Conclusion empty | ✅ written | `11-conclusion.tex`: answer / contribution / non-claims / outlook — right shape, right length |
| B4 Abstract placeholder w/ wrong numbers | ✅ rewritten | current numbers (0.88, 0.95/0.85, >0.97 ceiling, 4-cell negative); traces to committed artifacts |
| B5 Appendices A/B/C/E stubs | ✅ filled | field registry (generated), hypothesis register w/ dates + dispositions, datasheet (3 generated tables), reproducibility |
| B6 `app:registry` unresolved | ✅ resolved | `appendix.tex:3-4` defines the label; build reports zero unresolved |
| B7 Appendix-A contradiction (weighted metric) | ✅ resolved | now Appendix D, explicitly framed as an abandoned-design record |
| M1 inversion misattributed to end-to-end | ✅ retold | §6.8 + §7.3.1: inversion on directly-measured reading quality (0.777/0.774 → 0.906/0.913); "only the selected reader was re-measured end-to-end" stated in prose **and** in the lineage table's protocol note |
| M2 three incompatible decompositions | ✅ reconciled | §7.4 + `attribution-shares.tex` note: one arithmetic (0.3229 total; 0.2837 reading; 0.0392 structurer), per-miss 50.9/49.1 explicitly labelled a lower bound, understatement argument imported from the audit |
| M3 Berghaus contradiction unengaged | ✅ engaged | §3.1.3: headline finding stated in bold, three-part reconciliation (model class / converter class / measurability), residual disagreement left open |
| M4 "statistically tied" without statistics | ✅ substantiated | exact McNemar over 963 paired cells, 16/13 discordant, p = 0.71 — **recomputed by hand: 2·(0.5 − C(29,14)/2²⁹) = 0.7111 ✓**; artifact `eval/finalist-significance.json` |
| M5 scan channel called "photographed" | ✅ fixed | ch. 5 "deskews and contrast-enhances… milder degradation than a raw photograph"; ch. 7 "the favourable kind of degraded input"; ch. 10 "mildest form of camera capture" |
| M6 "text-only model" | ✅ fixed | ch. 5: "The model is natively multimodal; it is used here on text alone"; models named + cited in prose at first mention (Qwen3-VL-4B-Instruct, olmOCR-2-7B, gemma-4-E4B-it) |
| M7 52-miss audit imprecise | ✅ fixed | §7.3.2: "A symmetric pass over the general-purpose model's own residual misses followed… so that neither finalist was audited under a rule the other was spared" |
| Bib: Berghaus author/title | ✅ fixed | `references.bib:59-68`: David Berghaus, full title, IEEE BigData 2025 |
| Bib: Cai fabricated title | ✅ fixed | `references.bib:76-79`: actual arXiv 2506.12367 title |
| Bib: KIEval bare arXiv | ✅ upgraded | ICDAR 2025, LNCS 16025, pp. 270–286 — matches Springer record; "Khang et al." in ch. 5 verified correct (Minsoo Khang, Upstage AI) |
| Bib: en16931 vendor URL | ✅ fixed | CEN + EU eInvoicing URL |
| Statutes uncited in ch. 1 | ✅ fixed | `01-introduction.tex:22-24`: dsgvo32, stgb203, stberg62a all cited inline |

The verification pass I asked for after the two bibliography hits was evidently run. I sampled six more entries this pass (mdpbench2026, uluoglakci2026humility, kieval2025, the three model-card entries) — no defects.

---

## 3. New findings this pass

### N1 (defect). Wrong cross-reference in the Conclusion

`11-conclusion.tex:67`: "the registered hypotheses are reported as unevaluated, never quietly dropped (§\ref{sec:lim-scope})" — `sec:lim-scope` is "Language, Document Class and Jurisdiction". The list of unevaluated hypotheses is `sec:unevaluated`. A reader who follows the reference lands on the wrong section, in the sentence whose whole point is that nothing was hidden. Fix: one token.

### N2 (major, presentation). The figure poverty is now the manuscript's dominant weakness

Inventory: 2 TikZ diagrams (both ch. 4) + 6 generated charts (1 in ch. 6, 5 in ch. 7). Zero visual elements in chapters 2, 3, 5, 8, 9, 10, 11. Concretely missing, in descending order of grader impact:

1. **No VLM anatomy figure in ch. 2.** §2.1.1 describes patch embedding → vision encoder → projector → autoregressive decoder in prose. This is the *Background chapter of a CV thesis*; the architecture it spends a page describing is the single most expected figure in the entire document.
2. **No cohort-differences figure.** The thesis's stated contribution is evaluating a *new model class*. The three cohort members differ in verifiable, drawable ways — olmOCR-2-7B is a Qwen2.5-VL-7B fine-tune emitting linearised plain text; Qwen3-VL-4B is a general-purpose instruct model emitting whatever the prompt asks; granite-docling-258M is an Idefics3-architecture compact model emitting DocTags markup (all three verified against their model cards). Ch. 2 §2.1.1 *says* "Document-specialised VLMs differ in what they emit" — show it. This directly answers the "we dived into the core of the models" expectation a grader brings to Background/Related Work.
3. **No data-work figure.** The two-corpus design (§5.2) and the three-channel adjudication with five provenance classes (§5.4.2) are the most original data engineering in the project — 1,326 cells, 463 warrant-accepted, 248 hand-adjudicated, ranked escalation, sign-off. It reads as a wall of prose. One flow diagram would let a reader hold the protocol in one glance, and it is the thesis's answer to "where is the data work?".
4. **No defect-chronology figure in ch. 6.** The chapter's argument is a *sequence* (defect found → class → fix → score movement, on frozen generations). A timeline/waterfall would carry §6.3–§6.7 visually.
5. **No LoRA figure in ch. 2.** §2.1.2 defines ΔW = BA in prose; the adaptation experiment is a headline negative result. One small diagram.
6. **Ch. 8 describes five app surfaces** with zero visual support.

### N3 (major, formal). Citation style diverges from the supervisor's established preference

Current: `style=alphabetic` (`header.tex:205`), 102 `\cite` calls, rendering `[BBH+25]`-class labels. Both prior works graded by the same first examiner use `backend=biber, style=authoryear` with `\parencite`/`\textcite` (seminar: 61 `\parencite`, 2 `\textcite`; identical preamble pattern in the plant-health project). The Richtlinie's own text: "Zitierweise: Kurzbelegmethode (Details mit Betreuer klären)" — the supervisor's preference *is* the norm, and it is author–year. `thesis/README.md` line 96 already lists confirming the style as an open TODO; the evidence answers it. Switch to `authoryear` (with `maxcitenames=2, uniquename=false, uniquelist=false, maxbibnames=99` for the seminar's exact rendering) and convert citations contextually: parenthetical evidence → `\parencite`, author-as-subject ("Ghosh et al. find…") → `\textcite`.

### N4 (style). The deduplication pass from review 1 §8 was only half-done

- "rather than": **89 occurrences** (ch. 4: 18, ch. 5: 13, ch. 10: 11). The construction is good; its frequency makes it a verbal fingerprint.
- The sentence "a hypothesis that vanishes between registration and reporting is indistinguishable, to a reader, from one that was tested and (found) inconvenient" appears **verbatim in ch. 4 (§4.6), ch. 5 (§5.8), and ch. 10 (intro)**. Once is a principle; three times is copy-paste. Keep ch. 10's, reference it from the others.
- The honest-null gap-vs-fabrication argument is made in full at least four times (ch. 4 §4.1.1 — canonical; ch. 7 §7.5.2; ch. 9 RQ-1 answer; ch. 11 "The answer"). Ch. 4 owns it; later occurrences should assert + cite, not re-derive.
- "load-bearing" survives 4× (ch. 4 ×2, ch. 5, ch. 7 §7.2). Review 1 said vary or cut; 4 is defensible, 2 would be better.
- 277 em-dash pairs / 99 pages. The worst sentences carry two pairs each. Prune the second dash as a rule (review 1 §8.4, still open).

### N5 (grammar/micro).

- `04-system-design.tex:292`: "Which documents in this period are missing a particular the law requires?" — reads as a typo even though "particular" is the intended noun; insert "that": "…missing a particular that the law requires?".
- `01-introduction.tex:7-10`: five German parentheticals in the opening sentence — see §4, point 1.
- Ch. 2 §2.4.1's TP/FP/FN prose is fine, but the FN definition ("absent **or wrong**") quietly overlaps FP ("carries a value that is wrong") — a wrong value is both FP and FN. That is the standard convention for extraction F1 and matches the code, but one clause acknowledging the double-count convention would forestall a picky examiner. Optional.

### N6 (formal, open decisions carried from review 1 — still open, still yours to close)

- **Kurzfassung**: deliberately omitted per author decision 2026-08-15. The Richtlinie's part list does not mandate one; the decision is defensible — but it was to be re-confirmed with the Prüfungsamt "only if in doubt". Confirm or accept the residual risk consciously; do not discover it at the printer.
- **Overfull boxes**: README reports worst 3.2 pt (was 58.7). Acceptable; verify it stays ≤ 5 pt after the figure insertions this pass will cause.

---

## 4. The author's six concerns, answered with evidence

**1. "German words at the beginning are unnecessary" — partially right.** The five parentheticals (`Steuerberater`, `Wirtschaftsprüfer`, `Rechtsanwälte`, `Eingangsrechnungen`, `Belege`) live in one paragraph (`01-introduction.tex:7-10`), and each appears exactly **once** in the manuscript — they are introduced and never used, so as *terminology* they buy nothing. But do not flatten them all: `Steuerberater` and `Wirtschaftsprüfer` are the professions §203 StGB literally enumerates, and the legal argument two paragraphs later depends on those exact statutory categories, not on loose translations. Verdict: drop the German for *invoices* and *receipts* (zero legal content); keep the professions' German glosses only where the statute is introduced. `Kleinbetragsrechnung` (ch. 2) is a §33 UStDV term of art — keep. `Eidesstattliche Erklärung` is prescribed German — untouchable.

**2. "125 pages, worried about duplication" — you are measuring the wrong number, and the underlying concern is half right.** 125 is the total PDF. The Richtlinie's 80–120 window counts *Textseiten*; the body runs pp. 1–99 ≈ **99 pages, comfortably compliant** (front matter, appendices, bibliography, declaration are not Textteil). So there is no length problem to fix. There *is* a repetition problem to fix — N4 above quantifies it — but it is measured in sentences, not pages. Trimming it will cost 1–2 pages, which the new figures will more than reclaim.

**3. "Lack of optical comfort; expected architectures in Background/Related Work" — correct, and it is the biggest remaining weakness.** N2 above. Your instinct about "not just tried them based on claims and benchmarks" is exactly what the cohort-differences figure fixes: the manuscript already *selected* readers by internal failure mode (dropped letterhead regions vs. character slips, §7.3.2) — the analysis is there; the visual evidence of understanding is not.

**4. "Citations should be (Author et al. Year)" — correct.** N3 above. Your seminar and plant-health project both do it; the thesis does not; the Richtlinie defers to the supervisor and the supervisor's preference is established. This pass switches it.

**5. "Afraid the AI appendix admits too much; the Eidesstattliche Erklärung says the opposite; should we show less AI usage?" — you are mistaken, and in the dangerous direction.** Read the declaration's own prescribed sentence (`preamble/declaration.tex:21-25`): "…die aus fremden Quellen direkt oder indirekt übernommenen Gedanken **sowie durch eine künstliche Intelligenz wie ChatGPT erstellte oder bearbeitete Inhalte sind als solche kenntlich gemacht**." The declaration does not forbid AI use — it *asserts you disclosed it*. The appendix is the disclosure. Delete or thin the appendix and the declaration becomes a false statement under Eides Statt — that is the actual hazard, and it is the one you would be creating, not avoiding. FH Wedel's published AI guidance ("Lernen mit KI", fh-wedel.de) says it in as many words: *"Im Zweifel ist Transparenz die sichere Wahl: Wer offen kennzeichnet, kann allenfalls die Leistung nicht anerkannt bekommen — wer verschweigt, riskiert deutlich mehr."* It even supplies a disclosure template — name the tool, version, purposes, and state that responsibility for correctness lies fully with the author. What the appendix should do is not *less* disclosure but *sharper* disclosure: the current text is honest but slightly generic; it should name tool + purposes per the university's own template, keep the "what AI did not produce" paragraph (it is the strongest paragraph in it), and state the author-responsibility sentence in the university's formulation. The "selbstständig" requirement is satisfied by exactly what the thesis can prove: every number from committed artifacts, every claim author-approved, decisions in ADRs, verification gates in CI. That is a *stronger* Selbstständigkeit story than most hand-typed theses can tell.

**6. "Not much attention given to the data work" — correct as a matter of presentation, wrong as a matter of substance.** §5.2–§5.4 is nine pages of corpus design, ground-truth extraction, three-channel adjudication, provenance classes, circularity check, privacy cost — the substance is all there, and Appendix C carries the datasheet. What is missing is *salience*: zero figures, and the key numbers (1,326 cells / 463 warrant / 248 adjudicated / 39 sign-offs) are buried mid-paragraph. The corpus-map and adjudication-flow figures of N2 items 3, plus a summary sentence at the top of §5.4 that leads with the effort, fix this without adding a page of prose.

---

## 5. Prioritized actions (this pass)

1. **Figures** (N2): VLM anatomy (ch. 2), cohort architecture/output comparison (ch. 2), LoRA update (ch. 2), corpus map + split freeze (ch. 5), three-channel adjudication flow (ch. 5), defect-chronology (ch. 6), app surface map (ch. 8). TikZ, house palette, model-card-verified.
2. **Citation switch** (N3): `authoryear` + contextual `\parencite`/`\textcite` conversion of all 102 calls.
3. **Cross-ref fix** (N1): `sec:lim-scope` → `sec:unevaluated` in ch. 11.
4. **Dedup pass** (N4): vanishing-hypotheses sentence ×3 → ×1; honest-null re-derivations → references; "rather than" 89 → <50 in the worst chapters; double em-dashes pruned where two pairs share a sentence.
5. **German terms** (§4.1): ch. 1 opening rewritten; professions' German kept at the statute.
6. **AI appendix** (§4.5): sharpen to the university's template; no reduction in disclosure.
7. **Grammar** (N5): the ch. 4 "particular that" fix.
8. Rebuild clean; verify zero unresolved refs, overfull ≤ 5 pt, body ≤ 120 Textseiten.

---

*Every claim in this review cites its evidence: file paths and line numbers in this repository, committed JSON artifacts, the rendered PDF's page map, Hugging Face model cards (olmOCR-2-7B-1025: qwen2_5_vl fine-tune of Qwen2.5-VL-7B-Instruct; Qwen3-VL-4B-Instruct: qwen3_vl, 4.4 B; granite-docling-258M: idefics3, 258 M), the Springer record for KIEval (LNCS 16025, pp. 270–286), and FH Wedel's published AI guidance. Where I verified numbers, I recomputed them from the committed artifacts (McNemar p, channel gap, headline table) rather than trusting the tables.*

---

## Addendum — fixes applied (same pass, 2026-08-16)

All eight prioritized actions of §5 were applied immediately after this review was written: citation style switched to `authoryear` with all 102 citations converted contextually (`\parencite`/`\textcite`); seven figures authored and wired (`figures/vlm-anatomy.tex`, `cohort-comparison.tex`, `lora-update.tex`, `corpus-map.tex`, `gt-adjudication.tex`, `defect-chronology.tex`, `app-surfaces.tex`) — every chapter 2–8 now carries at least one visual element; ch.11 cross-reference corrected to `sec:unevaluated`; deduplication trim ("rather than" 89→42, "load-bearing" 4→1, vanishing-hypotheses sentence 3→1, honest-null re-derivation in ch.7 replaced by a reference); ch.1 German parentheticals consolidated at the §203 StGB sentence; AI-usage appendix sharpened to the FH disclosure template with the author-responsibility closing statement; ch.4 grammar fix. Verified: clean rebuild at 128 pp (body pp. 1–103 = 103 Textseiten, within the 80–120 window), zero unresolved references and citations, worst overfull box 3.2 pt (pre-existing), figure pages and bibliography visually inspected in the rendered PDF, `(Author et al., Year)` rendering confirmed on body pages.

---

## Addendum 2 — external abstract review adjudicated + applied (2026-08-16, same day)

The author obtained an independent review of the rendered abstract (Claude Opus, web). Adjudication against the manuscript, then application:

| # | External claim | Verdict | Action taken |
|---|---|---|---|
| 1 | System never named | **Confirmed** — "HORUS" appeared nowhere in the rendered thesis (only a `.tex` comment in `main.tex:2`) | Author decision: named in the abstract, ch.1 contribution bullet (with backronym "Hybrid OCR-free Reading and Understanding System"), ch.8 opening; subtitle `\untertitel{The HORUS System}` added. **Formality flag**: confirm subtitle against the registered title with the exam office — the header's own note (Leitfaden §2: final title may differ from the working title) suggests this is permitted, but verify. |
| 2 | Acronym expansions choke the abstract | **Confirmed, and exposed a deeper defect**: no `\acresetall` existed, so the abstract consumed every first-use expansion and the body never expanded anything | Abstract now self-contained (`\acs` short forms; only ZUGFeRD expanded via `\acf`); `\acresetall` added after the abstract in `main.tex`; body first-use expansions verified in the rebuilt PDF (e.g., UStG/UStDV expand in ch.1) |
| 3 | No models, no hardware named | **Confirmed** | Abstract now names Qwen3-VL-4B-Instruct (reader), gemma-4-E4B-it (structurer), "16 GB Apple-silicon laptop" — matching ch.5 §hardware exactly |
| 4 | 2×2 unreadable without factors | **Confirmed** | Factors named inline: "(training input distribution crossed with evaluation condition)" |
| 5 | Ends on a non-result; significance sentence missing | **Confirmed structurally; proposed wording rejected** — "rather than silent wrong values" overclaims (P=0.95 still means 5% wrong values), and "Kanzlei" would reintroduce decorative German | Scope disclosure moved before the methodological paragraph; new hedged closing sentence: omissions predominate → failures surface predominantly as blank fields → compatible with human-in-the-loop verification |
| 6 | ~370 words, target ~300 | **Overstated** (was ~330 rendered) and the target conflicts with adding #1/#3/#4 facts | Trimmed filler; landed at ~360 rendered words on one page — the added facts cost words the cuts don't fully recover; accepted deliberately |
| — | "Verify the ZUGFeRD expansion against FeRD naming" | **Non-finding** — `acronyms.tex:57` matches the official FeRD expansion exactly | None needed |

Lesson recorded: external LLM review diagnosed accurately (it clearly read the rendered PDF — it quoted the F1 expansion verbatim) but two of its prescriptions would have introduced new defects if pasted unexamined. Trust the diagnoses; re-derive the prescriptions.

Also authored this pass: reusable per-chapter and whole-thesis review prompts at `docs/prompts/reviews/` (`chapter-review-prompt.md` with 13 chapter blocks, `integration-review-prompt.md` with 13 integration dimensions), for fresh-session reviews of each chapter; `docs/structure.md` updated accordingly. Verified after all changes: clean rebuild at 128 pp, zero unresolved references/citations, worst overfull 3.22 pt (pre-existing), title page + abstract page visually inspected.
