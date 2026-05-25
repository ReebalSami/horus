# ---
# title: "EDA on the ZUGFeRD corpus"
# subtitle: "Descriptive-only analysis (Issue #46, ADR-024)"
# author: "Reebal Sami"
# date: "2026-05-25"
# format:
#   html:
#     toc: true
#     toc-depth: 3
#     code-fold: true
#     fig-format: svg
#   pdf:
#     toc: true
#     toc-depth: 3
#     fig-format: pdf
# jupyter: python3
# ---

# %% [markdown]
# # Introduction {#sec-intro}
#
# This notebook is a **descriptive-only** exploratory data analysis of the
# ZUGFeRD corpus on disk at `data/raw/german/zugferd-corpus/` (151 PDFs +
# 88 standalone XMLs, sealed via `MANIFEST.md`). Its scope per issue #46
# and the locked plan at `~/.windsurf/plans/eda-zugferd-9c4a5b.md`:
#
# 1. Characterize the corpus (per-flavor / per-profile / per-page-count
#    / per-field statistics).
# 2. Surface a complexity-tier proposal grounded in descriptive features.
# 3. Produce a fine-tuning sufficiency report grounded in literature anchors.
# 4. Capture exploratory observations to a separate log (NOT into H1–H6).
#
# ## HARKing safeguards (load-bearing)
#
# Per brainstorm v2 §2 (No-HARKing) + ADR-024:
#
# - The pre-registered hypothesis set H1–H6 (timestamped 2026-05-08 in
#   `docs/prompts/stages/02-brainstorm.md` §6) is **READ-ONLY** for this
#   artifact. New patterns surfaced go to §3.3k Exploratory observations,
#   NOT retro-fitted into H1–H6.
# - The complexity-tier thresholds were **PRE-COMMITTED** in
#   `configs/eda-zugferd.yaml` BEFORE this EDA ran. Retroactive adjustment
#   leaves a git-tracked paper trail.
# - Held-out test set is **EXTERNAL** per brainstorm v2 §9.3 literal reading
#   (Q4=A in the plan) — self-collected Belege + future GI 2021 frozen
#   subset. ZUGFeRD is fully training/dev substrate. Pilot-13 F1=0.49 is a
#   smoke result, NOT a thesis claim.
#
# ## Reading order
#
# Each section produces (a) a static editorial figure for thesis appendix,
# (b) optionally a Plotly interactive version in §11 Interactive Explorer
# (drops to static fallback in PDF), and (c) a brief discussion before the
# next section. Cross-references via `@fig-…` / `@sec-…` are first-class
# (Quarto rendering).

# %% [markdown]
# ---
#
# # Setup: configuration + libraries {#sec-setup}
#
# Per `horus-config-discipline`: ALL knobs live in `configs/eda-zugferd.yaml`.
# This notebook accepts ONE papermill parameter `cfg_path`. Pydantic
# validates at boot; missing/malformed YAML fails fast BEFORE any analysis.

# %%
from __future__ import annotations

import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import facturx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
import pypdfium2 as pdfium
import seaborn as sns
from lxml import etree

from horus.config import ExperimentConfig
from horus.eval.ground_truth import FIELDS, GroundTruth, parse_cii_xml
from horus.seeding import set_global_seed

# %% tags=["parameters"]
# Default for interactive runs (e.g., `quarto render` without `-P`).
# Papermill / Quarto override via `-P cfg_path:configs/<name>.yaml`.
cfg_path: str = "configs/eda-zugferd.yaml"

# %%
# Repo root (resolved from this file's location at jupytext-evaluation time;
# falls back to cwd for direct interactive use).
try:
    REPO_ROOT = Path(__file__).resolve().parent.parent  # type: ignore[name-defined]
except NameError:
    REPO_ROOT = Path.cwd()

# Resolve cfg_path relative to repo root if not absolute.
_cfg_resolved = Path(cfg_path)
if not _cfg_resolved.is_absolute():
    _cfg_resolved = REPO_ROOT / _cfg_resolved

cfg = ExperimentConfig.from_yaml(_cfg_resolved)
assert cfg.eda is not None, (
    f"Config at {_cfg_resolved} must declare an `eda:` section per ADR-024 "
    "+ horus-config-discipline."
)
EDA = cfg.eda

# Seed for any random sampling (e.g., random-pick examples per tier).
set_global_seed(cfg.seed)

# Resolve corpus root relative to repo root if not absolute.
CORPUS_ROOT = EDA.corpus_root if EDA.corpus_root.is_absolute() else REPO_ROOT / EDA.corpus_root

print("HORUS EDA on ZUGFeRD corpus")
print("=" * 60)
print(f"  Config:       {_cfg_resolved}")
print(f"  Corpus root:  {CORPUS_ROOT}")
print(f"  Output dir:   {EDA.output_dir}")
print(f"  Seed:         {cfg.seed}")
print(f"  MLflow exp:   {cfg.mlflow.experiment_name}")
print()
print("Pre-committed knobs (HARKing safeguards):")
print(f"  Page bins:    {EDA.page_count_bins}")
print(
    f"  Tiers:        simple<=({EDA.complexity.simple_max_pages}p, "
    f"{EDA.complexity.simple_max_line_items}li); "
    f"medium<=({EDA.complexity.medium_max_pages}p, "
    f"{EDA.complexity.medium_max_line_items}li)"
)
print(
    f"  FT anchors:   LoRA [{EDA.fine_tuning_anchors.lora_min_examples}, "
    f"{EDA.fine_tuning_anchors.lora_target_examples}]; "
    f"eval-min={EDA.fine_tuning_anchors.eval_min_examples_for_thesis}"
)

if not CORPUS_ROOT.is_dir():
    raise FileNotFoundError(
        f"Corpus root not found: {CORPUS_ROOT}\n"
        "Acquire the ZUGFeRD corpus first; see "
        "data/raw/german/zugferd-corpus/README.md."
    )

# %%
# Editorial palette + styling (FT/NYT-influenced muted aesthetic per Q5=C
# hybrid in the plan). Static figures = matplotlib/seaborn; interactive
# figures = Plotly. The two stacks are intentionally separate per ADR-024:
# static survives the PDF export; interactive is HTML-only.
sns.set_theme(
    style="white",
    palette=EDA.palette_static,
    context="paper",
    font_scale=1.05,
)
plt.rcParams["figure.dpi"] = EDA.figure_dpi
plt.rcParams["savefig.dpi"] = EDA.figure_dpi
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.titleweight"] = "semibold"
plt.rcParams["axes.titlepad"] = 14
plt.rcParams["axes.labelsize"] = 10
plt.rcParams["axes.labelweight"] = "regular"
plt.rcParams["xtick.labelsize"] = 9
plt.rcParams["ytick.labelsize"] = 9
plt.rcParams["legend.frameon"] = False
plt.rcParams["legend.fontsize"] = 9
plt.rcParams["figure.titlesize"] = 13

# Plotly default template + figure size.
pio.templates.default = EDA.palette_interactive
PLOTLY_LAYOUT = dict(
    margin=dict(t=60, l=60, r=20, b=60),
    font=dict(family="DejaVu Sans, sans-serif", size=12),
    title=dict(x=0.0, xanchor="left", font=dict(size=14)),
)

# Curated palette (12 muted colors for per-flavor / per-profile faceting).
# Two parallel forms: PALETTE = list of (r, g, b) tuples for matplotlib/seaborn
# (which accept tuples natively); PALETTE_HEX = list of "#rrggbb" strings for
# Plotly (which rejects raw RGB tuples in color_discrete_sequence /
# color_continuous_scale — see plotly/_plotly_utils/basevalidators.py).
PALETTE = sns.color_palette(EDA.palette_static, n_colors=12)
PALETTE_HEX = PALETTE.as_hex()

