"""inv-cdip-tobacco loader for the EDA Book chapter 7 (ADR-025 Phase C).

Loads + characterizes the inv-cdip-tobacco dataset (Salesforce inv-cdip
on GitHub, Gao et al. 2022 ACL Spa-NLP Workshop, CC-BY-NC-4.0): 350
labeled invoice annotations covering 7 canonical field labels
(Invoice_number / Purchase_order / Invoice_date / Due_date /
Amount_due / Total_amount / Total_tax). The dataset is a subset of
the CDIP corpus (Complaint, Document, Image Processing) drawing from
the UCSF Industry Documents Library tobacco-document collection.

**Annotations-only acquisition.** The underlying tobacco-industry PDF
scans are intentionally NOT downloaded — per acquisition decision
(sub-issue #28 closed not-planned 2026-05-13), the HORUS pilot uses
the 350 JSON annotations alone for Berghaus-baseline cross-comparison
without the raw scans. This makes the chapter focus on
annotation-schema characterization, not visual properties.

On disk under `<corpus_root>/`:

  - `annotation/<id>.json` — 350 labeled-invoice annotations (the
    primary EDA substrate)
  - `train_set.txt` — ~200K UNLABELED invoice IDs (scans not
    downloaded; document IDs only)
  - `test_set.txt` — 350 IDs matching the labeled set above
  - `README.md`, `LICENSE.txt`, `download_data.py`, etc. — metadata
    + Salesforce-provided acquisition scripts (the latter unused).

Per-annotation JSON schema (per README §"Annotation Description"):

  {
    "image_dims": "[width, height, channels]",  # str literal
    "Fields": [
      {
        "key": {"tag": str|None, "bbox": {xmin, ymin, xmax, ymax}},
        "value": {
          "label": str,                          # canonical 7-label set
          "tag": str,                            # extracted value text
          "bbox": {xmin, ymin, xmax, ymax}       # value location
        }
      },
      ...
    ]
  }

Public surface:

  - :func:`walk` — list all annotation JSONs under `annotation/`.
  - :func:`load_one_annotation` — read one annotation JSON.
  - :func:`load_examples` — load all annotations + derive per-form
    features (n_fields / field_labels / image_dims / has_key counts).
  - :func:`parse_image_dims` — parse the `"[w, h, c]"` string literal
    into a (width, height, channels) tuple.

Refs: ADR-025, `docs/sources/datasets/inv-cdip-tobacco.md`,
`data/raw/english/inv-cdip-tobacco/MANIFEST.md`.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

# Per the README §"Introduction": 7 canonical field labels with the
# README's documented capitalization.
INV_CDIP_LABELS_DOCUMENTED: tuple[str, ...] = (
    "Invoice_number",
    "Purchase_order",
    "Invoice_date",
    "Due_date",
    "Amount_due",
    "Total_amount",
    "Total_tax",
)

# Empirical labels actually present in the 350 JSON annotations (verified
# 2026-05-25 against the on-disk corpus). The set is the same size as the
# documented set BUT with case + suffix drift vs README:
#   - 3 documented capitalized labels MATCH:
#       Invoice_date / Invoice_number / Purchase_order
#   - 3 documented labels appear in LOWERCASE in JSON:
#       Due_date → due_date
#       Amount_due → amount_due
#       Total_amount → total_amount
#   - 1 documented label has both case drift + an extra suffix:
#       Total_tax → total_tax_amount
# Surfaced as a §6 Anomaly in the chapter; flagged for a Decision
# Register entry about cross-corpus label normalization (chapter
# @sec-cross-corpus).
INV_CDIP_LABELS_OBSERVED: tuple[str, ...] = (
    "Invoice_number",
    "Purchase_order",
    "Invoice_date",
    "due_date",
    "amount_due",
    "total_amount",
    "total_tax_amount",
)

# Mapping from OBSERVED label (as found in JSON) → DOCUMENTED label
# (as listed in README). Use to normalize empirical labels for
# cross-corpus comparison; surfaces the README-vs-JSON discrepancy
# rather than silently bridging it.
INV_CDIP_LABEL_NORMALIZATION: dict[str, str] = {
    "Invoice_number": "Invoice_number",
    "Purchase_order": "Purchase_order",
    "Invoice_date": "Invoice_date",
    "due_date": "Due_date",
    "amount_due": "Amount_due",
    "total_amount": "Total_amount",
    "total_tax_amount": "Total_tax",
}


def normalize_label(observed_label: str) -> str | None:
    """Map an observed JSON label to its documented (README) form.

    Returns None if the observed label is not in the known 7-label set —
    useful for surfacing previously-unseen labels in §6 Anomalies.
    """
    return INV_CDIP_LABEL_NORMALIZATION.get(observed_label)


def walk(corpus_root: Path) -> pd.DataFrame:
    """Walk the inv-cdip-tobacco annotation directory.

    Lists all `<id>.json` files under `<corpus_root>/annotation/`.

    Args:
        corpus_root: dataset root (typically
            `data/raw/english/inv-cdip-tobacco`).

    Returns:
        DataFrame with columns:
          - `form_id`: bare ID (e.g., `sfyx0118`)
          - `annotation_path`: absolute Path to the JSON
          - `annotation_size_bytes`: stat() size

    Raises:
        FileNotFoundError: if `<corpus_root>/annotation/` is absent.
    """
    ann_dir = corpus_root / "annotation"
    if not ann_dir.is_dir():
        raise FileNotFoundError(
            f"inv-cdip-tobacco annotation directory not found: {ann_dir}. "
            f"Acquire the corpus first; see "
            f"data/raw/english/inv-cdip-tobacco/MANIFEST.md."
        )
    ann_paths = sorted(ann_dir.glob("*.json"))
    rows: list[dict[str, object]] = []
    for p in ann_paths:
        rows.append(
            {
                "form_id": p.stem,
                "annotation_path": p,
                "annotation_size_bytes": p.stat().st_size,
            }
        )
    return pd.DataFrame(rows)


def load_one_annotation(ann_path: Path) -> dict[str, Any]:
    """Read a single inv-cdip-tobacco annotation JSON."""
    with ann_path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_image_dims(image_dims_str: str) -> tuple[int, int, int] | None:
    """Parse the `"[w, h, c]"` Python-literal-shaped string into a tuple.

    Per the inv-cdip JSON shape: `image_dims` is a string carrying a
    Python list-literal like `"[2195, 1706, 1]"` (width, height,
    channels). `ast.literal_eval` parses it safely.

    Returns None if the string is malformed (caller surfaces in §6
    Anomalies).
    """
    try:
        parsed = ast.literal_eval(image_dims_str)
    except ValueError, SyntaxError:
        return None
    if not (isinstance(parsed, (list, tuple)) and len(parsed) == 3):
        return None
    try:
        w, h, c = int(parsed[0]), int(parsed[1]), int(parsed[2])
    except TypeError, ValueError:
        return None
    return w, h, c


def load_examples(corpus_root: Path) -> pd.DataFrame:
    """Load all inv-cdip annotations + derive per-form features.

    Args:
        corpus_root: dataset root.

    Returns:
        DataFrame with one row per labeled annotation. Columns:
          - `form_id`: bare ID (e.g., `sfyx0118`)
          - `image_width`: parsed image width (or None on malformed dims)
          - `image_height`: parsed image height (or None)
          - `image_channels`: parsed image channels (or None)
          - `n_fields`: count of entries in the `Fields` array
          - `n_fields_with_key`: count of fields whose `key.tag` is not None
          - `field_labels`: frozenset of distinct `value.label` strings
                            observed on this form
          - `label_counts`: dict[str, int] — per-label entity count

    Raises:
        FileNotFoundError: if the annotation directory is absent.
    """
    file_index = walk(corpus_root)
    rows: list[dict[str, object]] = []
    for _, row in file_index.iterrows():
        ann = load_one_annotation(row["annotation_path"])
        dims = parse_image_dims(ann.get("image_dims", ""))
        fields_raw = ann.get("Fields", [])
        fields: list[dict[str, Any]] = fields_raw if isinstance(fields_raw, list) else []
        labels: Counter[str] = Counter()
        n_with_key = 0
        for fld in fields:
            value_block = fld.get("value", {})
            if isinstance(value_block, dict):
                label = value_block.get("label")
                if isinstance(label, str):
                    labels[label] += 1
            key_block = fld.get("key", {})
            if isinstance(key_block, dict) and key_block.get("tag") is not None:
                n_with_key += 1
        rows.append(
            {
                "form_id": row["form_id"],
                "image_width": dims[0] if dims else None,
                "image_height": dims[1] if dims else None,
                "image_channels": dims[2] if dims else None,
                "n_fields": len(fields),
                "n_fields_with_key": n_with_key,
                "field_labels": frozenset(labels.keys()),
                "label_counts": dict(labels),
            }
        )
    return pd.DataFrame(rows)


def aggregate_label_counts(df: pd.DataFrame) -> pd.Series:
    """Sum per-label entity counts across all rows in a load_examples DataFrame.

    Returns a Series indexed by label name with the total count.
    """
    total: Counter[str] = Counter()
    for label_counts in df["label_counts"]:
        if isinstance(label_counts, dict):
            for k, v in label_counts.items():
                total[k] += int(v)
    return pd.Series(total).sort_values(ascending=False)
