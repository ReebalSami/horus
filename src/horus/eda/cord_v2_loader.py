"""CORD-v2 loader for the EDA Book chapter 6 (ADR-025 Phase C).

Loads + characterizes the CORD-v2 dataset (Consolidated Receipt Dataset,
version 2; HuggingFace `naver-clova-ix/cord-v2`, CC-BY-4.0): 1000 Korean
receipt images with Donut-style hierarchical JSON ground-truth
annotations. Originally curated by NAVER CLOVA for the Donut paper
(Kim et al. 2022, ECCV) — widely used as OCR-free receipt-extraction
benchmark.

On disk: 6 parquet files under `<corpus_root>/data/`:

  - `train-00000-of-00004-*.parquet` through `train-00003-of-00004-*.parquet`
    — 4 train shards × 200 receipts = 800 train examples
  - `validation-00000-of-00001-*.parquet` — 100 validation examples
  - `test-00000-of-00001-*.parquet` — 100 test examples

Per-row schema (HuggingFace Datasets `imagefolder` builder format):

  - `image`: dict with `bytes` (raw image bytes, JPEG/PNG) + `path` (None
    for embedded images)
  - `ground_truth`: JSON-encoded string with top-level structure
    `{"gt_parse": {"menu": [...], "sub_total": {...}, "total": {...}, ...}}`
    — Donut-paper's "structured JSON ground truth" format.

Public surface:

  - :func:`walk` — discovers parquet files; returns one row per file with
    size + row-count + split inferred from filename prefix.
  - :func:`load_examples` — reads all rows; parses ground_truth JSON;
    derives per-row features (n_menu_items, top-level keys, total price
    extraction). Optionally drops image bytes for memory savings (default).
  - :func:`parse_ground_truth` — parse the JSON string into a Python dict.

Refs: ADR-025, `docs/sources/datasets/cord-v2.md`,
`data/raw/korean/cord-v2/MANIFEST.md`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk CORD-v2 corpus, returning one-row-per-parquet DataFrame.

    Looks for `*.parquet` files under `<corpus_root>/data/`. Per HF's
    `imagefolder` builder layout, splits are encoded in filenames:
    `train-NNNNN-of-MMMMM-*.parquet`, `validation-*.parquet`,
    `test-*.parquet`.

    Args:
        corpus_root: dataset root (typically `data/raw/korean/cord-v2`).

    Returns:
        DataFrame with columns:
          - `path`: absolute Path to the parquet
          - `filename`: bare filename
          - `split`: `"train"` / `"validation"` / `"test"` / `"unknown"`
          - `size_bytes`: stat() size
          - `n_rows`: row count from parquet metadata

    Raises:
        FileNotFoundError: if `<corpus_root>/data/` is absent.
        RuntimeError: if no parquet files are found.
    """
    data_dir = corpus_root / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"CORD-v2 data directory not found: {data_dir}. "
            f"Acquire the corpus first; see "
            f"data/raw/korean/cord-v2/MANIFEST.md."
        )
    parquets = sorted(data_dir.glob("*.parquet"))
    if not parquets:
        raise RuntimeError(
            f"No parquet files under {data_dir}. Verify the corpus is "
            f"fully fetched (expected: 4 train + 1 validation + 1 test)."
        )
    import pyarrow.parquet as pq

    rows: list[dict[str, object]] = []
    for p in parquets:
        meta = pq.read_metadata(p)
        name = p.name.lower()
        if name.startswith("train-"):
            split = "train"
        elif name.startswith("validation-") or name.startswith("val-"):
            split = "validation"
        elif name.startswith("test-"):
            split = "test"
        else:
            split = "unknown"
        rows.append(
            {
                "path": p,
                "filename": p.name,
                "split": split,
                "size_bytes": p.stat().st_size,
                "n_rows": meta.num_rows,
            }
        )
    return pd.DataFrame(rows)


def parse_ground_truth(gt_str: str) -> dict[str, Any]:
    """Parse the CORD-v2 ground_truth JSON string into a Python dict.

    The string is JSON-encoded; the top-level key is `gt_parse` which
    contains the receipt's structured fields. Returns the full parsed
    object including the `gt_parse` wrapper for downstream inspection.

    Args:
        gt_str: raw JSON string from the ground_truth column.

    Returns:
        Parsed JSON object (typically `{"gt_parse": {...}}`).

    Raises:
        json.JSONDecodeError: if the string is not valid JSON.
    """
    return json.loads(gt_str)


def _gt_parse_top_keys(gt_obj: dict[str, Any]) -> frozenset[str]:
    """Extract the top-level keys under `gt_parse` (Donut field categories)."""
    inner = gt_obj.get("gt_parse", {})
    if not isinstance(inner, dict):
        return frozenset()
    return frozenset(inner.keys())