# Suppress factur-x's verbose schema warnings during bulk parsing
# (we capture errors explicitly in §9 Anomalies; surface them there).
warnings.filterwarnings("ignore", category=UserWarning, module="facturx")

print(f"Static palette:      {EDA.palette_static} ({len(PALETTE)} colors)")
print(f"Interactive template: {EDA.palette_interactive}")
print(f"Figure DPI:          {EDA.figure_dpi}")

# %% [markdown]
# ---
#
# # 1. Manifest reconciliation {#sec-manifest}
#
# Walks the corpus root and builds a `corpus_index` DataFrame with one row
# per file. Verifies the live count matches the recorded `MANIFEST.md`
# expectations from the dataset-acquisition step. Failures here surface
# corpus-acquisition gaps immediately (per the `expected_min_pdfs` knob
# in `configs/eda-zugferd.yaml`).
#
# **What this section does NOT do**: parse embedded XML, count pages, or
# compute any per-PDF analytical features. Those live in later sections.
# §1 is a fast filesystem walk to anchor every later analysis on a
# reproducible substrate.

# %%
# ---------------------------------------------------------------------------
# Filesystem walk → corpus_index DataFrame.
# ---------------------------------------------------------------------------


def _classify_extension(path: Path) -> str:
    """Map filename to a normalized extension class.

    `.cii.xml` and `.ubl.xml` collapse to plain `.xml` since the schema
    distinction is captured by `subdir` (XML-Rechnung/CII vs UBL).
    """
    name = path.name.lower()
    if name.endswith(".pdf"):
        return ".pdf"
    if name.endswith(".xml"):
        return ".xml"
    return path.suffix.lower() or "(none)"


def walk_corpus(root: Path) -> pd.DataFrame:
    """Walk corpus root and produce a one-row-per-file DataFrame."""
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Skip MANIFEST.md / sha256.txt / README.md / LICENSE — these are
        # metadata, not corpus content.
        if path.name in {"MANIFEST.md", "sha256.txt", "README.md", "LICENSE"}:
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        flavor = parts[0] if len(parts) >= 1 else "(root)"
        subdir = parts[1] if len(parts) >= 2 else "(none)"
        nested = "/".join(parts[2:-1]) if len(parts) > 3 else ""
        ext = _classify_extension(path)
        rows.append(
            {
                "path": path,
                "relative_path": rel,
                "flavor": flavor,
                "subdir": subdir,
                "nested": nested,
                "filename": path.name,
                "extension": ext,
                "size_bytes": path.stat().st_size,
                "is_pdf": ext == ".pdf",
                "is_xml": ext == ".xml",
            }
        )
    if not rows:
        raise RuntimeError(
            f"Corpus walk produced zero files under {root}. Verify the corpus is fully fetched."
        )
    return pd.DataFrame(rows)


corpus_index = walk_corpus(CORPUS_ROOT)
print(f"Corpus walk produced {len(corpus_index):,} files.")
print(f"  PDFs: {int(corpus_index['is_pdf'].sum()):>4}")
print(f"  XMLs: {int(corpus_index['is_xml'].sum()):>4}")
print(f"  Other: {int((~corpus_index['is_pdf'] & ~corpus_index['is_xml']).sum()):>3}")

# %%
# ---------------------------------------------------------------------------
# Sanity check: PDF count >= expected_min_pdfs.
# ---------------------------------------------------------------------------
n_pdfs = int(corpus_index["is_pdf"].sum())
if n_pdfs < EDA.expected_min_pdfs:
    msg = (
        f"⚠️  Corpus has {n_pdfs} PDFs; expected at least "
        f"{EDA.expected_min_pdfs} per cfg.eda.expected_min_pdfs.\n"
        "   The corpus may not be fully fetched. Per-section results "
        "still render but should be interpreted with caution."
    )
    print(msg, file=sys.stderr)
else:
    print(
        f"✓ PDF count ({n_pdfs}) meets the cfg.eda.expected_min_pdfs floor "
        f"({EDA.expected_min_pdfs})."
    )

# %%
# ---------------------------------------------------------------------------
# Per-flavor counts at a glance.
# ---------------------------------------------------------------------------
flavor_summary = (
    corpus_index.groupby("flavor")
    .agg(
        files=("path", "count"),
        pdfs=("is_pdf", "sum"),
        xmls=("is_xml", "sum"),
        size_mb=("size_bytes", lambda s: s.sum() / 1_048_576),
    )
    .sort_values("files", ascending=False)
)
flavor_summary["size_mb"] = flavor_summary["size_mb"].round(1)
flavor_summary

# %% [markdown]
# **Discussion §1 (manifest reconciliation)**:
#
# - The corpus_index DataFrame is the load-bearing substrate for every
#   subsequent section — every per-PDF / per-XML analysis joins back to it.
# - Per-flavor counts above let us see at a glance how the corpus splits.
#   The `XML-Rechnung/FX` row is the pilot-13 substrate (26 PDFs); other
#   flavors expand the EDA's reach beyond what pilot-13 saw.
# - Files in `MANIFEST.md` / `sha256.txt` / `README.md` / `LICENSE` are
#   excluded as metadata. The corpus_index counts ONLY content files.

# %% [markdown]
# ---
#
# # 2. Per-flavor PDF + XML coverage {#sec-coverage}
#
# Extends §1 with a faceted view: for each flavor, how many PDFs vs how
# many standalone XMLs? Some flavors are PDF-centric (ZUGFeRDv1/v2,
# XML-Rechnung/FX); others are XML-only (XML-Rechnung/CII, UBL,
# fatturaPA, PEPPOL). The XML-only flavors characterize the German +
# European e-invoicing ecosystem but aren't directly testable by VLM (no
# paired PDF to feed the model).

# %%
# ---------------------------------------------------------------------------
# Per-flavor × file-type counts.
# ---------------------------------------------------------------------------
coverage = (
    corpus_index.assign(
        file_type=lambda df: np.where(df["is_pdf"], "PDF", np.where(df["is_xml"], "XML", "other"))
    )
    .groupby(["flavor", "file_type"])
    .size()
    .unstack(fill_value=0)
    .sort_values(by=[c for c in ["PDF", "XML"] if c is not None], ascending=False)
)
# Ensure both columns exist even if a column has zero entries.
for col in ("PDF", "XML"):
    if col not in coverage.columns:
        coverage[col] = 0
coverage = coverage[["PDF", "XML"] + [c for c in coverage.columns if c not in ("PDF", "XML")]]
coverage

# %%
# ---------------------------------------------------------------------------
# Static figure: stacked horizontal bar by flavor × file-type.
# ---------------------------------------------------------------------------
#| label: fig-coverage-static
#| fig-cap: "PDF and XML file counts per top-level corpus flavor. The pilot-13 substrate is XML-Rechnung/FX (26 PDFs)."
fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(coverage) + 1)))
coverage[["PDF", "XML"]].plot(
    kind="barh",
    stacked=True,
    ax=ax,
    color=[PALETTE[0], PALETTE[3]],
    edgecolor="white",
    linewidth=0.5,
)
ax.set_xlabel("Files")
ax.set_ylabel("")
ax.set_title("Per-flavor file coverage", loc="left")
ax.legend(title="", loc="lower right")
ax.invert_yaxis()
for container in ax.containers:
    ax.bar_label(
        container,
        fmt=lambda v: f"{int(v)}" if v > 0 else "",
        label_type="center",
        fontsize=8,
        color="white",
    )
