# ---
# title: "Parsee AI invoices-example (bilingual MIT Q-and-A sample)"
# subtitle: "Chapter 5 — 45 prompt and truth-answer pairs from 15 underlying invoice PDFs"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-parsee-ai.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # Parsee AI invoices-example {#sec-parsee-ai}
#
# This chapter characterizes the **Parsee AI Invoices Example** dataset
# ([HuggingFace `parsee-ai/invoices-example`](https://huggingface.co/datasets/parsee-ai/invoices-example),
# MIT license): 45 prompt / truth-answer pairs generated from 15
# underlying invoice PDFs publicly accessible on `app.parsee.ai`.
# Designed for evaluating LLMs on RAG-style invoice question answering
# using the parsee-core extraction toolkit (parsee-core v0.1.3.11 per
# the source `README.md`). Tiny by design — the goal was an evaluation
# fixture, not a training pool.
#
# **Bilingual (en + de).** Unique among the HORUS 7-dataset substrate:
# the only dataset that ships German content out of the box alongside
# English. The MANIFEST's `language: english` is technically wrong —
# the source `README.md` declares `en, de` and empirical inspection
# (§4) confirms a substantial German signal in roughly 40% of rows.
# Flagged in §6.
#
# **Q-and-A shaped, NOT NER-shaped.** Unlike fatura2's token-NER
# (chapter @sec-fatura2) or FUNSD's form-entity labels (chapter
# @sec-funsd), parsee-ai ships parsed full-prompt → ground-truth-answer
# pairs in a structured `(key): value\nSources: [N]` format. The
# parsee-core toolkit then evaluates an LLM's free-text response against
# the structured truth. This makes it a **RAG-eval substrate** for
# Layer 3 analytical-query smoke testing, not extraction training data.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical
# 7-section template + a Datasheet entry in the consolidated appendix.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-parsee-ai-setup}

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from horus.config import ExperimentConfig
from horus.eda import parsee_ai_loader as pl
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
cfg_path: str = "configs/eda-parsee-ai.yaml"


# %%
def _find_repo_root() -> Path:
    cur = Path.cwd().resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return cur


REPO_ROOT = _find_repo_root()
_cfg_resolved = Path(cfg_path)
if not _cfg_resolved.is_absolute():
    _cfg_resolved = REPO_ROOT / _cfg_resolved

cfg = ExperimentConfig.from_yaml(_cfg_resolved)
assert cfg.eda is not None
EDA = cfg.eda
set_global_seed(cfg.seed)

CORPUS_ROOT = (
    EDA.corpus_root
    if EDA.corpus_root.is_absolute()
    else REPO_ROOT / EDA.corpus_root
)

print("HORUS EDA — chapter 5 (parsee-ai-invoices-example)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire parsee-ai-invoices-example first; see "
        "data/raw/english/parsee-ai-invoices-example/MANIFEST.md."
    )

_styles = apply_styles(
    palette_static=EDA.palette_static,
    palette_interactive=EDA.palette_interactive,
    n_colors=12,
)
PALETTE = _styles.palette

plt.rcParams["figure.dpi"] = EDA.figure_dpi
plt.rcParams["savefig.dpi"] = EDA.figure_dpi
plt.rcParams["axes.titleweight"] = "semibold"
plt.rcParams["axes.titlepad"] = 14

pd.set_option("display.max_rows", None)
pd.set_option("display.min_rows", 25)

# %% [markdown]
# ---
#
# # 1. Provenance {#sec-parsee-ai-provenance}
#
# **Datasheets §3.1 Motivation.** Source archival stub:
# [`docs/sources/datasets/parsee-ai-invoices-example.md`](../docs/sources/datasets/parsee-ai-invoices-example.md).

# %%
manifest_path = CORPUS_ROOT / "MANIFEST.md"
manifest_text = manifest_path.read_text(encoding="utf-8")
print(f"MANIFEST: {manifest_path}")
for key in (
    "slug", "language", "source_url", "license_spdx",
    "retrieved_date", "commit_sha", "file_count", "total_bytes",
    "sha256_aggregate", "sample_load_passed", "acquisition_status",
):
    for line in manifest_text.splitlines():
        if line.startswith(f"{key}:"):
            print(f"  {line}")
            break

