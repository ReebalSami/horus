# Literature review — HORUS (Hybrid OCR-free Reading & Understanding System)

| Field | Value |
|---|---|
| **Phase** | `literature` (M2D.3) |
| **Status** | `approved` |
| **Date** | 2026-05-08 |
| **Scope** | Privacy-first document intelligence for German tax/accounting professionals via local Vision-Language Models (no OCR pipeline); knowledge-graph layer; compliance-aware fidelity evaluation under § 203 StGB / § 62a StBerG |

## 1 — Methodology

This literature review is an **import** of an existing user-conducted research review captured in `THESIS_BRAINSTORM_STATE_v2.md` §7 (critical research findings) and §15 (bibliography), locked 2026-05-06 (revision 2) by Reebal Sami + Claude Opus 4.7 over the period 2026-04 to 2026-05.

This is a deviation from the canonical `@literature-review` L3 skill procedure (which assumes a fresh interview → vault sweep → external sweep → triage → IMRAD-deep-read flow). The deviation is justified because the user-conducted review is already structured along IMRAD-equivalent lines and is the input the kickoff plan §4 explicitly hands off to M2D.3. The `@literature-review` skill's procedural shape is honoured at the artefact level: the present document carries the same Header / Methodology / Sources / Findings-by-theme / Gap-statement structure the skill specifies. *L3-skill enhancement queued: a future `--import-from <existing-doc>` mode would formalise this path.*

**Source counts**:

- **46 sources archived** under `docs/sources/<type>/<slug>.md` per the `horus-source-archival` workspace rule (ratified at M2D.2 by ADR-002):
  - 10 papers (`docs/sources/papers/`) — formal academic citations
  - 19 tools (`docs/sources/tools/`) — VLM cohort, RAG frameworks, inference engines, generators
  - 7 datasets (`docs/sources/datasets/`) — evaluation benchmarks
  - 10 legal (`docs/sources/legal/`) — German Berufsrecht, DSGVO, ZUGFeRD/EN 16931, vendor DPAs

