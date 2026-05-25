"""Tests for `horus.eda.inv_cdip_loader` (ADR-025 Phase C, chapter 7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus.eda.inv_cdip_loader import (
    INV_CDIP_LABEL_NORMALIZATION,
    INV_CDIP_LABELS_DOCUMENTED,
    INV_CDIP_LABELS_OBSERVED,
    aggregate_label_counts,
    load_examples,
    load_one_annotation,
    normalize_label,
    parse_image_dims,
    walk,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
INV_CDIP_CORPUS = REPO_ROOT / "data" / "raw" / "english" / "inv-cdip-tobacco"
INV_CDIP_ANN_DIR = INV_CDIP_CORPUS / "annotation"

_HAS_INV_CDIP = INV_CDIP_ANN_DIR.is_dir() and any(INV_CDIP_ANN_DIR.glob("*.json"))
skip_if_no_inv_cdip_corpus = pytest.mark.skipif(
    not _HAS_INV_CDIP,
    reason=(
        "Requires inv-cdip-tobacco annotations under "
        "data/raw/english/inv-cdip-tobacco/annotation/. "
        "Skips on CI per ADR-023."
    ),
)


# ---------------------------------------------------------------------------
# Pure-function tests (no corpus required)
# ---------------------------------------------------------------------------


def test_inv_cdip_labels_documented_count() -> None:
    """Per the README: exactly 7 canonical field labels."""
    assert len(INV_CDIP_LABELS_DOCUMENTED) == 7
    assert len(set(INV_CDIP_LABELS_DOCUMENTED)) == 7


def test_inv_cdip_labels_observed_count() -> None:
    """Empirical: the 350 JSONs expose exactly 7 distinct labels."""
    assert len(INV_CDIP_LABELS_OBSERVED) == 7
    assert len(set(INV_CDIP_LABELS_OBSERVED)) == 7


def test_normalization_map_round_trips() -> None:
    """Every observed label maps to a documented label; bijective."""
    assert set(INV_CDIP_LABEL_NORMALIZATION.keys()) == set(INV_CDIP_LABELS_OBSERVED)
    assert set(INV_CDIP_LABEL_NORMALIZATION.values()) == set(INV_CDIP_LABELS_DOCUMENTED)


def test_normalize_label_known() -> None:
    """Known observed labels normalize correctly."""
    assert normalize_label("total_amount") == "Total_amount"
    assert normalize_label("total_tax_amount") == "Total_tax"
    assert normalize_label("Invoice_date") == "Invoice_date"  # already canonical


def test_normalize_label_unknown() -> None:
    """Unknown labels return None (for §6 anomaly surfacing)."""
    assert normalize_label("FooBar") is None
    assert normalize_label("") is None


def test_parse_image_dims_valid() -> None:
    assert parse_image_dims("[2195, 1706, 1]") == (2195, 1706, 1)
    assert parse_image_dims("[100, 200, 3]") == (100, 200, 3)


def test_parse_image_dims_malformed() -> None:
    """Bad input returns None instead of raising — caller surfaces anomalies."""
    assert parse_image_dims("garbage") is None
    assert parse_image_dims("[100, 200]") is None  # wrong arity
    assert parse_image_dims("") is None
    assert parse_image_dims("[a, b, c]") is None  # non-numeric


def test_walk_raises_on_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="annotation directory not found"):
        walk(tmp_path)


def test_walk_returns_empty_dataframe_on_empty_dir(tmp_path: Path) -> None:
    """An existing-but-empty annotation directory returns an empty DataFrame, not an error."""
    (tmp_path / "annotation").mkdir()
    df = walk(tmp_path)
    assert len(df) == 0


def test_walk_lists_synthetic_annotations(tmp_path: Path) -> None:
    """Synthetic mini-corpus exercises the discovery code path."""
    ann_dir = tmp_path / "annotation"
    ann_dir.mkdir()
    (ann_dir / "abc0001.json").write_text('{"image_dims": "[10,20,1]", "Fields": []}')
    (ann_dir / "abc0002.json").write_text('{"image_dims": "[10,20,1]", "Fields": []}')
    df = walk(tmp_path)
    assert len(df) == 2
    assert set(df["form_id"]) == {"abc0001", "abc0002"}
    assert (df["annotation_size_bytes"] > 0).all()


def test_load_one_annotation_round_trip(tmp_path: Path) -> None:
    ann_path = tmp_path / "x.json"
    payload = {"image_dims": "[100, 200, 1]", "Fields": []}
    ann_path.write_text(json.dumps(payload))
    out = load_one_annotation(ann_path)
    assert out == payload


def test_load_examples_derives_features(tmp_path: Path) -> None:
    """Synthetic form with 3 fields (2 with keys, 1 without)."""
    ann_dir = tmp_path / "annotation"
    ann_dir.mkdir()
    annotation = {
        "image_dims": "[2195, 1706, 1]",
        "Fields": [
            {
                "key": {"tag": "inv.", "bbox": {"xmin": 1, "ymin": 1, "xmax": 2, "ymax": 2}},
                "value": {
                    "label": "Invoice_number",
                    "tag": "#1356",
                    "bbox": {"xmin": 3, "ymin": 3, "xmax": 4, "ymax": 4},
                },
            },
            {
                "key": {"tag": None},
                "value": {
                    "label": "Invoice_date",
                    "tag": "January 24, 1994",
                    "bbox": {"xmin": 5, "ymin": 5, "xmax": 6, "ymax": 6},
                },
            },
            {
                "key": {"tag": "total", "bbox": {"xmin": 7, "ymin": 7, "xmax": 8, "ymax": 8}},
                "value": {
                    "label": "total_amount",
                    "tag": "$1,000.00",
                    "bbox": {"xmin": 9, "ymin": 9, "xmax": 10, "ymax": 10},
                },
            },
        ],
    }
    (ann_dir / "test001.json").write_text(json.dumps(annotation))
    df = load_examples(tmp_path)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["form_id"] == "test001"
    assert row["image_width"] == 2195
    assert row["image_height"] == 1706
    assert row["image_channels"] == 1
    assert row["n_fields"] == 3
    assert row["n_fields_with_key"] == 2  # 2 fields have key.tag != None
    assert row["field_labels"] == frozenset({"Invoice_number", "Invoice_date", "total_amount"})
    assert row["label_counts"] == {
        "Invoice_number": 1,
        "Invoice_date": 1,
        "total_amount": 1,
    }


def test_load_examples_handles_malformed_dims(tmp_path: Path) -> None:
    """Malformed image_dims surfaces as None for width/height/channels columns."""
    ann_dir = tmp_path / "annotation"
    ann_dir.mkdir()
    (ann_dir / "broken.json").write_text(json.dumps({"image_dims": "garbage", "Fields": []}))
    df = load_examples(tmp_path)
    row = df.iloc[0]
    assert row["image_width"] is None
    assert row["image_height"] is None
    assert row["image_channels"] is None


def test_aggregate_label_counts_sums_across_rows(tmp_path: Path) -> None:
    """aggregate_label_counts sums each label's count across all rows."""
    ann_dir = tmp_path / "annotation"
    ann_dir.mkdir()
    for i, lab in enumerate(("Invoice_number", "Invoice_number", "total_amount")):
        annotation = {
            "image_dims": "[100, 100, 1]",
            "Fields": [
                {
                    "key": {"tag": None},
                    "value": {
                        "label": lab,
                        "tag": "v",
                        "bbox": {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
                    },
                },
            ],
        }
        (ann_dir / f"form{i}.json").write_text(json.dumps(annotation))
    df = load_examples(tmp_path)
    totals = aggregate_label_counts(df)
    assert int(totals["Invoice_number"]) == 2
    assert int(totals["total_amount"]) == 1


# ---------------------------------------------------------------------------
# Corpus-aware tests (require inv-cdip-tobacco annotations on disk)
# ---------------------------------------------------------------------------


@skip_if_no_inv_cdip_corpus
def test_walk_real_corpus_form_count() -> None:
    """Per the README: 350 labeled invoices in the annotation directory."""
    df = walk(INV_CDIP_CORPUS)
    assert len(df) == 350


@skip_if_no_inv_cdip_corpus
def test_load_examples_real_corpus_field_count_bounds() -> None:
    """Every annotated form has 1 ≤ n_fields ≤ 7 (≤ canonical label set size)."""
    df = load_examples(INV_CDIP_CORPUS)
    assert len(df) == 350
    assert int(df["n_fields"].min()) >= 1
    # Empirically max is 6 (no form has all 7 labels), but allow ≤7 for safety.
    assert int(df["n_fields"].max()) <= 7


@skip_if_no_inv_cdip_corpus
def test_load_examples_real_corpus_label_set_matches_observed() -> None:
    """All field labels in the corpus are in the INV_CDIP_LABELS_OBSERVED set."""
    df = load_examples(INV_CDIP_CORPUS)
    observed_labels: set[str] = set()
    for lab_set in df["field_labels"]:
        observed_labels.update(lab_set)
    assert observed_labels == set(INV_CDIP_LABELS_OBSERVED), (
        f"Found labels {observed_labels} differ from expected "
        f"{set(INV_CDIP_LABELS_OBSERVED)}. The empirical-observation constant "
        f"may need updating."
    )


@skip_if_no_inv_cdip_corpus
def test_load_examples_real_corpus_image_channels_grayscale() -> None:
    """All scans are grayscale (channels=1) per the tobacco-corpus format."""
    df = load_examples(INV_CDIP_CORPUS)
    distinct_channels = set(df["image_channels"].dropna().unique().tolist())
    assert distinct_channels == {1}


@skip_if_no_inv_cdip_corpus
def test_aggregate_label_counts_real_corpus() -> None:
    """Empirical: Invoice_date is the most-frequent label (343/350 forms)."""
    df = load_examples(INV_CDIP_CORPUS)
    totals = aggregate_label_counts(df)
    # Invoice_date is the dominant label (verified empirically as 343 occurrences).
    assert "Invoice_date" in totals.index
    assert int(totals["Invoice_date"]) >= 300
    # Every observed label appears at least once.
    for lab in INV_CDIP_LABELS_OBSERVED:
        assert int(totals.get(lab, 0)) > 0
