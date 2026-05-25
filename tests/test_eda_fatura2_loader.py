"""Tests for `horus.eda.fatura2_loader` (ADR-025 Phase C, chapter 2).

Pure-function tests for path-parsing helpers run unconditionally
(no I/O); corpus-aware tests for `walk` / `load_examples` are gated
behind `skip_if_no_fatura2_corpus` (a per-dataset analog of
`skip_if_no_corpus` for ZUGFeRD).

Refs: ADR-025 §"Per-chapter content template",
src/horus/eda/fatura2_loader.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.eda.fatura2_loader import (
    instance_id_from_path,
    load_examples,
    template_id_from_path,
    walk,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FATURA2_CORPUS = REPO_ROOT / "data" / "raw" / "english" / "fatura2-invoices"
FATURA2_DATA_DIR = FATURA2_CORPUS / "data"

# Per ADR-023 + tests/_corpus.py: corpus-dependent tests skip when content
# is not on disk. fatura2 follows the same gating model.
_HAS_FATURA2 = FATURA2_DATA_DIR.is_dir() and any(FATURA2_DATA_DIR.glob("*.parquet"))
skip_if_no_fatura2_corpus = pytest.mark.skipif(
    not _HAS_FATURA2,
    reason=(
        "Requires fatura2-invoices parquet files at "
        "data/raw/english/fatura2-invoices/data/*.parquet "
        "(gitignored per .gitignore). Skips automatically on CI + dev "
        "clones without the corpus fetched. Per ADR-023."
    ),
)


# ---------------------------------------------------------------------------
# Pure-function tests — no I/O, no corpus dependency.
# ---------------------------------------------------------------------------


def test_template_id_from_path_canonical() -> None:
    assert template_id_from_path("Template12_Instance0.jpg") == "Template12"
    assert template_id_from_path("Template1_Instance199.jpg") == "Template1"
    assert template_id_from_path("Template50_Instance0.jpg") == "Template50"


def test_template_id_from_path_case_insensitive() -> None:
    assert template_id_from_path("template7_instance3.JPG") == "Template7"


def test_template_id_from_path_returns_none_on_unknown_pattern() -> None:
    assert template_id_from_path("not-a-fatura2-name.jpg") is None
    assert template_id_from_path("invoice.png") is None
    assert template_id_from_path("") is None


def test_instance_id_from_path_canonical() -> None:
    assert instance_id_from_path("Template12_Instance0.jpg") == 0
    assert instance_id_from_path("Template1_Instance199.jpg") == 199
    assert instance_id_from_path("Template50_Instance7.jpg") == 7


def test_instance_id_from_path_returns_none_on_unknown_pattern() -> None:
    assert instance_id_from_path("not-a-fatura2-name.jpg") is None
    assert instance_id_from_path("template-only.jpg") is None


def test_walk_raises_on_missing_data_dir(tmp_path: Path) -> None:
    """`walk` raises FileNotFoundError when `<corpus_root>/data/` is absent."""
    with pytest.raises(FileNotFoundError, match="data directory not found"):
        walk(tmp_path)


def test_walk_raises_on_empty_data_dir(tmp_path: Path) -> None:
    """`walk` raises RuntimeError when `data/` exists but has no parquets."""
    (tmp_path / "data").mkdir()
    with pytest.raises(RuntimeError, match="No parquet files"):
        walk(tmp_path)


def test_load_examples_raises_when_split_not_found(tmp_path: Path) -> None:
    """Requesting a split that doesn't match any parquet → FileNotFoundError."""
    (tmp_path / "data").mkdir()
    # Stub a fake parquet matching neither "train-" nor "test-".
    fake = tmp_path / "data" / "validation-00000-of-00001.parquet"
    # Write a minimal valid parquet so `walk` doesn't fail at the empty-dir check.
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table({"x": [1, 2, 3]}), fake)
    with pytest.raises(FileNotFoundError, match="No parquet files matching"):
        load_examples(tmp_path, split="train")


# ---------------------------------------------------------------------------
# Corpus-aware tests — gated behind skip_if_no_fatura2_corpus.
# ---------------------------------------------------------------------------


@skip_if_no_fatura2_corpus
def test_walk_finds_train_and_test_parquets() -> None:
    """fatura2 ships with exactly 2 parquet files (train + test)."""
    df = walk(FATURA2_CORPUS)
    assert len(df) == 2
    assert set(df["split"]) == {"train", "test"}


@skip_if_no_fatura2_corpus
def test_walk_row_counts_match_dataset_card() -> None:
    """Per HuggingFace dataset card: train=8600 + test=1400 = 10000 total."""
    df = walk(FATURA2_CORPUS)
    train_rows = int(df[df["split"] == "train"]["n_rows"].iloc[0])
    test_rows = int(df[df["split"] == "test"]["n_rows"].iloc[0])
    assert train_rows == 8600
    assert test_rows == 1400


@skip_if_no_fatura2_corpus
def test_load_examples_default_drops_image_bytes() -> None:
    """Default `drop_image_bytes=True` keeps the DataFrame lightweight."""
    df = load_examples(FATURA2_CORPUS, split="test")
    assert "image_bytes" not in df.columns
    assert "image_bytes_len" in df.columns


@skip_if_no_fatura2_corpus
def test_load_examples_test_split_returns_1400_rows() -> None:
    df = load_examples(FATURA2_CORPUS, split="test")
    assert len(df) == 1400


@skip_if_no_fatura2_corpus
def test_load_examples_template_ids_parse_cleanly() -> None:
    """Every row's image_path must match the canonical pattern."""
    df = load_examples(FATURA2_CORPUS, split="test")
    # No nulls in template_id (canonical path-format invariant).
    assert df["template_id"].notna().all()
    # Templates are Template1 .. Template50 per the FATURA paper.
    template_ids = df["template_id"].unique()
    assert len(template_ids) <= 50
    for tid in template_ids:
        assert isinstance(tid, str) and tid.startswith("Template")


@skip_if_no_fatura2_corpus
def test_load_examples_token_count_in_expected_range() -> None:
    """Per the fatura2 inspection on 2026-05-25: tokens-per-invoice min~28,
    max~142, median~60. Smoke-check the test split lands in that envelope.
    """
    df = load_examples(FATURA2_CORPUS, split="test")
    n_tokens = df["num_tokens"]
    assert n_tokens.min() >= 1
    assert n_tokens.max() <= 500  # generous upper bound for any future row
    assert int(n_tokens.median()) > 10


@skip_if_no_fatura2_corpus
def test_load_examples_bbox_count_matches_token_count() -> None:
    """For well-formed rows, every token has a bbox (1:1 correspondence)."""
    df = load_examples(FATURA2_CORPUS, split="test")
    assert (df["num_tokens"] == df["bbox_count"]).all()


@skip_if_no_fatura2_corpus
def test_load_examples_image_bytes_len_nontrivial() -> None:
    """Every row should have JPEG bytes attached (non-empty)."""
    df = load_examples(FATURA2_CORPUS, split="test")
    assert (df["image_bytes_len"] > 0).all()


@skip_if_no_fatura2_corpus
def test_load_examples_all_split_concatenates() -> None:
    """`split='all'` returns 10000 rows = 8600 train + 1400 test."""
    df = load_examples(FATURA2_CORPUS, split="all")
    assert len(df) == 10000
    assert set(df["split"]) == {"train", "test"}