# %% [markdown]
# **Discussion §1 (Provenance)**:
#
# - **License**: MIT. **The most permissive license among the HORUS
#   7-dataset substrate.** Production HORUS deployment can train on
#   parsee-ai content without legal friction (parallels only
#   `fatura2-invoices` CC-BY-4.0, chapter @sec-fatura2). Surfaces in
#   the cross-corpus license-tier matrix (chapter @sec-cross-corpus).
# - **Provenance chain**: HuggingFace Hub commit
#   `85fd1e51ed6e2975dcf86b98b5d4256e72002e5e` (2024-03-20) →
#   `git clone` → sha256-sealed in MANIFEST.md.
# - **Underlying source PDFs**: 15 invoice PDFs accessible at
#   `https://app.parsee.ai/documents/view/<source_identifier>` (the
#   `source_identifier` column points to the public URL). NOT
#   downloaded to disk — the parquet ships extracted features +
#   ground-truth only, not the raw PDFs themselves.
# - **Generation**: rows produced via `parsee-core v0.1.3.11` per the
#   source README; 45 = 15 PDFs × 3 question-element types
#   (`general0`, `general1`, `general2`). Empirically confirmed in §2.
# - **Acquisition status**: `completed`; `sample_load_passed: true`
#   (PAR1 magic-byte spot-check per MANIFEST).

# %% [markdown]
# ---
#
# # 2. Composition {#sec-parsee-ai-composition}
#
# **Datasheets §3.2.** File count / format / schema.

# %%
files = pl.walk(CORPUS_ROOT)
print(f"Parquet files on disk:")
print(files[["filename", "size_bytes", "n_rows"]].to_string(index=False))
n_total = int(files["n_rows"].sum())

if n_total < EDA.expected_min_examples:
    print(
        f"\n⚠ Total {n_total} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"\n✓ Total {n_total} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
df = pl.load_examples(CORPUS_ROOT)
print(f"Loaded {len(df)} rows\n")
print("Per-row schema (parsee Q-and-A pair):")
print("  - source_identifier:  SHA256-like hash of source PDF")
print("                        (https://app.parsee.ai/documents/view/<id>)")
print("  - template_id:        parsee extraction-template ObjectId")
print("  - element_identifier: short label for the asked field")
print("                        (e.g., general0 / general1 / general2)")
print("  - prompt_text:        full RAG-style prompt supplied to the LLM")
print("  - truth_text:         structured truth answer")
print("                        ((key): value sections + Sources: [N] trailer)")
print("  - prompt_len / truth_len: character lengths (derived)")
print("  - n_truth_sections:   count of (key): value blocks in truth_text")
print("  - main_answer:        extracted (main question): VALUE if present")

# %%
print("Per-row distinct-value counts:")
print(f"  source_identifier  (underlying PDFs):    {df['source_identifier'].nunique()}")
print(f"  template_id        (parsee templates):   {df['template_id'].nunique()}")
print(f"  element_identifier (field-types):        {df['element_identifier'].nunique()}")
print()
print("element_identifier value counts:")
print(df["element_identifier"].value_counts().to_string())

# %%
print("Per-row length summary statistics:")
for col in ("prompt_len", "truth_len", "n_truth_sections"):
    s = df[col]
    print(
        f"  {col:<20s} min={int(s.min()):>5d} "
        f"median={int(s.median()):>5d} "
        f"mean={s.mean():>7.1f} "
        f"max={int(s.max()):>5d}"
    )

# %% [markdown]
# **Discussion §2 (Composition)**:
#
# - **45 rows = 15 source PDFs × 3 element types**. Empirically
#   confirmed above: every PDF gets queried for `general0` + `general1`
#   + `general2` (15 of each). This is a uniformly-balanced fixture,
#   not a randomly-sampled corpus.
# - **Single extraction template**: all 45 rows use the same
#   `template_id` (one parsee-internal extraction config). This means
#   the dataset cannot characterize template-shift robustness (compare
#   chapter @sec-fatura2 with its 50 templates) — but the template
#   uniformity is appropriate for its intended use as a controlled
#   LLM-evaluation fixture.
# - **Prompt length is substantial** (1668-6836 chars, median ~2.6K):
#   each prompt is a full RAG-style context with fragments + question.
#   Truth answers are short (21-88 chars, median ~34) — short-form QA,
#   not free-form generation. This shape is closer to extractive QA
#   (SQuAD-style) than to invoice-NER (LayoutLM-style).
# - **No images, no bboxes, no per-token data**: the parquet is pure
#   text features. The underlying invoice visuals live on `app.parsee.ai`
#   behind the `source_identifier` URL; not packaged in the dataset.

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-parsee-ai-samples}
#
# **Datasheets §3.3.** Inspect one full Q-and-A row to surface the
# data shape concretely; verify the MANIFEST's `sample_load_passed: true`
# claim holds.

