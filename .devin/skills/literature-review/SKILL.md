---
name: literature-review
description: Survey relevant prior work for a Python ML / research project: vault-resident notes (via `@vault-research`) + external papers (arxiv via huggingface `mcp4_paper_search`, plus general web search) + IMRAD-style per-source deep-read; produces `docs/prompts/stages/01-literature.md` ready to feed the `brainstorm` phase. Domain-agnostic across thesis, paper repro, Kaggle baselines, RL, vision, NLP, and LLM eval consumers.
activation: auto
phase: literature
produces_artifacts:
  - docs/prompts/stages/01-literature.md
requires_skills:
  - vault-research
sources_consulted:
  - ~/.codeium/windsurf/skills/vault-research/SKILL.md (own, L1) — adopted as-is for the vault-prior-art portion (READ bookend per ADR-024)
  - ~/.codeium/windsurf/skills/grill-me/SKILL.md (own, L1) — interview-discipline pattern (one focused question per turn) adopted for the triage step
  - refs/claude-skills/product-team/research-summarizer/SKILL.md (browsed, MIT) — IMRAD per-paper structure (Introduction / Methods / Results / Discussion) adopted for step 5 deep-read; broader workflow not adopted (different domain, single-source focus)
  - huggingface MCP `mcp4_paper_search` (tool, browsed) — arxiv + HF papers semantic search adopted for step 3 external-paper sweep
  - cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md (own) — B6=A spec for this skill
  - cascade-system/docs/decisions/ADR-006-skill-frontmatter-schema.md (own) — frontmatter schema
  - cascade-system/docs/decisions/ADR-024-vault-research-skill.md (own) — @vault-research rationale informing the composition relationship
adapted_for:
  - L3 placement at ~/.windsurf/templates/python-ml-uv/skills/literature-review/SKILL.md (deployed to consumer projects via /start-project step 6b)
  - python-ml-uv phases.yaml `literature` phase (terminal artifact: docs/prompts/stages/01-literature.md)
  - Domain-agnostic ML / research projects per handoff §9 (passes acceptance test for thesis, Kaggle, LLM-eval, vision, RL alike)
  - Composition over reinvention: wraps @vault-research for vault portion; adds external-source flow on top
  - Generic citation format (vault `[[wikilinks]]` + arxiv IDs + DOIs); consumer chooses bibtex / CSL at the `writeup` phase
---

# @literature-review — survey prior work for a Python ML / research project

Discrete invocable capability that produces a structured literature artifact from a unified vault + external corpus, IMRAD-deep-read on the user's selection, theme + gap synthesis, and a ready-to-cite source list.

## When to use

- `/run-phase literature` in a python-ml-uv consumer project (the canonical entry point per `phases.yaml`)
- Standalone — user asks *"what's the prior art on X?"* in a python-ml-uv project context
- Re-running mid-project to refresh the corpus when scope drifts (re-read at `/recalibrate`)

## Hard gate

Refuse to proceed if **any** of:

- Project's `your_pkg/` placeholder is unrenamed (per the M2B.3 queue entry — bootstrap is incomplete; route the user to the rename step before doing real work)
- No topic provided AND project's `README.md` doesn't yield a 1-line scope (literature without a topic is theatrical)
- More than 7 sources requested for deep-read (no-quantity-over-shape; user must narrow to ≤7)

## Procedure

### 1 — Verify scope

Ask one focused question (per `@grill-me` discipline):

```
What's the literature scope? (1–2 sentences. Concrete enough to filter
search hits — "graph neural networks for fraud detection" beats
"machine learning".)
```

If the project's `README.md` already contains a clear scope statement, surface it and confirm before asking.

### 2 — Vault sweep (delegate to `@vault-research`)

Invoke `@vault-research <topic>` per ADR-024. Returns 3–7 ranked vault notes with reasoning (composite recency × tag-overlap × MOC-distance). If `@vault-research` returns "vault is cold on this topic", proceed external-only; do not error.

Capture: list of `[[wikilinks]]` with composite scores + 1-line summaries.

### 3 — External sweep (arxiv + web)

Two parallel queries:

- **arxiv / HF papers**: `mcp4_paper_search query=<topic-as-query> results_limit=12`. Returns arxiv-tagged papers ranked by HF Papers' indexer. Filter to ≤8 most relevant by title + abstract.
- **General web**: `search_web query="<topic> review OR survey OR benchmark"` for non-arxiv sources (workshop papers, blog write-ups, OpenReview, Semantic Scholar pages). Cap at 5 hits; only follow links the user explicitly asks to deep-read.

