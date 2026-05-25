"""Tests for `horus.eda.cord_v2_loader` (ADR-025 Phase C, chapter 6)."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from horus.eda.cord_v2_loader import (
    load_examples,
    load_one_image_bytes,
    parse_ground_truth,
    walk,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORD_CORPUS = REPO_ROOT / "data" / "raw" / "korean" / "cord-v2"
CORD_DATA_DIR = CORD_CORPUS / "data"

_HAS_CORD = CORD_DATA_DIR.is_dir() and any(CORD_DATA_DIR.glob("*.parquet"))
skip_if_no_cord_corpus = pytest.mark.skipif(
    not _HAS_CORD,
    reason=(
        "Requires CORD-v2 parquet files under "
        "data/raw/korean/cord-v2/data/. "
        "Skips on CI per ADR-023."
    ),
)


# ---------------------------------------------------------------------------
# Helpers — build a synthetic CORD-v2-like parquet for pure-function tests
# ---------------------------------------------------------------------------


def _write_synthetic_parquet(
    parquet_path: Path, ground_truths: list[str], image_bytes: list[bytes]
) -> None:
    """Write a CORD-v2-shaped parquet to disk. `image` is a struct of
    {bytes: binary, path: string} and `ground_truth` is a string column."""
    image_struct = pa.array(
        [{"bytes": b, "path": None} for b in image_bytes],
        type=pa.struct([("bytes", pa.binary()), ("path", pa.string())]),
    )
    table = pa.table(
        {"image": image_struct, "ground_truth": pa.array(ground_truths, type=pa.string())}
    )
    pq.write_table(table, parquet_path)


def _make_gt(
    menu_items: int = 1,
    has_total: bool = True,
    has_sub_total: bool = False,
    total_price: str | None = "5000",
) -> str:
    """Build a CORD-v2-shaped ground_truth JSON string for tests."""
    if menu_items == 0:
        menu_block: object = None
    elif menu_items == 1:
        menu_block = {"nm": "Item A", "cnt": "1", "price": "1000"}
    else:
        menu_block = [{"nm": f"Item {i}", "cnt": "1", "price": "1000"} for i in range(menu_items)]
    gt_parse: dict[str, object] = {}
    if menu_block is not None:
        gt_parse["menu"] = menu_block
    if has_sub_total:
        gt_parse["sub_total"] = {"subtotal_price": "5000"}
    if has_total:
        if total_price is not None:
            gt_parse["total"] = {"total_price": total_price}
        else:
            gt_parse["total"] = {}
    return json.dumps({"gt_parse": gt_parse})


# ---------------------------------------------------------------------------
# Pure-function tests (no corpus required)
# ---------------------------------------------------------------------------


def test_walk_raises_on_missing_data_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="data directory not found"):
        walk(tmp_path)


def test_walk_raises_on_empty_data_dir(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    with pytest.raises(RuntimeError, match="No parquet files"):
        walk(tmp_path)


def test_walk_infers_split_from_filename(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(data / "train-00000-of-00001-x.parquet", [_make_gt()], [b"\x89PNG"])
    _write_synthetic_parquet(
        data / "validation-00000-of-00001-y.parquet", [_make_gt()], [b"\x89PNG"]
    )
    _write_synthetic_parquet(data / "test-00000-of-00001-z.parquet", [_make_gt()], [b"\x89PNG"])
    df = walk(tmp_path)
    assert len(df) == 3
    assert set(df["split"]) == {"train", "validation", "test"}
    # Each synthetic parquet has 1 row.
    assert (df["n_rows"] == 1).all()


def test_parse_ground_truth_round_trip() -> None:
    gt_str = _make_gt(menu_items=3, has_total=True, has_sub_total=True)
    parsed = parse_ground_truth(gt_str)
    assert "gt_parse" in parsed
    inner = parsed["gt_parse"]
    assert isinstance(inner["menu"], list)
    assert len(inner["menu"]) == 3
    assert inner["sub_total"]["subtotal_price"] == "5000"
    assert inner["total"]["total_price"] == "5000"


def test_load_examples_derives_features_single_menu(tmp_path: Path) -> None:
    """A receipt with `menu` as a single dict (1 item) — both list-and-dict
    conventions appear in CORD-v2 per the Donut paper's schema."""
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(
        data / "test-00000-of-00001-x.parquet",
        [_make_gt(menu_items=1, has_total=True, total_price="1000")],
        [b"\x89PNG"],
    )
    df = load_examples(tmp_path, split="test")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["split"] == "test"
    assert row["n_menu_items"] == 1
    assert row["total_price"] == "1000"
    assert "menu" in row["gt_top_level_keys"]
    assert "total" in row["gt_top_level_keys"]


