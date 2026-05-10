# AGENTS.md — HORUS

This is **HORUS** — *Hybrid OCR-free Reading & Understanding System*. Master's thesis project at FH Wedel (SS 2026): privacy-first document intelligence for German tax/accounting professionals (`Steuerberater` / `Wirtschaftsprüfer` / `Anwälte`) via local vision-language models. Documents stay inside the firm; the analyst keeps full audit-trail visibility.

## Start here

- `README.md` — top-level overview + `## Why HORUS?` (backronym, Egyptian-symbolism anchor, methodological mapping)
- `docs/structure.md` — universal docs layout (from `_shared/scaffold/`; per ADR-003 of the cascade-system meta-repo)
- `docs/decisions/INDEX.md` — Architectural Decision Records; highlight reading:
  - **ADR-001** — tool-decision discipline (every tool/model/library/dataset choice gets an ADR with `Current-state survey` / `Options` / `Decision + integration thoughts` / `Source archival` / `Supersession trigger` sections)
  - **ADR-002** — source-archival convention (every cited paper/tool-doc/dataset/legal-source is archived under `docs/sources/<type>/`)
  - **ADR-003** — brand-naming-horus ratification (HORUS chosen over vellum / hearth / aegis / codex)
  - …subsequent ADRs ratify each tool/model/library/dataset/framework choice (lifecycle: continuously)
- `docs/sources/` — archived primary sources (papers / tool docs / datasets / legal); see `docs/sources/README.md`
- `docs/prompts/stages/` — phase artifacts (`01-literature.md`, `02-brainstorm.md`, …) per the python-ml-uv phase chain
- `.windsurf/phases.yaml` — runtime source of truth for `/run-phase` (7-phase chain: `literature → brainstorm → spec → issues → experiment → implement → writeup`)

## Project-local rules (workspace scope; auto-load on Cascade activation)

In `.windsurf/rules/`:

- 18 global long-form rules copied from cascade-system (`document-as-you-go`, `context7-and-docs-first`, `adapt-from-all`, `branch-and-pr-required`, `clean-project-structure`, `make-sure-it-works`, `bidirectional-learning-pipe`, …)
- L3 (`python-ml-uv`) overrides: `notebook-discipline.md` (jupytext .py only, no .ipynb checked in), `uv-discipline.md` (uv exclusive; no pip/poetry/conda mixing)
- L2 (HORUS-specific):
  - `horus-decision-discipline.md` (ratified M2D.2) — tightens "significant decision" to **any** tool/model/library/dataset/framework choice; mandates the 5 ADR sections (Current-state survey / Options considered / Decision + integration thoughts / Source archival / Supersession trigger). See `docs/decisions/ADR-001-tool-decision-discipline.md`.
  - `horus-source-archival.md` (ratified M2D.2) — every cited source archived under `docs/sources/<type>/<slug>.md` with Obsidian-clipper-compatible frontmatter. See `docs/decisions/ADR-002-source-archival.md`.
  - `horus-config-discipline.md` (Bundle 1 ratified 2026-05-10; Bundle 2 closed 2026-05-10 via ADR-004 = pydantic-settings + pyyaml) — ALL experiment knobs (hyperparams / model IDs / dataset paths / seeds / batch sizes / learning rates / prompt strings / eval thresholds / MLflow tags) live in `configs/<experiment-slug>.yaml` files. `.py` files contain LOGIC + Pydantic schema (`src/horus/config.py` → `ExperimentConfig`) only. Experiments accept ONE papermill parameter `cfg_path`. Pydantic-validates-at-boot is the architectural forcing function (fails fast on missing/malformed YAML before any model loads). Pre-committed to L3 promotion at next `@sprint-review`. Canonical records: `cascade-system/docs/handoffs/cascade-d-master-thesis.md` §3.2 + `docs/decisions/ADR-004-config-library.md` + `configs/README.md`.

## How to start work

- **Resume / continue** an existing phase → `/run-phase <name>` from a Cascade conversation in this directory; reads `.windsurf/phases.yaml`, runs pre/post checks, invokes the phase's skill
- **No-arg** `/run-phase` → lists current phases with artifact status (which are open, which are closed)
- **Vertical pickup from a handoff doc** → `@kickoff <handoff-path>` (typically `cascade-system/docs/handoffs/<cascade-id>-<scope>.md`); reads handoff + parent plan + cited ADRs, asks ONE focused starting question

## Adding or modifying anything in this project

- **New tool/model/library/dataset/framework decision** → author an ADR in `docs/decisions/ADR-NNN-<slug>.md` (number reserved in `INDEX.md` first per ADR-009 of cascade-system) with the 5 mandatory sections per `horus-decision-discipline.md`. Cite the source(s) and archive them per `horus-source-archival.md`. **Never** silently introduce a new dependency in `pyproject.toml` without a corresponding ADR.
- **New rule / skill / workflow / contract / template** → route through `@propose-extension` (per ADR-017 of cascade-system; intake channel for any artifact addition or modification, at L1, L2, or L3)
- **Source citation in any artifact** → archive the source under `docs/sources/<type>/<slug>.md` per `horus-source-archival.md`. The stub frontmatter shape matches Obsidian-web-clipper output so a later clip overwrites the stub atomically.

## Landing changes

Route through `@release-manager` (cascade-system ADR-018). The skill owns the branch → commits → push → PR → CI → squash-merge → cleanup lifecycle, delegating to 4 helper workflows (`/branch-start`, `/branch-push-and-pr`, `/ci-watch`, `/branch-merge-and-cleanup`). **Never** `git push origin main` directly. The cold-start exception (initial commit immediately after `gh repo create`) was used once for M2D.0 and is closed.

## Sprint rhythm

Phase milestones (from `phases.yaml`) close → `sprint-review-prompt` rule fires → invoke `@sprint-review` → drain project-local retros → approved L1/L3 promotions hand off to `@update-horizontal` → retro closes with clean working tree.

Kickoff plan: `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` (Cascade D, Sprint 2).

Handoff context: `cascade-system/docs/handoffs/cascade-d-master-thesis.md`.

## Toolchain (Python ML / research)

- Python 3.14+ (pinned in `.python-version`)
- `uv` (Astral) — exclusive package manager
- Runtime: `pydantic` / `pydantic-settings` / `pyyaml` / `torch` — pinned in `pyproject.toml` `[project] dependencies`
- Dev: `pytest` / `ruff` / `mypy` / `jupytext` / `papermill` / `types-pyyaml` — pinned in `pyproject.toml` `[dependency-groups] dev`
- `make install && make test` — bootstrap validation (must always pass before merge)
- `make experiment NB=experiments/<slug>.py CFG=configs/<slug>.yaml` — single-cfg-path experiment runner per `horus-config-discipline`

## Pre-loaded thesis context (read-only)

- `/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/research/THESIS_BRAINSTORM_STATE_v2.md` — locked v2 thesis brainstorm (input to M2D.4 `/run-phase brainstorm`); §7 = critical research findings + §15 = bibliography (imported to `docs/sources/papers/` at M2D.3)
- Same dir: `THESIS_BRAINSTORM_STATE.md` (v1, superseded) + `THESIS_OVERVIEW.md` (2026-04-16, fully superseded — see v2 §13 "Roast"). Retained per ADR-011 supersession-over-deletion.
