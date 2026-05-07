# docs/sources — Source Archive

All primary sources cited in HORUS artefacts (ADRs, brainstorm, PRD, thesis chapters) are archived here per `docs/decisions/ADR-002-source-archival.md`.

## Taxonomy

| Directory | Contents |
|---|---|
| `papers/` | Research papers — VLM / document-understanding / OCR-free / RAG / KG literature |
| `tools/` | Tool documentation snapshots — inference frameworks, parsing libs, vector stores, API layers |
| `datasets/` | Dataset cards + licence info — evaluation benchmarks, domain-specific corpora |
| `legal/` | Primary legal + regulatory sources — §203 StGB, BStBK FAQ, DSGVO Art. 32, EN 16931, GoBD |

## Stub format

Each source is a `.md` file with YAML frontmatter:

```yaml
---
source_url: "https://..."
source_title: "..."
source_author: "..."
source_date: "YYYY-MM-DD"       # publication date; "" if unknown
retrieved_date: "YYYY-MM-DD"    # date stub created / URL last verified
extracted_concepts: []
tags: []
archived_pdf: ""                # relative path to PDF if present; "" otherwise
status: stub                    # stub | clipped | archived
---
```

`status` lifecycle:
- `stub` — Cascade-authored placeholder; URL valid at `retrieved_date`
- `clipped` — Obsidian Web Clipper overwrote with full content
- `archived` — PDF also present at `archived_pdf` path

## Naming convention

`<author-last-name>-<year>-<2-3-keyword-slug>.md`

Examples: `hu-2024-docowl.md`, `bstbk-2026-berufsgeheimnis-faq.md`, `mlx-docs-2025.md`

## Obsidian Web Clipper integration

The frontmatter schema matches Obsidian Web Clipper's default output. Clip the same URL later → clipper overwrites the stub; `status` transitions from `stub` → `clipped`. No conflicts, no double-filing.

To clip: in Obsidian, use Web Clipper with output path set to `docs/sources/<type>/<slug>.md` (or rename after clipping).

## Vault promotion

Per cascade-system ADR-030 Posture B: `@vault-distill` can promote stubs to `~/Projects/obsidian/second-brain/wiki/sources/<type>/horus/<slug>.md` with `[[wikilinks]]` to extracted concepts. Opt-in; repo stub is authoritative.

## Archival trigger rule

`.windsurf/rules/horus-source-archival.md` — fires at `model_decision`; enforces "create stub at cite-time, no citation without stub on `main`."
