# ---
# title: "fatura2-invoices (English synthetic)"
# subtitle: "Chapter 2 — 10K NER-tagged invoice images across 50 templates"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-fatura2.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # fatura2-invoices {#sec-fatura2}
#
# This chapter characterizes the **FATURA2 invoices** dataset
# ([HuggingFace `mathieu1256/FATURA2-invoices`](https://huggingface.co/datasets/mathieu1256/FATURA2-invoices),
# CC-BY-4.0): 10,000 synthetic English invoice images, generated from 50
# distinct layouts via per-template randomization of names, addresses,
# dates, and amounts (Limam et al. 2023, [arXiv:2311.11856](https://arxiv.org/abs/2311.11856)).
# Each invoice ships with per-token NER tags + bounding boxes encoded
# in HuggingFace-Transformers-compatible parquet — directly consumable
# by LayoutLMv3-class models.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical 7
# sections (Provenance / Composition / Sample inspection / Distributional
# properties / HORUS-relevance / Anomalies / Observations log) + a
# Datasheet entry in the consolidated appendix.
#
# **HARKing safeguards** (per brainstorm v2 §2 + ADR-025): this is a
# DESCRIPTIVE-only EDA. Hypothesis-shaped patterns surfaced during
# inspection go to §7 Exploratory observations log, NOT into H1–H6.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-fatura2-setup}
#
# Per `horus-config-discipline`: ALL knobs live in `configs/eda-fatura2.yaml`.

# %%
from __future__ import annotations

import io
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image

from horus.config import ExperimentConfig
from horus.eda import fatura2_loader as fl
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
# Default for interactive runs. Quarto Books overrides via the `params:`
# block in this file's YAML frontmatter; `make eda` overrides via
# `quarto render -P cfg_path:...`; `make experiment` overrides via
# papermill's parameter-cell-prepend.
cfg_path: str = "configs/eda-fatura2.yaml"


# %%
# Repo root: walk up from cwd looking for `pyproject.toml`. Robust to
# Quarto Books / papermill / direct interactive cwd state (per the
# pattern adopted in chapter 1; see `experiments/01-zugferd.py`).
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
assert cfg.eda is not None, (
    f"Config at {_cfg_resolved} must declare an `eda:` section per ADR-024 "
    "+ horus-config-discipline."
)
EDA = cfg.eda
set_global_seed(cfg.seed)

CORPUS_ROOT = (
    EDA.corpus_root
    if EDA.corpus_root.is_absolute()
    else REPO_ROOT / EDA.corpus_root
)

print("HORUS EDA — chapter 2 (fatura2-invoices)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
if EDA.expected_min_examples is not None:
    print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire fatura2 first; see "
        "data/raw/english/fatura2-invoices/MANIFEST.md."
    )

# %%
# Editorial palette + styling. Same FT/NYT-influenced muted aesthetic as
# chapter 1 for cross-chapter visual consistency.
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
pd.set_option("display.width", 120)

# %% [markdown]
# ---
#
# # 1. Provenance {#sec-fatura2-provenance}
#
# **Datasheets §3.1 Motivation.** Origin / license / retrieval recipe /
# MANIFEST verification. Source archival stub:
# [`docs/sources/datasets/fatura2-invoices.md`](../docs/sources/datasets/fatura2-invoices.md).

# %%
# ---------------------------------------------------------------------------
# Read MANIFEST.md frontmatter for provenance assertions.
# ---------------------------------------------------------------------------
manifest_path = CORPUS_ROOT / "MANIFEST.md"
manifest_text = manifest_path.read_text(encoding="utf-8")
print(f"MANIFEST: {manifest_path}")
print(f"  size: {manifest_path.stat().st_size} bytes")
print()
# Extract key frontmatter fields by simple line search (avoid heavy YAML dep).
for key in (
    "slug",
    "language",
    "source_url",
    "license_spdx",
    "retrieved_date",
    "commit_sha",
    "file_count",
    "total_bytes",
    "sha256_aggregate",
    "sample_load_passed",
    "acquisition_status",
):
    for line in manifest_text.splitlines():
        if line.startswith(f"{key}:"):
            print(f"  {line}")
            break

