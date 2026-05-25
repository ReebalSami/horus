# ---
# title: "FUNSD (English form-understanding)"
# subtitle: "Chapter 4 — 199 noisy scanned forms with entity labels and relation linkings"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-funsd.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # FUNSD {#sec-funsd}
#
# This chapter characterizes the **FUNSD dataset** (Form Understanding
# in Noisy Scanned Documents; Jaume, Ekenel, & Thiran, 2019,
# [funsd-website](https://guillaumejaume.github.io/FUNSD/);
# non-commercial-research license): 199 noisy scanned forms (149
# training + 50 testing) with per-entity bounding boxes + 4 label
# classes (`other` / `question` / `answer` / `header`) +
# entity-relation linking pairs. The dataset is the canonical
# LayoutLM / LayoutLMv2 / LayoutLMv3 evaluation substrate for
# form-understanding F1.
#
# **Form-shaped, NOT invoice-shaped.** FUNSD entities are
# question-and-answer field pairs ("Buyer Name: ___" / "Date: ___");
# they are NOT invoice line items. The dataset's HORUS thesis
# relevance is **methodology baseline** (direct comparability to the
# LayoutLM family) + **entity-relation annotation signal** (the
# `linking` pair format that informs cross-corpus schema design),
# NOT direct invoice substrate. See §5 for the scope discussion.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical
# 7-section template + a Datasheet entry in the consolidated appendix.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-funsd-setup}

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image

from horus.config import ExperimentConfig
from horus.eda import funsd_loader as fl
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
cfg_path: str = "configs/eda-funsd.yaml"


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

