# ---
# title: "CORD-v2 (Korean receipts)"
# subtitle: "Chapter 6 — 1000 receipt images with Donut-style hierarchical JSON ground truth"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-cord-v2.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # CORD-v2 {#sec-cord-v2}
#
# This chapter characterizes the **CORD-v2 dataset** (Consolidated
# Receipt Dataset, version 2;
# [HuggingFace `naver-clova-ix/cord-v2`](https://huggingface.co/datasets/naver-clova-ix/cord-v2),
# CC-BY-4.0): 1000 Korean receipt images (800 train + 100 validation +
# 100 test) with Donut-style hierarchical JSON ground-truth
# annotations. Originally curated by NAVER CLOVA for the Donut paper
# (Kim et al. 2022, ECCV) and widely used as the canonical OCR-free
# receipt-extraction benchmark.
#
# **Receipts, NOT invoices.** CORD-v2's content is point-of-sale
# receipts (Korean grocery / restaurant / retail receipts) — short
# documents with menu line-items + sub-totals + totals. This is a
# **related but distinct** document class from German B2B invoices
# (chapter @sec-zugferd). The thesis-relevant value is cross-domain:
# (a) a published-comparable VLM benchmark since most modern document
# VLMs include CORD in pre-training; (b) a Korean-language transfer
# test bed; (c) sanity-check substrate before evaluating on German
# Belege. See §5 for the scope discussion.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical
# 7-section template + a Datasheet entry in the consolidated appendix.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-cord-v2-setup}

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
from horus.eda import cord_v2_loader as cl
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
cfg_path: str = "configs/eda-cord-v2.yaml"


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

