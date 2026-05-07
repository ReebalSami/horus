---
trigger: model_decision
description: In the HORUS thesis project, EVERY tool/model/library/dataset/framework/hosting choice is a "significant decision" requiring a numbered ADR with 5 mandatory sections. Tightens the global `document-as-you-go` rule for scientific correctness. Ratified in `docs/decisions/ADR-001-tool-decision-discipline.md`.
sources_consulted:
  - ~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md §3.1 (own) — interview content that defines this rule
  - cascade-system/docs/rules/document-as-you-go.md (own) — global rule being tightened
  - THESIS_BRAINSTORM_STATE_v2.md §4.1 (own) — "scientific-correctness discipline" locked-a-priori commitment
  - cascade-system/docs/decisions/ADR-009 (own) — reserve-NNN-before-authoring convention
adapted_for:
  - L2 workspace rule — HORUS project only; lives at `~/Projects/horus/.windsurf/rules/horus-decision-discipline.md`
  - `model_decision` trigger — fires when a tool/model/library/dataset/framework/hosting choice surfaces; not always-on to preserve context budget
  - Extends, does not replace, the global `document-as-you-go` rule (which is always_on)
---

# horus-decision-discipline (L2, HORUS thesis)

> **CONSTRAINT**: In the HORUS project, *every* tool / model / library / dataset / framework / hosting choice requires a numbered ADR. The global `document-as-you-go` "significant decision" bar does not apply here — **every choice is significant**.

## What triggers this rule

Any time a decision is being made about:
- Which VLM / OCR / parsing / embedding / reranking model to use
- Which Python library or framework to adopt (`torch`, `transformers`, `mlx`, `langchain`, `llamaindex`, `neo4j`, `qdrant`, `fastapi`, `streamlit`, …)
- Which dataset(s) to use or evaluate against
- Which hosting / inference approach (local CPU, MPS, GGUF, API, Docker, …)
- Any other tooling or framework choice with a non-trivial alternative

## Steps you must follow

1. **Reserve the ADR number** in `docs/decisions/INDEX.md` before authoring the file (per ADR-009 of cascade-system). Add a row with `Status: Proposed`.
2. **Author `docs/decisions/ADR-NNN-<slug>.md`** with the standard header table PLUS the 5 mandatory sections below.
3. **Update INDEX.md** status to `Accepted` once the ADR is complete and added to a commit.

## The 5 mandatory sections

Every tool-decision ADR in HORUS **must** contain these sections, in this order:

### `## Current-state survey`
- Dated (YYYY-MM-DD = today) web-search + `context7` MCP findings for the decision space.
- The query `mcp2_resolve-library-id` + `mcp2_query-docs` must be called for any library/framework choice before authoring the Options section.
- Minimum 2–3 sentences of findings. Must be authored on the date of decision — not backdated.

### `## Options considered`
- Table or list with: candidate name | paper/repo/docs link | one-line why-considered | one-line why-not-chosen.
- Minimum 2 options (chosen + at least 1 evaluated alternative).
- Every item cited here must have a corresponding stub in `docs/sources/` per `horus-source-archival` rule.

### `## Decision + integration thoughts`
- *What* was chosen AND *how it fits the bigger HORUS puzzle*.
- Must address: interaction with already-decided components (reference their ADRs); forward-compatibility with `experiment`/`implement`/`writeup` phases; known limitations that become hypotheses or risk items.

### `## Source archival`
- Repo-relative paths to `docs/sources/<type>/<slug>.md` stubs for every item cited in `## Options considered`.
- If no sources needed (e.g., a pure naming ADR like ADR-003), explicitly state: *"No `docs/sources/` stubs required for this ADR."*

### `## Supersession trigger`
- Pre-commitment: "This ADR is superseded if [specific evidence criterion]."
- Must be concrete and falsifiable (not "if something better comes along").

## Gate at phase-milestone reviews

At each phase-milestone PR review (before squash-merge), check: does the PR introduce any new dependency in `pyproject.toml`, any new import in `src/horus/`, or any new tool/model/dataset in `experiments/`? If yes, the corresponding ADR must be present in the same PR or in a preceding merged PR. No tool without an ADR lands on `main`.
