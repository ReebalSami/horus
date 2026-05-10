# HORUS — Brainstorm

| Field | Value |
|---|---|
| **Phase** | `brainstorm` (M2D.4) |
| **Phase set** | `python-ml-uv` |
| **Status** | Approved |
| **Date** | 2026-05-08 |
| **Source** | `THESIS_BRAINSTORM_STATE_v2.md` (locked 2026-05-06, revision 2; user + Claude Opus 4.7) imported into the Cascade flow at M2D.3 (literature) + M2D.4 (this brainstorm) |

## 1 — Working direction

HORUS investigates how well current open-source local document VLMs handle the German B2B accounting workflow end-to-end (extraction → knowledge graph → analytical querying), and characterises where compliance-aware reasoning over an automatically constructed knowledge graph beats flat vector retrieval. Three layers: doc-VLM → KG → analytical query. Local-first inference (Apple Silicon / MLX as primary path). EU-hosted cloud baselines as honest comparators. German-specific compliance metric (§14 UStG / §33 UStDV) as the discriminating axis.

Full directional detail in v2 §0–§14.

## 2 — Discipline commitments (governing HOW we decide, not WHAT)

- **No HARKing** (per Kerr 1998 — `docs/sources/papers/kerr-1998-harking.md`). Hypotheses, scope, metric design, held-out test set freeze decided BEFORE seeing test data; reported as found, not retrofitted.
- **Branches on results, not on plans** (v2 §4.2). Implementation-phase architectural choices decided AT EACH STEP on evidence, not pre-committed at brainstorm phase.
- **ADR at every decision** (per `~/Projects/horus/.windsurf/rules/horus-decision-discipline.md` + `docs/decisions/ADR-001-tool-decision-discipline.md`). Every tool / model / library / dataset / framework / backend choice → 5-section ADR (current-state survey, options considered, decision + integration thoughts, source archival, supersession trigger). Authored at decision time, merged with the PR that introduces the dependency.
- **Source archival at citation time** (per `horus-source-archival.md` + ADR-002). Every external paper / tool / dataset / legal source cited anywhere → archived under `docs/sources/{papers,tools,datasets,legal}/<slug>.md` at first citation.
- **Scientific correctness over speed** (Säring's stated criterion, v2 §0 lock #9). Reproducibility, deterministic experiments, MLflow tracking, no p-hacking, no test-set contamination.

## 3 — Working assumptions (NOT locked — direction only)

The 11 v2 §0 markers and 11 v2 §3 decisions (D1–D11) are imported as the WORKING DIRECTION. None hard-locked at brainstorm phase. Any may be revised on:

- Pilot evidence (via `horus-decision-discipline` ADRs at implementation-phase)
- Säring sign-off at first technical-progress meeting (the §4.1 a-priori commitments)
- Supersession triggers (per ADR-001 §5)

Notable directional commitments (full list in v2 §0 + §3):
- German B2B accounting workflow primary; transfer-learning to non-German / non-B2B as secondary measurement
- §203 / §62a StBerG framing as Chapter-1 Motivation only
- Three-layer architecture (doc-VLM → KG → analytical query) as contribution scaffold
- EU-hosted cloud baselines as honest comparison axis
- End-to-end working prototype (FastAPI + Streamlit + Docker compose)
- Fine-tuning central (LoRA / QLoRA on at least one VLM)

## 4 — Open questions — Säring-blocked

Decided at the first technical-progress meeting with Prof. Säring (currently un-booked; gated on pilot results to demonstrate). Per v2 §11:

1. Sign-off on §14 UStG-derived field weights for compliance-aware F1 (v2 §5.2)
2. Sign-off on held-out test set design + freeze date (v2 §9.3)
3. Sign-off on falsifiable hypothesis set (v2 §6 H1–H6, possibly H7 transfer-learning)
4. Cloud API budget approval (cost estimate produced before meeting)
5. GPU rental budget approval (cost estimate ditto)
6. Supervision cadence (biweekly / monthly)

**Säring email status**: Initial thesis-confirmation exchanged 2026-04. Säring response: cordial, requested no further info "for now". Next touchpoint = first technical-progress meeting, booked once pilot evidence is in hand. **Not a near-term implementation blocker.**

## 5 — Open questions — implementation-phase (ADR-driven)

Decided at each step on evidence; each gets an ADR per `horus-decision-discipline`. Non-exhaustive. Per v2 §4.2:

| Decision | Trigger | ADR slot |
|---|---|---|
| Layer-1 architecture (single-shot vs orchestrated primary spine) | Both architectures tested on pilot | `ADR-NNN-layer-1-architecture.md` |
| Layer-1 model cohort (subset of v2 §8.1) | Zero-shot baselines reveal differentiation | `ADR-NNN-layer-1-cohort.md` |
| Cloud baseline count (subset of v2 §8.2) | Pilot reveals differentiating vs redundant + budget | `ADR-NNN-cloud-baselines.md` |
| Validator loop inclusion (Layer 1 stage 4) | Error analysis on extraction stage | `ADR-NNN-validator-loop.md` |
| Layer-2 graph storage (NetworkX / Neo4j / LightRAG internal) | Schema + query patterns stable | `ADR-NNN-layer-2-storage.md` |
| Layer-3 retrieval strategy (vector / graph / hybrid / per-query router) | Comparison runs | `ADR-NNN-layer-3-retrieval.md` |
| Models to fine-tune (which + how many) | Zero-shot baselines reveal gap | `ADR-NNN-fine-tuning-cohort.md` |
| Frontend feature scope (Streamlit detail) | Core pipeline works | `ADR-NNN-frontend-scope.md` |

Additional ADRs surface as implementation progresses.

## 6 — Implementation-start blockers (M2D.5 setup)

What MUST happen before code productively lands. Audited against current repo state post-M2D.0–M2D.3.

### 6.1 — Tooling installs (each = its own ADR per `horus-decision-discipline`)

- Mustang Project (Java) — ZUGFeRD generator/validator. Requires JDK
- MLX (Python, Apple Silicon) — `uv add mlx mlx-lm`
- Docling library (Python) — `uv add docling`
- HuggingFace transformers + datasets (Python) — `uv add transformers datasets`
- PyTorch + MPS (Python, Apple Silicon) — `uv add torch torchvision`
- MLflow (Python) — `uv add mlflow`

**No bulk install.** Each `uv add` triggers a 5-section ADR per ADR-001. Pattern explicitly enforced.

### 6.2 — Dataset downloads (user-action; some manual)

| Dataset | Access | Path (gitignored) | Approx size |
|---|---|---|---|
| **ZUGFeRD corpus** | https://github.com/ZUGFeRD/corpus (clone) | `data/raw/zugferd-corpus/` | hundreds of MB |
| **Mustang Project** | https://github.com/ZUGFeRD/mustangproject (clone or release JAR) | `tools/mustangproject/` | ~50 MB |
| **GI 2021 German invoices** | https://dl.gi.de/handle/20.500.12116/35795 (locate at M2D.5) | `data/raw/gi-2021-de-invoices/` | unknown |
| **CORD-v2** | HuggingFace `naver-clova-ix/cord-v2` (auto via `datasets.load_dataset`) | HF cache + `data/raw/cord-v2/` | ~1 GB |
| **SROIE** | https://rrc.cvc.uab.es/?ch=13 (registration required) | `data/raw/sroie/` | hundreds of MB |
| **FUNSD** | https://guillaumejaume.github.io/FUNSD/ (direct) | `data/raw/funsd/` | hundreds of MB |
| **OmniDocBench** | HuggingFace `opendatalab/OmniDocBench` | HF cache + `data/raw/omnidocbench/` | several GB |
| **inv-cdip Tobacco** | Locate at M2D.5 (used by Berghaus 2025) | `data/raw/inv-cdip-tobacco/` | unknown |

P0 vs P1 prioritisation pending — confirm at M2D.5 kickoff. ZUGFeRD corpus + Mustang are P0 (the data unlock). Others align with experiment-phase needs.

### 6.3 — Repo structural prep (M2D.5)

- `data/` directory (gitignored) for raw + processed datasets
- `eval/` directory for evaluation-harness scaffolding (verify against L3 template; may already exist)
- `notebooks/` for exploratory work
- `scripts/` for utility scripts (e.g., XML extraction from ZUGFeRD PDFs)
- `pyproject.toml` / `Makefile` / `.gitignore` updates as needed

## 7 — Approaches considered

v2 §3 D1–D11 imported as the working approach choices. Each entry below: alternative considered → working choice → reversal trigger.

| # | Working choice | Alternative | Reversible if |
|---|---|---|---|
| D1 | Donut excluded from cohort (historical reference only) | Include as legacy baseline | Pilot results show informative old-vs-new paradigm comparison value |
| D2 | LayoutLMv3 same | Same | Same |
| D3 | B2B + Belege | Receipts-only (CORD-v2-style) | German B2B scope proves untractable for thesis envelope |
| D4 | §203 + §62a StBerG framing | "DSGVO blocks cloud" (2022 framing) | Stable; literature-grounded at M2D.3 Theme F |
| D5 | LandingAI ADE as cloud baseline | Drop cloud entirely | Budget zero or cloud comparison adds no insight |
| D6 | Layer-1 four-stage pipeline | Two-stage (parser + extractor) | Single-shot wins decisively → orchestrated dropped per ADR |
| D7 | Working prototype required | Thesis-only, no demo | Säring permits |
| D8 | Fine-tuning central | Zero-shot only | Compute / timeline precludes |
| D9 | §203 → Chapter-1 Motivation only | §203 as research contribution | Stable; v2 §13 + Säring's scientific-correctness criterion both anchor |
| D10 | Branches on results | Waterfall planning | Stable; the entire `horus-decision-discipline` is built on this |
| D11 | Agentic validator loop conditional | Always include | Error analysis shows zero-shot has no measurable correctable error |

## 8 — Next phase

> **Amendment 2026-05-10**: see §11 for revision of the `issues`-skip decision. `spec`-skip remains in force.

Per `~/.windsurf/templates/python-ml-uv/phases.yaml`, the canonical next phase after `brainstorm` is `spec` (PRD authoring via `@to-prd`). HORUS deliberately adapts this:

**Adaptation: skip `spec` and `issues` phases for now; proceed directly to `experiment` (M2D.5+).**

Rationale:

- v2 §0–§14 already substitutes for ~70% of a PRD's typical content (working frame + decisions + open questions + datasets + tech stack)
- The §4.1 a-priori locks that a PRD typically formalises are Säring-blocked — cannot be locked until first technical-progress meeting, which is gated on pilot results
- Authoring a pre-Säring PRD risks over-committing to predictions that aren't pilot-grounded → HARKing risk

**M2D.5 kickoff scope** (next milestone):

1. Repo structural prep (§6.3 above)
2. First tooling-install ADRs (Mustang + MLX + Docling at minimum, per `horus-decision-discipline`)
3. First pilot data loop:
   - Mustang generator install + Mustang ADR
   - Generate ~10–50 synthetic ZUGFeRD invoices (Mustang)
   - Write XML-extraction-from-PDF script + first ADR on script architecture
   - Get ONE local VLM running on M1 Pro on 10 invoices (Granite-Docling via MLX strongly indicated, but cohort-selection ADR is what locks it)
   - Compute initial F1 with full rigor: v2 §5.1 standard token F1 + v2 §5.5 field-level error heatmap (per-field precision/recall), MLflow-tracked, deterministic seed. Säring-blocked metrics (v2 §5.2 field-weighted F1, v2 §5.3 compliance pass rate, v2 §5.4 Vorsteuerabzug eligibility) deferred pending field weights + validator stage. Pilot scope is small for tractability, NOT for skipping rigor
4. After pilot evidence in hand: schedule first Säring meeting + draft Säring agenda materials in parallel

If the phase-skip proves problematic (e.g., absence of explicit PRD becomes friction), revisit at `@sprint-review` and either author a retroactive lightweight PRD or refine the L3 phases.yaml.

---

## 9 — Amendment 2026-05-10: Claude-chat cross-check + verified candidate refresh

**Status**: amendment to §1–§8 directional content. Supplements, does not supersede. Original v2-derived working frame stays valid.

**Trigger**: user-led external review with Claude Opus 4.7 (web chat) on 2026-05-10 surfaced 15 candidate-list deltas vs the v2-derived directional content imported at M2D.4. Web verification done in Cascade D session (this resume rethink) via `search_web` + HuggingFace MCP. 14/15 factual claims verified; 1 caveat. 3 NEW candidates claude-chat missed. Plus a methodology refinement.

**Provenance**: `~/.windsurf/plans/cascade-d-resume-rethink-2f7f5a.md` (Cascade D's resume-rethink plan). Mirrored in `cascade-system/docs/handoffs/cascade-d-master-thesis.md` §3.1 (the canonical record for new cascades that pick up via `@kickoff`).

### 9.1 Verified candidate matrix

| External claim | Status | Action for new cascade |
|---|---|---|
| Drop Qwen2.5-VL → Qwen3-VL | ✅ verified | Replace v2 §8.1 `Qwen2.5-VL-7B` row with `Qwen3-VL-8B-Instruct` (Apache 2.0, arXiv 2505.09388, released 2025-09-23) and `Qwen3-VL-30B-A3B-Instruct` (MoE) for compute-permitted runs |
| Add PaddleOCR-VL 1.5 (0.9B SOTA OmniDocBench v1.5 = 94.5%) | ✅ verified | Add candidate. arXiv 2601.21957. Apache 2.0. Multilingual (en+zh tag). Caveat: Chinese-skewed pretraining → German eval needed |
| Granite-Docling 258M MLX-ready | ✅ verified | Already in v2 §8.1. MLX path: `ibm-granite/granite-docling-258M-mlx` (200-300 tok/s on M-class). Strong starter |
| olmOCR-2-7B English-skewed | ✅ verified | HF tag `language: en` only. Annotate v2 §8.1 with EN-skew caveat |
| Mistral OCR cheapest cloud (~$0.50/1k batch) | ✅ verified | Add to v2 §8.2. Mistral OCR 3 also released — newer/more capable/higher cost |
| Gemma 3 cloud (matches Berghaus) | ✅ verified | Add to v2 §8.2. Direct comparison to Berghaus arXiv 2509.04469 |
| ZUGFeRD 2.4 / Factur-X 1.08 (Dec 2025) | ✅ verified | Pin generator target to v2.4. Mustangproject 2.21.0 (2025-12-18) supports |
| Berghaus arXiv 2509.04469 | ✅ verified | Berghaus + Berger + Hillebrand + Cvejoski + Sifa (Fraunhofer IAIS + Lamarr). Already in v2 bibliography |
| Berghaus eval-code anonymous.4open.science URL | ⚠️ unauthorized | ADR slot: locate de-anon URL; fork-or-reinvent in new cascade |
| FATURA on HF (10k imgs, 50 templates) | ✅ verified | `mathieu1256/FATURA2-invoices`. arXiv 2311.11856. Add to v2 §9.2 |
| Aoschu/German_invoices_dataset | ⚠️ exists but n<1K, license unclear | Add as "sanity test only" |
| OmniDocBench v1.5 + Real5-OmniDocBench | ✅ verified | Real5 = arXiv 2603.04205 (March 2026), 1,355 imgs, 5 physical conditions. Add to v2 §9.2 |
| bge-m3 multilingual | ✅ verified | 149M downloads, MIT, 100+ langs, arXiv 2402.03216, XLM-RoBERTa base. Replace v2 §10 generic with bge-m3 indicated |
| vllm-mlx Apple Silicon serving | ✅ verified | `vllm-project/vllm-metal` + `waybarrios/vllm-mlx`. Add to v2 §8.4 |
| Python 3.14 + PyTorch 2.10+ compat | ✅ verified | PyTorch 2.10 = Py3.14 `torch.compile`; 2.11 latest. Already pinned in repo |

### 9.2 New finds (claude-chat missed)

- **MinerU 2.5-Pro** — 1.2B params, **95.69% on OmniDocBench v1.6** (April 2026, arXiv 2604.04771). v1.6 fixes element-matching biases + adds Hard subset; surpasses PaddleOCR-VL 1.5. Stronger candidate than PaddleOCR-VL 1.5 if v1.6 is the eval target.
- **MDPBench** — Multilingual Document Parsing Benchmark, 17 langs, 3,400 imgs, March 2026 (arXiv 2603.28130). Closed-source models robust; open-source drops 17.8% on photographed docs, 14% on non-Latin scripts.
- **Mistral OCR 3** — replaces `mistral-ocr-latest`. To survey at cloud-baseline ADR.

### 9.3 Methodology refinement (sharpens v2 §4.1 lock-vs-branch)

| Lock-timing tier | Items | Source |
|---|---|---|
| **Hard pre-commit** (before ANY model run, incl. pilot) | (1) Held-out test set freeze + hash; (2) Layer-1 eval protocol (v2 §5.1 token F1 + §5.5 field heatmap, MLflow-tracked, deterministic seed) | claude-chat refinement of v2 §4.1 |
| **First-Säring-meeting lock** | RQ; field weights (v2 §5.2); H1–H6; statistical reporting; freeze-date approval | v2 §4.1 + §12 |
| **Post-Layer-1-evidence** | v2 §5.2 weighted F1, §5.3 compliance pass rate, §5.4 Vorsteuerabzug eligibility, §5.6 validator catch rate | claude-chat refinement |
| **Layer-2/3-phase** | KG fidelity propagation; Layer 3 query-accuracy; GraphRAG-vs-vector metrics | branches per v2 §4.2 |

### 9.4 Forward-reference

§10 below authors the `horus-config-discipline` L2 rule that mandates YAML-based experiment configs — the architectural shape required for everything below. Every experiment YAML is the de-facto "lock" for that run, deterministically tied to a git commit + MLflow run.

---

## 10 — Amendment 2026-05-10: Config-discipline rule (L2)

**Status**: rule arrival. Bundle 1 of the config-discipline split-landing.

**Trigger**: user-surfaced gap during the 2026-05-10 Cascade D resume-rethink. Current `src/horus/config.py` is the L3-template `@dataclass` placeholder with hardcoded defaults (`seed=42`, `learning_rate=1e-3`, `batch_size=32`, `num_epochs=1`) — exactly the pattern that compromises reproducibility + scientific correctness if propagated into M2D.5 first-experiment authoring. `experiments/` empty. No `config-discipline` rule existed in `.windsurf/rules/`.

**Bundle 1** (this PR): adds project-local L2 rule `.windsurf/rules/horus-config-discipline.md`. Rule mandates:

- **Forbidden in `.py` files**: hardcoded knobs (hyperparameters / model IDs / dataset paths / seeds / batch sizes / learning rates / prompt strings / eval thresholds / MLflow tags) as default args, module-level constants, or inline literals
- **Allowed in `.py` files**: Pydantic schema literal defaults inside `src/horus/config.py` (that's the contract — defaults belong there); package metadata (`__version__`); structural constants (column names, schema field names, enum values for typing); test fixtures inside `tests/`
- **Contract**: experiments accept ONE papermill parameter `cfg_path: str`; cfg loaded via `ExperimentConfig.from_yaml(cfg_path)`; Pydantic raises on missing/malformed → fails fast before any model loads / dataset downloads
- **Forcing function**: Pydantic-validates-at-boot is the architectural backstop (no separate skill/workflow needed; the architecture itself is the workflow, cf. ADR-013/ADR-018 patterns)

Rule body documents: what's forbidden + what's allowed (with examples) + the contract (experiment `.py` shape template) + activation triggers (`model_decision` keywords) + when the rule does NOT fire + fires/does-not-fire examples + L3 promotion plan + source/provenance.

**L3 promotion plan**: pre-committed to surface for promotion to `~/.windsurf/templates/python-ml-uv/rules/config-discipline.md` at next `@sprint-review` (per Q7 commitment in resume-rethink plan §1; not deferred indefinitely). The shape is generic enough to apply to any python-ml-uv project.

**Bundle 2** (deferred to new cascade, M2D.5 step 0): walks `ADR-NNN-config-library` Socratically per `horus-decision-discipline` rule (Pydantic Settings indicated; Hydra / OmegaConf / stdlib + PyYAML alternatives surveyed) → installs chosen library via `uv add` (with full 5-section ADR per ADR-001) → replaces `src/horus/config.py` placeholder with chosen-library schema → scaffolds `configs/` directory + first per-experiment YAML → updates `Makefile` `experiment` target to accept `CFG=configs/<slug>.yaml` parameter.

The new cascade has the Bundle 1 rule loaded at conversation-start (workspace rule, AGENTS.md known) → actively gates Bundle 2 work as M2D.5 step 0, BEFORE any experiment is authored or any model knob is touched.

**Provenance**: `~/.windsurf/plans/cascade-d-resume-rethink-2f7f5a.md` + `cascade-system/docs/handoffs/cascade-d-master-thesis.md` §3.2 (the canonical record).

---

## 11 — Amendment 2026-05-10: Issues-phase restoration

**Status**: amendment to §8. Supplements + revises the `issues`-skip half of §8's phase-chain adaptation. `spec`-skip stays in force.

**Trigger**: 2026-05-10 user-led clarification session. User identified that all three §8 rationales — (1) v2 §0–§14 already covers ~70% of typical PRD content, (2) the §4.1 a-priori commitments are Säring-blocked, (3) pre-Säring PRD risks HARKing — are **spec-only** rationales. None of them are about `issues`-phase semantics. The previous Cascade authoring §8 conflated the two phases when bundling them under one "skip" decision.

**Decision**: Only the `spec` phase is skipped. The `issues` phase is **restored**. Issues are authored from brainstorm §8 (M2D.5 sub-steps) + handoff `cascade-d-master-thesis.md` §3 (M2D.5 work-breakdown + M2D.6+ shape) as inputs — adapted consumption pattern for `@to-issues` (it nominally consumes a PRD §11 vertical-slices section; HORUS substitutes brainstorm + handoff per this amendment, with the L3-template friction captured to the cross-project queue for the next `@sprint-review` to triage).

**Rationale (un-skip)**:

- Issues don't need a PRD as input. `@to-issues` adapts to consume brainstorm + handoff directly when `spec` is skipped — the L3 friction is whether `python-ml-uv` `phases.yaml` should formally allow `issues`-from-brainstorm when `spec` is skipped, or whether `@to-issues` should learn both inputs natively. Either resolution preserves the un-skip; the friction itself does not justify the original conflation.
- Conditional / sub-issue dependency chains express "branches on results, not on plans" (v2 §4.2; §2 D10 discipline commitment) **explicitly** on the Project v2 board — makes the decision-tree discipline auditable rather than implicit in narrative prose.
- Project board #6 is currently empty → `plan-drift-watcher` rule has nothing to detect drift against → the discipline is invisible to the rule. Issues populated to milestone `experiments-validated` (#5) give the watcher signal.
- Conventional-commit refs (`feat(experiment): ... refs #N`) require issues to exist before commits can reference them. Without issues, the per-commit traceability that `branch-and-pr-required` + `make-sure-it-works` rely on cannot be wired.

**Cross-link from §8**: top of §8 carries the callout `**Amendment 2026-05-10**: see §11 for revision of the `issues`-skip decision. `spec`-skip remains in force.`

**Pattern A vs ADR**: amendment recorded inline matching §9 + §10 precedent (both methodological/discipline revisions, neither carries an ADR). `horus-decision-discipline` literal scope is tool/model/library/dataset/framework/hosting choices — phase-chain revision falls outside. ADR promotion is reversible at any future `@sprint-review` if the pattern proves novel enough.

**Provenance**: parent clarify session plan `~/.windsurf/plans/horus-clarify-and-kickoff-fresh-m2d5-session-dd91c1.md` + execution kickoff plan `~/.windsurf/plans/kickoff-cascade-d-issues-restoration-f2c8e1.md` + execution wrapper `~/.windsurf/plans/kickoff-cascade-d-issues-restoration-execution-743f68.md` (this Cascade's plan summary).

---

## Provenance

- **Input**: `/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/research/THESIS_BRAINSTORM_STATE_v2.md` (locked 2026-05-06, revision 2 by Reebal Sami + Claude Opus 4.7)
- **L3 skill**: `~/.codeium/windsurf/skills/grill-me/SKILL.md` (procedure adapted: walked §0 markers initially, course-corrected on user feedback to NOT lock anything beyond directional principles; deviation captured in cascade-system queue for future @grill-me enhancement on "import-mode" thesis brainstorms)
- **Workspace rules applied**: `horus-decision-discipline.md` + `horus-source-archival.md` (M2D.2)
- **ADRs referenced**: ADR-001 (tool decisions), ADR-002 (source archival), ADR-003 (HORUS naming)
- **Phase artefact**: produced at M2D.4 per `~/.windsurf/templates/python-ml-uv/phases.yaml` `brainstorm` phase
- **Kickoff plan**: `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §4 M2D.4
