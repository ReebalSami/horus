# ADR-074: Citation style reversed to numeric brackets on the examiner's written instruction

**Status**: Accepted
**Date**: 2026-08-22
**Refs**: ADR-055 (thesis authoring; the 2026-08-16 review pass that introduced `authoryear`), ADR-069 (`docs/reviews/` canonical home), `horus-decision-discipline`, `horus-source-archival`

## Context (current-state survey)

The first examiner returned the interim manuscript on 2026-08-18 as an annotated PDF carrying **38** authored annotations. One of them, a sticky note on printed page 3, is an explicit instruction about citation style:

> *"Ich persönlich bevorzuge bei der Literaturangabe den IEEE oder ACM bibstyle - dort werden die Cites durch Nummern in Eckigen Klammern angegeben, was dann die Lesbarkeit verbessert."*

The manuscript currently uses `style=authoryear`. The rationale for that choice stands in `thesis/preamble/header.tex:206-211`:

```
%% authoryear per the first examiner's established preference: both prior graded
%% works under the same supervisor (WS25 seminar, SS25 deep-learning project) use
%% this exact option set, rendering (Author et al. Year) via \parencite/\textcite.
%% The Richtlinie prescribes the short-reference method and defers the concrete
%% form to the supervisor (Richtlinie 3.0, "Zitierweise: Kurzbelegmethode").
%% Switched from the template default `alphabetic` in the 2026-08-16 review pass.
```

Two defects, both material:

1. **The rationale is falsified.** It justifies `authoryear` as matching "the first examiner's established preference". That was an *inference*, drawn from the option sets of two prior graded works under the same supervisor. The examiner has now stated his preference directly, and it is the opposite. Inference from artefacts lost to primary evidence from the person himself. Correcting the option without correcting the comment would leave a false claim in the source, attributed to a named person.

2. **The original choice was never ratified.** `grep -rln "authoryear" docs/decisions/` returns nothing. A citation-style change is a convention that affects every page of the manuscript, and `horus-decision-discipline` classifies exactly that as requiring an ADR. It was made inside a review pass and recorded only as a source comment. This record closes that gap as well as reversing the decision.

The Richtlinie constraint is unchanged and is satisfied either way: it prescribes the *Kurzbelegmethode* and defers the concrete form to the supervisor. Numeric brackets are a short-reference form, and the supervisor has now specified it.

## Options considered

1. **Numeric bracketed style (IEEE/ACM family)** — **chosen**. It is what the examiner asked for, in writing, unprompted. He grades the work. The Richtlinie defers the form to him. There is no counter-argument of comparable weight.
2. **Keep `authoryear`** — rejected. The only support for it was an inference that primary evidence has now contradicted. Retaining it would mean overriding an explicit written instruction from the first examiner on a matter he called out for readability.
3. **Ask him to confirm** — rejected. The note is unambiguous, names two concrete style families, and gives his reason. Asking would spend supervisor goodwill to re-derive an answer already given.
4. **Numeric for citations, keep an author-sorted bibliography** — retained as an open implementation choice rather than a rejected option; see integration below. It is a sub-decision of option 1, not an alternative to it.

## Decision (+ integration thoughts)

Switch the manuscript to a **numeric bracketed citation style**. Three pieces of work, all deferred to the fix session that processes the review registry:

### 1. The style option

`thesis/preamble/header.tex:205-221` moves off `style=authoryear`. The concrete option set is **not fixed by this record** and must be settled by an actual build, because several currently-set options are `authoryear`-specific and become inert or meaningless under a numeric style — `maxcitenames=2`, `uniquename=false`, `uniquelist=false` exist to control author-list disambiguation that numeric rendering does not perform.

The open sub-decision is `sorting`: IEEE convention numbers in **citation order** (`sorting=none`), whereas the present `sorting=nty` would keep the bibliography alphabetical and assign numbers alphabetically. Both are legitimate; the examiner named the style family, not the sort. Pick one and record it in the header comment.

Verification is by `make thesis` — the option set either compiles and renders bracketed numerals or it does not. Context7 carries no entry for core `biblatex` (only `biblatex-iso690`), so this record deliberately does **not** assert a verified option string; asserting one from memory is precisely the failure mode `context7-and-docs-first` exists to prevent.

### 2. The falsified comment

The header comment is rewritten, not merely edited around. It must no longer attribute a preference to the examiner that he has contradicted. The replacement should record: the numeric choice, its source (his 2026-08-18 review note), the Richtlinie's deferral, and the fact that the earlier `authoryear` rationale was an inference now known to be wrong. Leaving the old text in place while flipping the option would preserve a false statement about a named person in tracked source.

### 3. The `\textcite` call sites

**17** call sites use `\textcite` (`03-related-work.tex` 10, `09-discussion.tex` 4, `05-methodology.tex` 2, `02-background.tex` 1). Under `authoryear` these render as "Author (Year) report …" and read naturally as sentence subjects. Under a numeric style the same construct degrades to "[12] report …", which is the readability regression the examiner is trying to avoid — so a mechanical style flip would partially defeat his own stated purpose. Each site needs either an explicit author mention with the numeric cite appended, or a rephrase to `\parencite`.

This is the reason the change is not a one-line edit and is sequenced **first** in the registry's suggested order: it alters every citation's rendering, so it must land before any prose proofreading.

## Source archival

The primary source is the examiner's annotated PDF and its covering email. Both carry his name and signature and are therefore **deliberately not archived** under `docs/sources/`, departing from `horus-source-archival`'s default that every cited source is archived at citation time.

The exception is recorded rather than taken silently:

- **Why**: archiving would commit a named third party's personal correspondence and signature to a git history that outlives the project. The same reasoning produced the earlier `chore/redact-supervisor-and-reframe-meeting` pass.
- **What is preserved instead**: the annotation's verbatim German text is reproduced in `docs/reviews/2026-08-18-first-supervisor-comment-registry.md` (row R02), together with its exact PDF coordinates, page, and resolved `.tex` target. The claim this ADR rests on is therefore checkable from tracked material.
- **Where the artefacts live**: `thesis/proff-kommentare/`, gitignored in full.

The Richtlinie source referenced above is already archived at `docs/sources/legal/fh-wedel-thesis-richtlinie.md` (extracted and verified in ADR-073).

## Supersession trigger

Supersede if any of:

- The first examiner revises the instruction, in writing or at a supervision meeting.
- The second examiner requires a conflicting style, in which case the conflict is escalated rather than resolved unilaterally.
- A future Richtlinie revision stops deferring the concrete short-reference form to the supervisor and prescribes one.

Do **not** supersede for aesthetic reconsideration. The decision rests on the graded-by preference of the examiner, not on the project's own taste.