def test_load_examples_derives_features_multi_menu(tmp_path: Path) -> None:
    """A receipt with `menu` as a list — typical multi-item receipt."""
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(
        data / "test-00000-of-00001-x.parquet",
        [_make_gt(menu_items=5, has_total=True, has_sub_total=True, total_price="9999")],
        [b"\x89PNG"],
    )
    df = load_examples(tmp_path, split="test")
    row = df.iloc[0]
    assert row["n_menu_items"] == 5
    assert row["total_price"] == "9999"
    assert {"menu", "sub_total", "total"} <= row["gt_top_level_keys"]


def test_load_examples_handles_missing_total(tmp_path: Path) -> None:
    """If `total` is absent or has no `total_price`, the extracted value is None."""
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(
        data / "test-00000-of-00001-x.parquet",
        [
            _make_gt(menu_items=1, has_total=False),
            _make_gt(menu_items=1, has_total=True, total_price=None),
        ],
        [b"\x89PNG", b"\x89PNG"],
    )
    df = load_examples(tmp_path, split="test")
    assert df.iloc[0]["total_price"] is None
    assert df.iloc[1]["total_price"] is None


def test_load_examples_drop_image_bytes_default(tmp_path: Path) -> None:
    """Default drop_image_bytes=True omits the `image_bytes` column."""
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(
        data / "test-00000-of-00001-x.parquet", [_make_gt()], [b"\x89PNG\x00\x00\x00"]
    )
    df = load_examples(tmp_path, split="test")
    assert "image_bytes" not in df.columns
    assert "image_bytes_len" not in df.columns


def test_load_examples_drop_image_bytes_false(tmp_path: Path) -> None:
    """Setting drop_image_bytes=False includes image bytes + length."""
    data = tmp_path / "data"
    data.mkdir()
    sample_bytes = b"\x89PNG\x00\x00\x00\x00\x00"
    _write_synthetic_parquet(data / "test-00000-of-00001-x.parquet", [_make_gt()], [sample_bytes])
    df = load_examples(tmp_path, split="test", drop_image_bytes=False)
    assert df.iloc[0]["image_bytes"] == sample_bytes
    assert df.iloc[0]["image_bytes_len"] == len(sample_bytes)


def test_load_examples_raises_on_no_matching_split(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(data / "train-00000-of-00001-x.parquet", [_make_gt()], [b"\x89PNG"])
    with pytest.raises(FileNotFoundError, match="matching split"):
        load_examples(tmp_path, split="test")


def test_load_one_image_bytes_returns_bytes(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    sample_bytes = b"\x89PNG\x01\x02\x03"
    _write_synthetic_parquet(data / "test-00000-of-00001-x.parquet", [_make_gt()], [sample_bytes])
    img = load_one_image_bytes(tmp_path, split="test", row_index=0)
    assert img == sample_bytes


def test_load_one_image_bytes_out_of_range(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _write_synthetic_parquet(data / "test-00000-of-00001-x.parquet", [_make_gt()], [b"\x89PNG"])
    img = load_one_image_bytes(tmp_path, split="test", row_index=99)
    assert img is None


# ---------------------------------------------------------------------------
# Corpus-aware tests (require CORD-v2 parquets on disk; ~2.3 GB total)
# ---------------------------------------------------------------------------


@skip_if_no_cord_corpus
def test_walk_real_corpus_total_rows() -> None:
    """Per the HF dataset card + dataset_infos.json:
    800 train + 100 validation + 100 test = 1000 receipts.
    """
    df = walk(CORD_CORPUS)
    assert int(df["n_rows"].sum()) == 1000
    by_split = df.groupby("split")["n_rows"].sum()
    assert int(by_split["train"]) == 800
    assert int(by_split["validation"]) == 100
    assert int(by_split["test"]) == 100


@skip_if_no_cord_corpus
def test_walk_real_corpus_file_count() -> None:
    """6 parquets: 4 train shards + 1 validation + 1 test."""
    df = walk(CORD_CORPUS)
    assert len(df) == 6
    by_split = df.groupby("split").size()
    assert int(by_split["train"]) == 4
    assert int(by_split["validation"]) == 1
    assert int(by_split["test"]) == 1


@skip_if_no_cord_corpus
def test_load_examples_real_corpus_test_split_structure() -> None:
    """Empirical: test split is 100 receipts; every receipt has `menu` + `total`."""
    df = load_examples(CORD_CORPUS, split="test")
    assert len(df) == 100
    # Every test receipt has `menu` + `total`.
    has_menu = df["gt_top_level_keys"].apply(lambda ks: "menu" in ks)
    has_total = df["gt_top_level_keys"].apply(lambda ks: "total" in ks)
    assert bool(has_menu.all())
    assert bool(has_total.all())
    # At least 90% have an extractable total_price (allowing for malformed
    # rows; empirical observation is 95/100).
    assert int(df["total_price"].notna().sum()) >= 90
