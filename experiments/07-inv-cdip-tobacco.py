# ---
# title: "inv-cdip-tobacco (Salesforce annotations-only labeled set)"
# subtitle: "Chapter 7 — 350 tobacco-industry invoice annotations with 7 canonical field labels"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-inv-cdip-tobacco.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # inv-cdip-tobacco {#sec-inv-cdip}
#
# This chapter characterizes the **inv-cdip-tobacco** dataset
# ([Salesforce inv-cdip on GitHub](https://github.com/salesforce/inv-cdip),
# Gao et al. 2022 ACL Spa-NLP Workshop, CC-BY-NC-4.0): 350 labeled
# invoice annotations covering 7 canonical field labels
# (Invoice_number / Purchase_order / Invoice_date / Due_date /
# Amount_due / Total_amount / Total_tax) drawn from the
# [UCSF Industry Documents Library](https://www.industrydocuments.ucsf.edu/)
# tobacco-document collection (1980s-2000s scanned business
# documents). The dataset is a labeled subset of the larger CDIP
# corpus (Complaint, Document, Image Processing).
#
# **Annotations-only acquisition.** The underlying tobacco-industry
# PDF scans are intentionally NOT downloaded — per acquisition
# decision (sub-issue #28 closed not-planned 2026-05-13), the HORUS
# pilot uses the 350 JSON annotations alone for Berghaus-baseline
# cross-comparison without the raw scans. This chapter therefore
# characterizes the **annotation schema** as the EDA subject, not
# visual properties.
#
# **Berghaus 2025 comparator.** Per
# [`docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md`](../docs/sources/papers/berghaus-2025-multimodal-invoice-parsing.md),
# Berghaus et al. 2025 use inv-cdip-tobacco as one of their VLM
# evaluation sets. Reporting HORUS-VLM-cohort numbers on the same
# 350-invoice subset enables direct comparison to Berghaus's
# GPT-5 / Gemini-2.5 / Gemma-3 baselines. This is the chapter's
# load-bearing HORUS-relevance hook.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", this chapter walks the canonical
# 7-section template + a Datasheet entry in the consolidated appendix.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-inv-cdip-setup}

# %%
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from horus.config import ExperimentConfig
from horus.eda import inv_cdip_loader as il
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
cfg_path: str = "configs/eda-inv-cdip-tobacco.yaml"


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

print("HORUS EDA — chapter 7 (inv-cdip-tobacco)")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Seed:         {cfg.seed}")
print(f"  Expected min examples: {EDA.expected_min_examples}")

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire inv-cdip-tobacco first; see "
        "data/raw/english/inv-cdip-tobacco/MANIFEST.md."
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
# # 1. Provenance {#sec-inv-cdip-provenance}
#
# **Datasheets §3.1 Motivation.** Source archival stub:
# [`docs/sources/datasets/inv-cdip-tobacco.md`](../docs/sources/datasets/inv-cdip-tobacco.md).

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
# - **License**: CC-BY-NC-4.0. **Non-commercial use only.** Restrictive
#   tier alongside OmniDocBench (chapter @sec-omnidocbench) and FUNSD
#   (chapter @sec-funsd). Production HORUS deployment must NOT train
#   on inv-cdip-tobacco; thesis-defense research use is acceptable.
# - **Provenance chain**: Salesforce inv-cdip GitHub commit
#   `f19e620340ff67cf18edba06a642a47e7506b7d1` (2024-10-29) →
#   `git clone` → sha256-sealed in MANIFEST.md.
# - **Underlying corpus**: UCSF Industry Documents Library tobacco
#   collection. Documents accessible at
#   `https://www.industrydocuments.ucsf.edu/docs/<document_id>` — the
#   bare 9-char IDs in `test_set.txt` / `train_set.txt` map directly
#   to that URL. **NOT downloaded locally** per acquisition decision
#   (sub-issue #28 closed not-planned 2026-05-13); annotation-only
#   acquisition is sufficient for Berghaus-baseline cross-comparison
#   without the raw scans.
# - **Original paper**: Gao, M., Chen, Z., Naik, N., Hashimoto, K.,
#   Xiong, C., & Xu, R. (2022). *Field Extraction from Forms with
#   Unlabeled Data*. ACL Spa-NLP Workshop. Original goal: train an
#   extraction model on the ~200K unlabeled invoices + evaluate on
#   the 350 labeled set. HORUS uses only the 350 labeled set.
# - **Acquisition status**: `completed`; `sample_load_passed: true`
#   (3 random JSONs parsed without error per MANIFEST notes).