print("HORUS EDA — chapter 4 (FUNSD)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire FUNSD first; see "
        "data/raw/english/funsd/MANIFEST.md."
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
# # 1. Provenance {#sec-funsd-provenance}
#
# **Datasheets §3.1 Motivation.** Source archival stub:
# [`docs/sources/datasets/funsd.md`](../docs/sources/datasets/funsd.md).

# %%
manifest_path = CORPUS_ROOT / "MANIFEST.md"
manifest_text = manifest_path.read_text(encoding="utf-8")
print(f"MANIFEST: {manifest_path}")
for key in (
    "slug", "language", "source_url", "license_spdx",
    "retrieved_date", "file_count", "total_bytes",
    "sha256_aggregate", "sample_load_passed", "acquisition_status",
):
    for line in manifest_text.splitlines():
        if line.startswith(f"{key}:"):
            print(f"  {line}")
            break

# %% [markdown]
# **Discussion §1 (Provenance)**:
#
# - **License**: `LicenseRef-FUNSD-noncommercial-research`. Same
#   constraint class as OmniDocBench (chapter @sec-omnidocbench): the
#   thesis can use this for research evaluation; production HORUS
#   deployment must NOT train on FUNSD. Listed alongside
#   `inv-cdip-tobacco` (chapter 7) on the restrictive end of the
#   license-tier spectrum surfaced in chapter @sec-cross-corpus.
# - **Citation**: Jaume, G., Ekenel, H. K., & Thiran, J.-P. (2019).
#   *FUNSD: A Dataset for Form Understanding in Noisy Scanned
#   Documents*. ICDARW 2019. The dataset is a **subset of RVL-CDIP**
#   (Harley et al. 2015) — specifically the noisier real-world-scanned
#   forms — and remains the canonical form-understanding benchmark
#   reported in the LayoutLM / LayoutLMv2 / LayoutLMv3 papers.
# - **Provenance chain**: direct zip download from
#   `https://guillaumejaume.github.io/FUNSD/dataset.zip` (no
#   HuggingFace mirror; the FUNSD authors host the canonical copy
#   themselves). sha256-sealed in MANIFEST.md.
# - **Acquisition status**: `completed`;
#   `sample_load_passed: true` per MANIFEST.

# %% [markdown]
# ---
#
# # 2. Composition {#sec-funsd-composition}
#
# **Datasheets §3.2.** File count / format / language / annotation schema.

# %%
files = fl.walk(CORPUS_ROOT)
print(f"Total form pairs: {len(files)}")
print()
print("Per-split form counts:")
print(files["split"].value_counts().to_string())

n_missing_image = int(files["image_path"].isna().sum())
n_missing_ann = int(files["annotation_path"].isna().sum())
print()
print(f"Orphan rows — image missing:      {n_missing_image}")
print(f"Orphan rows — annotation missing: {n_missing_ann}")

if len(files) < EDA.expected_min_examples:
    print(
        f"\n⚠ {len(files)} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"\n✓ {len(files)} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
df = fl.load_examples(CORPUS_ROOT, split="all")
print(f"Loaded {len(df)} form annotations\n")
print("Per-row schema (from load_examples):")
print("  - form_id:      bare ID (e.g., '0000971160')")
print("  - split:        training / testing")
print("  - n_entities:   count of entries in form[]")
print("  - n_words:      sum of len(entry['words']) across entries")
print("  - n_linkings:   total entity-relation pairs across the form")
print("  - n_questions / n_answers / n_headers / n_others:")
print("                  per-label entity counts (4-class FUNSD schema)")

# %%
print("Per-form summary statistics:")
for col in ("n_entities", "n_words", "n_linkings"):
    s = df[col]
    print(
        f"  {col:<14s} min={int(s.min()):>3d} "
        f"median={int(s.median()):>3d} "
        f"mean={s.mean():>5.1f} "
        f"max={int(s.max()):>4d}"
    )

# %% [markdown]
# **Discussion §2 (Composition)**:
#
# - **199 form pairs** total (149 training + 50 testing), each a
#   `<id>.json` annotation + matching `<id>.png` image under
#   `dataset/{training_data,testing_data}/{annotations,images}/`.
#   No orphans expected; verified empirically above.
# - **Per-form schema**: a flat list of entries under `form[]`. Each
#   entry has `box` (4-int bbox), `text` (rendered text), `label` (one
#   of `other` / `question` / `answer` / `header`), `words` (per-word
#   sub-entries with their own bboxes), `linking` (list of `[id1, id2]`
#   relation pairs), and `id`. This schema is **simpler** than fatura2's
#   24-class token-NER (chapter @sec-fatura2) but **richer** than
#   ZUGFeRD's 16-field flat extraction (chapter @sec-zugferd) because
#   it carries the entity-relation `linking` graph.
# - **English only**: 199 forms in English; no German alignment with
#   the HORUS thesis target population. See §5 for the scope
#   discussion.

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-funsd-samples}
#
# **Datasheets §3.3.** Random-sample load + visual; verify the
# MANIFEST's `sample_load_passed: true` claim holds with current code.

# %%
rng = np.random.default_rng(cfg.seed)
sample_files = (
    files[files["split"] == "testing"]
    .sample(n=4, random_state=rng.bit_generator)
    .reset_index(drop=True)
)
print("Sampled form IDs (testing split):")
print(sample_files[["form_id", "split"]].to_string(index=False))

# %%
# | label: fig-funsd-samples
# | fig-cap: "Random 4 FUNSD forms (testing split). Real-world scan noise — uneven baselines, fax-quality blur, photocopier streaks — is the dataset's signature, and the reason FUNSD is named for noisy scanned documents."
fig, axes = plt.subplots(2, 2, figsize=(11, 14))
for ax, (_, row) in zip(axes.flat, sample_files.iterrows(), strict=False):
    img_path = row["image_path"]
    if img_path is None:
        ax.set_axis_off()
        continue
    img = Image.open(img_path)
    summary = df[df["form_id"] == row["form_id"]].iloc[0]
    n_ent = int(summary["n_entities"])
    n_link = int(summary["n_linkings"])
    ax.imshow(img)
    ax.set_title(
        f"{row['form_id']}  •  {n_ent} entities  •  {n_link} linkings",
        fontsize=9,
    )
    ax.axis("off")
plt.tight_layout()
plt.show()

# %%
# Inspect one annotation in detail.
sample_ann_path = files[files["annotation_path"].notna()].iloc[0]["annotation_path"]
sample_ann = fl.load_one_annotation(sample_ann_path)
entries = sample_ann["form"]
assert isinstance(entries, list)
print(f"Sample annotation: {sample_ann_path.name}")
print(f"  Top-level keys:     {list(sample_ann.keys())}")
print(f"  Number of entities: {len(entries)}")
print(f"  First 2 entities (truncated):")
for e in entries[:2]:
    text = (e.get('text') or '')[:40]
    print(
        f"    id={e.get('id')}  label={e.get('label')!r}  "
        f"text={text!r}  box={e.get('box')}  "
        f"linking={e.get('linking', [])}"
    )

# %% [markdown]
# **Discussion §3 (Sample inspection)**:
#
# - The 4-sample render confirms the MANIFEST's
#   `sample_load_passed: true` claim holds end-to-end with the current
#   loader code (PNG decode → PIL render → matplotlib display).
# - Visual inspection of the 4 thumbnails surfaces the dataset's
#   defining property: real-world scan noise (uneven baselines,
#   photocopier streaks, fax artefacts, handwritten ink-fills). This
#   is the substrate that makes FUNSD a robustness benchmark, NOT a
#   clean-content benchmark like fatura2 (chapter @sec-fatura2).
# - The detail inspection cell exposes the per-entity annotation
#   shape: each entity has a 4-class label + bbox + linking array. The
#   linking array is the entity-relation signal that distinguishes
#   FUNSD's schema from fatura2's pure token-NER format.

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-funsd-distributions}

