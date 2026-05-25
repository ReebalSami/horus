# ---
# title: "Cross-corpus synthesis"
# subtitle: "Chapter 8 — comparison matrices and Decision Register across the 7-dataset substrate"
# author: "Reebal Sami"
# date: "2026-05-25"
# params:
#   cfg_path: "configs/eda-zugferd.yaml"
# jupyter: python3
# ---

# %% [markdown]
# # Cross-corpus synthesis {#sec-cross-corpus}
#
# This chapter integrates the seven per-dataset chapters
# (@sec-zugferd, @sec-fatura2, @sec-omnidocbench, @sec-funsd,
# @sec-parsee-ai, @sec-cord-v2, @sec-inv-cdip) into a single
# cross-dataset view. The synthesis surfaces **observations and
# methodology decisions** that any subsequent thesis phase (PRD /
# spec / training / evaluation) needs to consider — without making
# those decisions here.
#
# **Scope discipline**: this chapter is **descriptive synthesis**.
# Per ADR-025 + the HARKing safeguards locked in brainstorm v2 §2,
# the pre-registered H1–H6 hypothesis set is READ-ONLY for this
# artifact. The chapter's §6 Decision Register lists open questions
# that downstream PRD / ADR work will resolve; it does NOT pre-commit
# answers.
#
# Per [ADR-025](../docs/decisions/ADR-025-eda-multi-dataset-book-structure.md)
# §"Per-chapter content template", the synthesis chapter uses its own
# 6-section structure (master table + 4 dimensional matrices + the
# Decision Register), not the per-dataset 7-section template.

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-cross-corpus-setup}

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from horus.config import ExperimentConfig
from horus.eda.figures import apply_styles
from horus.seeding import set_global_seed

# %%
# This synthesis chapter does not load any single dataset's config — it
# integrates findings across all 7 chapters. It reuses ZUGFeRD's config
# only for the shared palette + figure DPI conventions (same FT/NYT-
# influenced muted aesthetic as chapters 1-7).
cfg_path: str = "configs/eda-zugferd.yaml"


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
set_global_seed(cfg.seed)

_styles = apply_styles(
    palette_static=cfg.eda.palette_static,
    palette_interactive=cfg.eda.palette_interactive,
    n_colors=12,
)
PALETTE = _styles.palette

plt.rcParams["figure.dpi"] = cfg.eda.figure_dpi
plt.rcParams["savefig.dpi"] = cfg.eda.figure_dpi
plt.rcParams["axes.titleweight"] = "semibold"
plt.rcParams["axes.titlepad"] = 14

pd.set_option("display.max_rows", None)
pd.set_option("display.min_rows", 25)
pd.set_option("display.max_colwidth", 200)

# %% [markdown]
# ---
#
# # 1. Master comparison table {#sec-cross-corpus-master}
#
# One row per dataset; columns capture the load-bearing dimensions
# (size / format / language / label-type / license / commercial-use
# eligibility / HORUS-relevance tier).