sns.despine(ax=ax, left=True)
ax.tick_params(left=False)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §2 (per-flavor coverage)**:
#
# - PDF-centric flavors (ZUGFeRDv1/correct, ZUGFeRDv2/correct, XML-Rechnung/FX)
#   are the testable evaluation substrate: each PDF has embedded CII XML
#   that `factur-x` can extract → 16-field GroundTruth dict for F1 scoring.
# - The `fail/` subdirs (ZUGFeRDv1/fail, ZUGFeRDv2/fail) are intentionally
#   invalid PDFs — useful as a robustness signal in §9 Anomalies; not part
#   of the evaluation substrate.
# - XML-only flavors (XML-Rechnung/CII, UBL; fatturaPA; PEPPOL) characterize
#   the broader e-invoicing ecosystem (German national variant + EU
#   procurement + Italian B2G/B2B) but cannot be tested by VLMs without
#   paired PDFs. They're informative for the thesis methodology chapter
#   ("HORUS scope = CII-anchored PDFs"), not for §5 field-presence analysis.

# %% [markdown]
# ---
#
# # 3. Page-count distribution {#sec-pages}
#
# Page counts are computed for every PDF via `pypdfium2` (already a HORUS
# dep per ADR-014; same engine as the pilot-13 rasterizer). The
# distribution informs (a) the multi-page rasterization strategy already
# locked by ADR-014 and (b) the complexity-tier proposal in §7.

# %%
# ---------------------------------------------------------------------------
# Compute page counts for every PDF.
# ---------------------------------------------------------------------------


def get_page_count(pdf_path: Path) -> int | None:
    """Return PDF page count via pypdfium2; None on parse failure.

    Uses the canonical try/finally + `.close()` pattern from
    `src/horus/eval/rasterize.py:119-138` (pypdfium2 4.30 lacks `__exit__`,
    so the `with` statement is unsupported per the upstream API).
    """
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
    except Exception:  # noqa: BLE001 — surface in §9 Anomalies, not here
        return None
    try:
        return len(doc)
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001 — cleanup; weakref.finalize is the safety net
            pass


pdf_rows = corpus_index[corpus_index["is_pdf"]].copy()
print(f"Computing page counts for {len(pdf_rows)} PDFs...", flush=True)
pdf_rows["page_count"] = pdf_rows["path"].apply(get_page_count)
pdf_rows["page_count_known"] = pdf_rows["page_count"].notna()
n_failed = int((~pdf_rows["page_count_known"]).sum())
print(f"  ✓ {len(pdf_rows) - n_failed} PDFs parsed; {n_failed} failed (surfaced in §9).")

# %%
# ---------------------------------------------------------------------------
# Distribution stats.
# ---------------------------------------------------------------------------
page_stats = pdf_rows["page_count"].dropna().astype(int)
if len(page_stats) == 0:
    print(
        "⚠️  No PDFs successfully parsed for page count. Skipping summary "
        "+ binned distribution; see §9 Anomalies."
    )
else:
    print(f"Page-count summary across {len(page_stats)} parseable PDFs:")
    print(f"  min:    {page_stats.min()}")
    print(f"  max:    {page_stats.max()}")
    print(f"  mean:   {page_stats.mean():.1f}")
    print(f"  median: {int(page_stats.median())}")
    print()
    print("Distribution by binned page count:")
    # Extend the user-configured bins with an upper edge ONLY if the corpus
    # max exceeds the last bin (else the bins are already non-monotonic).
    _max_page = int(page_stats.max())
    _bins = (
        EDA.page_count_bins
        if _max_page < EDA.page_count_bins[-1]
        else EDA.page_count_bins + [_max_page + 1]
    )
    binned = pd.cut(page_stats, bins=_bins, right=False, include_lowest=True)
    print(binned.value_counts().sort_index().to_string())

# %%
# ---------------------------------------------------------------------------
# Static figure: histogram with binned distribution + per-flavor color.
# ---------------------------------------------------------------------------
#| label: fig-pages-static
#| fig-cap: "PDF page-count distribution. Bin edges per `cfg.eda.page_count_bins` (pre-committed). Most invoices are 1-page; long-tail at 5+ pages for document packs."
fig, ax = plt.subplots(figsize=(8, 4))
if len(page_stats) == 0:
    ax.text(
        0.5, 0.5, "(no PDFs parseable; see §9 Anomalies)",
        transform=ax.transAxes, ha="center", va="center", fontsize=11, color="#888"
    )
    ax.set_axis_off()
else:
    flavors = pdf_rows["flavor"].unique()
    flavor_colors = dict(zip(sorted(flavors), PALETTE, strict=False))
    _max_page = int(page_stats.max())
    _bins = (
        EDA.page_count_bins
        if _max_page < EDA.page_count_bins[-1]
        else EDA.page_count_bins + [_max_page + 1]
    )
    sns.histplot(
        data=pdf_rows.dropna(subset=["page_count"]),
        x="page_count",
        hue="flavor",
        multiple="stack",
        bins=_bins,
        palette=[flavor_colors[f] for f in sorted(flavors)],
        ax=ax,
        edgecolor="white",
        linewidth=0.4,
    )
ax.set_xlabel("Pages per PDF")
ax.set_ylabel("Number of PDFs")
ax.set_title("Page-count distribution by flavor", loc="left")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §3 (page-count distribution)**:
#
# - Pilot-13 evidence (cited in `ComplexityTierConfig` defaults): most
#   invoices are 1-page; long tail at 5+ pages corresponds to document
#   packs / multi-page contracts. Confirmed (or refuted) by the figure
#   above — see histogram for the actual mass concentration.
# - Page count drives rasterization cost (per-page PNG via pypdfium2 at
#   300 DPI ≈ 200 KB per A4 page → 26-PDF pilot-13 sweep = ~10 MB
#   rasterizer cache; full 151-PDF sweep ≈ ~60 MB). Multi-page sweeps
#   already supported by ADR-014; no architectural change needed.
# - The 1-page mass is also why pilot-13's `sips`-based page-1-only
#   baseline (pre-ADR-014) was viable as a smoke; for the full corpus the
#   multi-page strategy is mandatory.

# %% [markdown]
# ---
#
# # 4. Profile / variant breakdown {#sec-profile}
#
# ZUGFeRD / Factur-X / XRechnung profiles (MINIMUM, BASIC, EN16931,
# EXTENDED, plus the German national XRECHNUNG variant) determine which
# of the 16 fields are MANDATORY vs OPTIONAL. EN16931 (the EU norm) is
# the canonical baseline; XRECHNUNG layers German B2G-specific
# requirements on top.
#
# Profile is determined here via two routes:
#
# 1. **Filename pattern** (fast, ~150 PDFs in seconds): regex against the
#    filename for the profile name (e.g., `EN16931_Einfach.pdf` → EN16931).
# 2. **Embedded XML** (authoritative, slower): parse the embedded CII XML
#    via `factur-x.get_level()`. Surfaced for the GT-parseable subset.
#
# The two routes' agreement rate is itself a quality signal.

# %%
# ---------------------------------------------------------------------------
# Route 1: profile from filename pattern.
# ---------------------------------------------------------------------------
# `\b` word boundaries DON'T work here because `_` is a word char in Python
# regex (\w includes underscore). Filenames like `zugferd_2p0_EN16931_Einfach.pdf`
# have `_` on both sides of the profile token — no word boundary exists. Use
# explicit `(?:^|[_/-])` and `(?:[_/-.]|$)` separators instead, plus IGNORECASE
# for camelcase variants.
# Char classes use `-` LAST to mean a literal hyphen (otherwise `[_/-.]` parses
# `/-.` as a malformed range from `/` to `.`).
PROFILE_PATTERNS = {
    "MINIMUM": re.compile(r"(?:^|[_/-])MINIMUM(?:[_/.-]|$)", re.IGNORECASE),
    "BASIC": re.compile(r"(?:^|[_/-])BASIC(?:WL)?(?:[_/.-]|$)", re.IGNORECASE),
    "EN16931": re.compile(r"(?:^|[_/-])EN[_]?16931(?:[_/.-]|$)", re.IGNORECASE),
    "EXTENDED": re.compile(r"(?:^|[_/-])(EXTENDED|Erweitert)(?:[_/.-]|$)", re.IGNORECASE),
    "XRECHNUNG": re.compile(r"(?:^|[_/-])XRECHNUNG(?:[_/.-]|$)", re.IGNORECASE),
}