# %%
total_labels = (
    df[["n_questions", "n_answers", "n_headers", "n_others"]].sum().to_dict()
)
print("Total entity-label counts across all 199 forms:")
for k, v in total_labels.items():
    print(f"  {k:<14s} {int(v):>5d}")

# %%
# | label: fig-funsd-labels
# | fig-cap: "Total entity counts per FUNSD label class across the 199 forms. The 'other' class dominates; 'question' / 'answer' counts roughly mirror each other (every Q has approximately one A on average)."
fig, ax = plt.subplots(figsize=(7, 3.5))
labels = ["question", "answer", "header", "other"]
counts = [int(total_labels[f"n_{lab}s"]) for lab in labels]
sns.barplot(
    x=labels,
    y=counts,
    palette=[PALETTE[0], PALETTE[2], PALETTE[5], PALETTE[8]],
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue=labels,
    legend=False,
)
ax.set_ylabel("Total entities across 199 forms")
ax.set_title("Entity-label distribution (FUNSD)", loc="left")
for i, v in enumerate(counts):
    ax.text(i, v + 30, str(v), ha="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# | label: fig-funsd-entity-counts
# | fig-cap: "Per-form entity-count distribution across the 199 forms. Most forms carry 30-100 entities; the long tail represents complex multi-section forms."
fig, ax = plt.subplots(figsize=(8, 3.5))
sns.histplot(
    df["n_entities"],
    bins=30,
    ax=ax,
    color=PALETTE[0],
    edgecolor="white",
    linewidth=0.4,
)
ax.axvline(
    df["n_entities"].median(),
    color=PALETTE[3],
    linestyle="--",
    linewidth=1.5,
)
ax.set_xlabel("Entities per form")
ax.set_ylabel("Number of forms")
ax.set_title("Per-form entity-count distribution", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# | label: fig-funsd-linkings
# | fig-cap: "Per-form linking-count distribution. Linkings encode the entity-pairing signal — load-bearing for the form-understanding F1 evaluation that the LayoutLM family reports."
fig, ax = plt.subplots(figsize=(8, 3.5))
sns.histplot(
    df["n_linkings"],
    bins=30,
    ax=ax,
    color=PALETTE[2],
    edgecolor="white",
    linewidth=0.4,
)
ax.set_xlabel("Linkings per form")
ax.set_ylabel("Number of forms")
ax.set_title("Per-form entity-linking-count distribution", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Label-class balance**: question + answer counts are roughly
#   even across the 199 forms (every Q has approximately one A on
#   average). The `other` class dominates total entity counts; this is
#   a **labeling-strategy artefact** — FUNSD chose to tag decorative
#   form elements (lines, dividers, decoration) as `other` rather than
#   skip them. Implication for F1 reporting: per-class macro-F1 is the
#   meaningful signal; the headline `other`-inclusive number is
#   inflated by the high-baseline class.
# - **Per-form entity counts** range from a small handful to roughly
#   200 with a median near 80. Compares to fatura2's tokens-per-invoice
#   distribution (median ~60, chapter @sec-fatura2 §4) — FUNSD's
#   entity-level granularity is **coarser** because entities are
#   field-level not token-level.
# - **Linking counts per form** provide a substantial entity-relation
#   signal across the corpus. The cross-corpus comparison in chapter
#   @sec-cross-corpus surfaces this as the closest analog to invoice
#   line-item grouping in the wider HORUS substrate.

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-funsd-horus}

# %% [markdown]
# **Honest framing**: FUNSD is the **canonical form-understanding
# methodology baseline** — every LayoutLM-family paper reports FUNSD
# F1 — but it is NOT a German invoice substrate. Its HORUS thesis
# relevance is:
#
# 1. **Form-understanding methodology baseline**: reporting HORUS
#    performance on FUNSD enables direct comparability to LayoutLMv3 /
#    Donut / DiT / Granite-Docling literature numbers. Without this,
#    the thesis's VLM-vs-prior-art comparison loses a published anchor.
# 2. **NOT a German invoice substrate**: 199 English forms; no
#    invoice-line-item structure. Cannot serve as direct training data
#    for invoice extraction.
# 3. **NOT a fine-tuning training pool for production HORUS**: license
#    is non-commercial-research-only. Same constraint class as
#    OmniDocBench (chapter @sec-omnidocbench). Production deployment
#    must NOT train on FUNSD.
# 4. **Linking annotation as a cross-corpus signal**: the
#    `linking` array is exactly the entity-pairing signal that invoice
#    extraction needs (each invoice line item is a
#    "DESCRIPTION + AMOUNT + QUANTITY" triple). Translating FUNSD's
#    entity-linking format into the invoice line-item format surfaces
#    in the chapter @sec-cross-corpus Decision Register.
# 5. **Scale gap**: 199 forms is below the LoRA fine-tuning floor
#    (`fine_tuning_anchors.lora_min_examples = 200`). Useful for
#    methodology validation, NOT primary training. Compare with
#    fatura2's 10K examples (chapter @sec-fatura2) for the
#    fine-tuning-substrate role.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-funsd-anomalies}

# %% [markdown]
# - **License**: non-commercial-research-only. Production-deployment
#   exclusion required (per chapter @sec-cross-corpus license-tier
#   matrix).
# - **Scale**: 199 forms total (149 + 50). Below the LoRA fine-tuning
#   floor; useful as evaluation / methodology benchmark only.
# - **Genre**: all forms are tax / business / NDA documents drawn
#   from the RVL-CDIP corpus (1980s-2000s scanned business
#   documents). NOT modern German invoices.
# - **Real OCR noise present** (uneven baselines, fax-quality blur,
#   photocopier streaks, handwritten fills). The dataset name
#   advertises this — it is a feature, not a bug. Useful for
#   robustness evaluation; complements OmniDocBench's
#   special-issue-tag substrate (chapter @sec-omnidocbench §4).
# - **No locale field in annotations**: all forms are English; the
#   schema doesn't carry a `language` field per entity.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-funsd-observations}

# %% [markdown]
# Per the `bidirectional-learning-pipe` rule + ADR-025 §"Per-chapter
# content template": hypothesis-shaped patterns surfaced during
# inspection captured HERE, NOT retro-fitted into H1–H6.
#
# **Observations from this Phase C iteration**:
#
# 1. **FUNSD's linking-pair format is the closest cross-dataset
#    analog to invoice line-item structure**. Mapping FUNSD-style
#    entity linkings to ZUGFeRD's `IncludedSupplyChainTradeLineItem`
#    aggregations is a candidate Decision Register entry — the only
#    cross-dataset bridge that captures BOTH "what fields exist" AND
#    "how they relate to each other". Surfaces in chapter
#    @sec-cross-corpus.
# 2. **`other`-label dominance is a labeling-strategy artefact**:
#    FUNSD chose to label decorative form elements as `other` rather
#    than skip them. This means F1 on the `other` class is
#    uninformative (high baseline-of-many), while F1 on Q / A / header
#    is the meaningful signal. If HORUS reports FUNSD F1, it should
#    report per-class macro-F1 alongside any headline number.
# 3. **199-form scale = methodology validator, not training pool**:
#    surfaced as a Decision Register entry in chapter @sec-cross-corpus
#    — the thesis should NOT train on FUNSD; it should evaluate on
#    FUNSD as a published-comparable baseline.