# %%
rng = np.random.default_rng(cfg.seed)
sample_idx = int(rng.integers(0, len(df)))
sample = df.iloc[sample_idx]

print(f"Sampled row {sample_idx} of {len(df)}:")
print(f"  source_identifier:  {sample['source_identifier']}")
print(f"  template_id:        {sample['template_id']}")
print(f"  element_identifier: {sample['element_identifier']}")
print(f"  prompt_len:         {sample['prompt_len']}")
print(f"  truth_len:          {sample['truth_len']}")
print()
print("Prompt (first 400 chars):")
print(sample["prompt_text"][:400])
print("[... truncated ...]")
print()
print(f"Full truth_text:")
print(sample["truth_text"])
print()
print("Parsed truth_text (parsee structured format):")
parsed = pl.parse_truth_answer(sample["truth_text"])
for k, v in parsed.items():
    print(f"  {k!r}: {v!r}")

# %% [markdown]
# **Discussion §3 (Sample inspection)**:
#
# - The sample row above confirms the MANIFEST's
#   `sample_load_passed: true` claim holds end-to-end with the current
#   loader code (PAR1 read → string column → parse_truth_answer →
#   structured dict).
# - The parsed-truth view exposes parsee's evaluation format: each
#   element-identifier produces a structured answer block with
#   `(main question)` / `(meta0)` / `(meta1)` keys + a `Sources: [N]`
#   trailer pointing at the underlying RAG-fragment indices. parsee-core
#   uses this format to score LLM responses field-by-field (not just
#   one big string-match).
# - The prompt-text view shows the RAG-style context structure: the
#   LLM receives numbered text fragments + a question; the prompt
#   header explains the evaluation protocol (*"answer based on text
#   fragments…"*, etc.).

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-parsee-ai-distributions}

# %%
# Per-element prompt-length comparison.
print("Per-element prompt-length summary:")
for elem in sorted(df["element_identifier"].unique()):
    s = df[df["element_identifier"] == elem]["prompt_len"]
    print(
        f"  {elem:<12s} min={int(s.min()):>5d} "
        f"median={int(s.median()):>5d} "
        f"mean={s.mean():>7.1f} "
        f"max={int(s.max()):>5d}"
    )