# %% [markdown]
# **Discussion §1 (Provenance)**:
#
# - **License**: CC-BY-4.0 — permits research + commercial use with attribution.
#   This is the most permissive license among the 7 datasets in the HORUS
#   substrate; only `parsee-ai-invoices-example` (MIT) is comparable.
# - **Provenance chain**: HuggingFace Hub commit
#   `bcbb2fbb3c4701b87f5659ecbfbc55ad695aac21` (2024-02-18) → git-clone →
#   sha256-sealed in MANIFEST.md (verifiable with
#   `make data-manifest SLUG=fatura2-invoices LANG=english`).
# - **Original paper**: Limam, M., Dhiaf, M., & Kessentini, Y. (2023).
#   *FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis
#   and Understanding.* arXiv:2311.11856. The HuggingFace `mathieu1256`
#   port repackages the LayoutLMv3-compatible split + adds `.parquet`
#   shards for direct `datasets.load_dataset()` use.
# - **Acquisition status**: `completed` (MANIFEST `acquisition_status:
#   completed` + `sample_load_passed: true`); the dataset is fully on
#   disk + spot-checked via PAR1 magic-byte verification.

# %% [markdown]
# ---
#
# # 2. Composition {#sec-fatura2-composition}
#
# **Datasheets §3.2.** File count / format breakdown / size-on-disk /
# language / label/annotation type / schema.

# %%
# ---------------------------------------------------------------------------
# File-level walk: discover parquet files + their row counts.
# ---------------------------------------------------------------------------
files = fl.walk(CORPUS_ROOT)
files["size_mb"] = (files["size_bytes"] / (1024 * 1024)).round(1)
print("Parquet files on disk:")
print(files[["filename", "split", "size_mb", "n_rows"]].to_string(index=False))

n_total = int(files["n_rows"].sum())
print(f"\nTotal examples: {n_total}")
if EDA.expected_min_examples is not None and n_total < EDA.expected_min_examples:
    print(
        f"⚠ Total {n_total} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"✓ Total {n_total} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
# ---------------------------------------------------------------------------
# Per-row schema characterization — load the test split (smaller; faster).
# ---------------------------------------------------------------------------
df = fl.load_examples(CORPUS_ROOT, split="all")
print(f"Loaded {len(df)} examples (train + test concatenated)")
print(f"Columns: {list(df.columns)}")
print()
print("Schema per row (HuggingFace LayoutLMv3 format):")
print("  - id:               unique invoice ID (e.g., '6437')")
print("  - image_path:       'TemplateNN_InstanceMM.jpg'")
print("  - template_id:      parsed 'TemplateNN'")
print("  - instance_id:      parsed integer M")
print("  - num_tokens:       count of OCR'd tokens")
print("  - unique_ner_tags:  set of distinct NER class IDs in this row")
print("  - bbox_count:       count of bounding boxes (= num_tokens for well-formed rows)")
print("  - image_bytes_len:  JPEG payload size in bytes")

# %%
# ---------------------------------------------------------------------------
# Per-split row counts vs MANIFEST expectations.
# ---------------------------------------------------------------------------
split_counts = df["split"].value_counts().to_frame("n_rows")
split_counts["expected"] = [8600, 1400]  # per HF dataset card
split_counts["match"] = split_counts["n_rows"] == split_counts["expected"]
split_counts

# %% [markdown]
# **Discussion §2 (Composition)**:
#
# - **2 parquet files** (train + test) totaling **10,000 invoice rows**;
#   per-row JPEG bytes embedded directly (no separate image directory).
#   This is HuggingFace's recommended "self-contained dataset" layout —
#   reproducible with one `datasets.load_dataset()` call.
# - **24 NER classes** (per the FATURA paper §3.2: `TABLE` / `LOGO` /
#   `DATE` / `NUMBER` / `SELLER ADDRESS` / `BUYER ADDRESS` / `TOTAL` /
#   etc.). The HuggingFace port encodes these as `int64` IDs without an
#   embedded `ClassLabel` mapping — § 4 below characterizes the empirical
#   distribution; the full label list is in the FATURA paper.
# - **Per-token bounding boxes** (image-pixel coordinates) make this
#   directly LayoutLMv3-trainable. Token count + bbox count have a 1:1
#   correspondence (verified in the loader's `bbox_count == num_tokens`
#   invariant, tested in `tests/test_eda_fatura2_loader.py`).
# - **English language** (only); not aligned with the German thesis
#   target population. See §5 HORUS-relevance for scope discussion.

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-fatura2-samples}
#
# **Datasheets §3.3.** Random-sample load + visual; verify the
# MANIFEST's `sample_load_passed: true` claim holds with current code.

