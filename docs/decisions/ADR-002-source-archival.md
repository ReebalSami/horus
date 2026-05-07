# ADR-002 — Source-Archival Convention

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-07 |
| **Milestone** | M2D.2 — Decision-discipline + source-archival setup |
| **Authored by** | Cascade D kickoff (`~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §3.2) |
| **Supersession trigger** | If HORUS adopts a dedicated reference-management tool (Zotero, JabRef) with its own repo-synced library, this convention is superseded by a Zotero-integration ADR that defines the new canonical archive location |

## Context

Every scientific claim in a master's thesis must be citable, retrievable, and verifiable — not just at submission time but for the entire shelf-life of the work. Three failure modes motivate a project-local archival convention:

1. **Link rot** — URLs to papers, tool docs, and legal texts become invalid. An archived copy in the repo survives link rot.
2. **Obsidian-sync dependency** — the author's Obsidian vault (`~/Projects/obsidian/second-brain/`) is private and non-reproducible by thesis reviewers. The repo must be self-contained for reproducibility audits.
3. **ADR-001 integration gap** — every HORUS tool/model/library/dataset decision ADR (per ADR-001) must cite its sources. Without a defined archival location, those citations have no stable landing point.

Additionally, the author uses Obsidian Web Clipper for clipping web pages to the vault. A repo-based stub format that matches the Obsidian-clipper frontmatter schema allows the clip to cleanly overwrite the stub, making the repo → vault bridge zero-friction.

## Decision

All sources cited in HORUS artefacts (ADRs, brainstorm, PRD, thesis chapters) are archived under `docs/sources/` in the HORUS repo under a four-way taxonomy:

```
docs/sources/
├── README.md           # this convention + Obsidian-clipper integration notes
├── papers/             # research papers (PDF link + markdown stub)
├── tools/              # tool-doc snapshots (one .md per tool)
├── datasets/           # dataset licence + docs (one .md per dataset)
└── legal/              # primary legal sources (§203 StGB, BStBK FAQ, DSGVO, EN 16931, …)
```

### Archive stub format

Each archived source is a markdown file with YAML frontmatter that matches the Obsidian Web Clipper output schema:

```yaml
---
source_url: "https://..."
source_title: "..."
source_author: "..."
source_date: "YYYY-MM-DD"        # publication date; "" if unknown
retrieved_date: "YYYY-MM-DD"     # date the stub was created / URL was valid
extracted_concepts: []           # filled by Obsidian-clipper or @vault-distill
tags: []                         # e.g. ["vlm", "ocr-free", "benchmark"]
archived_pdf: ""                 # relative path to PDF if downloaded; "" otherwise
status: stub                     # stub | clipped | archived
---

<!-- Body: paste abstract / key excerpt / summary here, or leave blank for Obsidian-clipper to fill -->
```

`status: stub` = Cascade-authored placeholder; `status: clipped` = Obsidian Web Clipper has overwritten with full content; `status: archived` = PDF also present.

### Naming convention

Filename: `<slug>.md` where `<slug>` is a kebab-case identifier derived from the primary author's last name + year + key term (e.g., `hu-2024-docowl`, `bstbk-2026-berufsgeheimnis-faq`, `zugferd-2023-standard`). No spaces, no special characters except `-`.

### Archival trigger

A source must be archived **at the time it is first cited** in any HORUS artefact. This means:
- When adding an option to `## Options considered` in a tool-decision ADR → archive the linked paper/doc
- When citing a legal source in the thesis brainstorm or PRD → archive the legal text
- When adopting a dataset → archive the dataset card / licence

The `## Source archival` section in every tool-decision ADR (ADR-001 §mandatory-sections) lists the repo-relative paths to the archived stubs for that ADR's cited sources.

## Workspace rule

Encoded in `.windsurf/rules/horus-source-archival.md` (workspace scope; auto-loads on Cascade activation under `~/Projects/horus/`).

## Obsidian vault bridge

Per cascade-system ADR-030 Posture B: each HORUS ADR also generates a vault card at `~/Projects/obsidian/second-brain/wiki/sources/adrs/horus/ADR-NNN.md` with `[[wikilinks]]` to extracted concepts/entities — this happens via `@vault-distill` post-ratification (opt-in, not blocking).

Each archived source stub can additionally be promoted to `wiki/sources/papers/horus/<slug>.md` (or analogous wiki sub-path) by `@vault-distill` when and if desired. The repo stub always remains authoritative; the vault card is a derived artefact.

## Consequences

- **Positive**: self-contained reproducibility (thesis reviewers can audit sources without vault access); clean Obsidian-clipper integration; ADR-001 `## Source archival` section has a defined landing point; link-rot resilient.
- **Negative**: small overhead per citation (create stub at cite-time). Mitigated by the stub template being a 10-line YAML header.
- **Neutral**: does not replace the Obsidian vault — supplements it. Vault remains the semantic-search + note-graph layer; repo is the reproducibility layer.

## Related ADRs

- ADR-001 — tool-decision discipline (the `## Source archival` mandatory section in every tool-decision ADR cites this convention)
- ADR-003 — brand naming (first ADR to archive sources under this convention)