print("HORUS EDA — chapter 6 (CORD-v2)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire CORD-v2 first; see "
        "data/raw/korean/cord-v2/MANIFEST.md."
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
# # 1. Provenance {#sec-cord-v2-provenance}
#
# **Datasheets §3.1 Motivation.** Source archival stub:
# [`docs/sources/datasets/cord-v2.md`](../docs/sources/datasets/cord-v2.md).

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
# - **License**: CC-BY-4.0. Permissive — research + commercial use
#   with attribution. Pairs with `fatura2-invoices` (CC-BY-4.0,
#   chapter @sec-fatura2) + `parsee-ai-invoices-example` (MIT,
#   chapter @sec-parsee-ai) on the permissive license tier. Production
#   HORUS deployment CAN train on CORD-v2 with attribution.
# - **Provenance chain**: HuggingFace Hub commit
#   `7f0115a4b758a71d6473b8d085751692da2fef98` (2022-07-19) →
#   `git clone --lfs` → sha256-sealed in MANIFEST.md.
#   ~2.3 GB on disk (image bytes embedded in parquet).
# - **Original paper**: Kim et al. 2022, *OCR-free Document
#   Understanding Transformer*, ECCV
#   ([arXiv:2111.15664](https://arxiv.org/abs/2111.15664)). The
#   Donut paper introduced both the OCR-free document-VLM
#   architecture AND the CORD-v2 evaluation benchmark. Donut's
#   training pipeline uses CORD-v2's `gt_parse` JSON ground-truth as
#   the supervision signal — this is the format that defines the
#   `image → structured JSON output` task convention used
#   subsequently by Pix2Struct, LayoutLMv3 (extended), and most
#   modern document-VLMs.
# - **Acquisition status**: `completed`; `sample_load_passed: true`
#   (3 random parquets PAR1 magic-byte verified per MANIFEST).

# %% [markdown]
# ---
#
# # 2. Composition {#sec-cord-v2-composition}
#
# **Datasheets §3.2.** File count / format / annotation schema.

# %%
files = cl.walk(CORPUS_ROOT)
files["size_mb"] = (files["size_bytes"] / (1024 * 1024)).round(1)
print("Parquet files on disk:")
print(files[["filename", "split", "size_mb", "n_rows"]].to_string(index=False))
n_total = int(files["n_rows"].sum())
print(f"\nTotal rows across all splits: {n_total}")

if n_total < EDA.expected_min_examples:
    print(
        f"⚠ {n_total} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"✓ {n_total} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
# Load all 1000 rows with image bytes dropped (small memory footprint).
# Image-bytes loading is deferred to per-sample retrievals in §3.
df = cl.load_examples(CORPUS_ROOT, split="all", drop_image_bytes=True)
print(f"\nLoaded {len(df)} rows (drop_image_bytes=True)\n")
print("Per-split row counts (derived):")
print(df["split"].value_counts().to_string())

# %%
print("\nDonut-style schema (per row):")
print("  - image:        struct {bytes, path} — JPEG/PNG bytes embedded")
print("                  in parquet; path=None for self-contained dataset")
print("  - ground_truth: JSON string with structure:")
print("                  {")
print('                    "gt_parse": {                  # receipt fields')
print('                      "menu": [{nm,cnt,price,...},...]  # line items')
print('                      "sub_total": {subtotal_price, tax_price, ...}')
print('                      "total": {total_price, total_etc, ...}')
print("                    },")
print('                    "meta":  {...},                # CORD-specific metadata')
print('                    "valid_line": [...],            # line-level OCR ground truth')
print('                    "roi":         {...},          # region of interest')
print("                    ...")
print("                  }")

# %%
# Top-level keys under gt_parse (the receipt-structure dimension).
all_gt_keys: Counter[str] = Counter()
for keys in df["gt_top_level_keys"]:
    for k in keys:
        all_gt_keys[k] += 1
print("\ngt_parse top-level key frequency (across all 1000 receipts):")
for k, n in all_gt_keys.most_common():
    print(f"  {k:<25s} {n:>4d}/1000  ({100 * n / len(df):.1f}%)")

# %%
# Menu items per receipt — distribution stats.
n_menu = df["n_menu_items"]
print("\nMenu items per receipt:")
print(
    f"  min={int(n_menu.min())} "
    f"median={int(n_menu.median())} "
    f"mean={n_menu.mean():.2f} "
    f"max={int(n_menu.max())}"
)
print(f"\ntotal_price extraction success: "
      f"{int(df['total_price'].notna().sum())}/{len(df)} "
      f"({100 * df['total_price'].notna().sum() / len(df):.1f}%)")

# %% [markdown]
# **Discussion §2 (Composition)**:
#
# - **1000 receipts** = 800 train + 100 validation + 100 test, matching
#   the HF dataset card + `dataset_infos.json`. Empirically confirmed
#   above.
# - **Donut-style JSON ground truth** is the load-bearing annotation
#   format: every receipt has a `gt_parse` block with hierarchical
#   field structure (`menu` → line items; `sub_total` → financial
#   sub-totals; `total` → total + tax). `menu` and `total` appear in
#   100% of receipts; `sub_total` in ~66% (smaller receipts often skip
#   the sub-total layer and go directly menu→total).
# - **Menu items per receipt** range from 1 to a long-tail maximum
#   (~30+), with a median of 2 and mean of ~2.5. Most CORD receipts
#   are small (≤5 items); the long tail represents grocery / restaurant
#   receipts with many items.
# - **Image bytes embedded in parquet** make this a
#   self-contained-dataset layout (no separate image directory). The
#   total ~2.3 GB on disk is dominated by image bytes; the JSON
#   ground-truth alone is ~5-10 KB per row.

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-cord-v2-samples}
#
# **Datasheets §3.3.** Render 4 random test-split receipts to verify
# the MANIFEST's `sample_load_passed: true` claim holds end-to-end.

# %%
# Sample 4 row indices from the test split (100 rows total).
rng = np.random.default_rng(cfg.seed)
sample_indices = sorted(rng.choice(100, size=4, replace=False).tolist())
print(f"Sampled row indices (test split): {sample_indices}")

# %%
# Load image bytes one row at a time (avoids loading all 1000 images at once).
# | label: fig-cord-v2-samples
# | fig-cap: "Random 4 CORD-v2 receipts (test split). Korean point-of-sale receipts: short documents with menu line-items + totals. Image sizes and aspect ratios vary across receipt types (long grocery receipts vs short restaurant receipts)."
fig, axes = plt.subplots(2, 2, figsize=(10, 13))
df_test = df[df["split"] == "test"].reset_index(drop=True)
for ax, row_idx in zip(axes.flat, sample_indices, strict=False):
    img_bytes = cl.load_one_image_bytes(CORPUS_ROOT, split="test", row_index=row_idx)
    if img_bytes is None:
        ax.set_axis_off()
        continue
    img = Image.open(io.BytesIO(img_bytes))
    ax.imshow(img)
    sample_row = df_test.iloc[row_idx]
    n_items = int(sample_row["n_menu_items"])
    tot = sample_row["total_price"] or "(none)"
    ax.set_title(
        f"row {row_idx}  •  {n_items} menu item(s)  •  total={tot}",
        fontsize=9,
    )
    ax.axis("off")
plt.tight_layout()
plt.show()

# %%
# Inspect the GT structure for one sampled receipt.
sample_idx = sample_indices[0]
sample_gt_str = df_test.iloc[sample_idx]["gt_raw"]
sample_gt = cl.parse_ground_truth(sample_gt_str)
print(f"Sample GT structure (test row {sample_idx}):")
print(f"  Top-level keys:      {list(sample_gt.keys())}")
gt_parse = sample_gt.get("gt_parse", {})
print(f"  gt_parse top keys:   {list(gt_parse.keys())}")
menu = gt_parse.get("menu")
if isinstance(menu, list):
    print(f"  menu (list of {len(menu)} items, first 2):")
    for item in menu[:2]:
        keys = list(item.keys()) if isinstance(item, dict) else []
        print(f"    {keys}: {item}")
elif isinstance(menu, dict):
    print(f"  menu (single item dict): {menu}")
total = gt_parse.get("total")
if isinstance(total, dict):
    print(f"  total: {total}")

# %% [markdown]
# **Discussion §3 (Sample inspection)**:
#
# - The 4-receipt sample render confirms the MANIFEST's
#   `sample_load_passed: true` claim holds end-to-end. Image-bytes
#   decode → PIL render → matplotlib display works for arbitrary test
#   rows; total memory cost is ~4 × ~300 KB = ~1.2 MB (manageable).
# - The GT-structure inspection shows the Donut JSON schema concretely:
#   `gt_parse` is the receipt-field wrapper; `menu` is either a single
#   dict (1-item receipt) or a list (multi-item receipt); `total`
#   typically contains `total_price` + tax-related fields.
# - The sample receipt images surface a recurring CORD-v2 visual
#   property: receipts are **tall and narrow** (point-of-sale roll
#   format), with high aspect ratios that differ from invoice / form
#   documents (chapters @sec-zugferd / @sec-fatura2 / @sec-funsd). This
#   may matter for VLM-image-encoding (resolution + cropping) when
#   running cross-domain.

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-cord-v2-distributions}

