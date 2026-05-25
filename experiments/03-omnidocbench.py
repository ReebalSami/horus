# ---
# title: "OmniDocBench (multilingual document benchmark)"
# subtitle: "Chapter 3 — 1651 Chinese + English + mixed pages from books, papers, PPTs, exams"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-omnidocbench.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # OmniDocBench {#sec-omnidocbench}
#
# This chapter characterizes the **OmniDocBench** dataset
# ([HuggingFace `opendatalab/OmniDocBench`](https://huggingface.co/datasets/opendatalab/OmniDocBench),
# custom non-commercial-research license): 1651 multilingual document
# images with per-region annotations covering text blocks, titles,
# equations, figures, tables, headers, footers, and 14 other category
# types. The corpus mixes Chinese (~47%) + English (~46%) + en/ch
# mixed (~7%) pages drawn from books, PPT-to-PDF, academic literature,
# exam papers, colorful textbooks, newspapers, magazines, research
# reports, notes, and historical documents.
#
# **NOT an invoice dataset.** OmniDocBench's `data_source` taxonomy
# contains zero invoice-class entries (verified empirically; see §4
# below). The dataset's HORUS thesis relevance is **breadth** (general
# OCR-route robustness on diverse document layouts + Chinese-language
# transfer test bed), NOT direct invoice substrate. See §5 for the
# scope discussion.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical
# 7-section template + a Datasheet entry in the consolidated appendix.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-omnidocbench-setup}

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
from horus.eda import omnidocbench_loader as ol
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
cfg_path: str = "configs/eda-omnidocbench.yaml"


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

print("HORUS EDA — chapter 3 (OmniDocBench)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire OmniDocBench first; see "
        "data/raw/multilingual/omnidocbench/MANIFEST.md."
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
# # 1. Provenance {#sec-omnidocbench-provenance}
#
# **Datasheets §3.1 Motivation.** Source archival stub:
# [`docs/sources/datasets/omnidocbench.md`](../docs/sources/datasets/omnidocbench.md).

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
# - **License**: custom non-commercial-research-only (`LicenseRef-
#   OmniDocBench-research-only`). The HuggingFace page lacks an SPDX
#   tag; the README's Copyright Statement says *"for research purposes
#   only and not for commercial use"*. **Implication for HORUS**: this
#   dataset cannot be used to train production-shipped models; thesis-
#   defense use is research-scope and acceptable, but a production
#   HORUS deployment would need to drop training on OmniDocBench and
#   document the license boundary.
# - **Provenance chain**: HuggingFace Hub commit
#   `d386947f7fc3bafdcd756c8485845a2f43a19875` (2026-04-10) → git-clone
#   → sha256-sealed in MANIFEST.md.
# - **Acquisition status**: `completed` (1659 files / 1.5 GB on disk;
#   1651 image entries indexed in OmniDocBench.json + auxiliary JSON +
#   data_diversity.png + show_pdf_types_*.png + .gitattributes + 2 LFS
#   metadata files).

# %% [markdown]
# ---
#
# # 2. Composition {#sec-omnidocbench-composition}
#
# **Datasheets §3.2.** File count / format / language / annotation schema.

# %%
df = ol.load_index(CORPUS_ROOT)
print(f"OmniDocBench.json entries: {len(df)}")
if len(df) < EDA.expected_min_examples:
    print(
        f"⚠ {len(df)} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"✓ {len(df)} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
print("Per-row schema (hoisted from page_info + page_attribute):")
print(f"  - image_path:      relative path under images/ (e.g., 'page-aaa.png')")
print(f"  - page_no:         0-indexed page within source document")
print(f"  - width / height:  image dimensions in pixels")
print(f"  - language:        simplified_chinese / english / en_ch_mixed / traditional_chinese / other")
print(f"  - data_source:     book / PPT2PDF / academic_literature / exam_paper / ...")
print(f"  - layout:          single_column / double_column / three_column / 1andmore_column / other_layout")
print(f"  - subset:          v1.5 / equation_hard / table_hard / layout_hard")
print(f"  - special_issues:  tuple of issue tags (table_horizontal, watermark, ...)")
print(f"  - n_layout_dets:   count of region-level annotations on this page")
print(f"  - category_types:  set of distinct category_type values in layout_dets")

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-omnidocbench-samples}

# %%
rng = np.random.default_rng(cfg.seed)
sample_idx = rng.choice(len(df), size=4, replace=False)
sample_df = df.iloc[sample_idx]
print("Sampled entries:")
print(
    sample_df[["image_path", "language", "data_source", "layout", "n_layout_dets"]]
    .to_string(index=False)
)

# %%
# | label: fig-omnidocbench-samples
# | fig-cap: "Random 4 OmniDocBench pages — diverse layouts (single-column / double-column / table-heavy / mixed) across data sources (book / PPT / paper / exam) and languages (Chinese / English)."
fig, axes = plt.subplots(2, 2, figsize=(10, 13))
for ax, (_, row) in zip(axes.flat, sample_df.iterrows(), strict=False):
    img_bytes = ol.load_image_bytes(CORPUS_ROOT, row["image_path"])
    if img_bytes is None:
        ax.set_axis_off()
        continue
    try:
        img = Image.open(io.BytesIO(img_bytes))
        ax.imshow(img)
    except Exception:  # noqa: BLE001
        ax.set_axis_off()
        continue
    ax.set_title(
        f"{row['data_source']} • {row['language']}\n"
        f"{row['layout']} • {row['n_layout_dets']} regions",
        fontsize=9,
    )
    ax.axis("off")
plt.tight_layout()
plt.show()

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-omnidocbench-distributions}