def profile_from_filename(name: str) -> str | None:
    for profile, pat in PROFILE_PATTERNS.items():
        if pat.search(name):
            return profile
    return None


pdf_rows["profile_from_name"] = pdf_rows["filename"].apply(profile_from_filename)
print("Profile distribution (from filename pattern):")
print(pdf_rows["profile_from_name"].value_counts(dropna=False).to_string())

# %%
# ---------------------------------------------------------------------------
# Route 2: profile from embedded XML (factur-x extraction).
# ---------------------------------------------------------------------------


def extract_xml_and_level(pdf_path: Path) -> tuple[bytes | None, str | None, str | None]:
    """Return (xml_bytes, flavor, level) or (None, None, None) on failure.

    Suppresses stderr noise from factur-x's schema warnings; surfaces
    failures in §9 (Anomalies). Used for both §4 (level) and §5 (16-field
    presence rates) and §7 (line-item count).
    """
    try:
        pdf_bytes = pdf_path.read_bytes()
        # check_xsd / check_schematron disabled for bulk EDA — corpus has
        # known-invalid PDFs in fail/ subdirs (intentional).
        result = facturx.get_xml_from_pdf(pdf_bytes, check_xsd=False, check_schematron=False)
        if not result or not result[0]:
            return None, None, None
        _name, xml_bytes = result
        try:
            tree = etree.fromstring(xml_bytes)
            flavor = facturx.get_flavor(tree)
            level = facturx.get_level(tree)
        except Exception:  # noqa: BLE001
            return xml_bytes, None, None
        return xml_bytes, flavor, level
    except Exception:  # noqa: BLE001
        return None, None, None


print(f"Extracting embedded XML for {len(pdf_rows)} PDFs (slow; ~30-90s)...", flush=True)
extractions = pdf_rows["path"].apply(extract_xml_and_level)
pdf_rows["xml_bytes"] = extractions.map(lambda t: t[0])
pdf_rows["xml_flavor"] = extractions.map(lambda t: t[1])
pdf_rows["xml_level"] = extractions.map(lambda t: t[2])
pdf_rows["xml_extracted"] = pdf_rows["xml_bytes"].notna()
n_xml_ok = int(pdf_rows["xml_extracted"].sum())
print(f"  ✓ {n_xml_ok} / {len(pdf_rows)} PDFs yielded an embedded XML attachment.")

# %%
# ---------------------------------------------------------------------------
# Route-agreement check.
# ---------------------------------------------------------------------------
agree = pdf_rows[pdf_rows["xml_extracted"]].copy()
# `xml_level` from factur-x is a string like "en16931" / "basic" / … (lowercase).
# Normalize both routes: drop spaces + uppercase. "EN 16931" -> "EN16931" matches
# the filename pattern's canonical key.
agree["xml_level_norm"] = (
    agree["xml_level"].astype(str).str.replace(r"\s+", "", regex=True).str.upper()
)
agree["filename_level_norm"] = agree["profile_from_name"].astype(str).str.upper()

# Two separate metrics:
#   1. Coverage: fraction of XML-extractable PDFs that ALSO match a filename pattern.
#   2. Agreement (within the matched subset): when both routes produce a value, do
#      they agree? This is the meaningful corpus-quality signal.
n_xml_known = int((agree["xml_level_norm"] != "NONE").sum())
n_filename_known = int((agree["filename_level_norm"] != "NONE").sum())
both_known = agree[
    (agree["xml_level_norm"] != "NONE") & (agree["filename_level_norm"] != "NONE")
]
n_both = len(both_known)
n_match = int((both_known["xml_level_norm"] == both_known["filename_level_norm"]).sum())
print(
    f"Filename-pattern coverage: {n_filename_known} / {len(agree)} PDFs "
    f"({100 * n_filename_known / max(1, len(agree)):.1f}%; rest don't follow the "
    f"<flavor>_<profile>_<name>.pdf convention)."
)
print(
    f"XML-route coverage:        {n_xml_known} / {len(agree)} PDFs "
    f"({100 * n_xml_known / max(1, len(agree)):.1f}%)."
)
if n_both > 0:
    print(
        f"Route agreement (within {n_both}-PDF intersection): {n_match} / {n_both} "
        f"({100 * n_match / n_both:.1f}%). Disagreements indicate corpus-quality issues."
    )
else:
    print("Route agreement: N/A (no PDFs have BOTH a filename profile and an XML level).")

# %%
# ---------------------------------------------------------------------------
# Static figure: profile counts (XML-derived; the authoritative route).
# ---------------------------------------------------------------------------
#| label: fig-profile-static
#| fig-cap: "Profile distribution (level) extracted from embedded CII XML via factur-x. EN16931 is the EU norm baseline; XRECHNUNG is the German B2G variant."
profile_counts = (
    pdf_rows.dropna(subset=["xml_level"]).groupby("xml_level").size().sort_values(ascending=False)
)
fig, ax = plt.subplots(figsize=(8, max(3, 0.45 * len(profile_counts) + 1)))
sns.barplot(
    x=profile_counts.values,
    y=profile_counts.index,
    color=PALETTE[1],
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
)
ax.set_xlabel("Number of PDFs")
ax.set_ylabel("")
ax.set_title("Profile distribution (CII XML level)", loc="left")
for i, v in enumerate(profile_counts.values):
    ax.text(v + 0.3, i, str(int(v)), va="center", fontsize=9, color="#444")
sns.despine(ax=ax, left=True)
ax.tick_params(left=False)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §4 (profile breakdown)**:
#
# - Profiles are nested: MINIMUM ⊂ BASIC ⊂ EN16931 ⊂ EXTENDED. XRECHNUNG
#   is a German B2G layering on EN16931. Higher profiles carry more
#   mandatory fields; the per-field presence rates in §5 should correlate
#   with profile mix.
# - The two-route agreement rate is a corpus-quality signal: high
#   agreement = filename conventions are reliable; low agreement = either
#   the filenames are wrong or the embedded XML doesn't match the
#   declared profile (a real bug in some test corpora). Use the embedded-
#   XML route as authoritative.

# %% [markdown]
# ---
#
# # 5. 16-field presence rates {#sec-fields}
#
# For each PDF that yielded an embedded CII XML, parse the 16-field
# `GroundTruth` dict via `horus.eval.ground_truth.parse_cii_xml` (the
# canonical pipeline used by ADR-014's pilot-13 evaluation harness).
# Each field is `present` if its `value` is not None after normalization;
# this matches the F1 scorer's `IS_GT` / `NO_GT` truth-table dimension
# from ADR-013.
#
# This is the EVALUATION SUBSTRATE for the thesis: every reported F1
# number scales with the number of present-fields per PDF.

# %%
# ---------------------------------------------------------------------------
# Parse GroundTruth dict for every successfully-extracted XML.
# ---------------------------------------------------------------------------


def parse_one_gt(xml_bytes: bytes | None) -> GroundTruth | None:
    if xml_bytes is None:
        return None
    try:
        return parse_cii_xml(xml_bytes)
    except Exception:  # noqa: BLE001
        return None


print(f"Parsing GroundTruth for {n_xml_ok} extracted XMLs...", flush=True)
pdf_rows["gt"] = pdf_rows["xml_bytes"].apply(parse_one_gt)
pdf_rows["gt_parseable"] = pdf_rows["gt"].notna()
n_gt = int(pdf_rows["gt_parseable"].sum())
print(f"  ✓ {n_gt} PDFs yielded a parseable GroundTruth dict.")
print(
    f"  ✗ {len(pdf_rows) - n_gt} PDFs failed somewhere in the chain "
    "(no XML attachment, malformed XML, or schema deviations); see §9."
)