# %%
# All values declared verbatim from the per-chapter §1 Provenance + §2
# Composition sections (chapters 1-7). This is NOT a re-computed table —
# the chapter's authors hand-curated these dimensions from the per-dataset
# loaders' output.
MASTER_TABLE = pd.DataFrame(
    [
        {
            "chapter": "@sec-zugferd",
            "dataset": "ZUGFeRD corpus",
            "language": "DE",
            "n_examples": 151,
            "size_mb": 145,
            "format": "PDF + sidecar XML",
            "label_type": "16-field EN16931",
            "license": "Apache-2.0",
            "production_ok": True,
            "horus_role": "primary German invoice substrate",
        },
        {
            "chapter": "@sec-fatura2",
            "dataset": "fatura2-invoices",
            "language": "EN",
            "n_examples": 10000,
            "size_mb": 343,
            "format": "Parquet (embedded JPEG)",
            "label_type": "24-class token-NER",
            "license": "CC-BY-4.0",
            "production_ok": True,
            "horus_role": "VLM training pool + template-shift robustness",
        },
        {
            "chapter": "@sec-omnidocbench",
            "dataset": "OmniDocBench",
            "language": "ZH/EN/mixed",
            "n_examples": 1651,
            "size_mb": 1500,
            "format": "PNG + JSON annotations",
            "label_type": "18+ region category_types",
            "license": "LicenseRef-OmniDocBench-research-only",
            "production_ok": False,
            "horus_role": "OCR-route robustness + Chinese transfer",
        },
        {
            "chapter": "@sec-funsd",
            "dataset": "FUNSD",
            "language": "EN",
            "n_examples": 199,
            "size_mb": 28,
            "format": "PNG + JSON annotations",
            "label_type": "4 entity labels + linking pairs",
            "license": "LicenseRef-FUNSD-noncommercial-research",
            "production_ok": False,
            "horus_role": "form-understanding methodology baseline (LayoutLM family)",
        },
        {
            "chapter": "@sec-parsee-ai",
            "dataset": "parsee-ai-invoices-example",
            "language": "EN+DE (bilingual)",
            "n_examples": 45,
            "size_mb": 0.05,
            "format": "Parquet (text only)",
            "label_type": "Q-and-A prompt+structured-truth pairs",
            "license": "MIT",
            "production_ok": True,
            "horus_role": "Layer 3 analytical-query smoke + bilingual fixture",
        },
        {
            "chapter": "@sec-cord-v2",
            "dataset": "CORD-v2",
            "language": "KO",
            "n_examples": 1000,
            "size_mb": 2300,
            "format": "Parquet (embedded image)",
            "label_type": "Donut-style hierarchical JSON",
            "license": "CC-BY-4.0",
            "production_ok": True,
            "horus_role": "OCR-free VLM benchmark + Korean transfer",
        },
        {
            "chapter": "@sec-inv-cdip",
            "dataset": "inv-cdip-tobacco",
            "language": "EN",
            "n_examples": 350,
            "size_mb": 2,
            "format": "JSON annotations only (no scans)",
            "label_type": "7-field invoice schema",
            "license": "CC-BY-NC-4.0",
            "production_ok": False,
            "horus_role": "Berghaus 2025 cross-comparison anchor",
        },
    ]
)
print("Master comparison table (7 datasets × 9 dimensions):")
print(MASTER_TABLE.to_string(index=False))

# %%
# Totals row — substrate-wide aggregates.
total_examples = int(MASTER_TABLE["n_examples"].sum())
total_size_mb = MASTER_TABLE["size_mb"].sum()
n_permissive = int(MASTER_TABLE["production_ok"].sum())
n_restrictive = int((~MASTER_TABLE["production_ok"]).sum())
print(f"\nSubstrate totals:")
print(f"  Total examples across all 7 datasets: {total_examples:>7,d}")
print(f"  Total on-disk size:                   {total_size_mb:>7.0f} MB")
print(f"  Permissive-license datasets (production-OK): {n_permissive}/7")
print(f"  Restrictive-license datasets (research-only): {n_restrictive}/7")

# %% [markdown]
# **Discussion §1 (Master table)**:
#
# - **One-order-of-magnitude size spread**: fatura2 (10K examples)
#   dominates by example count; CORD-v2 (2.3 GB) dominates by disk
#   footprint due to embedded image bytes. The smallest datasets
#   (parsee-ai 45 rows / FUNSD 199 / inv-cdip 350) are evaluation
#   fixtures, NOT training pools.
# - **The German anchor is small**: ZUGFeRD's 151 invoices are the
#   ONLY German content in the substrate. Every other dataset is
#   English, Korean, or Chinese-dominant. The HORUS thesis target
#   (German tax advisors) has 151 native examples — below the
#   `eval_min_examples_for_thesis = 100` floor for thesis-defendable
#   F1, BUT also below most published-fine-tuning thresholds.
# - **Five distinct label schemas** across 7 datasets (see §4):
#   16-field flat extraction (ZUGFeRD + inv-cdip), 24-class token-NER
#   (fatura2), 4-class entity-linking (FUNSD), Donut hierarchical
#   JSON (CORD-v2), 18+ region categories (OmniDocBench), Q-and-A
#   structured truth (parsee-ai).

# %% [markdown]
# ---
#
# # 2. Format coverage matrix {#sec-cross-corpus-format}