# %% [markdown]
# ---
#
# # 2. Composition {#sec-inv-cdip-composition}
#
# **Datasheets §3.2.** File count / annotation schema / no-images
# scope decision.

# %%
files = il.walk(CORPUS_ROOT)
print(f"Annotation files: {len(files)}")
print(f"\nSample form_ids: {files['form_id'].head(5).tolist()}")
print()
total_ann_bytes = int(files["annotation_size_bytes"].sum())
print(f"Total annotation size on disk: {total_ann_bytes / 1024:.1f} KB")

# Additional dataset files (NOT annotations) — sanity-check what else is there.
all_files = sorted((CORPUS_ROOT.glob("*")))
meta_files = [p.name for p in all_files if p.is_file()]
print(f"\nMetadata files at corpus root: {meta_files}")

# train_set.txt / test_set.txt sanity check.
test_ids = (CORPUS_ROOT / "test_set.txt").read_text().splitlines()
train_ids = (CORPUS_ROOT / "train_set.txt").read_text().splitlines()
print(f"\ntest_set.txt:  {len(test_ids)} IDs (the labeled subset; annotations on disk)")
print(f"train_set.txt: {len(train_ids)} IDs (UNLABELED bulk; scans not downloaded)")

if len(files) < EDA.expected_min_examples:
    print(
        f"\n⚠ {len(files)} < expected_min_examples {EDA.expected_min_examples}; "
        f"corpus may not be fully fetched."
    )
else:
    print(f"\n✓ {len(files)} ≥ expected_min_examples {EDA.expected_min_examples}.")

# %%
# Per-annotation JSON schema (per Salesforce README §"Annotation Description").
print("Annotation JSON schema (per README §'Annotation Description'):")
print("  Top-level keys:")
print("    image_dims:  str — Python literal '[width, height, channels]'")
print("    Fields:      list — per-field entries")
print()
print("  Per-Fields entry:")
print("    key.tag:     str | None — textual key (e.g., 'inv.', 'total billing')")
print("    key.bbox:    {xmin, ymin, xmax, ymax} | absent")
print("    value.label: str — canonical field type")
print("    value.tag:   str — extracted value")
print("    value.bbox:  {xmin, ymin, xmax, ymax}")

# %%
df = il.load_examples(CORPUS_ROOT)
print(f"\nLoaded {len(df)} forms")
print(f"Columns: {list(df.columns)}")

# %%
print("Per-form summary statistics:")
for col in ("n_fields", "n_fields_with_key", "image_width", "image_height"):
    s = df[col].dropna()
    print(
        f"  {col:<22s} min={int(s.min()):>5d} "
        f"median={int(s.median()):>5d} "
        f"mean={s.mean():>7.1f} "
        f"max={int(s.max()):>5d}"
    )
print(f"  image_channels distinct: {sorted(df['image_channels'].dropna().unique().tolist())}")

# %% [markdown]
# **Discussion §2 (Composition)**:
#
# - **350 annotation files** match the README's labeled-set claim
#   exactly. Each JSON is small (~few KB) — total annotation footprint
#   ~2 MB.
# - **No images locally**: the underlying UCSF tobacco-document scans
#   are not on disk (acquisition decision). The chapter is therefore
#   annotation-only: image_width / image_height come from the
#   `image_dims` JSON field, NOT from PIL-decoding actual files.
# - **All scans are grayscale** (image_channels distinct = `[1]`).
#   Tobacco-era business-document scans are typically 1-bit / 8-bit
#   grayscale faxes / photocopies, NOT modern color images.
# - **train_set.txt ≠ labeled set**: the ~200K IDs in `train_set.txt`
#   are the UNLABELED bulk (per the Gao 2022 paper's
#   unlabeled-data approach). Only `test_set.txt` (350 IDs) matches
#   the labeled annotations.
# - **Per-form field count is 1-6** (median 4), well below the 7
#   canonical labels. This means **most invoices DON'T have all 7
#   fields** — the annotation schema is sparse in practice.

# %% [markdown]
# ---
#
# # 3. Sample inspection {#sec-inv-cdip-samples}
#
# **Datasheets §3.3.** Pretty-print one annotation to surface the
# schema concretely. Visual sample inspection is N/A (no images on
# disk by design); the annotation IS the sample.

# %%
rng = np.random.default_rng(cfg.seed)
sample_row = files.iloc[int(rng.integers(0, len(files)))]
print(f"Sampled annotation: {sample_row['form_id']}.json")
print(f"  Source PDF URL: https://www.industrydocuments.ucsf.edu/docs/{sample_row['form_id']}")
print(f"  Annotation size: {sample_row['annotation_size_bytes']} bytes")
print()

