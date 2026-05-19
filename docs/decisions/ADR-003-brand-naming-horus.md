# ADR-003 — Brand Naming: HORUS

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-07 |
| **Milestone** | M2D.2 — Decision-discipline + source-archival setup |
| **Authored by** | Cascade D kickoff (`~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §1) |
| **Supersession trigger** | If the thesis is commercialised or open-sourced post-defence and a trademark conflict with "HORUS" is discovered, supersede with a new naming ADR |

## Context

The project required a stable, memorable slug that would serve as:
- The local directory name (`~/Projects/horus/`)
- The GitHub repository name (`ReebalSami/horus`)
- The Python package name (`import horus`)
- The stylised brand in the thesis title page, defence slides, and any demo artefacts

The working thesis title is long (*Berufsgeheimnis-konforme Dokumentenintelligenz: Lokale Vision-Language-Modelle für die Verarbeitung deutscher B2B-Rechnungen und Belege*) and unsuitable as a slug. A separate brand name was needed that is:
1. Short (≤8 characters preferred)
2. English (package/repo conventions)
3. Creative and memorable (not a descriptive taxonomy of the scope)
4. Grounded in the service itself, not in details like the domain or methodology label

## Current-state survey

*Date: 2026-05-07.*

Evaluated approaches:
- Descriptive (scope-first): `berufsgeheimnis-doc-ai`, `lokale-dokumentenintelligenz`, `docintel-de` — all encode too many domain specifics; fragile under methodology pivots
- Research-axis (technique-first): `thesis-doc-kg` — encodes the KG layer which may be de-emphasised; poor if pivot happens
- Creative (product-brand): single-word evocative names — evaluated four candidates (see Options below)

No trademark or PyPI conflicts found for "HORUS" in the target domain at evaluation date. OpenAI's "Codex" (a rejected candidate) is dormant but still brand-associated with OpenAI, confirming it was right to avoid.

## Options considered

| Candidate | Angle | Why not chosen |
|---|---|---|
| `vellum` | Heritage + privacy (parchment + Latin *velum* = veil) | Beautiful but no backronym; the "veil" metaphor implies hiding/obscuring rather than *seeing*; misaligns with the VLM-first "see holistically" commitment |
| `hearth` | On-premise + trust (stays at home; §203 "stays at the firm") | Evokes warmth/domesticity rather than intelligence/perception; no expansion or acronym; German *Herd* = stove, doesn't carry the same weight |
| `aegis` | Protection + shield (Greek mythology; "under the aegis of") | Strong privacy framing but no document/vision angle; could fit any compliance-focused product; not distinctive for this project |
| `codex` | Structured knowledge (classical manuscript; root of "code" + "codification") | Compelling but dormant-brand-associated with OpenAI Codex; risks confusion in AI circles |
| **`horus`** | Vision + perception (Egyptian mythology; **HORUS** backronym) | **Chosen — see Decision** |

## Decision + integration thoughts

**Chosen name**: **HORUS** — *Hybrid OCR-free Reading & Understanding System*

**Symbolic anchor**: Horus is the Egyptian falcon-headed god of vision and kingship. The **Eye of Horus** (*wedjat*) is one of antiquity's most enduring symbols of perception, protection, and restoration. The mythology maps directly to the central methodological commitment of this thesis:

- Falcon-headed god = the system that *sees* documents
- "Eye of Horus" = the VLM's holistic visual-language understanding (no OCR transcription step; the model processes the raw document image directly)
- "Vision and kingship" = the system is authoritative about what it sees (structured extraction, not guesswork)

**Backronym**: **H**ybrid **O**CR-free **R**eading & **U**nderstanding **S**ystem
- *Hybrid* — combines visual (VLM) and linguistic (LM) understanding; optionally augmented with a knowledge graph layer
- *OCR-free* — the central architectural differentiator; documents are processed as images, not transcribed text
- *Reading* — the perceptual/extraction layer
- *Understanding* — the structured-output / knowledge-graph layer
- *System* — complete end-to-end pipeline, not a library or model

**Integration fit**:
- The name is agnostic to single-shot vs. orchestrated pipeline (brainstorm v2 §0 "still open to revision"), to VLM choice (olmOCR-2 / Granite-Docling / LLaVA-Next / etc.), and to graph storage backend (Neo4j vs. NetworkX vs. in-memory) — name survives all foreseeable pivots
- `horus` as a Python package name: no kebab/snake split needed (`horus` = both); clean import story (`import horus`, `from horus.config import Config`)
- GitHub repo `ReebalSami/horus`: short URL, unambiguous, no disambiguation suffix needed

**Forward-compatibility**: the name will appear on the thesis title page ("HORUS: Hybrid OCR-free Reading & Understanding System"), the defence slides, any demo artefacts, and the project's GitHub README. It is robust to future publication of the thesis (e.g., as a journal paper or open-source release) since it does not encode the university, the semester, or the narrow domain.

## Source archival

No external sources cited in this ADR (naming decision; primary inputs were the kickoff conversation on 2026-05-07, the brainstorm v2 §0–§3 for methodology context, and a trademark/PyPI availability scan).

*No `docs/sources/` stubs required for this ADR.*

## Supersession trigger

This ADR is superseded if:
- A trademark conflict with "HORUS" is discovered in the target domain (document-intelligence or professional-services software)
- The thesis is commercialised/open-sourced post-defence and a rename is required for brand or legal reasons

In either case, a superseding ADR-NNN-brand-naming-v2.md is authored; this ADR is updated to `Superseded by ADR-NNN`.

## Consequences

- **Positive**: memorable, short, defensible brand; backronym documents the methodology in the name itself; Egyptian symbolism anchors the VLM-first architectural commitment in a way that sticks.
- **Negative**: requires explaining the backronym to non-technical audiences (supervisor, thesis committee). Mitigated by the `## Why HORUS?` section in `README.md` and this ADR being linkable from the thesis text.
- **Neutral**: no impact on Python package structure, GitHub hosting, or CI/CD tooling.

## Related ADRs

- ADR-001 — tool-decision discipline (this ADR was the first to exercise the new ADR shape; the mandatory sections above serve as a template for subsequent tool-decision ADRs)
- ADR-002 — source-archival convention (no sources archived for this ADR, as noted in `## Source archival`)