def _count_menu_items(gt_obj: dict[str, Any]) -> int:
    """Count `menu` items in the parsed GT. The `menu` field is either a
    single dict (1 item) or a list of dicts (N items); both conventions
    appear in CORD-v2 per the Donut paper's schema."""
    inner = gt_obj.get("gt_parse", {})
    if not isinstance(inner, dict):
        return 0
    menu = inner.get("menu")
    if menu is None:
        return 0
    if isinstance(menu, list):
        return len(menu)
    if isinstance(menu, dict):
        return 1
    return 0


def _extract_total_price(gt_obj: dict[str, Any]) -> str | None:
    """Extract the total_price field from gt_parse.total, if present.
    Returns None if `total` or `total_price` is absent or malformed."""
    inner = gt_obj.get("gt_parse", {})
    if not isinstance(inner, dict):
        return None
    total = inner.get("total")
    if not isinstance(total, dict):
        return None
    val = total.get("total_price")
    return val if isinstance(val, str) else None


def load_examples(
    corpus_root: Path,
    *,
    split: Literal["train", "validation", "test", "all"] = "all",
    drop_image_bytes: bool = True,
) -> pd.DataFrame:
    """Load CORD-v2 rows + derive lightweight per-row features.

    Args:
        corpus_root: dataset root.
        split: `"train"` / `"validation"` / `"test"` / `"all"` (default).
        drop_image_bytes: if True (default), read only `ground_truth` column
            from parquet (image bytes never enter memory). If False, load
            the full row including the image dict. The default is True
            because CORD-v2 image bytes are ~300-500 KB per row and the
            chapter-level distribution analysis does not need them.

    Returns:
        DataFrame with one row per receipt. Columns (always present):
          - `split`: train / validation / test
          - `gt_top_level_keys`: frozenset of top-level keys under `gt_parse`
          - `n_menu_items`: count of menu items in this receipt
          - `total_price`: extracted total_price string (or None)
          - `gt_raw`: raw JSON string (for downstream inspection)
        Plus (only if `drop_image_bytes=False`):
          - `image_bytes`: raw image bytes
          - `image_bytes_len`: byte length

    Raises:
        FileNotFoundError: if no parquet files match the requested split.
    """
    file_index = walk(corpus_root)
    if split != "all":
        file_index = file_index[file_index["split"] == split]
    if len(file_index) == 0:
        raise FileNotFoundError(
            f"No parquet files matching split={split!r} under {corpus_root}/data/"
        )
    frames: list[pd.DataFrame] = []
    columns = ["ground_truth"] if drop_image_bytes else None
    for _, file_row in file_index.iterrows():
        df_raw = pd.read_parquet(file_row["path"], columns=columns)
        gt_objs = df_raw["ground_truth"].apply(parse_ground_truth)
        derived = pd.DataFrame(
            {
                "split": file_row["split"],
                "gt_top_level_keys": gt_objs.apply(_gt_parse_top_keys),
                "n_menu_items": gt_objs.apply(_count_menu_items),
                "total_price": gt_objs.apply(_extract_total_price),
                "gt_raw": df_raw["ground_truth"].astype(str),
            }
        )
        if not drop_image_bytes and "image" in df_raw.columns:
            derived["image_bytes"] = df_raw["image"].apply(
                lambda img: img["bytes"] if isinstance(img, dict) else None
            )
            derived["image_bytes_len"] = derived["image_bytes"].apply(
                lambda b: len(b) if isinstance(b, (bytes, bytearray)) else 0
            )
        frames.append(derived)
    return pd.concat(frames, ignore_index=True)


def load_one_image_bytes(corpus_root: Path, *, split: str, row_index: int) -> bytes | None:
    """Load image bytes for a single row from a specific split parquet.

    Used by the chapter's §3 sample-inspection cells to render preview
    images one at a time, avoiding the memory cost of loading all 1000
    receipt images simultaneously.

    Args:
        corpus_root: dataset root.
        split: `"train"` / `"validation"` / `"test"`.
        row_index: zero-indexed position within the concatenated split
            (e.g., row_index=0 returns the first row of the first parquet
            shard for that split).

    Returns:
        Raw image bytes if found; None if the row index is out of range.
    """
    file_index = walk(corpus_root)
    file_index = file_index[file_index["split"] == split].reset_index(drop=True)
    cumulative = 0
    for _, file_row in file_index.iterrows():
        n_rows = int(file_row["n_rows"])
        if row_index < cumulative + n_rows:
            local_idx = row_index - cumulative
            df_one = pd.read_parquet(file_row["path"], columns=["image"]).iloc[
                local_idx : local_idx + 1
            ]
            img = df_one["image"].iloc[0]
            if isinstance(img, dict):
                img_bytes = img.get("bytes")
                if isinstance(img_bytes, (bytes, bytearray)):
                    return bytes(img_bytes)
            return None
        cumulative += n_rows
    return None