# %%
# Build a matrix: dataset × format-type (PDF / image / parquet / annotations-only).
FORMAT_FLAGS = {
    "ZUGFeRD corpus":             {"PDF": True,  "image": False, "parquet": False, "json_only": False, "xml_sidecar": True},
    "fatura2-invoices":           {"PDF": False, "image": True,  "parquet": True,  "json_only": False, "xml_sidecar": False},
    "OmniDocBench":               {"PDF": False, "image": True,  "parquet": False, "json_only": False, "xml_sidecar": False},
    "FUNSD":                      {"PDF": False, "image": True,  "parquet": False, "json_only": False, "xml_sidecar": False},
    "parsee-ai-invoices-example": {"PDF": False, "image": False, "parquet": True,  "json_only": False, "xml_sidecar": False},
    "CORD-v2":                    {"PDF": False, "image": True,  "parquet": True,  "json_only": False, "xml_sidecar": False},
    "inv-cdip-tobacco":           {"PDF": False, "image": False, "parquet": False, "json_only": True,  "xml_sidecar": False},
}
format_matrix = pd.DataFrame(FORMAT_FLAGS).T
print("Format coverage matrix (dataset × format-component):")
print(format_matrix.astype(int).to_string())

# %%
# | label: fig-cross-corpus-format
# | fig-cap: "Format coverage matrix. PDF appears only in ZUGFeRD (with sidecar XML); image-bearing datasets (fatura2 / OmniDocBench / FUNSD / CORD-v2) ship the visuals; parsee-ai is text-only parquet; inv-cdip-tobacco is annotations-only (no underlying scans)."
fig, ax = plt.subplots(figsize=(8, 4.5))
sns.heatmap(
    format_matrix.astype(int),
    annot=True,
    cbar=False,
    cmap="Blues",
    linewidths=0.5,
    ax=ax,
)
ax.set_xlabel("Format component")
ax.set_ylabel("")
ax.set_title("Format coverage across the 7-dataset substrate", loc="left")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §2 (Format coverage)**:
#
# - **PDF is rare**: ZUGFeRD is the only PDF-bearing dataset. Every
#   other image-bearing dataset (fatura2 / OmniDocBench / FUNSD /
#   CORD-v2) ships rasterized images (PNG / JPEG). PDFs uniquely
#   carry the embedded-text-layer + sidecar-XML signal that ZUGFeRD's
#   chapter @sec-zugferd §10 sufficiency report leverages.
# - **OCR-route validation substrate scarcity**: only ZUGFeRD has the
#   "PDF + structured XML ground-truth" combo that lets HORUS
#   compare OCR-extracted text against authoritative field-value
#   ground truth at the original-document level. The held-out
#   Belege are off-corpus per the locked plan + brainstorm v2 §9.3.
# - **Annotation-only is unique to inv-cdip**: the deliberate
#   acquisition scope decision (sub-issue #28 closed not-planned)
#   makes inv-cdip-tobacco the only dataset where visual EDA is N/A
#   and Datasheet completeness comes from the annotation schema alone.

# %% [markdown]
# ---
#
# # 3. Language coverage map {#sec-cross-corpus-language}

# %%
# Per-language datasets + cumulative example counts.
language_table = pd.DataFrame(
    [
        {"language": "DE (German)",    "datasets": ["ZUGFeRD"],                                  "n_examples_cum": 151},
        {"language": "EN (English)",    "datasets": ["fatura2", "FUNSD", "inv-cdip-tobacco"],     "n_examples_cum": 10000 + 199 + 350},
        {"language": "EN+DE bilingual", "datasets": ["parsee-ai-invoices-example"],               "n_examples_cum": 45},
        {"language": "ZH+EN OmniDoc",  "datasets": ["OmniDocBench"],                              "n_examples_cum": 1651},
        {"language": "KO (Korean)",    "datasets": ["CORD-v2"],                                   "n_examples_cum": 1000},
    ]
)
print("Language coverage:")
print(language_table.to_string(index=False))