# %%
# ---------------------------------------------------------------------------
# Pick 4 random invoices from the test split + show image + tokens + tags.
# ---------------------------------------------------------------------------
rng = np.random.default_rng(cfg.seed)
sample_ids = (
    df[df["split"] == "test"]
    .sample(n=4, random_state=rng.bit_generator)["id"]
    .tolist()
)
print(f"Sampled invoice IDs (seed={cfg.seed}): {sample_ids}")

# %%
# ---------------------------------------------------------------------------
# Static figure: 2×2 grid of sampled invoice thumbnails.
# ---------------------------------------------------------------------------
# | label: fig-fatura2-samples
# | fig-cap: "Random sample of 4 fatura2 invoices (test split). Templates differ; logos / table layouts / per-field positioning vary across the 50 layouts."
fig, axes = plt.subplots(2, 2, figsize=(9, 11))
for ax, rid in zip(axes.flat, sample_ids, strict=False):
    img_bytes = fl.decode_image_bytes(CORPUS_ROOT, rid)
    if img_bytes is None:
        ax.set_axis_off()
        continue
    img = Image.open(io.BytesIO(img_bytes))
    ax.imshow(img)
    template = df[df["id"] == rid]["template_id"].iloc[0]
    n_toks = int(df[df["id"] == rid]["num_tokens"].iloc[0])
    ax.set_title(f"id={rid}  •  {template}  •  {n_toks} tokens", fontsize=10)
    ax.axis("off")
plt.tight_layout()
plt.show()

# %%
# ---------------------------------------------------------------------------
# Inspect one row's tokens + tags side-by-side.
# ---------------------------------------------------------------------------
import pyarrow.parquet as pq

inspect_path = CORPUS_ROOT / "data" / "test-00000-of-00001.parquet"
raw = pq.read_table(inspect_path).to_pandas().head(1)
tokens = list(raw["tokens"].iloc[0])[:20]
tags = list(raw["ner_tags"].iloc[0])[:20]
bboxes = [list(bb) for bb in raw["bboxes"].iloc[0][:5]]
print(f"First-row tokens (first 20): {tokens}")
print(f"First-row ner_tags (first 20): {tags}")
print(f"First-row bboxes (first 5):  {bboxes}")

# %% [markdown]
# **Discussion §3 (Sample inspection)**:
#
# - The 4-sample render confirms the MANIFEST's
#   `sample_load_passed: true` claim holds end-to-end with the current
#   loader code (PAR1 → JPEG decode → PIL render → matplotlib display).
# - Visual inspection of the 4 thumbnails surfaces the FATURA paper's
#   claim: each template has a distinctive layout (logo position, table
#   structure, header / footer organization), with per-instance content
#   randomization (names, addresses, line items) layered on top.
# - The token + bbox + ner_tag triple per row is the standard LayoutLM
#   input format; no preprocessing required to feed into a LayoutLMv3
#   training loop.

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-fatura2-distributions}
#
# Per-row feature distributions: tokens-per-invoice, template balance,
# NER-tag distribution, image-size distribution.