# %%
# Menu-item count distribution per split.
# | label: fig-cord-v2-menu-items
# | fig-cap: "Menu items per receipt across all 1000 CORD-v2 receipts. Most receipts have ≤5 items; the long right tail represents grocery / multi-item restaurant receipts."
fig, ax = plt.subplots(figsize=(9, 4))
max_items_for_plot = min(int(df["n_menu_items"].max()), 30)
sns.histplot(
    df["n_menu_items"].clip(upper=max_items_for_plot),
    bins=range(0, max_items_for_plot + 2),
    ax=ax,
    color=PALETTE[0],
    edgecolor="white",
    linewidth=0.4,
    discrete=True,
)
ax.axvline(
    df["n_menu_items"].median(),
    color=PALETTE[3],
    linestyle="--",
    linewidth=1.5,
)
ax.set_xlabel(f"Menu items per receipt (clipped at {max_items_for_plot})")
ax.set_ylabel("Number of receipts")
ax.set_title("Menu-item count distribution (1000 receipts)", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Per-split menu-item summary statistics.
print("Per-split menu-item summary:")
for split_name in ("train", "validation", "test"):
    s = df[df["split"] == split_name]["n_menu_items"]
    print(
        f"  {split_name:<12s} n={len(s):>4d}  "
        f"min={int(s.min())}  "
        f"median={int(s.median())}  "
        f"mean={s.mean():>5.2f}  "
        f"max={int(s.max())}"
    )

# %%
# gt_parse top-level field-presence rate per split.
# | label: fig-cord-v2-field-presence
# | fig-cap: "gt_parse top-level field presence rate (% of receipts containing each field) across splits. `menu` + `total` are universal; `sub_total` appears in roughly 60-70% — the smaller receipts skip the sub-total layer."
fields_of_interest = ["menu", "sub_total", "total"]
rates_per_split = []
for split_name in ("train", "validation", "test"):
    sub = df[df["split"] == split_name]
    for field in fields_of_interest:
        rate = sub["gt_top_level_keys"].apply(lambda ks, f=field: f in ks).mean()
        rates_per_split.append(
            {"split": split_name, "field": field, "rate_pct": 100 * rate}
        )
rates_df = pd.DataFrame(rates_per_split)
fig, ax = plt.subplots(figsize=(8, 4))
sns.barplot(
    data=rates_df,
    x="field",
    y="rate_pct",
    hue="split",
    palette=[PALETTE[0], PALETTE[2], PALETTE[5]],
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
)
ax.set_ylabel("Rate of receipts containing field (%)")
ax.set_xlabel("gt_parse top-level field")
ax.set_title("Donut-field presence rate per split", loc="left")
ax.set_ylim(0, 105)
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# total_price extraction success rate per split.
print("total_price extraction success rate per split:")
for split_name in ("train", "validation", "test"):
    sub = df[df["split"] == split_name]
    n_extracted = int(sub["total_price"].notna().sum())
    print(f"  {split_name:<12s} {n_extracted:>4d}/{len(sub):<4d}  "
          f"({100 * n_extracted / len(sub):.1f}%)")

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Menu-item distribution is heavily right-skewed**: median 2,
#   mean 2.5, but max in the train split runs into the double digits
#   (multi-item grocery receipts). The split-level statistics are
#   similar across train / validation / test — no systematic
#   distribution shift between splits.
# - **Donut-field presence rates are stable across splits**: `menu` +
#   `total` appear in ~100% of receipts in each split; `sub_total`
#   appears in ~60-70% consistently. This confirms the HF train /
#   validation / test partition is randomly sampled from a common
#   distribution (not a deliberate hard-test / easy-train split).
# - **total_price extraction succeeds in 90%+ of receipts** across
#   all three splits. The non-extracting receipts surface a CORD-v2
#   GT-quality observation: some receipts have a `total` block
#   without `total_price` (e.g., service-charge-only receipts,
#   refund-only receipts).

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-cord-v2-horus}