# %%
# | label: fig-parsee-prompt-lens
# | fig-cap: "Per-element prompt-length distribution across the 45 parsee-ai rows. The three element types (general0 / general1 / general2) draw from the same underlying PDFs but produce different prompt sizes — element selection drives the RAG-context window size."
fig, ax = plt.subplots(figsize=(8, 4))
sns.boxplot(
    data=df,
    x="element_identifier",
    y="prompt_len",
    palette=[PALETTE[0], PALETTE[2], PALETTE[5]],
    ax=ax,
    hue="element_identifier",
    legend=False,
)
ax.set_xlabel("Element identifier")
ax.set_ylabel("Prompt length (characters)")
ax.set_title("Prompt-length distribution per element type", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# main_answer extraction success rate per element.
print("main_answer extraction success rate (rows where parse_truth_answer found a (main question) section):")
for elem in sorted(df["element_identifier"].unique()):
    sub = df[df["element_identifier"] == elem]
    n_main = int(sub["main_answer"].notna().sum())
    print(f"  {elem:<12s} {n_main:>3d}/{len(sub)}")

# %%
# Bilingual signal: count rows containing German-language indicators.
de_indicators = (
    "Rechnung", "Datum", "Betrag", "MwSt", "USt", "€",
    "Nettobetrag", "Gesamtbetrag", "Lieferung", "Steuer",
)
de_hit_per_row = df["prompt_text"].apply(
    lambda txt: sum(1 for w in de_indicators if w in txt)
)
n_de_hits = int((de_hit_per_row > 0).sum())
print(f"Rows with at least one German-language indicator: {n_de_hits}/{len(df)}")
print(f"Per-row German-indicator-hit count summary:")
print(
    f"  min={int(de_hit_per_row.min())} "
    f"median={int(de_hit_per_row.median())} "
    f"max={int(de_hit_per_row.max())}"
)

# %%
# | label: fig-parsee-bilingual
# | fig-cap: "German-language indicator hit count per row. A simple keyword scan (`Rechnung`, `MwSt`, `€`, `Betrag`, etc.) over the 45 prompts confirms a substantial German signal — the dataset is genuinely bilingual, not the English-only label the MANIFEST claims."
fig, ax = plt.subplots(figsize=(8, 3.5))
sns.histplot(
    de_hit_per_row,
    bins=range(0, int(de_hit_per_row.max()) + 2),
    ax=ax,
    color=PALETTE[1],
    edgecolor="white",
    linewidth=0.4,
    discrete=True,
)
ax.set_xlabel("German-language indicator hits per row")
ax.set_ylabel("Number of rows")
ax.set_title("Bilingual signal across the 45 parsee-ai rows", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Per-PDF row count (sanity-check: every PDF should appear 3 times).
per_pdf = df["source_identifier"].value_counts()
print(f"Per-PDF row count summary (expected exactly 3 each):")
print(f"  Distinct PDFs:   {len(per_pdf)}")
print(f"  Rows per PDF:    min={per_pdf.min()} max={per_pdf.max()}")
assert (per_pdf == 3).all(), (
    "Empirical invariant from MANIFEST + README: 15 PDFs × 3 elements = 45 rows. "
    f"Found per-PDF row counts: {dict(per_pdf)}"
)
print(f"  All 15 PDFs appear exactly 3 times each ✓")

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Per-element prompt-length variation**: the three element types
#   draw from the same underlying 15 PDFs but produce different
#   prompt-context sizes. Element selection (which field the LLM is
#   asked about) is what drives the RAG context-window size, not the
#   underlying PDF.
# - **main_answer extraction is element-dependent**: only `general0`
#   rows have a `(main question): VALUE` section. `general1` and
#   `general2` produce different truth-structure shapes (meta blocks,
#   line-item blocks, etc.) — a reminder that parsee's evaluation
#   format is **template + element specific**, not a single uniform
#   schema across rows.
# - **Bilingual signal is real**: ~40% of rows contain German-language
#   indicators on a simple keyword scan. The MANIFEST's
#   `language: english` is technically wrong; the source README declares
#   `en, de`. Flagged in §6.
# - **Per-PDF uniformity**: every one of the 15 source PDFs produces
#   exactly 3 rows. The empirical invariant (15 × 3 = 45) is asserted
#   above; a violation would surface as an immediate `AssertionError`
#   during the chapter render.

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-parsee-ai-horus}

# %% [markdown]
# **Honest framing**: parsee-ai is the **bilingual MIT-licensed
# sanity-check fixture** in the HORUS substrate. NOT a primary
# training or evaluation substrate. Its HORUS thesis relevance is:
#
# 1. **Layer 3 analytical-query smoke**: per the brainstorm v2 §9
#    amendment (parsee-ai called out as the bilingual eval comparator),
#    this dataset can serve as a tiny, controlled fixture for early
#    Layer 3 (analytical query / RAG) smoke testing — *before*
#    investing in a custom en+de eval set built from the Belege.
# 2. **Bilingual eval anchor**: the only HORUS dataset that ships
#    de + en together. ZUGFeRD (chapter @sec-zugferd) is pure German;
#    fatura2 / FUNSD / OmniDocBench-English / inv-cdip are pure
#    English; CORD-v2 (chapter @sec-cord-v2) is Korean; OmniDocBench
#    is Chinese-dominant (chapter @sec-omnidocbench). parsee-ai is
#    the bilingual integration substrate.
# 3. **MIT license is unique among HORUS datasets**: combined with
#    fatura2's CC-BY-4.0 (chapter @sec-fatura2), parsee-ai forms the
#    "permissive-license" tier that production HORUS deployment can
#    train on (vs. the restrictive-license tier at @sec-omnidocbench /
#    @sec-funsd / @sec-inv-cdip). Surfaces in the cross-corpus
#    license-tier matrix.
# 4. **NOT a training pool**: 45 rows is ~4× below the LoRA
#    fine-tuning floor (`fine_tuning_anchors.lora_min_examples = 200`).
#    Useful only as eval/methodology fixture.
# 5. **NOT a direct invoice-extraction substrate**: the dataset ships
#    pre-parsed Q-and-A pairs, not raw OCR + bboxes. Cannot train an
#    extraction model; can only evaluate one whose output can be
#    matched against parsee's structured truth format.
# 6. **Q-and-A shape is methodologically distinct from extraction**:
#    parsee-ai measures "did the LLM answer this question correctly?"
#    whereas the other 6 HORUS datasets measure "did the model
#    correctly tag / label / extract these fields?" The schema gap
#    surfaces in the chapter @sec-cross-corpus label-schema overlap
#    section.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-parsee-ai-anomalies}

# %% [markdown]
# - **MANIFEST `language: english` is wrong**: the source `README.md`
#   declares `en, de` and §4 empirical evidence shows ~40% of rows
#   contain German content. The MANIFEST should read
#   `language: bilingual-en-de` or `language: en,de`. Surfaces as a
#   provenance discrepancy that future MANIFEST updates should fix
#   (acquisition-side, not loader-side). Captured here, not silently
#   fixed, per `bidirectional-learning-pipe`.
# - **Tiny size**: 45 rows total. Below LoRA floor; below eval-thesis
#   minimum (`eval_min_examples_for_thesis = 100`). Methodology
#   validator only.
# - **No raw PDFs locally**: the 15 underlying invoice PDFs live on
#   `app.parsee.ai` behind the `source_identifier` URL; the parquet
#   ships extracted features only. Cannot validate the
#   parsee-extraction pipeline end-to-end without fetching the PDFs
#   separately.
# - **Single extraction template**: all 45 rows share one parsee
#   `template_id`. Cannot characterize template-shift robustness
#   (unlike fatura2's 50 templates, chapter @sec-fatura2).
# - **No images, no bboxes, no per-token data**: the dataset is pure
#   text features; cannot serve any visual-extraction or
#   bbox-prediction evaluation.
# - **parsee-specific truth format**: the `(key): value\nSources: [N]`
#   structure is parsee-core's own evaluation convention, NOT a
#   widely-adopted standard. Comparing parsee F1 to LayoutLMv3 F1
#   (chapter @sec-fatura2) or OmniDocBench F1 (chapter
#   @sec-omnidocbench) requires a label-mapping that the chapter
#   @sec-cross-corpus Decision Register will surface.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-parsee-ai-observations}

# %% [markdown]
# Per the `bidirectional-learning-pipe` rule + ADR-025 §"Per-chapter
# content template": hypothesis-shaped patterns surfaced during
# inspection captured HERE, NOT retro-fitted into H1–H6.
#
# **Observations from this Phase C iteration**:
#
# 1. **MANIFEST language-tag drift is a systematic concern**: the
#    parsee-ai MANIFEST claims `language: english` despite the source
#    README declaring `en, de` and content evidence confirming a
#    substantial German signal. If this drift exists for parsee-ai,
#    similar drift may exist for OmniDocBench (whose
#    `language: multilingual` masks Chinese-dominance per chapter
#    @sec-omnidocbench §4). A Decision Register entry in chapter
#    @sec-cross-corpus should flag MANIFEST language tags as
#    "auto-detected, not authoritative" and surface a candidate
#    follow-up: a `make data-manifest-language-audit` target that
#    cross-checks MANIFEST language fields against per-row content
#    sampling.
# 2. **Q-and-A vs NER vs form-entity schema asymmetry**: parsee-ai
#    is the third distinct schema-shape in the HORUS substrate
#    (token-NER in fatura2 + form-entity-with-linking in FUNSD +
#    Q-and-A in parsee-ai + field-extraction in ZUGFeRD + layout
#    regions in OmniDocBench). Each schema requires a different
#    evaluation metric. The chapter @sec-cross-corpus label-schema
#    overlap section will need to surface "is there a unifying eval
#    metric across these schema shapes, or does HORUS need 4+ separate
#    F1 measurements per model?" as a methodology decision.
# 3. **Permissive license + tiny size combo is rare and valuable**:
#    MIT + 45 rows is the only HORUS dataset where the licensed-
#    deployable-fixture overlaps with the small-enough-to-iterate-on
#    constraint. The trade-off (tiny → not a training pool) is real,
#    but for early-stage methodology iteration this combo is
#    operationally useful and should NOT be discarded just because of
#    scale.