# %%
# ---------------------------------------------------------------------------
# Tokens-per-invoice distribution.
# ---------------------------------------------------------------------------
# | label: fig-fatura2-tokens-hist
# | fig-cap: "Tokens-per-invoice distribution across all 10,000 fatura2 invoices. Min/median/max: see annotation. Right-skewed long tail = invoice-with-many-line-items templates."
fig, ax = plt.subplots(figsize=(8, 4))
n_tokens = df["num_tokens"]
sns.histplot(
    n_tokens,
    bins=40,
    ax=ax,
    color=PALETTE[0],
    edgecolor="white",
    linewidth=0.4,
)
ax.set_xlabel("Tokens per invoice")
ax.set_ylabel("Number of invoices")
ax.set_title("Tokens-per-invoice distribution (10,000 invoices)", loc="left")
ax.axvline(n_tokens.median(), color=PALETTE[3], linestyle="--", linewidth=1.5)
ax.text(
    n_tokens.median() + 2,
    ax.get_ylim()[1] * 0.92,
    f"median = {int(n_tokens.median())}",
    fontsize=9,
    color=PALETTE[3],
)
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

print(
    f"Tokens-per-invoice: min={int(n_tokens.min())}  "
    f"median={int(n_tokens.median())}  "
    f"mean={n_tokens.mean():.1f}  "
    f"max={int(n_tokens.max())}"
)

# %%
# ---------------------------------------------------------------------------
# Template balance: how evenly distributed are the 50 templates?
# ---------------------------------------------------------------------------
template_counts = df["template_id"].value_counts().sort_index()
print(f"Distinct templates: {len(template_counts)}")
print(f"Per-template invoice count: min={template_counts.min()} "
      f"median={int(template_counts.median())} max={template_counts.max()}")
print(
    f"\nPer-template stdev: {template_counts.std():.1f}  "
    f"(coefficient of variation: {template_counts.std() / template_counts.mean():.3f})"
)

# %%
# ---------------------------------------------------------------------------
# Static figure: per-template invoice count.
# ---------------------------------------------------------------------------
# | label: fig-fatura2-template-counts
# | fig-cap: "Per-template invoice count across the 50 fatura2 layouts. Near-uniform distribution = balanced template coverage."
fig, ax = plt.subplots(figsize=(11, 4.5))
# Sort by template integer ID for ordering rather than alphabetical.
tc_sorted = template_counts.reindex(
    sorted(template_counts.index, key=lambda s: int(s.replace("Template", "")))
)
ax.bar(
    range(len(tc_sorted)),
    tc_sorted.values,
    color=PALETTE[1],
    edgecolor="white",
    linewidth=0.3,
)
ax.set_xlabel("Template ID")
ax.set_ylabel("Number of invoices")
ax.set_title("Per-template invoice count (50 layouts)", loc="left")
ax.set_xticks(range(0, len(tc_sorted), 5))
ax.set_xticklabels([tc_sorted.index[i].replace("Template", "T") for i in range(0, len(tc_sorted), 5)])
ax.axhline(tc_sorted.mean(), color=PALETTE[3], linestyle="--", linewidth=1, alpha=0.7)
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# ---------------------------------------------------------------------------
# NER-tag distribution (across 100 sampled rows for tractability).
# ---------------------------------------------------------------------------
sample_for_tags = df.sample(n=min(len(df), 1000), random_state=cfg.seed)
all_observed_tags: list[int] = []
for tag_set in sample_for_tags["unique_ner_tags"]:
    all_observed_tags.extend(int(t) for t in tag_set)
tag_counter = Counter(all_observed_tags)
print(f"Distinct NER tag IDs observed (in 1000-row sample): {sorted(tag_counter.keys())}")
print(f"Top tag-ID frequencies (rows-where-tag-appears): ")
for tag_id, n in sorted(tag_counter.most_common(), key=lambda x: x[0]):
    print(f"  Tag {tag_id:>3d}: {n} rows ({100 * n / len(sample_for_tags):.1f}%)")

