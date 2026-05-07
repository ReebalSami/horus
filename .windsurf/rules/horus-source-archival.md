---
trigger: model_decision
description: In the HORUS thesis project, every source cited in any artefact (ADR, brainstorm, PRD, thesis chapter) must be archived under `docs/sources/<type>/<slug>.md` with Obsidian-clipper-compatible frontmatter at the time of citation. Ratified in `docs/decisions/ADR-002-source-archival.md`.
sources_consulted:
  - ~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md §3.2 (own) — interview content that defines this rule
  - cascade-system/docs/decisions/ADR-030 (own) — ADR↔vault posture; Posture B applies here
  - THESIS_BRAINSTORM_STATE_v2.md §7 + §15 (own) — bibliography as first archival input at M2D.3
adapted_for:
  - L2 workspace rule — HORUS project only; lives at `~/Projects/horus/.windsurf/rules/horus-source-archival.md`
  - `model_decision` trigger — fires when a citation, source reference, or "according to paper X" language surfaces
  - Complements `horus-decision-discipline.md`; the `## Source archival` section in every tool-decision ADR is the primary invocation point
---

# horus-source-archival (L2, HORUS thesis)

> **CONSTRAINT**: In the HORUS project, every source you cite anywhere — paper, tool doc, dataset card, legal text — must have a corresponding stub archived under `docs/sources/<type>/<slug>.md` at the time of citation. Do not cite and not archive.

## Taxonomy

| Type | Directory | Examples |
|---|---|---|
| Research paper | `docs/sources/papers/` | VLM survey papers, OCR-free benchmarks, document-understanding datasets, RAG/KG papers |
| Tool documentation | `docs/sources/tools/` | MLX docs, Granite-Docling, olmOCR-2, Docling, LightRAG, Qdrant, FastAPI, … |
| Dataset | `docs/sources/datasets/` | ZUGFeRD corpus, CORD-v2, SROIE, FUNSD, OmniDocBench, inv-cdip, GI 2021 |
| Legal / regulatory | `docs/sources/legal/` | §203 StGB, §62a StBerG, BStBK FAQ 2026, DSGVO Art. 32, EN 16931, GoBD |

## Stub format

Create a file at `docs/sources/<type>/<slug>.md` with this frontmatter:

```yaml
---
source_url: "https://..."
source_title: "..."
source_author: "..."
source_date: "YYYY-MM-DD"       # publication date; "" if unknown
retrieved_date: "YYYY-MM-DD"    # TODAY (date the stub is created)
extracted_concepts: []          # filled later by Obsidian-clipper or @vault-distill
tags: []                        # e.g. ["vlm", "ocr-free", "benchmark", "legal"]
archived_pdf: ""                # relative path to PDF if downloaded; "" otherwise
status: stub                    # stub | clipped | archived
---

<!-- paste abstract / key excerpt / one-paragraph summary here -->
```

## Naming convention

`<author-last-name>-<year>-<2-3-keyword-slug>.md`

Examples:
- `hu-2024-docowl.md` (DocOwl paper by Hu et al. 2024)
- `bstbk-2026-berufsgeheimnis-faq.md`
- `zugferd-2023-en16931.md`
- `wei-2024-olmocr2.md`

For tools without a single paper: `<tool-name>-docs-<year>.md` (e.g., `mlx-docs-2024.md`).

## When to create a stub

Create the stub at the moment you first write the citation — not after. This applies to:
- Adding an item to `## Options considered` in a tool-decision ADR → create a stub for every linked paper/doc
- Mentioning a dataset in any artefact → create a stub under `docs/sources/datasets/`
- Citing a legal source in brainstorm, PRD, or thesis chapter → create a stub under `docs/sources/legal/`
- Referencing a tool in `pyproject.toml` or a new `import` → create a stub under `docs/sources/tools/`

## Obsidian-clipper integration

The frontmatter schema matches Obsidian Web Clipper's default output. When the author later clips the same URL via Obsidian Web Clipper:
- If the stub exists: the clipper overwrites the stub cleanly (frontmatter merge + body replacement); `status` changes from `stub` to `clipped`
- No double-filing; no conflicts

## Vault promotion (opt-in, not blocking)

Per cascade-system ADR-030 Posture B: `@vault-distill` can promote archived source stubs to `~/Projects/obsidian/second-brain/wiki/sources/<type>/horus/<slug>.md` with `[[wikilinks]]` to extracted concepts. This is opt-in; the repo stub is always authoritative.

## Checking at milestone reviews

At each phase-milestone PR review: does the PR cite any paper, tool, dataset, or legal text that doesn't have a corresponding stub in `docs/sources/`? If yes, add the missing stubs before merge. No citation without a stub lands on `main`.
