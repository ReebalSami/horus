"""FUNSD loader for the EDA Book chapter 4 (ADR-025 Phase C).

Loads + characterizes the FUNSD dataset (Form Understanding in Noisy
Scanned Documents; Jaume, Ekenel, & Thiran, 2019;
https://guillaumejaume.github.io/FUNSD/, non-commercial-research
license): 199 noisy scanned forms (149 training + 50 testing) with
per-entity bounding boxes + 4-class labels (`other` / `question` /
`answer` / `header`) + entity-relation linking pairs. The dataset is
**form-shaped, not invoice-shaped** — fields are question-answer
pairs ("Buyer Name: ___"), NOT invoice line items. Used by
LayoutLM / LayoutLMv2 / LayoutLMv3 papers as a canonical form-
understanding benchmark.

On disk:

  - `dataset/training_data/{annotations,images}/` — 149 form pairs
  - `dataset/testing_data/{annotations,images}/` — 50 form pairs
  - Each annotation JSON: `{"form": [{box, text, label, words, linking, id}, ...]}`

Public surface:

  - :func:`walk` — return one row per form pair (annotation + image).
  - :func:`load_examples` — derive lightweight per-form features
    from every annotation JSON (entity counts per label / linking
    counts / word counts).
  - :func:`load_one_annotation` — read one annotation JSON.

Refs: ADR-025, docs/sources/datasets/funsd.md.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal

import pandas as pd

# Per the FUNSD paper §3.2 + dataset conventions: 4 entity-label classes.
FUNSD_LABELS: tuple[str, ...] = ("other", "question", "answer", "header")


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk FUNSD corpus, returning one-row-per-form DataFrame.

    The dataset ships under `<corpus_root>/dataset/{training_data,
    testing_data}/{annotations,images}/`. This walker pairs each
    `<id>.json` annotation with its `<id>.png` image; orphans (one
    without the other) surface as a row with `image_path=None` or
    `annotation_path=None` and are flagged in §6 Anomalies.

    Args:
        corpus_root: dataset root (typically `data/raw/english/funsd`).

    Returns:
        DataFrame with columns:
          - `form_id`: bare ID (e.g., "0000971160")
          - `split`: "training" / "testing"
          - `annotation_path`: absolute Path to the JSON or None
          - `image_path`: absolute Path to the PNG or None
          - `image_size_bytes`: stat() size or 0
          - `annotation_size_bytes`: stat() size or 0

    Raises:
        FileNotFoundError: if `<corpus_root>/dataset/` is absent.
    """
    dataset_dir = corpus_root / "dataset"
    if not dataset_dir.is_dir():
        raise FileNotFoundError(
            f"FUNSD dataset directory not found: {dataset_dir}. "
            f"Acquire the corpus first; see "
            f"data/raw/english/funsd/MANIFEST.md."
        )
    rows: list[dict[str, object]] = []
    for split_name in ("training_data", "testing_data"):
        split_root = dataset_dir / split_name
        if not split_root.is_dir():
            continue
        ann_dir = split_root / "annotations"
        img_dir = split_root / "images"
        # Collect form IDs from annotation filenames; pair with images
        # of the same stem.
        ann_paths = sorted(ann_dir.glob("*.json")) if ann_dir.is_dir() else []
        img_paths = sorted(img_dir.glob("*.png")) if img_dir.is_dir() else []
        ann_ids = {p.stem: p for p in ann_paths}
        img_ids = {p.stem: p for p in img_paths}
        all_ids = sorted(set(ann_ids) | set(img_ids))
        split_label = "training" if split_name == "training_data" else "testing"
        for fid in all_ids:
            ann = ann_ids.get(fid)
            img = img_ids.get(fid)
            rows.append(
                {
                    "form_id": fid,
                    "split": split_label,
                    "annotation_path": ann,
                    "image_path": img,
                    "image_size_bytes": img.stat().st_size if img else 0,
                    "annotation_size_bytes": ann.stat().st_size if ann else 0,
                }
            )
    return pd.DataFrame(rows)


def load_one_annotation(ann_path: Path) -> dict[str, object]:
    """Read a single FUNSD annotation JSON. Returns parsed dict."""
    with ann_path.open(encoding="utf-8") as f:
        return json.load(f)


def load_examples(
    corpus_root: Path,
    *,
    split: Literal["training", "testing", "all"] = "all",
) -> pd.DataFrame:
    """Load FUNSD annotations + derive lightweight per-form features.

    Args:
        corpus_root: dataset root.
        split: one of `"training"` / `"testing"` / `"all"`.

    Returns:
        DataFrame with one row per form. Columns:
          - `form_id`: bare ID
          - `split`: "training" / "testing"
          - `n_entities`: count of entries in `form[]`
          - `n_words`: sum of `len(entry["words"])` across entries
          - `n_linkings`: total entity-relation pairs across the form
          - `label_counts`: dict[str, int] — count per FUNSD_LABELS class
          - `n_questions` / `n_answers` / `n_headers` / `n_others`:
            convenience flat columns derived from `label_counts`
    """
    file_index = walk(corpus_root)
    if split != "all":
        file_index = file_index[file_index["split"] == split]
    rows: list[dict[str, object]] = []
    for _, row in file_index.iterrows():
        ann_path = row["annotation_path"]
        if ann_path is None or not (isinstance(ann_path, Path) and ann_path.exists()):
            continue
        ann = load_one_annotation(ann_path)
        entries_raw = ann.get("form", [])
        entries: list[dict[str, object]] = entries_raw if isinstance(entries_raw, list) else []
        labels: Counter[str] = Counter()
        n_words = 0
        n_linkings = 0
        for entry in entries:
            label = entry.get("label", "(unknown)")
            labels[str(label)] += 1
            words = entry.get("words", [])
            linking = entry.get("linking", [])
            if isinstance(words, list):
                n_words += len(words)
            if isinstance(linking, list):
                n_linkings += len(linking)
        rows.append(
            {
                "form_id": row["form_id"],
                "split": row["split"],
                "n_entities": len(entries),
                "n_words": n_words,
                "n_linkings": n_linkings,
                "label_counts": dict(labels),
                "n_questions": labels.get("question", 0),
                "n_answers": labels.get("answer", 0),
                "n_headers": labels.get("header", 0),
                "n_others": labels.get("other", 0),
            }
        )
    return pd.DataFrame(rows)