# %%
# ---------------------------------------------------------------------------
# Image-bytes size distribution (per-JPEG payload).
# ---------------------------------------------------------------------------
# | label: fig-fatura2-image-sizes
# | fig-cap: "Per-invoice JPEG payload size distribution (KB). Templates with logos / large tables produce larger payloads."
fig, ax = plt.subplots(figsize=(8, 4))
sizes_kb = df["image_bytes_len"] / 1024
sns.histplot(
    sizes_kb,
    bins=40,
    ax=ax,
    color=PALETTE[2],
    edgecolor="white",
    linewidth=0.4,
)
ax.set_xlabel("JPEG payload (KB)")
ax.set_ylabel("Number of invoices")
ax.set_title("JPEG payload size distribution (10,000 invoices)", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

print(f"JPEG payload (KB): min={sizes_kb.min():.1f}  "
      f"median={sizes_kb.median():.1f}  "
      f"mean={sizes_kb.mean():.1f}  "
      f"max={sizes_kb.max():.1f}")

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Tokens-per-invoice** ranges from ~28 to ~140, with a median of
#   ~60. Compares to the ZUGFeRD corpus where the canonical 16-field
#   ground-truth schema produces ~10–20 IS_GT fields per invoice (see
#   chapter @sec-zugferd §5). fatura2's token-level granularity is
#   ~3-7× finer — it labels individual address words, currency symbols,
#   and amount digits, not just field-level concepts.
# - **Template balance**: 50 layouts, with per-template invoice count
#   centered around 200 (10000 / 50) and low coefficient of variation.
#   Generation was clearly designed to produce uniform per-template
#   coverage — useful for evaluating template-shift robustness.
# - **NER tag distribution**: observed integer IDs in the 1000-row
#   sample fall in `{1..6, 10..13, ...}`. The full 24-class label table
#   is in the FATURA paper §3.2; the loader exposes the raw IDs since
#   the HuggingFace port doesn't embed a `ClassLabel` mapping.
# - **JPEG payload size** distribution is moderately spread (~30–100 KB
#   per image), reflecting per-template logo + table-rule density
#   variation. No catastrophic outliers.

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-fatura2-horus}
#
# Which thesis evaluation paths can use this dataset? **Descriptive only**;
# this section surfaces the question, NOT a scope decision (decisions live
# in @sec-cross-corpus / future ADRs).

# %% [markdown]
# **Candidate uses for HORUS**:
#
# 1. **VLM training pool**: 10,000 invoice images with token-level NER
#    annotations is a large, clean training substrate. Per the
#    `cfg.eda.fine_tuning_anchors` literature anchors:
#    - LoRA fine-tuning min: 200 examples → fatura2 alone is **50×**
#      above that floor.
#    - LoRA target: 2,000 examples → fatura2 alone is **5×** above.
#    - Eval-min for thesis-defendable F1: 100 examples → fatura2 test
#      split (1,400 examples) alone is **14×** above.
# 2. **Cross-language transfer test bed**: fatura2 is English-only;
#    the HORUS thesis target population is German-speaking
#    `Steuerberater` / `Wirtschaftsprüfer`. A model fine-tuned on
#    fatura2 + ZUGFeRD German (chapter @sec-zugferd) may exhibit
#    interesting cross-language transfer patterns; the MULTILINGUAL
#    chapter @sec-omnidocbench will broaden this further.
# 3. **Template-shift robustness benchmark**: 50 distinct layouts
#    with uniform per-template coverage make this an ideal
#    held-out-template evaluation: train on 40 templates, test on 10
#    held out, measure F1 degradation. NOT a thesis hypothesis (per
#    HARKing safeguards) but worth flagging as an *Exploratory observation*.
# 4. **NOT directly comparable to ZUGFeRD's 16-field schema**: fatura2
#    uses token-level NER tags (24 classes); ZUGFeRD chapter @sec-zugferd
#    uses field-level F1 (16 EN16931 fields). Cross-dataset F1 requires
#    a label-mapping (token-NER → 16-field-EN16931) that the chapter
#    @sec-cross-corpus will surface as a Decision Register entry.
# 5. **Synthetic, NOT real**: per the FATURA paper, content is
#    randomized — names / addresses / amounts / dates are
#    template-faithful but NOT drawn from real consumer invoices. The
#    HORUS thesis-defense quality bar requires real-world Belege as
#    held-out test (per the locked plan + brainstorm v2 §9.3); fatura2
#    is dev/training substrate, not the held-out test set.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-fatura2-anomalies}
#
# License caveats, schema gaps, mislabeled files, missing-by-design
# subsets.

