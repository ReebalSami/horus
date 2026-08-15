# 05 — Writeup phase (kickoff)

| Field | Value |
|---|---|
| **Phase** | 7/7 — `writeup` (per `.windsurf/phases.yaml`) |
| **Skill** | `@writeup` (forward-reference; not yet an L1 skill — authored manually for now) |
| **Milestone** | `submission-ready` |
| **Status** | Open — full draft complete; author read-through pending |
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

Chapter map reshaped 2026-07-31 for ADR-054's scope freeze, then extended
2026-08-09 with Measurement Validity as its own chapter (ch.6), giving the
twelve-chapter map below. All chapters and all six appendices are **drafted**
as of 2026-08-15 (supervisor-review fix plan applied; see
`docs/reviews/2026-08-15-first-supervisor-review.md`).

| Ch | Title | Status |
|---|---|---|
| 1 | Introduction | **Drafted** — statutes cited at the legal claims (#96 closed); Berghaus gap characterization corrected |
| 2 | Background | **Drafted** (2026-08-15) — VLM anatomy, e-invoicing law, KG vocabulary, evaluation foundations |
| 3 | Related Work | **Drafted** (2026-08-15) — incl. head-on Berghaus engagement + adaptation-literature anchor |
| 4 | System Design | **Drafted** — three-layer design; Layers 2–3 design-only |
| 5 | Methodology | **Drafted** — incl. accurate phone-scan channel description |
| 6 | Measurement Validity | **Drafted** — the instrument-validation chapter |
| 7 | Results | **Drafted** — reader-selection story retold on the correct instrument; McNemar test added; two-decomposition attribution |
| 8 | Implementation and Prototype | **Drafted** |
| 9 | Discussion | **Drafted** |
| 10 | Limitations and Future Work | **Drafted** |
| 11 | Conclusion | **Drafted** (2026-08-15) |
| — | Abstract | **Drafted** (2026-08-15, English-only) |
| A–F | Appendices | **Drafted** (2026-08-15): field registry (generated), hypothesis register, datasheet, abandoned metric record, AI-usage, reproducibility |

## 3. Content waves

- **Wave 1 (done, June)**: authoring setup + chapter skeletons + green build; first Introduction draft.
- **Wave 2 (done, 2026-07-31)**: rebase onto the landed endgame work; ADR renumber 054→055; formal-compliance fixes (part order, verbatim declaration, title-page data policy, contents-list spacing); chapter map reshaped to the frozen scope; Introduction rewritten. Build green (32 pp).
- **Wave 3 (done, 2026-08-09–14)**: full prose of Methodology, Measurement Validity, Results, System Design, Implementation, Discussion, Limitations; tables/figures generated from committed evidence.
- **Wave 4 (done, 2026-08-15)**: supervisor-review fix plan — evidential repairs (M1–M7), bibliography corrections, Background, Related Work, Conclusion, Abstract, all appendices, formatting pass.
- **Wave 5 (open)**: author read-through of the full PDF + supervisor confirmation of citation style; then submission build.
- **Writing model**: Claude Opus 5 at high/xhigh effort (per the ADR-055 amendment).

## 4. Open items

**Needs the author (cannot be resolved by Cascade):**

- **Read-through of the full PDF** — the author signs off every sentence before
  submission (the AI-usage appendix documents the drafting process; the
  declaration asserts the disclosure).
- Confirm citation style with the supervisor — the Richtlinie prescribes the
  short-reference ("Kurzbeleg") method and says the supervisor's own preference
  overrides; biblatex `alphabetic` is the current (valid) choice.
- Print, sign and date the statutory declaration in the submitted copies.

**Resolved this wave (2026-08-15):**

- Title-page values: filled 2026-08-09; verified complete in the review.
- Legal framing (#96): statutes now cited at the claims; framing verified
  against public sources in the review.
- Kurzfassung: deliberately omitted (author decision, English-only).
- Bibliography reconciliation: berghaus2025 (author+title+venue), cai2025
  (author+title+journal), kieval2025 (ICDAR), en16931 (CEN), fhwedelrichtlinie
  corrected; archival stubs updated to match.
- `[PENDING]` markers: none remain; every number is generated from committed
  evidence.
- #48 (OCR-free framing): the terminology note is in ch.1 §Scope.