if EDA.ground_truth_required and n_gt == 0:
    raise RuntimeError(
        "cfg.eda.ground_truth_required=True but the GT-parseable subset is "
        "empty (0 PDFs). The corpus may be misconfigured. See §9 for the "
        "anomaly distribution."
    )

# %%
# ---------------------------------------------------------------------------
# Build a 16-column boolean matrix: rows = PDFs, columns = field-keys.
# ---------------------------------------------------------------------------
field_keys = list(FIELDS.keys())
gt_subset = pdf_rows[pdf_rows["gt_parseable"]].copy()


def field_value_present(gt: GroundTruth, key: str) -> bool:
    """True iff the field has a non-None normalized value (IS_GT per ADR-013).

    Per `src/horus/eval/ground_truth.py:GroundTruthField` schema:
      - `is_present=False` → field absent from XML → NO_GT
      - `is_present=True` + `normalized_value is None` → present but normalizer
        rejected → EXCLUDED (per ADR-013 §Truth table)
      - `normalized_value is not None` → IS_GT (countable for F1)
    """
    field = gt.header.get(key)
    if field is None:
        return False
    return field.normalized_value is not None


# BUG-CATCH: an earlier version of this cell used
#   pd.DataFrame({key: gt_subset["gt"].apply(...) for key in field_keys},
#                index=gt_subset["filename"])
# Pandas tried to ALIGN the Series-from-apply (RangeIndex 0..145) against the
# string-typed `filename` index → no common labels → all values became NaN →
# `.astype(bool)` converted NaN → True → presence_matrix was solid-True →
# every field's presence rate was a fake 1.0. The check that surfaced it was
# the contradiction with cell [40] field-frequency counts (123 currency
# values, not 146). Bypassing the trap by constructing from positional list
# comprehensions (no Series alignment) and attaching the filename index
# AFTER construction.
gt_list = list(gt_subset["gt"])
presence_data = {
    key: [field_value_present(gt, key) for gt in gt_list] for key in field_keys
}
presence_matrix = pd.DataFrame(presence_data, dtype=bool)
presence_matrix.index = pd.Index(gt_subset["filename"].values, name="filename")
presence_matrix.shape

# %%
# ---------------------------------------------------------------------------
# Per-field presence rate (across all GT-parseable PDFs).
# ---------------------------------------------------------------------------
field_rates = (
    presence_matrix.mean(axis=0)
    .sort_values(ascending=False)
    .rename("presence_rate")
    .to_frame()
    .assign(
        present_count=lambda df: (df["presence_rate"] * len(presence_matrix)).round().astype(int)
    )
)
field_rates["bt_code"] = [FIELDS[f].bt_code for f in field_rates.index]
field_rates

# %%
# ---------------------------------------------------------------------------
# Static figure: 16-field presence-rate bar chart.
# ---------------------------------------------------------------------------
#| label: fig-presence-bar
#| fig-cap: "Per-field presence rate across the GT-parseable subset. Near-100% fields are corpus-universal mandatory anchors; lower rates indicate optional / profile-specific fields."
fig, ax = plt.subplots(figsize=(8, 5.5))
sns.barplot(
    x=field_rates["presence_rate"].values,
    y=field_rates.index,
    palette=sns.color_palette(EDA.palette_static, n_colors=len(field_rates)),
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue=field_rates.index,
    legend=False,
)
ax.set_xlim(0, 1.0)
ax.set_xlabel("Presence rate (fraction of GT-parseable PDFs)")
ax.set_ylabel("")
ax.set_title("Per-field presence rates (16-field schema)", loc="left")
ax.axvline(0.95, color="#888", linestyle=":", linewidth=1)
ax.text(
    0.96,
    len(field_rates) - 0.5,
    "near-universal\nthreshold (95%)",
    fontsize=8,
    color="#888",
    va="bottom",
)
for i, (rate, count) in enumerate(
    zip(field_rates["presence_rate"], field_rates["present_count"], strict=True)
):
    ax.text(
        rate + 0.01,
        i,
        f"{count}/{len(presence_matrix)} ({rate * 100:.0f}%)",
        va="center",
        fontsize=8,
        color="#444",
    )
sns.despine(ax=ax, left=True)
ax.tick_params(left=False)
plt.tight_layout()
plt.show()

# %%
# ---------------------------------------------------------------------------
# Static figure: 16-field × N-PDF presence heatmap (matplotlib; PDF-safe).
# ---------------------------------------------------------------------------
#| label: fig-presence-heatmap
#| fig-cap: "Field-presence heatmap (rows = PDFs, columns = 16 fields). White = present, gray = missing. Rows sorted by total-present count to surface profile / completeness clusters."
heatmap_data = presence_matrix.copy()
heatmap_data["_total"] = heatmap_data.sum(axis=1)
heatmap_data = heatmap_data.sort_values("_total", ascending=False).drop(columns=["_total"])
fig, ax = plt.subplots(figsize=(9, max(6, 0.06 * len(heatmap_data) + 1)))
sns.heatmap(
    heatmap_data.astype(int),
    cmap=sns.light_palette(PALETTE[2], as_cmap=True),
    cbar=False,
    linewidths=0,
    linecolor="white",
    ax=ax,
    yticklabels=False,
)
ax.set_xlabel("")
ax.set_ylabel(f"{len(heatmap_data)} PDFs (sorted by total fields present)")
ax.set_title("Per-PDF × per-field presence heatmap", loc="left")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §5 (16-field presence rates)**:
#
# - Near-universal fields (>=95% presence) are the corpus's mandatory
#   backbone — these are the F1-scorer's "everyone must produce these"
#   targets. Pilot-13's MONEY-field FN failures (per ADR-019 bug catalog)
#   are concentrated in these high-presence-rate fields, which is exactly
#   why adapter improvements there drive headline F1.
# - Lower-presence fields are optional or profile-specific (e.g.,
#   `currency_code` BT-5 only present when EN16931+; `delivery_address`
#   only present when distinct from buyer). These DO NOT enter F1
#   denominators per ADR-013 §"Truth table" — fields with `NO_GT` are
#   excluded from both numerator and denominator. So a corpus full of
#   missing optionals is NOT a corpus full of FN.
# - The heatmap surfaces row-clusters = profile groupings (MINIMUM rows
#   are short; EN16931+ rows are full). A future column-cluster ordering
#   could highlight field co-occurrence (deferred — not load-bearing for
#   this descriptive pass).

# %% [markdown]
# ---
#
# # 6. Per-field GT-value distributions {#sec-values}
#
# Beyond presence, what do the actual values look like?
#
# - **String fields** (`seller_name`, `buyer_name`): length distribution
#   (chars). Long tails identify outlier vendors with verbose legal names.
# - **Date fields** (`invoice_date`, `due_date`): year/month distribution.
#   Catches corpora with a single-year bias (would limit transfer
#   evaluation to that year's invoice formats).
# - **Money fields** (`grand_total_amount`, `tax_amount`, …): log-scale
#   distribution. Surfaces extreme-magnitude outliers (e.g., €1B test
#   invoices in the synthetic corpus).
# - **Code fields** (`currency_code`, `tax_id`): frequency table. Cross-
#   currency / cross-VAT-jurisdiction coverage.

# %%
# ---------------------------------------------------------------------------
# Helper: collect non-None values for a given field across the GT-parseable subset.
# ---------------------------------------------------------------------------


def field_values(field_key: str) -> list[object]:
    out: list[object] = []
    for gt in gt_subset["gt"]:
        f = gt.header.get(field_key)
        if f is None or f.normalized_value is None:
            continue
        out.append(f.normalized_value)
    return out