# %% [markdown]
# - **License caveat**: CC-BY-4.0 — permissive, but research / commercial
#   use requires attribution to Limam et al. 2023 + the HuggingFace
#   `mathieu1256` port. Both are cited in the references chapter.
# - **Schema gap — no embedded label mapping**: the HuggingFace parquet
#   ports the FATURA `ner_tags` as raw `int64` IDs, *without* an
#   embedded `ClassLabel` table mapping `0 → "O"`, `1 → "B-DATE"`, etc.
#   The full mapping is in Limam et al. 2023 §3.2 + Table 2; downstream
#   chapters that need to interpret tag semantics must consult the
#   paper. Not a corpus error — a HuggingFace port simplification.
# - **Synthetic content limitation**: per the FATURA paper §3.3, all
#   text content (names, addresses, amounts) is randomized from curated
#   repositories. Logos are generated via latent-diffusion text-to-image.
#   No real-world OCR noise (paper handling artefacts, scan tilt,
#   overlapping stamps, handwritten annotations). The dataset
#   characterizes "what a perfect-OCR pipeline sees" — useful for
#   methodology validation, but NOT a stand-in for real Belege noise.
# - **English-only scope**: 1 of 7 datasets in the HORUS substrate
#   addresses the German thesis target. Cross-language transfer is
#   testable but requires acknowledging the locale gap.
# - **No multi-page invoices**: every fatura2 example is single-page
#   (verified empirically: every row has exactly one image). Multi-page
#   handling is exercised by ZUGFeRD chapter @sec-zugferd (which has
#   1-4 page invoices); fatura2 alone cannot validate multi-page
#   robustness.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-fatura2-observations}
#
# Per the `bidirectional-learning-pipe` rule + ADR-025 §"Per-chapter
# content template": hypothesis-shaped patterns surfaced during
# inspection captured HERE, NOT retro-fitted into H1–H6.

# %% [markdown]
# **Observations from this Phase C iteration**:
#
# 1. **Template balance suggests held-out-template evaluation is
#    feasible**: with ~200 examples per template across 50 templates,
#    a held-out 10-template / 40-template split would yield ~2,000
#    test + ~8,000 training examples. Worth flagging as a candidate
#    H7 (template-shift robustness) for a future hypothesis-design
#    round; NOT promoted to H1–H6 here per HARKing discipline.
# 2. **Token-level vs field-level annotation gap**: fatura2's 24-class
#    token-NER schema does NOT have a 1:1 mapping to ZUGFeRD's 16-field
#    EN16931 schema. Cross-dataset F1 comparison (e.g., "fine-tuned on
#    fatura2 → tested on ZUGFeRD") requires an explicit label-mapping
#    table. This is a Decision Register entry for chapter
#    @sec-cross-corpus.
# 3. **JPEG-only renders, no PDF artefacts**: fatura2 ships rasterized
#    JPEGs; the OCR-route validation that the HORUS thesis claims is
#    fundamentally different on JPEGs vs PDFs (no embedded XML / no
#    PDF-text-layer fallback). Worth surfacing in chapter
#    @sec-cross-corpus alongside the Hetzner unstructured PDF
#    (chapter @sec-zugferd §1) as the "OCR-route candidate" set.