ann = il.load_one_annotation(sample_row["annotation_path"])
print(f"Top-level keys: {list(ann.keys())}")
print(f"image_dims (raw): {ann['image_dims']!r}")
print(f"image_dims (parsed): {il.parse_image_dims(ann['image_dims'])}")
print(f"Fields count: {len(ann['Fields'])}")
print()
print("Pretty-printed Fields (first 3):")
for i, fld in enumerate(ann["Fields"][:3]):
    print(f"--- Field {i + 1} ---")
    print(json.dumps(fld, indent=2))

# %% [markdown]
# **Discussion §3 (Sample inspection)**:
#
# - The sampled annotation confirms the README's schema description:
#   each `Fields[i]` entry has a `key` block (optional textual label
#   + bbox) and a `value` block (canonical label + extracted text +
#   bbox). The `key.tag: null` case (no preceding label) appears in
#   real data; the loader handles it gracefully.
# - The `image_dims` parses cleanly via `ast.literal_eval` (it's a
#   Python list literal stored as a string, not a JSON array).
# - The form-ID round-trip to the UCSF Industry Documents URL works
#   directly — anyone with research access can fetch the underlying
#   PDF for any of the 350 annotations using the `form_id` from
#   this DataFrame.

# %% [markdown]
# ---
#
# # 4. Distributional properties {#sec-inv-cdip-distributions}

# %%
# Aggregated label-occurrence counts across all 350 forms.
totals = il.aggregate_label_counts(df)
print("Aggregated label occurrences across all 350 forms:")
print(totals.to_string())
print()

# Per-label per-form presence rate.
label_presence = pd.DataFrame(
    {
        "label_observed": list(totals.index),
        "n_occurrences": [int(totals[k]) for k in totals.index],
    }
)
label_presence["normalized_label"] = label_presence["label_observed"].apply(
    il.normalize_label
)
label_presence["presence_rate_pct"] = 100 * label_presence["n_occurrences"] / len(df)
print("Per-label presence rate (% of forms containing each label):")
print(label_presence.to_string(index=False))

# %%
# | label: fig-inv-cdip-label-presence
# | fig-cap: "Per-label presence rate across the 350 inv-cdip-tobacco annotations. Invoice_date + Invoice_number dominate (≥95% of forms); the financial fields (total_amount / amount_due / total_tax_amount) appear in 20-65% of forms; Purchase_order + due_date are the least-common."
fig, ax = plt.subplots(figsize=(10, 4))
order_idx = label_presence.sort_values("presence_rate_pct", ascending=True).index
sns.barplot(
    data=label_presence.loc[order_idx],
    x="presence_rate_pct",
    y="label_observed",
    palette=[PALETTE[0]] * len(label_presence),
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue="label_observed",
    legend=False,
)
ax.set_xlabel("Presence rate (% of 350 forms)")
ax.set_ylabel("")
ax.set_title("Per-label presence rate (inv-cdip-tobacco)", loc="left")
ax.set_xlim(0, 105)
for i, v in enumerate(label_presence.loc[order_idx, "presence_rate_pct"]):
    ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Per-form field-count distribution.