# %%
# Language distribution.
lang_dist = df["language"].value_counts()
print("Language distribution:")
for k, n in lang_dist.items():
    print(f"  {k:<25s} {n:>5d}  ({100 * n / len(df):.1f}%)")

# %%
# | label: fig-omnidocbench-language
# | fig-cap: "Language mix across the 1651 OmniDocBench pages. Chinese + English are co-dominant."
fig, ax = plt.subplots(figsize=(8, 4))
sns.barplot(
    x=lang_dist.values,
    y=lang_dist.index,
    palette=[PALETTE[0]] * len(lang_dist),
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue=lang_dist.index,
    legend=False,
)
ax.set_xlabel("Number of pages")
ax.set_ylabel("")
ax.set_title("Language distribution (OmniDocBench)", loc="left")
for i, v in enumerate(lang_dist.values):
    ax.text(v + 5, i, str(int(v)), va="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Data-source distribution.
ds_dist = df["data_source"].value_counts()
print("\nData-source distribution:")
for k, n in ds_dist.items():
    print(f"  {k:<25s} {n:>5d}  ({100 * n / len(df):.1f}%)")

# %%
# | label: fig-omnidocbench-source
# | fig-cap: "Data-source distribution. Books + PPTs + academic literature dominate; NO invoices."
fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(
    x=ds_dist.values,
    y=ds_dist.index,
    palette=[PALETTE[1]] * len(ds_dist),
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue=ds_dist.index,
    legend=False,
)
ax.set_xlabel("Number of pages")
ax.set_ylabel("")
ax.set_title("Data-source distribution (OmniDocBench)", loc="left")
for i, v in enumerate(ds_dist.values):
    ax.text(v + 3, i, str(int(v)), va="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Verify zero invoice-class entries (the load-bearing finding for §5).
invoice_sources = [s for s in ds_dist.index if "invoice" in str(s).lower() or "finance" in str(s).lower()]
print(f"Invoice-class data_sources (heuristic match): {invoice_sources}")
assert invoice_sources == [], (
    "OmniDocBench is supposed to have zero invoice-class entries; "
    f"found {invoice_sources}. The §5 HORUS-relevance framing depends "
    "on this invariant."
)

# %%
# Layout + special-issue distribution.
print("\nLayout distribution:")
for k, n in df["layout"].value_counts().items():
    print(f"  {k:<25s} {n:>5d}")

print("\nTop special-issue tags (across all pages; multi-issue pages counted once per tag):")
issue_counter: Counter[str] = Counter()
for issues in df["special_issues"]:
    for issue in issues:
        issue_counter[issue] += 1
for k, n in issue_counter.most_common(10):
    print(f"  {k:<35s} {n:>5d}")

# %%
# Region-level category_type distribution (which annotation types
# appear in OmniDocBench's schema).
counts = ol.category_counts(df)
print(f"\nDistinct category_types: {len(counts)}")
print(f"Top 15 (pages-where-category-appears):")
print(counts.head(15).to_string())

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Language mix**: simplified_chinese (46%) + english (46%) +
#   en_ch_mixed (7%) + traditional_chinese (1%) + other (<1%).
#   OmniDocBench is **co-dominant Chinese + English**, NOT broadly
#   multilingual in the German-locale-relevant sense. For the HORUS
#   thesis (German `Steuerberater` target population), the Chinese
#   half doesn't transfer; the English half overlaps with chapter
#   @sec-fatura2's coverage but with very different document-types.
# - **Data-source distribution**: books (276) + PPT2PDF (253) +
#   academic_literature (215) + exam_paper (193) + colorful_textbook
#   (159) + newspaper (151) + magazine (149) + research_report (132)
#   + note (118) + historical_document (5). **Zero invoices.** Verified
#   programmatically in the cell above; the §5 HORUS-relevance framing
#   depends on this invariant.
# - **Layout diversity**: 887 single-column + 184 double-column + 53
#   three-column + 155 1-and-more-column + 372 other_layout. The
#   "other_layout" category is the test-cases-for-multi-column-edge-
#   cases substrate.
# - **Annotation schema**: 18+ distinct category_type values
#   (`text_block` / `title` / `equation_isolated` / `header` / `figure`
#   / `page_number` / `abandon` / `footer` / `figure_caption` / `table`
#   / `table_caption` / `text_mask` / `equation_caption` / `reference`
#   / `table_footnote` / `figure_footnote` / `equation_semantic` /
#   `page_footnote` / `list_group` / `code_txt`). **Wider schema** than
#   ZUGFeRD's 16 EN16931 fields or fatura2's 24 NER classes — but the
#   schema is page-level (regions on a page), not document-level
#   (invoice-as-record).
# - **Special-issue tags** include `table_horizontal` (332) +
#   `colorful_background` (266) + `table_full_line` (160) +
#   `watermark` (73) + `fuzzy_scan` (30) + `geometric_deformation`
#   (13) + `handwriting` (2). These are robustness-test substrate
#   labels; useful for "VLM degrades-gracefully-under-noise" stress
#   testing.

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-omnidocbench-horus}

# %% [markdown]
# **Honest framing**: OmniDocBench is a **document-understanding
# breadth benchmark**, NOT an invoice substrate. With zero invoice
# entries, it cannot serve as direct invoice training/evaluation
# data. Its HORUS thesis relevance is:
#
# 1. **OCR-route robustness benchmark**: OmniDocBench's diverse data
#    sources (books / PPTs / papers / exams) + special-issue tags
#    (watermarks / colorful backgrounds / geometric deformation /
#    handwriting) make it a realistic robustness substrate for the
#    OCR-route comparator that the HORUS thesis methodology (per
#    chapter @sec-zugferd §1) needs to validate alongside the VLM
#    route. A VLM that handles OmniDocBench's noise patterns is
#    expected to handle the same noise patterns on Belege.
# 2. **Cross-language transfer test bed (Chinese)**: at 778 Chinese-
#    language pages, OmniDocBench provides a substantial Chinese
#    test set. NOT directly aligned with German-target HORUS, but
#    a useful test of "what happens when a VLM trained on
#    English+German invoices encounters a Chinese page" — a real
#    production failure mode for international tax advisors.
# 3. **Page-region taxonomy comparison**: OmniDocBench's 18+
#    category_type schema differs from ZUGFeRD's 16-field EN16931
#    schema and fatura2's 24-class NER schema. Cross-corpus
#    comparison (chapter @sec-cross-corpus) will surface these
#    schema gaps as a Decision Register entry.
# 4. **NOT a fine-tuning training pool for invoices**: license is
#    non-commercial-research-only; even if it had invoice entries,
#    a production HORUS deployment couldn't ship a model trained
#    on OmniDocBench. Thesis-defense use is acceptable; production
#    deployment is not.
# 5. **NOT a primary evaluation substrate**: per the HORUS thesis
#    F1 evaluation chain (chapter @sec-zugferd §10 + future PRD
#    decisions), the held-out evaluation is German Belege +
#    ZUGFeRDv2 corpus. OmniDocBench is breadth, not depth.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-omnidocbench-anomalies}

# %% [markdown]
# - **License**: non-commercial-research-only. Strongest constraint
#   among the 7 datasets; documented in MANIFEST.md `anomalies[1]`.
#   Production HORUS deployments must NOT train on this dataset.
# - **34 mislabeled `.png` files**: per MANIFEST.md `anomalies[0]`,
#   34 of 670 `.png` files contain JPEG content (header `ffd8ffe0`
#   instead of PNG's `89504e47`). Source-side dataset issue, NOT
#   download corruption. PIL's auto-detection handles them; the
#   loader's `load_image_bytes` reads raw bytes regardless of
#   extension. Surfaces as a Quality observation, not a deal-breaker.
# - **Heavy Chinese skew**: ~47% Chinese + 7% mixed = ~54% Chinese
#   content. The HORUS thesis target is German; the language gap
#   limits direct transfer.
# - **No invoice content**: confirmed empirically (data_source
#   contains zero invoice-class entries). For invoice-specific
#   evaluation, this dataset is N/A.
# - **JSON-format-only ground truth**: the dataset ships
#   `OmniDocBench.json` as the canonical annotation format (no
#   COCO / no Pascal VOC). Re-parsing required for any downstream
#   tool that expects standard formats.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-omnidocbench-observations}

# %% [markdown]
# **Observations from this Phase C iteration**:
#
# 1. **OmniDocBench's special-issue tags are an under-leveraged
#    robustness substrate**: with explicit labels for
#    `geometric_deformation`, `fuzzy_scan`, `watermark`, `handwriting`,
#    etc., the dataset enables hypothesis-driven robustness eval that
#    the HORUS thesis could leverage (e.g., "does HORUS extraction
#    degrade gracefully on watermarked pages?"). Captured here as an
#    H7-candidate; NOT promoted to H1–H6 per HARKing discipline.
# 2. **Cross-dataset annotation-schema gap is now load-bearing**:
#    chapters @sec-zugferd (16 EN16931 fields), @sec-fatura2 (24-class
#    NER), and @sec-omnidocbench (18+ category_types) use mutually
#    incompatible schemas. The chapter @sec-cross-corpus Decision
#    Register will need to surface "what's the unifying evaluation
#    schema for cross-dataset F1 comparison?" as a thesis
#    methodology question.
# 3. **License-tier asymmetry across the 7 datasets**: ZUGFeRD
#    (Apache-2.0), fatura2 (CC-BY-4.0), and parsee-ai (MIT) are
#    permissive; OmniDocBench (non-commercial-research) and
#    inv-cdip-tobacco (CC-BY-NC-4.0) are restrictive. The Decision
#    Register should surface "if HORUS deploys to production, which
#    training subsets must be excluded?" — a real-world legal
#    constraint, not just a methodology footnote.