# %% [markdown]
# **Honest framing**: CORD-v2 is **receipts, not invoices**, and
# **Korean, not German** — a cross-domain comparator, not a direct
# HORUS evaluation substrate. Its HORUS thesis relevance is:
#
# 1. **Published-comparable VLM benchmark**: most modern document
#    VLMs (Donut, Pix2Struct, LayoutLMv3-extended, Qwen-VL, etc.)
#    report CORD F1 in their papers. Reporting HORUS-VLM-cohort
#    performance on CORD-v2 enables direct comparability to the
#    published literature — without this anchor, HORUS's VLM choice
#    rationale lacks an apples-to-apples reference point.
# 2. **OCR-free architecture training substrate**: the Donut paper
#    (Kim et al. 2022) used CORD-v2 as its primary training set
#    showing that an `image → structured JSON` OCR-free pipeline is
#    feasible. This methodology is directly applicable to HORUS's
#    VLM-route (chapter @sec-zugferd §10 sufficiency report) — CORD-v2
#    is the evidence that the OCR-free path works on receipts; HORUS
#    extends to German invoices.
# 3. **Korean-language transfer test bed**: at 1000 Korean-language
#    receipts, CORD-v2 provides the largest non-Latin-script substrate
#    in the HORUS substrate. NOT German-aligned, but a useful test
#    of "what happens when a VLM trained on Latin-script invoices
#    encounters non-Latin script" — a real production failure mode
#    for tax advisors with international clients.
# 4. **Permissive license**: CC-BY-4.0 means production HORUS
#    deployment CAN train on CORD-v2 with attribution. Pairs with
#    fatura2 (CC-BY-4.0) + parsee-ai (MIT) on the permissive license
#    tier; contrasts with FUNSD / OmniDocBench / inv-cdip-tobacco on
#    the restrictive tier.
# 5. **NOT a primary fine-tuning training pool for invoices**: 1000
#    Korean receipts is small for fine-tuning, AND the document class
#    is wrong (receipts ≠ invoices). Useful for methodology validation
#    + cross-domain benchmarking, NOT for primary HORUS supervised
#    training.
# 6. **Receipt vs invoice schema gap**: CORD-v2's `menu` + `sub_total`
#    + `total` doesn't map cleanly to ZUGFeRD's 16-field EN16931
#    schema or fatura2's 24-class NER. Cross-dataset F1 comparison
#    requires schema-bridging — surfaces in chapter @sec-cross-corpus.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-cord-v2-anomalies}

