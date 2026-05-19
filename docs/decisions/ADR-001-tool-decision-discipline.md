# ADR-001 — Tool-Decision Discipline

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-07 |
| **Milestone** | M2D.2 — Decision-discipline + source-archival setup |
| **Authored by** | Cascade D kickoff (`~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §3.1) |
| **Supersession trigger** | If the thesis evolves into a commercial/open-source project and ADR volume becomes unsustainable, this rule can be relaxed to the global `document-as-you-go` default via a superseding ADR |

## Context

The global cascade-system rule `document-as-you-go` requires an ADR at the time of "significant decisions." Its default bar — cross-cutting architectural choices — is too coarse for a thesis. A master's thesis is a scientific artefact; every tool/model/library/dataset/framework choice carries methodological weight. Future reviewers (supervisor, thesis committee, peer researchers) need a traceable rationale chain, not just working code.

Additionally, the thesis context introduces two failure modes the global rule doesn't address:
1. **Integration-fit blind spot** — choosing a tool that solves the immediate next step but is incompatible with the downstream pipeline (e.g., picking a VLM that doesn't support structured output needed for knowledge-graph extraction).
2. **Current-state decay** — ML tooling moves fast; a choice ratified without a dated web-survey becomes scientifically undefended within months.

The brainstorm v2 §4.1 explicitly lists "scientific-correctness discipline" as a locked-a-priori commitment. This ADR is the operational encoding of that commitment.

## Decision

Every **tool / model / library / dataset / framework / hosting** choice in the HORUS project constitutes a "significant decision" and requires a numbered ADR in `docs/decisions/ADR-NNN-<slug>.md`, numbered reserved in `docs/decisions/INDEX.md` first (per `document-as-you-go` + ADR-009 of cascade-system).

Each such ADR **must** contain the following sections, in addition to the standard `Context` / `Decision` / `Consequences` shape:

### Mandatory ADR sections for HORUS tool/model/library/dataset decisions

#### `## Current-state survey`

Dated (YYYY-MM-DD) web-search findings for the decision space. Must be authored on the date of the decision — not backdated. Should cite `context7` MCP outputs when applicable (e.g., for library/framework choices). Purpose: provide a time-stamped snapshot that defends "we considered what was available at that moment." Even if the thesis pre-dates a better tool, the ADR's survey explains why.

#### `## Options considered`

A table or list of every considered alternative, each with:
- Link to paper / repo / docs / official site
- One-line "why considered"
- One-line "why not chosen" (or "chosen — see Decision")

Minimum 2 options required (the chosen one + at least 1 evaluated alternative). If no meaningful alternative exists, justify it in this section.

#### `## Decision + integration thoughts`

Not just *what* was chosen, but *how it fits the bigger HORUS puzzle*. Required content:
- How this component interacts with already-decided components (reference their ADRs)
- Forward-compatibility with downstream phases: does this choice create constraints for `experiment` / `implement` / `writeup` phases?
- Known limitations that will need mitigation (these become `experiment` phase hypotheses or `implement` phase risk items)

Purpose: prevents tunnel-vision on the current phase; forces the Socratic "not just next step" check from the brainstorm v2.

#### `## Source archival`

Repo-relative paths to archived sources for every item cited in `## Options considered`:
- Papers → `docs/sources/papers/<slug>.md`
- Tool docs → `docs/sources/tools/<slug>.md`
- Datasets → `docs/sources/datasets/<slug>.md`
- Legal sources → `docs/sources/legal/<slug>.md`

Per ADR-002 source-archival convention. Archival stub must exist at time of ADR ratification; Obsidian-web-clipper overwrites the stub later.

#### `## Supersession trigger`

A pre-commitment in the form: "This ADR is superseded if [specific evidence criterion is met]." Examples:
- "Superseded if a VLM with ≥5pp better accuracy on OmniDocBench is released under an Apache-2 licence before submission."
- "Superseded if MLX adds native bf16 GGUF quantisation support before the `experiment` phase milestone."

Purpose: scientific correctness per brainstorm v2 §4.1 (locked-a-priori commitments should be explicit about what would invalidate them).

## Workspace rule

Encoded in `.windsurf/rules/horus-decision-discipline.md` (workspace scope; auto-loads on Cascade activation under `~/Projects/horus/`). The rule fires at `trigger: model_decision` and also acts as a checklist gate at phase-milestone reviews.

## Integration with phases

| Phase | How this ADR fires |
|---|---|
| `literature` | Each model/tool/dataset surveyed → stub ADR if it becomes a candidate; full ADR when adopted |
| `experiment` | Every model / tool tried → full ADR with `Current-state survey` + `Integration thoughts` **before** `make test` validates the choice |
| `implement` | Every stack choice (inference server, API layer, graph DB, embedding model, …) → full ADR |
| `writeup` | Thesis chapters cite ADRs by path; supersession chain = the thesis's own audit trail (supervisor criterion) |

## Consequences

- **Positive**: complete traceable rationale for every significant choice; defends scientific correctness at thesis review; prevents integration-blind decisions.
- **Negative**: overhead per decision. Mitigated by the fact that HORUS has a bounded scope (single model pipeline + single data domain) — ADR count should stay in the 15–30 range across all phases.
- **Neutral**: extends, not replaces, the global `document-as-you-go` rule. No cascade-system artifact is modified.

## Related ADRs

- ADR-002 — source-archival convention (the `## Source archival` section of every tool-decision ADR references it)
- ADR-003 — brand naming (first ADR to use this discipline)
- cascade-system `document-as-you-go` rule (global; this ADR tightens it project-locally)