# %%
# | label: fig-cross-corpus-language
# | fig-cap: "Cumulative example count per language coverage class. EN dominates by raw count (fatura2 + FUNSD + inv-cdip = 10,549 examples); German is the thesis target but smallest single-language pool (151); Korean (CORD-v2) and Chinese-dominant (OmniDocBench) are cross-script comparators."
fig, ax = plt.subplots(figsize=(9, 4))
sns.barplot(
    data=language_table,
    x="n_examples_cum",
    y="language",
    palette=[PALETTE[i] for i in (0, 2, 5, 8, 10)],
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue="language",
    legend=False,
)
ax.set_xlabel("Cumulative example count")
ax.set_ylabel("")
ax.set_title("Language coverage across the substrate", loc="left")
ax.set_xscale("log")
for i, v in enumerate(language_table["n_examples_cum"]):
    ax.text(v * 1.1, i, f"{int(v):,}", va="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §3 (Language coverage)**:
#
# - **German is the thesis target but the smallest pool**: 151
#   ZUGFeRD invoices are the entire German content in the substrate.
#   For comparison, English content totals ~10,549 examples across
#   3 datasets. Cross-language transfer (EN → DE) is the load-bearing
#   methodology assumption for any HORUS model that supplements
#   ZUGFeRD with English pretraining.
# - **Bilingual content exists at scale = 45 rows**: parsee-ai is the
#   only en+de mixed dataset; 45 rows is methodology-fixture scale
#   only. Genuine en+de evaluation requires self-collected Belege
#   (per brainstorm v2 §9.3) or custom en+de synthesis.
# - **Cross-script test bed**: Korean (CORD-v2 / 1000) + Chinese
#   (OmniDocBench / ~760 ZH) provide a non-Latin-script
#   generalization-test substrate. NOT German-aligned, but a useful
#   stress test for VLM image-encoders trained primarily on Latin
#   script.

# %% [markdown]
# ---
#
# # 4. Label-schema overlap {#sec-cross-corpus-schema}

# %%
# Per-dataset label-schema summary. Five distinct shapes across 7 datasets.
schema_table = pd.DataFrame(
    [
        {
            "dataset": "ZUGFeRD",
            "schema_shape": "Flat field-extraction",
            "n_canonical_labels": 16,
            "example_label": "BT-1 (Invoice number), BT-2 (Issue date), ...",
            "evaluation_metric": "per-field F1 (presence-conditional)",
        },
        {
            "dataset": "fatura2",
            "schema_shape": "Token-level NER",
            "n_canonical_labels": 24,
            "example_label": "B-DATE / B-TOTAL / B-SELLER-ADDRESS / ...",
            "evaluation_metric": "token-NER F1 (BIO scheme)",
        },
        {
            "dataset": "OmniDocBench",
            "schema_shape": "Region-level category",
            "n_canonical_labels": 18,
            "example_label": "text_block / title / equation_isolated / figure / table / ...",
            "evaluation_metric": "page-region detection mAP",
        },
        {
            "dataset": "FUNSD",
            "schema_shape": "Entity + relation-linking",
            "n_canonical_labels": 4,
            "example_label": "other / question / answer / header + linking pairs",
            "evaluation_metric": "entity F1 + linking F1",
        },
        {
            "dataset": "parsee-ai",
            "schema_shape": "Q-and-A structured truth",
            "n_canonical_labels": 3,
            "example_label": "general0 / general1 / general2 (parsee elements)",
            "evaluation_metric": "parsee-core structured-answer match",
        },
        {
            "dataset": "CORD-v2",
            "schema_shape": "Hierarchical JSON (Donut)",
            "n_canonical_labels": "3+ (menu / sub_total / total + nested fields)",
            "example_label": "gt_parse.menu[i].{nm, cnt, price} + gt_parse.total.total_price",
            "evaluation_metric": "tree-edit-distance F1 (Donut)",
        },
        {
            "dataset": "inv-cdip-tobacco",
            "schema_shape": "Flat field-extraction",
            "n_canonical_labels": 7,
            "example_label": "Invoice_number / Invoice_date / total_amount / ...",
            "evaluation_metric": "per-field F1 (presence-conditional)",
        },
    ]
)
print("Label-schema overlap (5 distinct schema shapes across 7 datasets):")
print(schema_table.to_string(index=False))

# %%
# How many datasets fall into each schema shape?
shape_counts = schema_table["schema_shape"].value_counts()
print("\nSchema-shape distribution:")
print(shape_counts.to_string())

# %% [markdown]
# **Discussion §4 (Label-schema overlap)**:
#
# - **Five distinct schema shapes** in 7 datasets. ZUGFeRD and
#   inv-cdip-tobacco share the "flat field-extraction" shape (16
#   and 7 fields respectively) — they're the most direct
#   cross-comparators. Every other dataset has its own schema
#   convention.
# - **NO unifying evaluation metric exists across all 7 datasets**.
#   Each schema shape requires its own F1 / mAP / tree-edit-distance
#   measurement. A single "HORUS extraction F1" headline number that
#   averages across all 7 is **methodologically meaningless** —
#   reported numbers must be per-dataset.
# - **Cross-dataset F1 comparison requires label-mapping tables**.
#   Example: fatura2's 24-class token-NER → ZUGFeRD's 16-field flat
#   extraction would need a `{B-TOTAL → BT-112, B-DATE → BT-2, ...}`
#   normalization. The chapter @sec-fatura2 §5 + @sec-inv-cdip §6
#   already surface this; the work itself is downstream of the EDA.
# - **`Invoice_date`-style labels are NOT consistent across the
#   substrate**: ZUGFeRD uses EN16931 codes (BT-2), inv-cdip uses
#   capitalized strings (`Invoice_date`), fatura2 uses BIO tags
#   (`B-DATE`), CORD-v2 uses nested JSON keys. Label-canonicalization
#   is a real prerequisite for any cross-dataset claim.

# %% [markdown]
# ---
#
# # 5. License-tier asymmetry {#sec-cross-corpus-license}

# %%
LICENSE_TIER = pd.DataFrame(
    [
        {"dataset": "ZUGFeRD",           "tier": "permissive",  "spdx": "Apache-2.0",
         "production_train_ok": True,  "production_inference_ok": True,
         "attribution_required": True,  "commercial_restriction": "none"},
        {"dataset": "fatura2",           "tier": "permissive",  "spdx": "CC-BY-4.0",
         "production_train_ok": True,  "production_inference_ok": True,
         "attribution_required": True,  "commercial_restriction": "none"},
        {"dataset": "parsee-ai",         "tier": "permissive",  "spdx": "MIT",
         "production_train_ok": True,  "production_inference_ok": True,
         "attribution_required": True,  "commercial_restriction": "none"},
        {"dataset": "CORD-v2",           "tier": "permissive",  "spdx": "CC-BY-4.0",
         "production_train_ok": True,  "production_inference_ok": True,
         "attribution_required": True,  "commercial_restriction": "none"},
        {"dataset": "OmniDocBench",     "tier": "restrictive", "spdx": "LicenseRef-OmniDocBench-research-only",
         "production_train_ok": False, "production_inference_ok": False,
         "attribution_required": True,  "commercial_restriction": "non-commercial-research only"},
        {"dataset": "FUNSD",             "tier": "restrictive", "spdx": "LicenseRef-FUNSD-noncommercial-research",
         "production_train_ok": False, "production_inference_ok": False,
         "attribution_required": True,  "commercial_restriction": "non-commercial-research only"},
        {"dataset": "inv-cdip-tobacco", "tier": "restrictive", "spdx": "CC-BY-NC-4.0",
         "production_train_ok": False, "production_inference_ok": False,
         "attribution_required": True,  "commercial_restriction": "non-commercial only"},
    ]
)
print("License-tier matrix:")
print(LICENSE_TIER.to_string(index=False))

# %%
# Production-deployment scope: what's usable for a production HORUS that
# could ship to paying clients vs research-only thesis defense.
print(f"\nProduction-deployment scope (a production HORUS shipping to paying clients):")
permissive = LICENSE_TIER[LICENSE_TIER["tier"] == "permissive"]["dataset"].tolist()
restrictive = LICENSE_TIER[LICENSE_TIER["tier"] == "restrictive"]["dataset"].tolist()
print(f"  Permissive (production-OK):       {permissive}")
print(f"  Restrictive (research-only):      {restrictive}")
print(f"\nThesis-defense scope (research-only is acceptable; the thesis itself is academic):")
print(f"  ALL 7 datasets in scope: {LICENSE_TIER['dataset'].tolist()}")

# %% [markdown]
# **Discussion §5 (License-tier asymmetry)**:
#
# - **4 permissive vs 3 restrictive**: a near-even split. Production
#   HORUS deployment can train on ~40% of substrate examples by count
#   (excluding restrictives) — ZUGFeRD (151) + fatura2 (10000) +
#   parsee-ai (45) + CORD-v2 (1000) = 11,196 examples. Restrictive
#   datasets (OmniDocBench 1651 + FUNSD 199 + inv-cdip 350 = 2200
#   examples) are thesis-only.
# - **The Berghaus 2025 cross-comparison anchor is restrictive**:
#   inv-cdip-tobacco (CC-BY-NC-4.0) is the load-bearing dataset for
#   HORUS-vs-published-baseline F1 comparison (chapter @sec-inv-cdip
#   §5). The thesis can report numbers; a production product cannot
#   ship a model trained on the same data. This is a real
#   methodology gap that needs an ADR-worthy decision.
# - **Permissive cluster shares CC-BY-4.0 / MIT / Apache-2.0**:
#   standard ML-permissive licenses with attribution requirements
#   but no commercial restriction. ZUGFeRD's Apache-2.0 + fatura2's
#   CC-BY-4.0 + parsee-ai's MIT + CORD-v2's CC-BY-4.0 form the
#   production-deployable training pool.

# %% [markdown]
# ---
#
# # 6. Decision Register {#sec-cross-corpus-decisions}
#
# Methodology questions and observations surfaced during the EDA
# that downstream PRD / spec / ADR phases need to address. **This
# section does NOT make scope decisions** — it surfaces them.

# %% [markdown]
# ## DR-1 — ZUGFeRDv1 parser-incompatibility
#
# **Context**: chapter @sec-zugferd §9 surfaced that the current
# `parse_cii_xml` parser does not handle the ZUGFeRDv1 namespace
# (urn:ferd:CrossIndustryDocument:invoice:1p0). 25 of the 151
# ZUGFeRD invoices use the v1 schema and are currently parser-
# incompatible.
#
# **Decision needed (future ADR)**: extend `parse_cii_xml` to
# handle v1 namespace OR explicitly scope the held-out evaluation
# to ZUGFeRDv2+ only? Scoping out v1 reduces the substrate by 17%;
# extending the parser is non-trivial because v1's schema differs
# from v2 in field semantics, not just namespace.

# %% [markdown]
# ## DR-2 — Cross-dataset label-schema bridging
#
# **Context**: chapter §4 above documents 5 distinct schema shapes
# across 7 datasets. No unifying evaluation metric exists.
#
# **Decision needed (future ADR)**: report per-dataset F1 only
# (acknowledging the schema gap) OR build a label-mapping table
# that normalizes 4-5 invoice schemas (ZUGFeRD 16-field, fatura2
# 24-NER, inv-cdip 7-field, parsee-ai 3-element) into a common
# canonical schema for cross-dataset comparison? The former is
# methodologically safer; the latter enables stronger thesis
# claims at the cost of additional label-engineering work.

# %% [markdown]
# ## DR-3 — License-tier production exclusions
#
# **Context**: chapter §5 above documents 3 restrictive-license
# datasets (OmniDocBench / FUNSD / inv-cdip-tobacco). Berghaus
# 2025 baseline comparator (inv-cdip-tobacco) is restrictive.
#
# **Decision needed (future ADR)**: if HORUS is intended for
# production deployment to paying tax-advisor clients, which
# training subsets must be excluded? Thesis-only training is fine;
# production-licensed training requires explicit dropping of the
# restrictive subset + an architectural decision about whether
# HORUS-research vs HORUS-production share weights at all.

# %% [markdown]
# ## DR-4 — OCR-route validation substrate scarcity
#
# **Context**: chapter §2 above + chapter @sec-zugferd §1 surfaced
# that the OCR-route methodology (compare OCR output against
# authoritative ground truth at the PDF level) requires a
# "PDF + structured-XML ground-truth" combo that ONLY ZUGFeRD
# provides on-corpus. The Hetzner unstructured PDF (chapter
# @sec-zugferd §1) is the single non-ZUGFeRD-Factur-X PDF
# available; the German Belege (private + PII-sensitive) are
# off-corpus per the locked plan.
#
# **Decision needed (future ADR)**: is the OCR-route validation
# claim defensible with N=151 ZUGFeRD PDFs + 1 Hetzner PDF
# alone? If not, what's the minimal Belege subset that needs
# redaction + co-location with the OCR-route ADR? Surfacing
# this here, not deciding.

# %% [markdown]
# ## DR-5 — MANIFEST/README accuracy drift
#
# **Context**: two source-side documentation discrepancies
# surfaced during EDA:
#
# 1. **parsee-ai** (chapter @sec-parsee-ai §6): MANIFEST claims
#    `language: english` but README declares `en, de` AND empirical
#    inspection finds ~40% German content per row.
# 2. **inv-cdip-tobacco** (chapter @sec-inv-cdip §6): README
#    documents 7 capitalized labels but the actual JSON annotations
#    use a mix of capitalization + an extra suffix (4 of 7 labels
#    have drift).
#
# **Decision needed (future ADR or process change)**: should the
# acquisition pipeline include a `make data-manifest-content-audit`
# target that cross-checks documented schemas + languages against
# per-file content sampling? Discrepancies should be FOUND at
# acquisition time, not by downstream EDA inspection. Sub-issue
# candidate.

# %% [markdown]
# ## DR-6 — Quarto Book YAML-parser markdown trigger
#
# **Context**: during Phase C.4 (chapter @sec-funsd authoring), a
# multi-iteration debug session failed to resolve a Quarto-render
# `YAMLException: unidentified alias *Discussion` error. Clean-room
# rewrite from chapter @sec-fatura2's structure rendered green on
# first try. Empirical observation (uninstrumented): `## Discussion`
# heading + `**Bold**: text` bullet adjacency in `.py:percent`
# markdown cells triggers a Quarto-internal YAML lexer; the
# `**Discussion §N (Caption)**:` bold-prefix-label pattern bypasses
# it.
#
# **Decision needed (defer)**: codify the working pattern as an L3
# `python-ml-uv` rule? Captured to
# `cascade-system/queue/pending-review.md` 2026-05-25; promotion
# deferred until a second project hits the same error class OR an
# instrumented bisect confirms the root cause.

# %% [markdown]
# ## DR-7 — Presence-conditional F1 methodology
#
# **Context**: chapter @sec-inv-cdip §6 + chapter @sec-zugferd §10
# surface that most invoices in field-extraction datasets DON'T
# have every possible field. inv-cdip's 350 invoices average 4 of
# 7 labels; ZUGFeRD's 16-field schema is partially-filled per
# invoice.
#
# **Decision needed (future ADR)**: F1-per-canonical-label is
# misleading when most labels are absent in most forms (high
# baseline-of-absence inflates the headline). Should HORUS report
# F1 conditional on field-presence-in-ground-truth, OR report a
# per-field precision/recall pair, OR both? An ADR-worthy
# evaluation-design decision.

# %% [markdown]
# ## DR-8 — Cross-script transferability test design
#
# **Context**: the HORUS substrate contains German (ZUGFeRD),
# English (fatura2 / FUNSD / inv-cdip / parsee-ai-en), Korean
# (CORD-v2), and Chinese-dominant (OmniDocBench) content. This
# enables an unusual cross-script generalization test.
#
# **Decision needed (defer; possibly H7 candidate)**: should the
# thesis include a cross-script-transferability evaluation arm,
# OR scope it to within-language evaluation only? Captured as
# Exploratory observation in chapter @sec-cord-v2 §7 + chapter
# @sec-omnidocbench §7; NOT promoted to H1–H6 per HARKing
# discipline. The decision criterion is "does this strengthen the
# thesis claim?" — that's a PRD-phase question.

# %% [markdown]
# ## Closing
#
# Eight Decision Register entries (DR-1 through DR-8) surface
# methodology questions that future thesis-PRD / spec / ADR work
# will resolve. None are blockers for the EDA itself; all are
# load-bearing for the **next phase** that this EDA enables.
#
# **The EDA's purpose is met when these decisions are surfaced,
# NOT when they're answered.** Per ADR-025 + brainstorm v2 §2
# HARKing discipline, surfacing questions is the right output
# shape for a descriptive EDA artifact; answering them belongs
# downstream.