# %% [markdown]
# - **Receipts, not invoices**: the canonical caveat. CORD-v2 cannot
#   train an invoice-extraction model directly; it can only train a
#   document-VLM whose receipt-skill transfers (or not) to invoices.
# - **Korean language**: NOT German. Cross-language transfer is
#   testable but adds a confound — performance differences between
#   CORD-v2 and German Belege could be language OR document-type
#   OR both.
# - **Donut-paper-specific GT format**: the `gt_parse` JSON
#   convention is Donut's authoring choice, not an industry standard
#   (compare ZUGFeRD's EN16931 XML schema, chapter @sec-zugferd).
#   Comparing CORD-v2 F1 across non-Donut models requires schema
#   bridging.
# - **`menu` list-vs-dict polymorphism**: when a receipt has 1 item,
#   `menu` is a dict; with N>1 items, `menu` is a list. The loader
#   handles both, but any downstream code that assumes list-only
#   will break on single-item receipts. Captured by
#   `test_load_examples_derives_features_single_menu` +
#   `test_load_examples_derives_features_multi_menu` tests.
# - **~10% of receipts lack a parseable `total_price`**: some `total`
#   blocks contain only sub-fields without the main total. Not a
#   loader bug — a CORD-v2 GT-quality property. Captured by §4
#   distributional analysis.
# - **Image-bytes embedded in parquet (~2.3 GB on disk)**: the
#   self-contained-dataset layout is convenient but heavy.
#   Memory-conscious loading via `drop_image_bytes=True` is the
#   default; full-image loading is a per-sample retrieval.
# - **`gt_parse` is one of several top-level GT keys**: the full
#   ground_truth JSON also contains `meta`, `valid_line`, `roi`,
#   `repeating_symbol`, `dontcare` — CORD-internal annotation
#   metadata not directly usable for extraction supervision. The
#   loader exposes only `gt_parse` because that's the supervised
#   target; richer downstream use (e.g., line-level OCR re-training)
#   would re-parse the full JSON.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-cord-v2-observations}

# %% [markdown]
# Per the `bidirectional-learning-pipe` rule + ADR-025 §"Per-chapter
# content template": hypothesis-shaped patterns surfaced during
# inspection captured HERE, NOT retro-fitted into H1–H6.
#
# **Observations from this Phase C iteration**:
#
# 1. **OCR-free methodology lineage from CORD-v2 to HORUS-VLM-route is
#    direct**: the Donut paper (Kim et al. 2022) established that
#    `image → structured JSON` works as an OCR-free document-
#    understanding pattern. HORUS's VLM-route inherits this lineage
#    (chapter @sec-zugferd §10 sufficiency report cites Donut-class
#    architectures). The chapter @sec-cross-corpus Decision Register
#    should surface "CORD-v2 OCR-free precedent supports HORUS's
#    VLM-route choice" as a methodology anchor.
# 2. **Cross-script transfer testability**: with 1000 Korean receipts
#    plus 145 German ZUGFeRD invoices plus ~10K English fatura2
#    invoices plus ~1651 Chinese+English OmniDocBench documents, the
#    HORUS substrate enables an unusual cross-script generalization
#    test (Korean ↔ German ↔ Chinese ↔ English). NOT a thesis hypothesis
#    here per HARKing discipline — flagged as an H7-candidate for
#    future hypothesis-design rounds.
# 3. **The "menu list-vs-dict polymorphism" is a generic data-shape
#    pitfall**: a similar polymorphism appears in FUNSD's `linking`
#    (sometimes empty list, sometimes populated) and ZUGFeRD's
#    `IncludedSupplyChainTradeLineItem` (single vs repeated). The
#    chapter @sec-cross-corpus Decision Register entry "Schema-shape
#    asymmetries across the substrate" should consolidate these
#    polymorphism patterns into a single observation.