**Deep-read status**: All sources are at `status: stub` — frontmatter + 1-paragraph context-summary derived from brainstorm v2 §7. Three sources (Cai & O'Connor 2025, Berghaus et al. 2025, Han et al. 2025) constitute the IMRAD-deep-read core because brainstorm v2 §7 already provides Methods/Results/Discussion-equivalent analysis for each. Remaining sources are catalogued at the option-considered level; full deep-reads occur on-demand when the `experiment` phase or thesis writeup needs to ground a specific claim.

## 2 — Sources

### 2.1 — Papers (10)

- `docs/sources/papers/kim-2022-donut.md` — Donut OCR-free Document Understanding Transformer (Kim et al., ECCV 2022). **Historical** OCR-free paradigm reference.
- `docs/sources/papers/huang-2022-layoutlmv3.md` — LayoutLMv3 (Huang et al., ACL 2022). **Historical** orchestrated-pipeline (text+image+layout) reference.
- `docs/sources/papers/ibm-2025-granite-docling.md` — IBM Granite-Docling 258M (IBM, Oct 2025, Apache 2.0). **Primary Layer-1 candidate**.
- `docs/sources/papers/livathinos-2025-docling.md` — Docling technical report (Livathinos et al., arXiv 2501.17887). Orchestrated-specialists baseline pipeline.
- `docs/sources/papers/poznanski-2025-olmocr2.md` — olmOCR-2-7B (AllenAI, RLVR-trained). **Primary Layer-1 candidate**.
- `docs/sources/papers/han-2025-graphrag-vs-vector-rag.md` — Han et al. 2025 GraphRAG vs vector RAG empirical study. **Layer-3 design pivot point**.
- `docs/sources/papers/cai-2025-kg-extraction-eval.md` — Cai & O'Connor 2025 KG extraction evaluation (arXiv 2506.12367). **Direct prior for thesis novelty**.
- `docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md` — Berghaus et al. 2025 (Fraunhofer IAIS, arXiv 2509.04469). **Direct literature gap** — benchmarked cloud VLMs on invoices but excluded the Oct-2025 open-source cohort.
- `docs/sources/papers/gi-2021-german-invoices.md` — GI 2021 German invoice dataset (977 PDFs, 60+ class annotations). Secondary corpus.
- `docs/sources/papers/kerr-1998-harking.md` — Kerr 1998 HARKing methodological reference. Anchors thesis's locked-a-priori discipline.

### 2.2 — Tools (19)

**Local document VLM cohort (Layer 1 candidates, Oct-2025 wave)**:
- `docs/sources/tools/nanonets-ocr2.md`, `docs/sources/tools/dots-ocr.md`, `docs/sources/tools/mineru-2-5.md`, `docs/sources/tools/monkey-ocr.md`, `docs/sources/tools/chandra-ocr.md`, `docs/sources/tools/paddleocr-vl.md`, `docs/sources/tools/deepseek-ocr.md`, `docs/sources/tools/smoldocling-256m.md`

**Orchestrated baseline pipeline**:
- `docs/sources/tools/docling-library.md` — IBM Docling library (Apache 2.0)

**Apple Silicon inference frameworks (M1-Pro target)**:
- `docs/sources/tools/mlx-apple-silicon.md` (primary), `docs/sources/tools/mlc-llm.md` (secondary), `docs/sources/tools/llama-cpp.md` (GGUF fallback), `docs/sources/tools/ollama.md` (ergonomic UX), `docs/sources/tools/pytorch-mps.md` (slow baseline)

**Layer-3 retrieval / RAG frameworks**:
- `docs/sources/tools/lightrag.md` (primary hybrid), `docs/sources/tools/hipporag.md` (multi-hop alternative), `docs/sources/tools/microsoft-graphrag.md` (heavyweight baseline)

**Synthetic-data generation**:
- `docs/sources/tools/mustang-project.md` — ZUGFeRD generator, the data unlock
- `docs/sources/tools/fattural.md` — ZUGFeRD/Factur-X synthetic-data generation tooling (companion to Mustang)

**Cloud-baseline reference**:
- `docs/sources/tools/landingai-ade.md` — Landing AI ADE (SaaS / VPC / on-premise + ZDR)

### 2.3 — Datasets (7)

**Primary German B2B invoice corpora**:
- `docs/sources/datasets/zugferd-corpus.md` — public ZUGFeRD invoices (PDF/A-3 + embedded XML ground truth)
- `docs/sources/datasets/gi-2021-de-invoices.md` — 977 real German B2B invoices (Krieger et al. 2021; pending author request, sub-issue #26)

**Cross-domain evaluation benchmarks**:
- `docs/sources/datasets/cord-v2.md` — receipts (NAVER CLOVA, HuggingFace)
- `docs/sources/datasets/sroie.md` — receipts (ICDAR 2019)
- `docs/sources/datasets/funsd.md` — forms (Jaume et al. 2019)
- `docs/sources/datasets/omnidocbench.md` — modern multi-domain (OpenDataLab)
- `docs/sources/datasets/inv-cdip-tobacco.md` — invoice subset (referenced by Berghaus 2025)

### 2.4 — Legal (10)

**German Steuerberater Berufsgeheimnis trinity**:
- `docs/sources/legal/stgb-203.md` — § 203 StGB criminal-law confidentiality
- `docs/sources/legal/stberg-57.md` — § 57 StBerG general professional duties
- `docs/sources/legal/stberg-62a.md` — § 62a StBerG external-provider gate (Abs. 4 foreign-provider clause is the cloud fault-line)

**Kammer guidance**:
- `docs/sources/legal/bstbk-2026-ki-faq.md` — BStBK FAQ on AI tooling (January 2026, primary)
- `docs/sources/legal/bstbk-dsgvo-hinweise.md` — BStBK Hinweise on personal-data handling

**EU/general data-protection**:
- `docs/sources/legal/dsgvo-art-32.md` — Art. 32 DSGVO (necessary but not sufficient)

**Vendor compliance contracts (cloud-baseline column)**:
- `docs/sources/legal/openai-dpa.md`, `docs/sources/legal/anthropic-dpa.md`, `docs/sources/legal/azure-openai-frankfurt.md`

**E-invoicing standard**:
- `docs/sources/legal/zugferd-en16931.md` — ZUGFeRD/XRechnung standard, B2B mandate active 2025-01-01

## 3 — Findings by theme

### Theme A — Local document VLMs eclipse the orchestrated pipeline (Oct-2025 wave)

**Consensus**: A new cohort of small-to-mid-scale OCR-free document VLMs released since October 2025 — Granite-Docling 258M, olmOCR-2 7B, Nanonets-OCR2 3B, dots.ocr 3B, MinerU 2.5, Monkey OCR, Chandra OCR, PaddleOCR-VL 0.9B, DeepSeek-OCR, SmolDocling 256M — collectively constitute a generational shift past the Donut (2022) / LayoutLMv3 (2022) era. Most ship with permissive licences (Apache 2.0 in Granite-Docling's case) and several have native Apple Silicon (MLX) support.

**Contradictions**: Direct head-to-head benchmarks across the full cohort do not yet exist in the published literature. Benchmark numbers reported in individual release notes (e.g., olmOCR-2's ~82.5 on olmOCR-Bench) are author-reported on author-curated benchmarks, not third-party-replicated.

**Gaps**: No single 2025-era benchmark report covers more than 2–3 of the cohort entries on the same evaluation set. Performance ranking on German B2B invoices specifically — the HORUS evaluation domain — is entirely unexplored in the literature.

### Theme B — GraphRAG often loses to vanilla vector RAG (literature consensus pivot)

**Consensus** (Han et al. 2025, `docs/sources/papers/han-2025-graphrag-vs-vector-rag.md`): On standard QA benchmarks, GraphRAG often **loses** to vanilla vector RAG: ~13.4 pp lower accuracy on Natural Questions, only modest 4.5 pp gain on HotpotQA multi-hop, and ~2.3× higher latency on average.

**Contradictions**: Multi-hop QA settings (HotpotQA) show modest GraphRAG gains; some specialised domains (medical, legal, multi-document scientific) report larger graph benefits. Hybrid frameworks (LightRAG) split the difference.

**Gaps**: No published per-query routing rule predicting *when* graph reasoning helps vs hurts. The headline question is no longer "does the graph help" but "*when* does it help, *when* does it hurt, can we predict per query." This is a Layer-3 design opportunity for HORUS.

### Theme C — KG-fidelity evaluation has a single direct precedent (thesis novelty bridge)

**Consensus** (Cai & O'Connor 2025, `docs/sources/papers/cai-2025-kg-extraction-eval.md`): KG-extraction quality must be evaluated at two levels — micro-level edge accuracy AND macro-level graph-structural properties (community detection, connectivity) — because extraction-quality decline produces *systematic* (not additive) biases in graph-level metrics.

**Contradictions**: None — Cai & O'Connor 2025 is a single paper without a direct counter-example in the surveyed literature.

**Gaps**: Cai & O'Connor evaluate text→KG extraction on news/encyclopaedia text; image→KG (the HORUS scope) is unaddressed. Compliance-aware fidelity metrics (does the KG preserve the legally-relevant invoice fields with sufficient accuracy?) are unaddressed. Layer-3 query-accuracy propagation (how does Layer-2 extraction quality flow into Layer-3 QA accuracy?) is unaddressed. **All three gaps together define the thesis's methodological contribution**.

### Theme D — German B2B invoices are an unlocked evaluation domain (the data unlock)

**Consensus**: Germany's B2B e-invoicing mandate (ZUGFeRD/XRechnung, EN 16931 standard, mandatory to receive 2025-01-01, mandatory to issue by 2027) creates an unprecedented public corpus of structured invoices: hybrid PDF/A-3 with embedded XML providing **per-document ground truth without manual labelling**. The Mustang Project tooling enables synthetic generation of arbitrary-content ZUGFeRD invoices on top of the public corpus. The GI 2021 paper provides 977 real-world German invoices for distribution-shift validation.

**Contradictions**: None observed.

**Gaps**: No published benchmark uses this evaluation loop (render PDF → VLM extract JSON → compare against embedded XML) to evaluate Oct-2025 open-source VLMs. Berghaus et al. 2025 (`docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md`) ran a similar evaluation but on *cloud* VLMs (GPT-5, Gemini 2.5, Gemma 3) and not the open-source cohort. **This is the most concrete literature gap HORUS fills**.

### Theme E — Apple Silicon is a viable inference target, but throughput claims need validation

**Consensus** (single source, brainstorm v2 §7.2): Reported throughput ranking on M-class Macs for LLM inference is MLX (~230 tok/s) > MLC-LLM (~190) > llama.cpp short-context (~150) > Ollama (20–40) > PyTorch MPS (~7–9). MLX is the highest-performing path; PyTorch MPS is impractical.

**Contradictions**: The benchmark is single-source (a late-2025 blog) and not third-party-replicated. Numbers vary substantially by model architecture, quantization, and context length.

**Gaps**: No HORUS-internal benchmark exists yet on the M1 Pro target hardware. Per ADR-001 current-state-survey discipline, any thesis-claim about Apple Silicon throughput must be backed by HORUS-internal measurements, not the cited blog. **This is an experiment-phase deliverable**, not a literature-defended claim.

### Theme F — DSGVO is solvable for cloud APIs; § 203 + § 62a StBerG is not

**Consensus** (BStBK FAQ Jan 2026, `docs/sources/legal/bstbk-2026-ki-faq.md` + brainstorm v2 §7.6): For German Steuerberater handling Mandantendaten:
- DSGVO (Art. 32 DSGVO + DPA per Art. 28) is solvable via OpenAI / Anthropic / Azure-Frankfurt DPAs — these provide EU data residency, EU inference residency (since Jan 2026 for OpenAI Enterprise/API), and acceptable TOM postures.
- **§ 203 StGB + § 62a StBerG is not solvable** for current cloud offerings. § 62a Abs. 4 StBerG requires foreign service providers to offer comparable secrecy protection; US providers fail this even with EU servers due to extraterritorial reach of US Cloud Act / FISA 702. As of early 2026, no major cloud AI provider offers a separate Berufsgeheimnis-Verpflichtung in Textform per § 62a StBerG.
- Penalties under § 203: up to 1 year imprisonment + Berufsverbot.

**Contradictions**: Some commentary treats Azure-Frankfurt as broadly compliant; the BStBK FAQ January 2026 explicitly disagrees for Mandantendaten without the § 62a-specific Verpflichtung.

**Gaps**: No published study evaluates open-source local-inference VLMs on the same German B2B invoice scope under the § 203-StBerG legal frame. **This is HORUS's positioning argument** — the chapter-1 motivation that makes "local VLM thesis" the right scope rather than a generic "VLM benchmarking" thesis.

### Theme G — LandingAI ADE represents the cloud-baseline column honestly

**Consensus**: LandingAI ADE offers three deployment modes (SaaS US/EU, VPC, on-premise) plus Zero Data Retention. The honest comparison to local open-source is "EU-hosted ZDR-enabled cloud SaaS vs local open-source," not "any cloud vs any local." LandingAI sits closest to compliance among commercial offerings.

**Gaps**: Performance benchmarks of LandingAI ADE on German B2B invoices are not publicly reported. § 62a Abs. 4 foreign-provider clause still applies (Landing AI is US-based) — even the most compliant cloud option fails the Steuerberater-specific test.

## 4 — Gap statement (bridge to brainstorm)

The literature surveys above converge on a coherent thesis-shaped gap:

> **No published benchmark evaluates the Oct-2025 open-source local-document-VLM cohort on German B2B invoices using the embedded-XML-ground-truth evaluation loop, under the § 203 StGB / § 62a StBerG legal frame that excludes cloud baselines for Mandantendaten, with KG-extraction fidelity measured at both micro and macro levels (Cai & O'Connor 2025 extension), and with Layer-3 query-accuracy propagation evaluated against a per-query graph-vs-vector routing decision (Han et al. 2025 extension).**

That single sentence collapses six concrete contributions:

1. **Layer-1 cohort benchmark** — first head-to-head of Granite-Docling, olmOCR-2, Nanonets-OCR2, plus orchestrated-Docling baseline, on the same German B2B invoice scope
2. **Embedded-XML evaluation methodology** — label-free, scalable evaluation loop reusable beyond the thesis
3. **§ 203 StBerG legal positioning** — the chapter-1 argument distinguishing this work from generic invoice-VLM benchmarks
4. **Image→KG extension of Cai & O'Connor 2025** — micro+macro fidelity for an image-input KG-extraction setting (the original works on text-input)
5. **Compliance-aware KG-fidelity metric** — does the extracted KG preserve legally-required invoice fields with sufficient accuracy for Steuerberater use? Novel metric.
6. **Layer-3 routing extension of Han et al. 2025** — per-query "graph helps vs hurts" prediction, using LightRAG's hybrid framework as the substrate

The M2D.4 brainstorm walks brainstorm v2 §0–§12 to determine which of these six are in-scope for the master's-thesis envelope and which are deferred.

## 5 — Citation format

This artefact uses repo-relative paths to `docs/sources/<type>/<slug>.md` stubs. Stubs carry full source metadata (URL, author, date, tags) in YAML frontmatter compatible with Obsidian Web Clipper output (per ADR-002 + `horus-source-archival` rule).

The `writeup` phase (downstream) converts these to the consumer's chosen citation style (BibTeX for LaTeX thesis; CSL-JSON for any submission requiring a different style; plain-text Wikipedia-style for non-academic surfaces).

## 6 — Provenance

- **Input source**: `/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/research/THESIS_BRAINSTORM_STATE_v2.md` §7 (critical research findings) + §15 (bibliography), locked 2026-05-06 (revision 2) by Reebal Sami + Claude Opus 4.7
- **Phase artefact**: produced at M2D.3 per `~/.windsurf/templates/python-ml-uv/phases.yaml` `literature` phase
- **Workspace rules applied**: `horus-source-archival.md` (every cited source archived) + `horus-decision-discipline.md` (model/tool selections inform but do not commit to ADRs at this phase — ADRs land at `experiment` / `implement`)
- **L3 skill referenced**: `~/.windsurf/skills/literature-review/SKILL.md` (procedure adapted to import mode; deviation noted in §1 Methodology)
- **Kickoff plan**: `~/.windsurf/plans/kickoff-cascade-d-horus-362eef.md` §4 M2D.3
