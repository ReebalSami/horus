"""omnidocbench loader for the EDA Book chapter 3 (ADR-025 Phase C).

Loads + characterizes the OmniDocBench dataset (HuggingFace
`opendatalab/OmniDocBench`, custom non-commercial-research license):
1651 multilingual (Chinese 47% + English 46% + mixed 7%) document
images covering books, academic papers, PPT-to-PDF, exam papers,
colorful textbooks, newspapers, magazines, research reports, notes,
and historical documents. Per-page region-level annotations encode
text_block / title / equation / figure / table / header / footer /
page_number / etc. — the "what's on the page" structure that downstream
document-AI evaluations consume.

**NOT an invoice dataset.** OmniDocBench's `data_source` taxonomy
contains exactly zero invoice-class entries (verified empirically on
2026-05-25; see chapter @sec-omnidocbench §4). The dataset's HORUS
thesis relevance is BREADTH (general OCR-route robustness on diverse
documents + Chinese-language transfer test bed), NOT direct invoice
substrate.

On disk:

  - `OmniDocBench.json` (40 MB) — 1651 entries; one per image
  - `with_mask.json` (50 KB) — separate mask annotations (auxiliary)
  - `images/` (1651 .png files) — page renders, ~1.5 GB total
  - `data_diversity.png` + `show_pdf_types_*.png` — auxiliary visuals
  - 34 of the 670 .png files are mislabeled JPEG content per the
    upstream dataset (MANIFEST.md `anomalies[0]`); not corruption.

Public surface:

  - :func:`load_index` — read `OmniDocBench.json`; return DataFrame
    with one row per entry + page_attribute fields hoisted to columns.
  - :func:`category_counts` — aggregate per-row layout_det category
    types into a frequency table.
  - :func:`load_image` — fetch a single image's PNG bytes by row.

Refs: ADR-025 §"Per-chapter content template",
docs/sources/datasets/omnidocbench.md (provenance stub),
data/raw/multilingual/omnidocbench/MANIFEST.md (sha256 seal +
mislabeled-png anomaly note).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd


def load_index(corpus_root: Path) -> pd.DataFrame:
    """Read the OmniDocBench.json index and return one row per entry.

    Hoists `page_info.page_attribute.{language, data_source, layout,
    subset, special_issue}` and `page_info.{height, width, image_path,
    page_no}` into top-level columns for direct DataFrame analysis.

    Args:
        corpus_root: dataset root (typically
            `data/raw/multilingual/omnidocbench`).

    Returns:
        DataFrame with columns:
          - `image_path`: relative filename in `images/` subdir
          - `page_no`: 0-indexed page within the source document
          - `width` / `height`: image dimensions in pixels
          - `language`: one of `simplified_chinese` / `english` /
            `en_ch_mixed` / `traditional_chinese` / `other`
          - `data_source`: one of `book` / `PPT2PDF` /
            `academic_literature` / `exam_paper` / etc.
          - `layout`: one of `single_column` / `double_column` /
            `three_column` / `1andmore_column` / `other_layout`
          - `subset`: dataset subset (e.g., `v1.5` /
            `equation_hard` / `table_hard` / `layout_hard`)
          - `special_issues`: tuple of special-issue tags (e.g.,
            `("table_horizontal", "colorful_background")`)
          - `n_layout_dets`: count of region-level annotations on
            this page
          - `category_types`: frozenset of distinct category_type
            values in this page's layout_dets

    Raises:
        FileNotFoundError: if `OmniDocBench.json` is absent.
    """
    json_path = corpus_root / "OmniDocBench.json"
    if not json_path.is_file():
        raise FileNotFoundError(
            f"OmniDocBench.json not found: {json_path}. "
            f"Acquire the corpus first; see "
            f"data/raw/multilingual/omnidocbench/MANIFEST.md."
        )
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    rows: list[dict[str, object]] = []
    for entry in data:
        page_info = entry.get("page_info", {})
        page_attr = page_info.get("page_attribute", {})
        layout_dets = entry.get("layout_dets", [])
        category_types = frozenset(det.get("category_type", "(unknown)") for det in layout_dets)
        rows.append(
            {
                "image_path": page_info.get("image_path"),
                "page_no": page_info.get("page_no"),
                "width": page_info.get("width"),
                "height": page_info.get("height"),
                "language": page_attr.get("language"),
                "data_source": page_attr.get("data_source"),
                "layout": page_attr.get("layout"),
                "subset": page_attr.get("subset"),
                "special_issues": tuple(page_attr.get("special_issue", [])),
                "n_layout_dets": len(layout_dets),
                "category_types": category_types,
            }
        )
    return pd.DataFrame(rows)


def category_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-row `category_types` frozensets into a frequency table.

    Counts how many PAGES have each category_type at least once
    (NOT how many bounding boxes — for that, re-load the JSON and
    count layout_dets directly). Useful for the §4 distributional
    "what kinds of regions appear in OmniDocBench's annotation
    schema" table.

    Args:
        df: DataFrame from :func:`load_index`.

    Returns:
        DataFrame indexed by category_type with `n_pages` column.
    """
    counter: Counter[str] = Counter()
    for cats in df["category_types"]:
        for c in cats:
            counter[c] += 1
    return pd.DataFrame.from_dict(counter, orient="index", columns=["n_pages"]).sort_values(
        "n_pages", ascending=False
    )


def load_image_bytes(corpus_root: Path, image_path: str) -> bytes | None:
    """Read PNG bytes for one image. Returns None if not found.

    The dataset's MANIFEST flags 34 of 670 `.png` files as actually
    containing JPEG content (header `ffd8ffe0` instead of `89504e47`).
    This loader reads the raw bytes regardless; downstream callers
    that want to decode-and-display should use PIL's auto-detection
    rather than rely on the file extension.
    """
    path = corpus_root / "images" / image_path
    if not path.is_file():
        return None
    return path.read_bytes()
