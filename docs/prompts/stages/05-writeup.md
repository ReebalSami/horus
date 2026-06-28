# 05 — Writeup phase (kickoff)

| Field | Value |
|---|---|
| **Phase** | 7/7 — `writeup` (per `.windsurf/phases.yaml`) |
| **Skill** | `@writeup` (forward-reference; not yet an L1 skill — authored manually for now) |
| **Milestone** | `submission-ready` |
| **Status** | Open — authoring in progress |
| **Date opened** | 2026-06-28 |
| **Scope** | Compile the master-thesis manuscript from the project's results. This doc is the phase's living index: it opens with the authoring setup (ADR-054) and tracks chapter status + content waves. |

> **Results-integrity caveat (inherited).** Every in-sample number from the
> experiment phase is **diagnostic, NOT real-world accuracy** (see
> `04-experiments.md` §"READ THIS FIRST"). The manuscript's headline results
> surface is the held-out Belege split + cloud comparison. No in-sample F1 may be
> cited as HORUS's real-world accuracy. Results enter the manuscript as
> **generated** figures/tables (never hand-copied), per ADR-054.

## 1. Authoring setup

- **Manuscript home**: `thesis/` (in-repo). Build: `make thesis` → `thesis/_build/main.pdf`.
- **Format / language**: LaTeX (FH Wedel KOMA/biblatex template adapted to English).
- **Decision record**: `docs/decisions/ADR-054-thesis-authoring-setup.md`.
- **Structure + conventions**: `thesis/README.md`.
- **Compliance**: the statutory declaration carries the AI-disclosure clause; AI-tool usage is documented in an appendix (FH Wedel Richtlinie).

## 2. Chapter status

| Ch | Title | Status | Basis |
|---|---|---|---|
| 1 | Introduction | Drafted | brainstorm v2 §7 (legal motivation), §2 (scope) |
| 2 | Background | Scaffolded | `docs/sources/` literature |
| 3 | Related Work | Scaffolded | berghaus-2025, cai-2025, han-2025 |
| 4 | Methodology | Scaffolded (a-priori locks) | brainstorm v2 §5/§6; ADR-035/040/041 |
| 5 | Layer 1: Extraction | Partial | ADR-009…038; `04-experiments.md` |
| 6 | Layer 2: Knowledge Graph | Stub (pending work) | — |
| 7 | Layer 3: Query | Stub (pending work) | — |
| 8 | System & Prototype | Partial | ADR-036/039 |
| 9 | Discussion | Stub | — |
| 10 | Conclusion | Stub | — |

## 3. Content waves

- **Wave 1 (this PR)**: authoring setup + chapter skeletons + green build; Introduction drafted.
- **Wave 2**: Background + Related Work + Methodology full drafts (all writable now from existing research + ADRs).
- **Wave 3**: Layer 1 (ch.5) from the experiment-phase record + held-out results as they land.
- **Wave 4+**: Layers 2/3 (ch.6/7) as that work completes; Discussion + Conclusion + Abstract last.

## 4. Open items

- Title-page placeholders (Matrikelnummer, address, email, second examiner) — `thesis/preamble/titlepage.tex`.
- Confirm citation style (template default biblatex `alphabetic`) + whether a German `Kurzfassung` is required.
- Verify the exact declaration + AI-clause wording against FH Wedel Richtlinie 3.0.
- Reconcile `thesis/references.bib` metadata against the verified `docs/sources/` stubs.
- Wire the figure/table generation pipeline (results → `thesis/figures` + `thesis/tables`).