# | label: fig-inv-cdip-n-fields
# | fig-cap: "Per-form field-count distribution. Most forms carry 3-5 of the 7 possible labels; no form has all 7 in this corpus, and a small minority have only 1-2 (the very-sparse-annotation subset)."
fig, ax = plt.subplots(figsize=(8, 3.5))
sns.histplot(
    df["n_fields"],
    bins=range(0, int(df["n_fields"].max()) + 2),
    ax=ax,
    color=PALETTE[2],
    edgecolor="white",
    linewidth=0.4,
    discrete=True,
)
ax.set_xlabel("Fields per form")
ax.set_ylabel("Number of forms")
ax.set_title("Per-form field-count distribution", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Image-dimension distribution.
# | label: fig-inv-cdip-dims
# | fig-cap: "Image-dimension scatter for the underlying tobacco scans (NOT loaded locally — coordinates come from the `image_dims` JSON field). Widths cluster around 2000-2500 px; heights around 1500-2000 px. All scans are single-channel grayscale."
fig, ax = plt.subplots(figsize=(7.5, 5))
ax.scatter(
    df["image_width"],
    df["image_height"],
    alpha=0.4,
    s=20,
    color=PALETTE[1],
    edgecolor="white",
    linewidth=0.3,
)
ax.set_xlabel("Image width (pixels)")
ax.set_ylabel("Image height (pixels)")
ax.set_title("Image-dim scatter (350 tobacco invoice scans)", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %%
# Field-with-key rate distribution.
key_rate = (df["n_fields_with_key"] / df["n_fields"]).fillna(0)
print(f"Per-form 'fields with key.tag' rate:")
print(
    f"  min={key_rate.min():.2f}  "
    f"median={key_rate.median():.2f}  "
    f"mean={key_rate.mean():.2f}  "
    f"max={key_rate.max():.2f}"
)
n_no_keys = int((df["n_fields_with_key"] == 0).sum())
print(f"Forms where no field has a key: {n_no_keys}/{len(df)}")

# %% [markdown]
# **Discussion §4 (Distributions)**:
#
# - **Per-label presence is highly skewed**: `Invoice_date` (98%) and
#   `Invoice_number` (96%) dominate; the financial fields
#   (`total_amount` 64%, `amount_due` 42%, `total_tax_amount` 21%)
#   are progressively rarer; `due_date` (16%) and `Purchase_order`
#   (24%) are the least-common. **Interpretation**: not every
#   tobacco-business invoice has every possible field — sparser
#   labels reflect actual document content, not annotation oversight.
# - **No form has all 7 labels** (max n_fields = 6); median = 4.
#   This is a real schema-sparsity property of the dataset.
# - **Image dimensions cluster around modest sizes** (~2K × ~1.7K).
#   Compatible with mid-DPI scanned business documents; consistent
#   with the 1980s-2000s tobacco-corpus origin.
# - **Most fields have keys**: median 100% key-presence rate per form
#   means that when an invoice has a labeled field, the textual key
#   (e.g., "invoice number:", "total billing:") is usually annotated
#   alongside the value. This is a richer signal than fatura2's
#   pure-value NER (chapter @sec-fatura2) — closer to FUNSD's
#   entity-pair format (chapter @sec-funsd).

# %% [markdown]
# ---
#
# # 5. HORUS-relevance assessment {#sec-inv-cdip-horus}

# %% [markdown]
# **Honest framing**: inv-cdip-tobacco is the **Berghaus 2025
# cross-comparison anchor** in the HORUS substrate. NOT a primary
# training pool. Its HORUS thesis relevance is:
#
# 1. **Berghaus 2025 baseline cross-comparator**: per the source
#    stub, Berghaus et al. 2025 use inv-cdip-tobacco as one of their
#    VLM evaluation sets reporting GPT-5 / Gemini-2.5 / Gemma-3
#    extraction-F1 numbers. Reporting HORUS-VLM-cohort numbers on
#    the same 350-invoice subset is the most direct comparability
#    available to the thesis — without this anchor, claiming "open-
#    source VLMs match closed-model invoice extraction" lacks an
#    apples-to-apples reference point.
# 2. **NOT a fine-tuning training pool**: CC-BY-NC-4.0 license
#    excludes production-deployment training. Same constraint class
#    as FUNSD (chapter @sec-funsd) + OmniDocBench (chapter
#    @sec-omnidocbench). Thesis-defense use is acceptable; production
#    deployment is not.
# 3. **Methodology baseline for unlabeled+labeled extraction**: the
#    Gao 2022 paper trains on 200K unlabeled + 350 labeled — a
#    semi-supervised approach. If HORUS later explores semi-
#    supervised fine-tuning (NOT in current scope), the train_set.txt
#    ID list (~200K UCSF Industry Documents IDs) is a known-clean
#    candidate substrate.
# 4. **Tobacco-era document genre**: 1980s-2000s scanned business
#    documents. Visually noisy (fax artefacts, photocopier streaks,
#    handwritten annotations). Complements FUNSD's noise substrate
#    (chapter @sec-funsd §3) and OmniDocBench's special-issue tags
#    (chapter @sec-omnidocbench §4) for robustness evaluation.
# 5. **Genuinely invoice-shaped, NOT receipt or form**: of the 7
#    HORUS-substrate datasets, only ZUGFeRD (@sec-zugferd),
#    fatura2 (@sec-fatura2), parsee-ai (@sec-parsee-ai), and
#    inv-cdip-tobacco are *invoice*-class. CORD-v2 (@sec-cord-v2) is
#    receipts; FUNSD (@sec-funsd) is forms; OmniDocBench
#    (@sec-omnidocbench) is mixed-document. inv-cdip-tobacco brings
#    the English-invoice-with-real-OCR-noise dimension that the
#    cleaner-but-synthetic fatura2 lacks.

# %% [markdown]
# ---
#
# # 6. Anomalies & limitations {#sec-inv-cdip-anomalies}

# %% [markdown]
# - **README-vs-JSON label drift**: the README documents 7 capitalized
#   labels (Invoice_number, Purchase_order, Invoice_date, Due_date,
#   Amount_due, Total_amount, Total_tax) but the actual JSONs use a
#   mix of capitalization + an extra suffix:
#     - 3 documented capitalized labels match (`Invoice_number`,
#       `Invoice_date`, `Purchase_order`)
#     - 3 labels appear LOWERCASE in JSON (`due_date`, `amount_due`,
#       `total_amount`)
#     - 1 label has case drift PLUS an extra `_amount` suffix
#       (`Total_tax` → `total_tax_amount`)
#   This is a real source-side data-quality bug in the Salesforce
#   inv-cdip repo. Captured in `INV_CDIP_LABELS_OBSERVED` constant +
#   `normalize_label` helper for cross-corpus comparison. Flagged
#   here, NOT silently fixed at acquisition time.
# - **No images locally**: per the acquisition decision (sub-issue
#   #28 closed not-planned 2026-05-13), the underlying tobacco PDF
#   scans were not downloaded. Visual EDA is therefore N/A; the
#   chapter is annotation-only by design.
# - **License**: CC-BY-NC-4.0. Strongest license constraint
#   among the 7 HORUS datasets alongside OmniDocBench
#   (@sec-omnidocbench, non-commercial-research) and FUNSD
#   (@sec-funsd, non-commercial-research). Production HORUS
#   deployment must NOT train on inv-cdip-tobacco.
# - **Scale**: 350 labeled invoices. Above the LoRA fine-tuning floor
#   (`fine_tuning_anchors.lora_min_examples = 200`) but below the
#   thesis-defendable training-pool size. Useful as eval substrate,
#   marginal as standalone training pool.
# - **Schema sparsity**: most invoices have only 3-4 of 7 possible
#   fields. F1 evaluation must be per-field-conditional-on-presence,
#   not per-canonical-label (otherwise the absent-field F1 dominates).
# - **Tobacco-document scope**: the corpus is 100% tobacco-industry
#   business documents. NOT generalizable to modern e-commerce /
#   B2B / SaaS invoices without an explicit domain-shift caveat.

# %% [markdown]
# ---
#
# # 7. Exploratory observations log {#sec-inv-cdip-observations}

# %% [markdown]
# Per the `bidirectional-learning-pipe` rule + ADR-025 §"Per-chapter
# content template": hypothesis-shaped patterns surfaced during
# inspection captured HERE, NOT retro-fitted into H1–H6.
#
# **Observations from this Phase C iteration**:
#
# 1. **README-vs-JSON label drift is a recurring substrate-quality
#    pattern**: chapter @sec-parsee-ai surfaced a similar MANIFEST-vs-
#    README language-field discrepancy (en vs en+de). The
#    inv-cdip-tobacco discrepancy is bigger (7 labels with case +
#    suffix drift) and more consequential (downstream extraction
#    code that filters by canonical-name will silently fail). The
#    chapter @sec-cross-corpus Decision Register should consolidate
#    these into a *"trust source content over source documentation"*
#    methodology note + a candidate `make data-manifest-schema-audit`
#    target that cross-checks documented schemas against per-file
#    content sampling.
# 2. **Annotation-only acquisition is a valid scope-restriction
#    pattern**: the sub-issue #28 decision (don't download the raw
#    UCSF scans) leveraged the fact that the annotation files alone
#    are sufficient for the chapter's research goal (Berghaus
#    cross-comparison). This is a `make-sure-it-works`-aligned scope
#    discipline — avoid downloading 200K+ files when 350 KB of JSON
#    suffices for the question being asked. Worth surfacing as a
#    cross-project acquisition-methodology observation: *"when
#    evaluating a published model on a benchmark, the annotations are
#    often sufficient even when the original dataset shipping the
#    annotations also includes large file blobs"*.
# 3. **Field-presence schema sparsity is the cross-corpus gotcha**:
#    inv-cdip-tobacco has 7 possible labels but most forms have only
#    3-4. Compare ZUGFeRD's 16-field EN16931 schema (chapter
#    @sec-zugferd §5), where most invoices have only a partial-fill.
#    F1-by-canonical-label is a misleading metric when most labels
#    are absent in most forms. The chapter @sec-cross-corpus
#    Decision Register should surface this as the *"presence-
#    conditional F1"* methodology question — likely an ADR-worthy
#    eval-design decision.