# %%
# ---------------------------------------------------------------------------
# String fields: length distribution.
# ---------------------------------------------------------------------------
#| label: fig-string-lengths
#| fig-cap: "String-field value-length distribution (characters). Long tails = verbose legal vendor/buyer names."
string_fields = [k for k, spec in FIELDS.items() if spec.field_type == "STRING"]
fig, axes = plt.subplots(
    nrows=max(1, (len(string_fields) + 1) // 2),
    ncols=2,
    figsize=(9, 2.2 * max(1, (len(string_fields) + 1) // 2)),
    squeeze=False,
)
for ax, field in zip(axes.flat, string_fields, strict=False):
    values = [str(v) for v in field_values(field)]
    if not values:
        ax.set_axis_off()
        continue
    lengths = [len(v) for v in values]
    sns.histplot(lengths, ax=ax, color=PALETTE[4], bins=15, edgecolor="white", linewidth=0.4)
    ax.set_title(field, loc="left", fontsize=10)
    ax.set_xlabel("Length (chars)")
    ax.set_ylabel("Count")
    sns.despine(ax=ax)
# Hide unused subplots.
for ax in axes.flat[len(string_fields) :]:
    ax.set_axis_off()
plt.tight_layout()
plt.show()

# %%
# ---------------------------------------------------------------------------
# Date fields: year/month distribution.
# ---------------------------------------------------------------------------
#| label: fig-date-coverage
#| fig-cap: "Date-field temporal coverage (year). Single-year mass = corpus may not span multiple invoice formats."
date_fields = [k for k, spec in FIELDS.items() if spec.field_type == "DATE"]
year_records: list[dict[str, object]] = []
for field in date_fields:
    for v in field_values(field):
        try:
            year = int(str(v)[:4])
            year_records.append({"field": field, "year": year})
        except ValueError, TypeError:
            continue
year_df = pd.DataFrame(year_records)
if not year_df.empty:
    fig, ax = plt.subplots(figsize=(8, 3.5))
    sns.histplot(
        data=year_df,
        x="year",
        hue="field",
        multiple="dodge",
        discrete=True,
        palette=sns.color_palette(EDA.palette_static, n_colors=len(date_fields)),
        ax=ax,
        edgecolor="white",
        linewidth=0.4,
    )
    ax.set_title("Date-field year distribution", loc="left")
    ax.set_xlabel("Year")
    ax.set_ylabel("Count")
    sns.despine(ax=ax)
    plt.tight_layout()
    plt.show()
else:
    print("(no date values present; skipping date-field figure)")

# %%
# ---------------------------------------------------------------------------
# Money fields: log-scale distribution.
# ---------------------------------------------------------------------------
#| label: fig-money-distribution
#| fig-cap: "Money-field log10 distribution. Long tails = synthetic-test extremes (€1B-class)."
money_fields = [k for k, spec in FIELDS.items() if spec.field_type == "MONEY"]
money_records: list[dict[str, object]] = []
for field in money_fields:
    for v in field_values(field):
        try:
            money_records.append({"field": field, "amount": float(str(v))})
        except ValueError, TypeError:
            continue
money_df = pd.DataFrame(money_records)
if not money_df.empty:
    money_df = money_df[money_df["amount"] > 0]  # log10 needs positive
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(
        data=money_df,
        x="amount",
        y="field",
        palette=sns.color_palette(EDA.palette_static, n_colors=len(money_fields)),
        ax=ax,
        hue="field",
        legend=False,
    )
    ax.set_xscale("log")
    ax.set_title("Money-field magnitude (log scale)", loc="left")
    ax.set_xlabel("Amount (EUR; log10)")
    ax.set_ylabel("")
    sns.despine(ax=ax)
    plt.tight_layout()
    plt.show()
else:
    print("(no money values present; skipping money-field figure)")

# %%
# ---------------------------------------------------------------------------
# Code fields: frequency table.
# ---------------------------------------------------------------------------
code_fields = [k for k, spec in FIELDS.items() if spec.field_type == "CODE"]
print("Code-field frequency (top 5 per field):")
for field in code_fields:
    values = [str(v) for v in field_values(field)]
    if not values:
        print(f"\n  {field}: (no values present)")
        continue
    counter = Counter(values)
    print(f"\n  {field} ({len(values)} present):")
    for code, n in counter.most_common(5):
        print(f"    {code:<24s} {n:>4d}")

# %% [markdown]
# **Discussion §6 (per-field value distributions)**:
#
# - String length distributions identify outlier vendors. A median-length
#   ~25 chars is typical; >100-char names (full legal entity strings)
#   cluster at the long tail and are real-world inputs the VLM must
#   handle. ANLS thresholding (per ADR-013) was chosen partly for this.
# - Date coverage: a single-year mass (e.g., 100% 2018) limits transfer-
#   evaluation conclusions. The held-out test set per Q4=A (self-collected
#   Belege) WILL span recent years, balancing this.
# - Money distributions in test corpora have synthetic extremes
#   (€1B-class). These are valid TEST inputs but not representative of
#   real-firm transactions. The thesis methodology chapter should note
#   this as a limitation if the headline F1 includes them.
# - Code-field frequencies (currency, tax IDs) reveal jurisdictional
#   coverage. EUR-only + DE-only would limit cross-jurisdiction
#   conclusions. EU-wide PEPPOL XMLs in §1 broaden this picture.

# %% [markdown]
# ---
#
# # 7. Complexity-tier proposal {#sec-tiers}
#
# Categorizes each GT-parseable PDF into `simple` / `medium` / `complex`
# tiers based on PRE-COMMITTED descriptive features (page count + line-
# item count). Thresholds locked in `cfg.eda.complexity` in
# `configs/eda-zugferd.yaml` BEFORE this EDA ran (HARKing safeguard).
#
# **What this is NOT**: a hypothesis. The tier is a descriptive label
# that informs future per-tier F1 stratification; it does NOT enter the
# H1–H6 set.

# %%
# ---------------------------------------------------------------------------
# Line-item count via lxml xpath on the embedded CII XML.
# ---------------------------------------------------------------------------
NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
}


def line_item_count(xml_bytes: bytes | None) -> int | None:
    if xml_bytes is None:
        return None
    try:
        tree = etree.fromstring(xml_bytes)
        items = tree.xpath("//ram:IncludedSupplyChainTradeLineItem", namespaces=NS)
        return len(items)
    except Exception:  # noqa: BLE001
        return None


pdf_rows["line_item_count"] = pdf_rows["xml_bytes"].apply(line_item_count)

# %%
# ---------------------------------------------------------------------------
# Apply the pre-committed tier rule.
# ---------------------------------------------------------------------------


def assign_tier(pages: int | None, items: int | None) -> str:
    """Apply EDA.complexity thresholds (locked in YAML)."""
    if pages is None or items is None:
        return "(unknown)"
    cfg_c = EDA.complexity
    if pages <= cfg_c.simple_max_pages and items <= cfg_c.simple_max_line_items:
        return "simple"
    if pages <= cfg_c.medium_max_pages and items <= cfg_c.medium_max_line_items:
        return "medium"
    return "complex"


pdf_rows["complexity_tier"] = [
    assign_tier(p, li)
    for p, li in zip(pdf_rows["page_count"], pdf_rows["line_item_count"], strict=False)
]
print("Complexity tier counts:")
print(pdf_rows["complexity_tier"].value_counts(dropna=False).to_string())

# %%
# ---------------------------------------------------------------------------
# Static figure: tier counts.
# ---------------------------------------------------------------------------
#| label: fig-tier-counts
#| fig-cap: "Complexity-tier distribution under the pre-committed thresholds (simple ≤ 1p / 5li; medium ≤ 3p / 20li; else complex)."
tier_order = ["simple", "medium", "complex", "(unknown)"]
tier_counts = pdf_rows["complexity_tier"].value_counts().reindex(tier_order, fill_value=0)
fig, ax = plt.subplots(figsize=(7, 3.5))
sns.barplot(
    x=tier_counts.index,
    y=tier_counts.values,
    palette=[PALETTE[0], PALETTE[2], PALETTE[5], "#cccccc"],
    ax=ax,
    edgecolor="white",
    linewidth=0.4,
    hue=tier_counts.index,
    legend=False,
)
ax.set_xlabel("")
ax.set_ylabel("Number of PDFs")
ax.set_title("Complexity-tier distribution (pre-committed thresholds)", loc="left")
for i, v in enumerate(tier_counts.values):
    ax.text(i, v + 0.3, str(int(v)), ha="center", fontsize=9, color="#444")
sns.despine(ax=ax)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Discussion §7 (complexity tiers)**:
#
# - Tier distribution informs future per-tier F1 stratification: if the
#   `complex` tier is sparse (<10 PDFs), per-tier F1 has wide CIs and the
#   stratification is mostly cosmetic. The held-out test set per Q4=A
#   should target a more balanced tier distribution.
# - The thresholds were pre-committed in YAML; if the distribution above
#   is highly skewed (e.g., 95% simple, 5% complex, 0% medium), the YAML
#   thresholds are reviewable in a follow-up commit AFTER recording this
#   observation in §3.3k. The pre-commitment + git-tracked-revision
#   pattern is the HARKing safeguard.

# %% [markdown]
# ---
#
# # 8. Locale + language coverage {#sec-locale}
#
# Country / language mix from the address fields (`seller_country` BT-40,
# `buyer_country` BT-55) and the currency mix from BT-5. Confirms the
# "German-centric" thesis scope.

# %%
# ---------------------------------------------------------------------------
# Country code distribution (extracted from address-string heuristic).
# ---------------------------------------------------------------------------
# The 16-field schema has no explicit country fields. Country is derived
# from EU VAT-ID prefixes (DE/FR/GB/ES/IT/...) — the first 2 chars of
# `seller_vat_id` and `buyer_vat_id` per ISO 3166 / EU VAT structure.
vat_prefix_pattern = re.compile(r"^([A-Z]{2})")


def extract_country_codes(gt: GroundTruth) -> list[tuple[str, str]]:
    """Return [(role, country)] pairs derived from VAT-ID prefixes."""
    out: list[tuple[str, str]] = []
    for role, key in (("seller", "seller_vat_id"), ("buyer", "buyer_vat_id")):
        f = gt.header.get(key)
        if f is None or f.normalized_value is None:
            continue
        m = vat_prefix_pattern.match(str(f.normalized_value))
        if m:
            out.append((role, m.group(1)))
    return out


seller_countries: list[str] = []
buyer_countries: list[str] = []
for gt in gt_subset["gt"]:
    for role, country in extract_country_codes(gt):
        if role == "seller":
            seller_countries.append(country)
        else:
            buyer_countries.append(country)

print(f"Seller country (from VAT-ID prefix; {len(seller_countries)} present):")
for code, n in Counter(seller_countries).most_common(5):
    print(f"  {code:<5s} {n:>4d}")
print(f"\nBuyer country (from VAT-ID prefix; {len(buyer_countries)} present):")
for code, n in Counter(buyer_countries).most_common(5):
    print(f"  {code:<5s} {n:>4d}")

# %%
# ---------------------------------------------------------------------------
# Currency code distribution.
# ---------------------------------------------------------------------------
currencies = [str(v) for v in field_values("invoice_currency_code")]
print(f"\nCurrency code frequency ({len(currencies)} present):")
for code, n in Counter(currencies).most_common(5):
    print(f"  {code:<5s} {n:>4d}")

# %% [markdown]
# **Discussion §8 (locale + language coverage)**:
#
# - DE-dominant country codes confirm the thesis scope ("privacy-first
#   document intelligence for German tax/accounting professionals" per
#   AGENTS.md). EU-neighbor codes (FR, IT, etc.) reflect cross-border
#   B2B test invoices in the corpus.
# - EUR-dominant currencies match DE/EU scope. Non-EUR test invoices
#   exist in the corpus for completeness but don't represent the thesis
#   target population.

# %% [markdown]
# ---
#
# # 9. Anomalies + corpus-quality flags {#sec-anomalies}
#
# Catalogs the failure modes encountered during §3 (page-count parse),
# §4 (XML extraction), §5 (GT parse). These are the "broken" PDFs that
# the pilot would face on a robustness sweep — informative for the
# thesis methodology chapter's "limitations" section.

# %%
# ---------------------------------------------------------------------------
# Failure-mode counts.
# ---------------------------------------------------------------------------
n_total = len(pdf_rows)
n_no_pages = int((~pdf_rows["page_count_known"]).sum())
n_no_xml = int((~pdf_rows["xml_extracted"]).sum())
n_no_gt = int((~pdf_rows["gt_parseable"]).sum())
print("Failure-mode counts (cumulative; later stages depend on earlier):")
print(f"  PDFs total:                  {n_total:>4}")
print(f"  Page-count parse failed:     {n_no_pages:>4}  ({100 * n_no_pages / n_total:.1f}%)")
print(f"  XML attachment missing/bad:  {n_no_xml:>4}  ({100 * n_no_xml / n_total:.1f}%)")
print(f"  GroundTruth parse failed:    {n_no_gt:>4}  ({100 * n_no_gt / n_total:.1f}%)")

# %%
# ---------------------------------------------------------------------------
# Per-flavor failure breakdown.
# ---------------------------------------------------------------------------
failure_table = (
    pdf_rows.groupby("flavor")
    .agg(
        pdfs=("path", "count"),
        no_pages=("page_count_known", lambda s: (~s).sum()),
        no_xml=("xml_extracted", lambda s: (~s).sum()),
        no_gt=("gt_parseable", lambda s: (~s).sum()),
    )
    .sort_values("pdfs", ascending=False)
)
failure_table

# %%
# ---------------------------------------------------------------------------
# Duplicate filename check (sanity guard).
# ---------------------------------------------------------------------------
dup_mask = corpus_index["filename"].duplicated(keep=False)
n_dup_filenames = int(dup_mask.sum())
print(f"Duplicate filenames in the corpus: {n_dup_filenames}")
if n_dup_filenames:
    print("(may be intentional — same invoice in multiple flavors; verify)")

# %% [markdown]
# **Discussion §9 (anomalies)**:
#
# - The `fail/` subdirs (ZUGFeRDv1/fail, ZUGFeRDv2/fail) are the
#   intentionally-invalid corpus; their non-zero failure rates here are
#   EXPECTED. Any failures in the `correct/` flavors deserve manual
#   inspection — those represent corpus-quality issues, not robustness
#   tests.
# - Per-flavor failure counts above let us see at a glance which flavors
#   are robust and which have known broken PDFs.
# - Duplicate filenames across flavors are usually intentional (the same
#   reference invoice in multiple ZUGFeRD variants).

# %% [markdown]
# ---
#
# # 10. Fine-tuning sufficiency commentary {#sec-sufficiency}
#
# Plain-text commentary section per the locked plan §3.3j. NOT a
# hypothesis test, NOT a recommendation — a structured statement of what
# the corpus is, what the thesis-defendable evaluation needs, and what
# future fine-tuning would need.

# %%
# ---------------------------------------------------------------------------
# Numbers feeding the commentary.
# ---------------------------------------------------------------------------
A = EDA.fine_tuning_anchors
n_eval_substrate = n_gt
n_total_corpus = n_total
n_user_belege_committed = 60  # per Q4 user-strategic-input (plan §7.1)
n_user_belege_target = 100  # per Q4 user-strategic-input
n_lora_min = A.lora_min_examples
n_lora_target = A.lora_target_examples
n_eval_min = A.eval_min_examples_for_thesis
print(f"Evaluation substrate (GT-parseable):     {n_eval_substrate}")
print(f"Total ZUGFeRD corpus:                    {n_total_corpus}")
print(f"User-committed Belege (existing):        {n_user_belege_committed}")
print(f"User-targeted Belege (self-collectable): {n_user_belege_target}")
print(f"LoRA range (literature anchor):          [{n_lora_min}, {n_lora_target}]")
print(f"Eval N for thesis-defendable F1 (≤±0.10 95% CI half-width): {n_eval_min}")

# %% [markdown]
# **Sufficiency commentary** (per plan §3.3j; informs future fine-tuning ADR
# at issue #55, NOT decided here):
#
# **For thesis-defendable evaluation** (the headline F1 numbers):
#
# - The literature anchor for ≤±0.10 95% CI half-width on a binary
#   success rate is `eval_min_examples_for_thesis` = `{n_eval_min}` PDFs.
# - Comparators: arxiv 2510.15727 (Oct 2025 invoice extraction, Docling vs
#   LlamaExtractor) used 102 invoices. Berghaus et al. 2025 (cited in
#   brainstorm v2 §7.1) used 350.
# - The ZUGFeRD corpus's GT-parseable subset = `{n_eval_substrate}` PDFs.
#   This is the dev/training substrate, NOT the held-out test set per
#   Q4=A in the EDA plan + brainstorm v2 §9.3.
# - The held-out test set is EXTERNAL: user has 60+ private Belege in
#   hand + ~40 reachable via self-collection = ~100 redacted Belege
#   (matches `eval_min_examples_for_thesis`). Belege storage =
#   `data/raw/german/belege/` gitignored; only sha256 + MANIFEST
#   committed; thesis figures use anonymized exemplars only.
#
# **For future LoRA fine-tuning** (issue #55, not decided in this EDA):
#
# - LoRA range per literature anchor: `[lora_min_examples,
#   lora_target_examples]` = `[{n_lora_min}, {n_lora_target}]` examples.
# - ZUGFeRD GT-parseable alone (`{n_eval_substrate}`) is below
#   `lora_min_examples` = `{n_lora_min}`. Augmentation paths:
#   - **Mustang Project + factur-x synthesis** (per brainstorm v2 §7.5):
#     unlimited synthetic ZUGFeRD invoices already supported by
#     `make zugferd-smoke`. Generator-shaped (NOT Beleg-shaped); thesis
#     methodology chapter must frame this carefully.
#   - **Self-collected Belege training portion** (~50 of the ~100 user-
#     targeted, with the other ~50 reserved as held-out test). Real-
#     world distribution; PII-redaction is a separate effort.
#   - **GI 2021 acquisition** (P1 deferred, brainstorm v2 §6.2): 977 real
#     German invoices from `dl.gi.de`. Adds breadth; license review +
#     MANIFEST authoring + sha256 sealing pending.
# - Total reachable training pool: ~`{n_eval_substrate}` (ZUGFeRD) +
#   ~50 (Belege train portion) + N (Mustang synth) ≈ `{n_eval_substrate + 50}`+
#   even before any GI 2021 acquisition. With Mustang synth this scales
#   freely into the LoRA target range.
#
# **What this section does NOT do**:
#
# - Decide whether to fine-tune. That's issue #55's ADR.
# - Decide which corpora to mix. That's issue #55's ADR.
# - Decide whether to acquire GI 2021. That's a separate dataset-
#   acquisition milestone with its own license review + MANIFEST.

# %% [markdown]
# ---
#
# # 11. Exploratory observations log {#sec-exploratory}
#
# Per the plan §3.3k + `bidirectional-learning-pipe` rule: any pattern
# that looks hypothesis-shaped surfaces HERE, NOT in §6 H1–H6. This is
# the canonical capture point for the descriptive-EDA-to-future-work
# bridge.

# %% [markdown]
# **Initial observations from this EDA pass** (placeholder; populated
# during the Socratic walk in plan §4 Step 5):
#
# - _(Each observation = 1-line statement + reference to the §N section
#   it surfaced from + a brief note on whether it's worth promoting to
#   `cascade-system/queue/pending-review.md` for cross-project review.)_
# - _(No observations recorded yet. The Socratic walk in plan §4 Step 5
#   captures these.)_

# %% [markdown]
# ---
#
# # 12. Interactive Explorer (HTML only) {#sec-explorer}
#
# Per Q5=C hybrid: this section's Plotly figures are ONLY useful in the
# HTML output (interactive hover, drill-down). PDF export drops them to
# static fallbacks gracefully. They mirror the static figures in §2 / §3 /
# §5 with hover affordances added.

# %%
#| label: fig-coverage-interactive
#| fig-cap: "Per-flavor file coverage (interactive). Hover for exact counts."
fig = px.bar(
    coverage[["PDF", "XML"]]
    .reset_index()
    .melt(id_vars="flavor", var_name="file_type", value_name="count"),
    y="flavor",
    x="count",
    color="file_type",
    orientation="h",
    color_discrete_sequence=[PALETTE_HEX[0], PALETTE_HEX[3]],
    title="Per-flavor file coverage (interactive)",
)
fig.update_layout(**PLOTLY_LAYOUT, yaxis=dict(autorange="reversed"))
fig.show()

# %%
#| label: fig-pages-interactive
#| fig-cap: "Page-count distribution by flavor (interactive). Hover for per-flavor counts."
plot_data = pdf_rows.dropna(subset=["page_count"]).copy()
plot_data["page_count"] = plot_data["page_count"].astype(int)
fig = px.histogram(
    plot_data,
    x="page_count",
    color="flavor",
    nbins=int(page_stats.max()),
    color_discrete_sequence=PALETTE_HEX,
    title="Page-count distribution (interactive)",
)
fig.update_layout(
    **PLOTLY_LAYOUT, barmode="stack", xaxis_title="Pages per PDF", yaxis_title="Number of PDFs"
)
fig.show()

# %%
#| label: fig-presence-heatmap-interactive
#| fig-cap: "Per-PDF × per-field presence heatmap (interactive). Hover to see PDF filename + field BT code + presence."
heatmap_long = presence_matrix.reset_index().melt(
    id_vars="filename", var_name="field", value_name="present"
)
heatmap_long["bt_code"] = heatmap_long["field"].map({k: spec.bt_code for k, spec in FIELDS.items()})
fig = px.density_heatmap(
    heatmap_long,
    y="filename",
    x="field",
    z="present",
    histfunc="sum",
    color_continuous_scale=[PALETTE_HEX[2], PALETTE_HEX[0]],
    title="Per-PDF × per-field presence (interactive)",
)
fig.update_layout(
    **PLOTLY_LAYOUT,
    height=max(600, 14 * len(presence_matrix)),
    yaxis=dict(autorange="reversed", showticklabels=False),
    xaxis=dict(tickangle=-45),
    coloraxis_colorbar=dict(title="present"),
)
fig.show()

# %% [markdown]
# ---
#
# # Conclusion + handoff {#sec-conclusion}
#
# - **What this EDA established**: a complete descriptive characterization
#   of the ZUGFeRD corpus (151 PDFs + 88 standalone XMLs across 7
#   flavors) — flavor coverage (§2), page-count distribution (§3),
#   profile breakdown (§4), 16-field presence rates (§5), per-field value
#   distributions (§6), pre-committed complexity-tier proposal (§7),
#   locale coverage (§8), anomaly catalog (§9), fine-tuning sufficiency
#   commentary (§10).
# - **What this EDA did NOT do**: hypothesis testing on H1–H6 (read-
#   only), held-out test-set evaluation (deferred to external Belege per
#   Q4=A), fine-tuning decisions (issue #55).
# - **Next step (per the plan)**: Socratic walk through findings (plan §4
#   Step 5) → exploratory observations get logged in §11 → cross-project
#   ones surface to `cascade-system/queue/pending-review.md` per
#   `bidirectional-learning-pipe`.
# - **Refs**: ADR-024 (visualization stack), ADR-014 (rasterizer +
#   harness substrate), ADR-013 (16-field GT scorer), ADR-009 (cohort),
#   issue #46, plan `~/.windsurf/plans/eda-zugferd-9c4a5b.md`,
#   brainstorm v2 §2 + §6 + §9.3 + §12.