Substantial threshold: if both queries return zero hits AND vault was cold, surface *"Literature is cold on `<topic>`; proceeding to brainstorm with no prior art is acceptable per the brainstorm B5=A `literature` phase trivial-close pattern. Confirm to proceed?"*. User confirms → write a 1-paragraph "no relevant prior art" artifact and exit cleanly.

### 4 — Triage (one focused interview turn)

Present the unified candidate pool in three sections — `VAULT` (wikilinks + composite score + reasoning per `@vault-research` step 6), `ARXIV / HF PAPERS` (title + year + arxiv ID + 2-sentence summary), `WEB` (title + URL + 1-line note). Order: vault → arxiv → web.

Ask the user to pick 3–7 sources for deep-read (vault wikilinks / arxiv IDs / URLs). Validate count; refuse outside the range.

### 5 — Deep-read each picked source (IMRAD per source)

For each picked source, read fully and extract an IMRAD-style summary:

- **I**ntroduction — what problem does the source address? Why does it matter?
- **M**ethods — what approach / dataset / model / experiment design?
- **R**esults — what did they find? Effect sizes / benchmarks / qualitative observations?
- **D**iscussion — what limitations do the authors flag? What gaps remain?

Vault sources: `obsidian read <wikilink>` for full content (CLI-preferred per ADR-022). External sources: `read_url_content` per the URL or arxiv abstract page. For arxiv-only papers without freely available PDFs, abstract + linked HF page suffice; flag "abstract-only deep-read" in the artifact.

Adapted from `refs/claude-skills/product-team/research-summarizer/SKILL.md` (IMRAD shape; the rest of that skill's product-research framing is browsed-only).

### 6 — Synthesize themes + gaps

Group the deep-read summaries by emergent theme (e.g., "GNN architecture variants", "training-stability tricks", "evaluation methodology critiques"). For each theme, identify:

- **Consensus** — what do most sources agree on?
- **Contradictions** — where do sources disagree, and what's the basis?
- **Gaps** — what's notably absent (no source addresses X) or weakly addressed?

The gap statement is the bridge to `brainstorm` — it tells the next phase what's worth designing for.

### 7 — Author artifact

Write `docs/prompts/stages/01-literature.md` with these sections:

- **Header** — `# Literature review — <topic>`; metadata block (Phase / Status / Date / Scope)
- **Methodology** — counts per source channel (vault / arxiv / web) + deep-read count P (3 ≤ P ≤ 7)
- **Sources** — three sub-sections (Vault `[[wikilinks]]`, Papers with arxiv IDs / DOIs, Web URLs); 1-line summary per source
- **Findings by theme** — one sub-section per theme; each carries Consensus / Contradictions / Gaps bullets
- **Gap statement (bridge to brainstorm)** — 1–3 paragraphs identifying what's worth designing for
- **Citation format note** — `[[wikilinks]]` for vault + arxiv IDs + DOIs; `writeup` phase converts to bibtex / CSL per consumer choice

Initial `Status: draft`; flips to `approved` at step 8.

### 8 — User-approval gate (mirrors `@to-prd` + `@grill-me` step 9)

Present the artifact. User edits / approves. Status flips from `draft` to `approved`. Don't auto-proceed to `brainstorm` — `@grill-me` is invoked separately by the user (or by `/run-phase brainstorm`).

## Anti-patterns

- **Auto-incorporating top results without user triage** — mirrors `@vault-research`; this skill's job is *surface, reason, deep-read on user pick, synthesize*, not *decide*.
- **Citing without reading** — every source in the artifact must have a real IMRAD-style summary; abstract-only deep-reads must be flagged as such.
- **Domain-specific framing** — must NOT bias toward any ML domain; the artifact's findings shape themselves around the user's topic, not around thesis / Kaggle / RL pre-conceptions.
- **Skipping the substantial-threshold gate** — fabricating literature for a cold topic is worse than honestly closing the phase as "no relevant prior art".
- **Returning >7 deep-read sources** — clamp is a discipline (per `no-quantity-over-shape`).
- **Treating `@vault-research` failure as fatal** — vault may not be configured; external-only mode is valid.

## Termination

`@literature-review` ends when:

- `docs/prompts/stages/01-literature.md` exists, status = `approved`, 3–7 deep-reads with IMRAD summaries + theme + gap statements. **Or**
- Substantial-threshold gate failed → 1-paragraph "no relevant prior art" artifact written + status = `approved`. **Or**
- User cancels at any focused-question gate → no artifact written.

## Provenance

See frontmatter `sources_consulted`. Spec: `cascade-system/docs/prompts/stages/02-brainstorm-python-ml-uv.md` §B6=A. Issue: M2B.4 (`ReebalSami/cascade-system#78`). Pairs with `@run-experiment` (sibling L3 skill, M2B.4 second deliverable). Composes `@vault-research` (L1) for vault portion per ADR-024.
