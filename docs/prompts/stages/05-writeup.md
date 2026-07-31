# 05 — Writeup phase (kickoff)

| Field | Value |
|---|---|
| **Phase** | 7/7 — `writeup` (per `.windsurf/phases.yaml`) |
| **Skill** | `@writeup` (forward-reference; not yet an L1 skill — authored manually for now) |
| **Milestone** | `submission-ready` |
| **Status** | Open — authoring in progress |
| **Date opened** | 2026-06-28 |
| **Scope** | Compile the master-thesis manuscript from the project's results. This doc is the phase's living index: it opens with the authoring setup (ADR-055) and tracks chapter status + content waves. Thesis scope itself is frozen by ADR-054. |

> **Results-integrity caveat (inherited).** Every in-sample number from the
> experiment phase is **diagnostic, NOT real-world accuracy** (see
> `04-experiments.md` §"READ THIS FIRST"). The manuscript's headline results
> surface is the **sealed validation split** — the cloud comparison arm is
> descoped to future work per ADR-054, so it is no longer part of the reporting
> surface. No in-sample F1 may be cited as HORUS's real-world accuracy. Results
> enter the manuscript as **generated** figures/tables (never hand-copied).

## 1. Authoring setup

- **Manuscript home**: `thesis/` (in-repo). Build: `make thesis` → `thesis/_build/main.pdf`.
- **Format / language**: LaTeX (FH Wedel KOMA/biblatex template adapted to English).
- **Authoring decision**: `docs/decisions/ADR-055-thesis-authoring-setup.md` (authored as 054, renumbered after the endgame ADR landed first; carries the 2026-07-31 scope-freeze amendment).
- **Scope decision — what the manuscript may claim**: `docs/decisions/ADR-054-thesis-endgame-reader-first-recovery-and-scope-freeze.md`.
- **Structure + conventions**: `thesis/README.md`.
- **Compliance**: the statutory declaration carries the AI-disclosure clause; AI-tool usage is documented in an appendix (FH Wedel Richtlinie).

## 2. Chapter status

Chapter map reshaped 2026-07-31 for ADR-054's scope freeze (see the ADR-055
amendment). The three-layer vision survives as ch.4 (design); the unbuilt
knowledge-graph and query layers are absorbed by ch.9. **No empty chapters.**

| Ch | Title | Status | Basis |
|---|---|---|---|
| 1 | Introduction | **Drafted** (rewritten for frozen scope) | softened legal framing (#96), OCR-free note (#48), Layer-1 RQ + 4 sub-questions |
| 2 | Background | Scaffolded | `docs/sources/` literature; KG section deliberately kept short |
| 3 | Related Work | Scaffolded (repositioned) | berghaus-2025; new measurement-validity section; KG/RAG demoted to design motivation |
| 4 | System Design | **Scaffolded (new)** | three-layer design; Layers 2–3 marked design-only + not-evaluated |
| 5 | Methodology | **Scaffolded (deepened)** | corpus, GT-from-embedded-XML, metric suite, measurement-validity lineage, sealed splits, reading proxy, attribution design, pre-registration |
| 6 | Results | Scaffolded + explicit `[PENDING]` markers | ADR-009…053; attribution audit; placeholders for reader selection / re-baseline / adaptation |
| 7 | Implementation and Prototype | Partial | ADR-036/039 |
| 8 | Discussion | Scaffolded (reframed) | reading-as-binding-constraint + measuring-before-optimising |
| 9 | Limitations and Future Work | **Scaffolded (new)** | ADR-054 descoped list + registered-but-unevaluated hypotheses |
| 10 | Conclusion | Stub (short by design) | — |

## 3. Content waves

- **Wave 1 (done, June)**: authoring setup + chapter skeletons + green build; first Introduction draft.
- **Wave 2 (done, 2026-07-31)**: rebase onto the landed endgame work; ADR renumber 054→055; formal-compliance fixes (part order, verbatim declaration, title-page data policy, contents-list spacing); chapter map reshaped to the frozen scope; Introduction rewritten. Build green (32 pp).
- **Wave 3 (next)**: full prose drafts of the GPU-independent chapters, in this order — Methodology (strongest owned material) → Results (real numbers + `[PENDING]` placeholders) → Related Work → Limitations and Future Work → System Design.
- **Wave 4**: Discussion, Conclusion, Abstract — written last, after the reader-selection numbers land.
- **Writing model**: Claude Opus 5 at high/xhigh effort (per the ADR-055 amendment).

## 4. Open items

**Needs the author (cannot be resolved by Cascade):**

- Title-page values still marked `<...>` in `thesis/preamble/titlepage.tex`: Matrikelnummer, university e-mail, second examiner (name + e-mail), first examiner's exact e-mail. No postal address is used (decision 2026-07-31).
- **Supervisor sign-off on the softened legal framing** in ch.1 §Motivation (the paragraph carries a `SUPERVISOR GATE` comment). Closes #96.
- Confirm citation style with the supervisor — the Richtlinie prescribes the short-reference ("Kurzbeleg") method and says the supervisor's own preference overrides; the template default (biblatex `alphabetic`) is one valid short-reference form.
- Confirm whether a German `Kurzfassung` is required alongside the English abstract (commented stub in `chapters/00-abstract.tex`).
- Consider whether the registered working title still fits the frozen scope (it no longer promises the graph/query layers, so it is defensible as-is).

**Cascade-side, remaining:**

- Reconcile `thesis/references.bib` metadata against the verified `docs/sources/` stubs (entries currently flagged `approx.`).
- Wire the figure/table generation pipeline (results → `thesis/figures` + `thesis/tables`); no number is hand-copied.
- Draft the Wave 3 chapters.
- Close #48 (OCR-free framing) once ch.1 is final — the terminology note is already written.
