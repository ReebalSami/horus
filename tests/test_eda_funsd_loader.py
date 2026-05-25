"""Tests for `horus.eda.funsd_loader` (ADR-025 Phase C, chapter 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus.eda.funsd_loader import (
    FUNSD_LABELS,
    load_examples,
    load_one_annotation,
    walk,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FUNSD_CORPUS = REPO_ROOT / "data" / "raw" / "english" / "funsd"
FUNSD_DATASET = FUNSD_CORPUS / "dataset"

_HAS_FUNSD = FUNSD_DATASET.is_dir() and any(
    (FUNSD_DATASET / "training_data" / "annotations").glob("*.json")
)
skip_if_no_funsd_corpus = pytest.mark.skipif(
    not _HAS_FUNSD,
    reason=(
        "Requires FUNSD dataset under "
        "data/raw/english/funsd/dataset/{training,testing}_data/. "
        "Skips on CI per ADR-023."
    ),
)


def test_funsd_labels_constant() -> None:
    """FUNSD ships exactly 4 entity-label classes per the paper."""
    assert FUNSD_LABELS == ("other", "question", "answer", "header")
    assert len(set(FUNSD_LABELS)) == 4


def test_walk_raises_on_missing_dataset_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="dataset directory not found"):
        walk(tmp_path)


def test_walk_pairs_annotations_and_images(tmp_path: Path) -> None:
    """Synthetic mini-corpus exercises the form-ID pairing logic."""
    base = tmp_path / "dataset" / "training_data"
    (base / "annotations").mkdir(parents=True)
    (base / "images").mkdir(parents=True)
    (base / "annotations" / "form001.json").write_text('{"form": []}')
    (base / "images" / "form001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    df = walk(tmp_path)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["form_id"] == "form001"
    assert row["split"] == "training"
    assert row["annotation_path"] is not None
    assert row["image_path"] is not None


def test_walk_surfaces_orphans(tmp_path: Path) -> None:
    """Form IDs with one of {annotation, image} missing surface as orphans."""
    base = tmp_path / "dataset" / "testing_data"
    (base / "annotations").mkdir(parents=True)
    (base / "images").mkdir(parents=True)
    # Annotation only (no image) → orphan with image_path=None
    (base / "annotations" / "orphan_ann.json").write_text('{"form": []}')
    # Image only (no annotation) → orphan with annotation_path=None
    (base / "images" / "orphan_img.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    df = walk(tmp_path)
    assert len(df) == 2
    ann_only = df[df["form_id"] == "orphan_ann"].iloc[0]
    assert ann_only["image_path"] is None
    img_only = df[df["form_id"] == "orphan_img"].iloc[0]
    assert img_only["annotation_path"] is None


def test_load_examples_derives_features(tmp_path: Path) -> None:
    base = tmp_path / "dataset" / "training_data"
    (base / "annotations").mkdir(parents=True)
    (base / "images").mkdir(parents=True)
    annotation = {
        "form": [
            {
                "box": [0, 0, 10, 10],
                "text": "Name:",
                "label": "question",
                "words": [{"box": [0, 0, 5, 10], "text": "Name:"}],
                "linking": [[0, 1]],
                "id": 0,
            },
            {
                "box": [10, 0, 30, 10],
                "text": "Alice Smith",
                "label": "answer",
                "words": [
                    {"box": [10, 0, 20, 10], "text": "Alice"},
                    {"box": [20, 0, 30, 10], "text": "Smith"},
                ],
                "linking": [[0, 1]],
                "id": 1,
            },
            {
                "box": [0, 20, 100, 30],
                "text": "header text",
                "label": "header",
                "words": [{"box": [0, 20, 100, 30], "text": "header"}],
                "linking": [],
                "id": 2,
            },
        ]
    }
    (base / "annotations" / "f.json").write_text(json.dumps(annotation))
    (base / "images" / "f.png").write_bytes(b"\x89PNG")
    df = load_examples(tmp_path, split="training")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["n_entities"] == 3
    assert row["n_words"] == 4  # 1 + 2 + 1
    assert row["n_linkings"] == 2  # 1 + 1 + 0
    assert row["n_questions"] == 1
    assert row["n_answers"] == 1
    assert row["n_headers"] == 1
    assert row["n_others"] == 0


def test_load_one_annotation_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    target.write_text(json.dumps({"form": [{"text": "hi"}]}))
    out = load_one_annotation(target)
    assert out == {"form": [{"text": "hi"}]}


# Corpus-aware tests
@skip_if_no_funsd_corpus
def test_walk_real_corpus_form_counts() -> None:
    """Per the FUNSD paper: 199 forms total = 149 train + 50 test."""
    df = walk(FUNSD_CORPUS)
    assert len(df) == 199
    assert int((df["split"] == "training").sum()) == 149
    assert int((df["split"] == "testing").sum()) == 50


@skip_if_no_funsd_corpus
def test_load_examples_real_corpus_label_distribution() -> None:
    """Empirical: every form has at least 1 entity; labels are non-empty."""
    df = load_examples(FUNSD_CORPUS, split="all")
    assert len(df) == 199
    assert (df["n_entities"] > 0).all()
    # FUNSD labels should appear at least once across the corpus.
    total_questions = int(df["n_questions"].sum())
    total_answers = int(df["n_answers"].sum())
    assert total_questions > 0
    assert total_answers > 0


@skip_if_no_funsd_corpus
def test_load_examples_real_corpus_linking_present() -> None:
    """FUNSD's linking pairs (entity-relation grouping) appear across forms."""
    df = load_examples(FUNSD_CORPUS, split="all")
    assert int(df["n_linkings"].sum()) > 0
