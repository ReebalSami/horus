"""fatura2-invoices loader for the EDA Book chapter 2 (ADR-025 Phase C).

Loads + characterizes the FATURA2 invoices dataset
(`mathieu1256/FATURA2-invoices` on HuggingFace, CC-BY-4.0, ~10K
synthetic English invoice images with NER-tagged tokens + bounding
boxes, generated from 50 distinct layouts per Limam et al. 2023
arXiv:2311.11856). On disk: 2 parquet files (train: 8600 examples;
test: 1400 examples) under `data/raw/english/fatura2-invoices/data/`.

The dataset's HuggingFace-Transformers-compatible format encodes each
invoice as a row with:

  - `image`: dict with `bytes` (JPEG bytes) + `path` (e.g.,
    `Template12_Instance0.jpg`)
  - `tokens`: list[str] — OCR'd tokens from the invoice
  - `bboxes`: list[list[int]] — per-token bounding boxes (xmin, ymin,
    xmax, ymax) in image-pixel coordinates
  - `ner_tags`: list[int] — per-token NER class IDs from the FATURA
    24-class schema (TABLE / LOGO / DATE / NUMBER / SELLER ADDRESS /
    TOTAL / ...). The full label table lives in the FATURA paper §3.2;
    this loader exposes the integer IDs as-observed.
  - `id`: str — invoice ID

Public surface:

  - :func:`walk` — discovers parquet files under `corpus_root/data/`,
    returns one row per file with size + row-count + split.
  - :func:`load_examples` — reads parquet rows; returns DataFrame with
    `id` / `image_path` / `template_id` / `instance_id` / `num_tokens` /
    `unique_ner_tags` / `bbox_count`.
  - :func:`template_id_from_path` / :func:`instance_id_from_path` —
    parse `Template12_Instance0.jpg` filename pattern.
  - :func:`decode_image_bytes` — extract JPEG bytes from a parquet row.

Refs: ADR-025 §"Per-chapter content template",
docs/sources/datasets/fatura2-invoices.md (provenance stub),
data/raw/english/fatura2-invoices/MANIFEST.md (sha256 seal).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd

# Filename pattern for FATURA2 image paths: `Template<N>_Instance<M>.jpg`.
# Exposed as a module constant so callers can introspect the regex if needed.
_FATURA2_PATH_PATTERN = re.compile(
    r"^Template(?P<template>\d+)_Instance(?P<instance>\d+)\.jpg$",
    re.IGNORECASE,
)


def template_id_from_path(image_path: str) -> str | None:
    """Extract `Template<N>` from a FATURA2 image path string.

    Returns `None` if the path does not match the canonical pattern
    (e.g., a malformed entry the chapter would surface in §6 Anomalies).
    """
    match = _FATURA2_PATH_PATTERN.search(image_path)
    if match is None:
        return None
    return f"Template{match.group('template')}"


def instance_id_from_path(image_path: str) -> int | None:
    """Extract the instance number from a FATURA2 image path string.

    Returns `None` if the path does not match the canonical pattern.
    """
    match = _FATURA2_PATH_PATTERN.search(image_path)
    if match is None:
        return None
    return int(match.group("instance"))


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk the fatura2 corpus root, returning one-row-per-parquet-file DataFrame.

    Looks for `*.parquet` files under `<corpus_root>/data/`. Per the
    HuggingFace dataset layout, train + test splits are separate parquet
    files: `train-00000-of-00001.parquet` + `test-00000-of-00001.parquet`.

    Args:
        corpus_root: dataset root (typically `data/raw/english/fatura2-invoices`).

    Returns:
        DataFrame with columns:
          - `path`: absolute Path to the parquet file
          - `filename`: bare filename
          - `split`: `"train"` / `"test"` / `"unknown"` inferred from filename prefix
          - `size_bytes`: stat() size
          - `n_rows`: row count read from the parquet metadata (no full load)

    Raises:
        FileNotFoundError: if `<corpus_root>/data/` does not exist.
        RuntimeError: if no parquet files are found (suggests partial download).
    """
    data_dir = corpus_root / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"fatura2 data directory not found: {data_dir}. "
            f"Acquire the corpus first; see "
            f"data/raw/english/fatura2-invoices/MANIFEST.md."
        )
    parquets = sorted(data_dir.glob("*.parquet"))
    if not parquets:
        raise RuntimeError(
            f"No parquet files under {data_dir}. Verify the corpus is "
            f"fully fetched (expected: train-*.parquet + test-*.parquet)."
        )
    rows: list[dict[str, object]] = []
    for p in parquets:
        # Read just the parquet metadata for row count; no actual data load.
        import pyarrow.parquet as pq

        meta = pq.read_metadata(p)
        n_rows = meta.num_rows
        # Infer split from filename prefix.
        name = p.name.lower()
        if name.startswith("train-"):
            split = "train"
        elif name.startswith("test-"):
            split = "test"
        elif name.startswith("validation-") or name.startswith("val-"):
            split = "validation"
        else:
            split = "unknown"
        rows.append(
            {
                "path": p,
                "filename": p.name,
                "split": split,
                "size_bytes": p.stat().st_size,
                "n_rows": n_rows,
            }
        )
    return pd.DataFrame(rows)


