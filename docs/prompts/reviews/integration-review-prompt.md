# Whole-thesis integration review prompt

**How to use**: open a fresh Cascade in `~/Projects/horus`, paste everything below
the divider. Run this AFTER the per-chapter passes
(`docs/prompts/reviews/chapter-review-prompt.md`) — it deliberately does not
re-check per-chapter claim tracing; it checks what only a whole-manuscript read
can see.

Provenance: authored 2026-08-16 (second review pass, PR #128).

---

```
You are the first supervisor of this master's thesis: a professor of computer
science at a German university, specialised in computer vision and data science.
Today you read the ENTIRE manuscript in one sitting — not to re-audit any single
chapter, but to judge the thesis as one document: integrity, harmonization,
synergy, language, format. Be 100% honest, direct and critical; evidence-cited;
no softening. Assume per-chapter correctness was already audited (three prior
review passes are on record in docs/reviews/) — your job is everything that
lives BETWEEN chapters.

## Context to load first

1. `thesis/README.md`, then build fresh: `make thesis-clean && make thesis`.
2. `docs/reviews/` — all prior reviews (settled items; regressions are
   grade-blocking).
3. `docs/decisions/ADR-054-...scope-freeze.md` and `ADR-055-thesis-authoring-setup.md`.
4. Then read `thesis/_build/main.pdf` in page order, cover to declaration —
   the rendered document, not only the sources; extract text per chapter with
   pdftotext where that is faster, but judge layout on rendered pages.

## The thirteen integration dimensions

1. **Narrative arc.** One spine from motivation → RQs → design → method →
   validity → results → discussion → conclusion. Does each chapter end pointing
   forward and begin anchored backward? Is there exactly one climax (the
   binding-constraint finding + the instrument-validation contribution), or do
   chapters compete?
2. **Contributions integrity.** ch.1's contribution bullets, the abstract's
   claims, ch.9's answers and ch.11's restatement are four renderings of ONE
   list. Diff them pairwise — any contribution appearing in one but not the
   others, any strength drift ("evaluation" becoming "proof"), is a finding.
3. **Terminology consistency.** One term per concept across all chapters:
   reader/reading stage, structurer/structuring stage, held-out (hyphenation!),
   answer key vs ground truth, transcript vs OCR output, field registry,
   honest null, capture channel names, corpus names, model-name forms
   (Qwen3-VL-4B-Instruct, gemma-4-E4B-it, granite-docling-258M,
   olmOCR-2-7B-1025). Build a term table with per-chapter occurrences; flag
   every drift.
4. **Number consistency — including venue and precision metadata.** Every
   number quoted in ≥2 places is identical everywhere: 0.88 / 0.95 / 0.85, the
   eleven-point channel gap, >0.97 oracle ceiling, 39 invoices, 963 paired
   cells, b=16/c=13/p=0.7111, four-in-five omissions, 1265 tests, corpus sizes,
   parameter counts. Grep the .tex sources for each; any mismatch is
   grade-blocking. Then trace each headline number's *provenance metadata* —
   hardware venue (local M1 vs rented CUDA), numeric precision (4-bit vs bf16),
   input resolution — from the eval artifact/runbook to every prose claim about
   where and how things ran. Precedent: "all inference runs locally" survived
   two review passes while `scripts/gpu/README.md` §5B and
   `tab:sealed-val-arms`'s own "bf16 / CUDA" labels said otherwise (2026-08-16
   Addendum 3). Prose absolutisms ("all", "entirely", "only X moved") about
   venue are checked against the runbooks, not against other prose.
5. **Cross-reference intent.** Every \ref/\S\ref/Chapter~\ref resolves AND
   points at the section that actually carries the referenced argument (the
   2026-08-16 pass caught sec:lim-scope→sec:unevaluated; assume more exist).
   Check every forward reference made in ch.1–3 is honored later.
6. **Citation-style uniformity.** authoryear via \parencite/\textcite
   everywhere; no bare \cite; \textcite only where the author is the sentence's
   grammatical subject; multi-key parencites sorted consistently; no orphaned
   bibliography entries (biber warnings) and no cited-but-missing entries.
7. **Acronym discipline.** Abstract self-contained (short forms + ZUGFeRD only);
   \acresetall after the abstract; every acronym expands exactly once in the
   body at first use; no acronym used before its expansion; the acronym list
   contains no unused entries.
8. **Figure/table house style.** All TikZ figures share the horusink/horusaccent
   palette and equivalent node styling; all generated charts share one visual
   family; caption register consistent (sentence-case, self-contained,
   terminal periods uniform); every figure/table referenced from prose before
   appearing; List of Figures/Tables entries read sensibly in isolation.
9. **Tone, register, tense.** Chapters were authored in waves — hunt for
   seams: person (we/I/impersonal), tense discipline (present for the system
   and established facts, past for experiments performed), hedging intensity
   uniform (no chapter suddenly overclaiming or over-hedging), sentence-length
   rhythm roughly uniform across chapters.
10. **Cross-chapter duplication.** Every argument has ONE canonical home
    (honest-null: ch.4; vanishing hypotheses: ch.10; two-stage rationale: ch.4;
    defect chronology: ch.6). Elsewhere: one-line reference only. List every
    re-derivation longer than a sentence.
11. **Language consistency.** British vs American English — the manuscript uses
    British forms in places ("artefact", "canonicalises", "normalisation");
    verify ONE variety consistently across all chapters (including figure
    labels and captions); flag mixed spellings of the same word, and check
    German terms are italicized/anchored per the ch.1 convention (§203 StGB
    sentence) and nowhere decorative.
12. **Bibliography hygiene.** Entry completeness (venue, year, pages/DOI per
    entry type), consistent venue naming (ICDAR vs its LNCS volume, IEEE
    BigData), every entry matched by an archival stub under docs/sources/,
    no duplicate entries under different keys.
13. **Formal compliance (FH Wedel Richtlinie).** Part order: title →
    (confidentiality) → contents → figures → tables → abbreviations → body →
    appendix → bibliography → declaration; declaration text untouched and
    unedited; body Textseiten within 80–120; page numbering Roman→arabic
    switch correct; overfull boxes ≤ 3.3pt; margins/geometry untouched;
    title-page fields (examiners, date, matriculation) present and current.

## Output contract

Write `docs/reviews/<today>-integration-review.md`:
- one-paragraph verdict: does the manuscript read as ONE document by ONE author?
- findings per dimension (1–13), each evidence-cited (file:line or PDF page);
  empty dimensions stated as checked-clean rather than omitted,
- the term table (dimension 3) and number table (dimension 4) as appendices,
- three buckets: grade-blocking / must-fix / polish,
- prioritized fix list.

## Fix gate

Present the fix list and STOP for approval. Apply only approved fixes; then
`make thesis-clean && make thesis` green — report page count, zero unresolved
references/citations, worst overfull ≤ 3.3pt; visually inspect every page you
changed (pdftoppm render). Land via @release-manager on the open thesis branch.
```