def load_examples(
    corpus_root: Path,
    *,
    split: Literal["train", "test", "all"] = "all",
    drop_image_bytes: bool = True,
) -> pd.DataFrame:
    """Load fatura2 parquet rows + derive lightweight per-row features.

    Args:
        corpus_root: dataset root (typically `data/raw/english/fatura2-invoices`).
        split: one of `"train"` / `"test"` / `"all"`. Default `"all"` reads
            both splits and concatenates with a `split` column added.
        drop_image_bytes: if True (default), drops the `image.bytes` blob
            (~50 KB per row) from the returned DataFrame to keep memory
            usage manageable for the §3 sample-inspection use case. Set
            False if the chapter needs to render thumbnail previews.

    Returns:
        DataFrame with one row per invoice. Columns:
          - `id`: invoice ID (string)
          - `split`: `"train"` / `"test"`
          - `image_path`: original image filename (e.g., `Template12_Instance0.jpg`)
          - `template_id`: parsed `Template<N>` (or None on regex miss)
          - `instance_id`: parsed instance integer (or None on regex miss)
          - `num_tokens`: count of OCR'd tokens
          - `unique_ner_tags`: set of distinct NER tag IDs in the row (frozenset)
          - `bbox_count`: count of bounding boxes (= num_tokens for well-formed rows)
          - `image_bytes_len`: length in bytes of the JPEG (for size-distribution analysis)
          - `image_bytes`: JPEG bytes (only if `drop_image_bytes=False`)

    Raises:
        FileNotFoundError: if no parquet files are found for the requested split.
    """
    file_index = walk(corpus_root)
    if split == "all":
        files = file_index
    else:
        files = file_index[file_index["split"] == split]
    if len(files) == 0:
        raise FileNotFoundError(
            f"No parquet files matching split={split!r} under {corpus_root}/data/"
        )
    frames: list[pd.DataFrame] = []
    for _, file_row in files.iterrows():
        df_raw = pd.read_parquet(file_row["path"])
        derived = pd.DataFrame(
            {
                "id": df_raw["id"].astype(str),
                "split": file_row["split"],
                "image_path": df_raw["image"].apply(
                    lambda img: img["path"] if isinstance(img, dict) else None
                ),
                "image_bytes_len": df_raw["image"].apply(
                    lambda img: (
                        len(img["bytes"]) if isinstance(img, dict) and img.get("bytes") else 0
                    )
                ),
                "num_tokens": df_raw["tokens"].apply(
                    lambda toks: len(toks) if toks is not None else 0
                ),
                "unique_ner_tags": df_raw["ner_tags"].apply(
                    lambda tags: (
                        frozenset(int(t) for t in tags) if tags is not None else frozenset()
                    )
                ),
                "bbox_count": df_raw["bboxes"].apply(
                    lambda bbs: len(bbs) if bbs is not None else 0
                ),
            }
        )
        derived["template_id"] = derived["image_path"].apply(
            lambda p: template_id_from_path(p) if p else None
        )
        derived["instance_id"] = derived["image_path"].apply(
            lambda p: instance_id_from_path(p) if p else None
        )
        if not drop_image_bytes:
            derived["image_bytes"] = df_raw["image"].apply(
                lambda img: img["bytes"] if isinstance(img, dict) else None
            )
        frames.append(derived)
    return pd.concat(frames, ignore_index=True)


def decode_image_bytes(corpus_root: Path, row_id: str) -> bytes | None:
    """Fetch JPEG bytes for one invoice by ID. Returns None if not found.

    Used by the chapter's §3 sample-inspection cells to render a small
    set of preview images. Loads the parquet on-demand (no cache; the
    chapter calls this for ≤5 rows so the overhead is acceptable).
    """
    df = load_examples(corpus_root, split="all", drop_image_bytes=False)
    matches = df[df["id"] == row_id]
    if len(matches) == 0:
        return None
    image_bytes = matches.iloc[0]["image_bytes"]
    return image_bytes if isinstance(image_bytes, bytes) else None
