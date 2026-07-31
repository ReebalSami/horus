"""Tests for `horus.finetune.split` — the sealed, stratified train/val partition (issue #55).

Pure-logic (no corpus): synthetic `InvoiceRecord`s use an empty `GroundTruth(header={})` to
satisfy the `ready` predicate (the split only reads `.ready`, `.stem`, `.subdir` — never the GT
contents). This keeps the no-HARKing seal's invariants (determinism, disjointness, coverage,
fingerprint integrity) fast to verify.
"""

from __future__ import annotations

from pathlib import Path

from horus.eval.ground_truth import GroundTruth
from horus.finetune.dataset import InvoiceRecord
from horus.finetune.split import load_split, seal_split, write_split


def _rec(stem: str, subdir: str, *, ready: bool = True) -> InvoiceRecord:
    return InvoiceRecord(
        pdf_path=Path(f"{stem}.pdf"),
        stem=stem,
        subdir=subdir,
        gt=GroundTruth(header={}) if ready else None,
        gt_error=None if ready else "no attachment",
        transcript_path=Path(f"{stem}.txt") if ready else None,
    )


def _synthetic_corpus() -> list[InvoiceRecord]:
    """45 ready records across 9 strata (3 subdirs × 3 profiles × 5 each)."""
    records: list[InvoiceRecord] = []
    for subdir in ("XML-Rechnung", "ZUGFeRDv1", "ZUGFeRDv2"):
        for profile in ("EN16931", "BASIC", "MINIMUM"):
            for i in range(5):
                records.append(_rec(f"{subdir}__{profile}__{i:02d}", subdir))
    return records


def test_split_is_deterministic_for_a_fixed_seed() -> None:
    records = _synthetic_corpus()
    a = seal_split(records, seed=42)
    b = seal_split(records, seed=42)
    assert a.train == b.train
    assert a.val == b.val
    assert a.sha256_all == b.sha256_all


def test_split_is_disjoint_and_covers_all_ready_records() -> None:
    records = _synthetic_corpus()
    split = seal_split(records, val_fraction=0.2)
    train, val = set(split.train), set(split.val)

    assert train.isdisjoint(val)
    assert train | val == {r.stem for r in records}
    assert len(split.train) + len(split.val) == len(records)


def test_split_stratifies_every_segment() -> None:
    """round(5 × 0.2) = 1 to val, 4 to train, in EACH of the 9 strata."""
    split = seal_split(_synthetic_corpus(), val_fraction=0.2)
    assert len(split.strata) == 9
    for counts in split.strata.values():
        assert counts == {"train": 4, "val": 1}


def test_split_excludes_non_ready_records() -> None:
    records = [*_synthetic_corpus(), _rec("broken__no_gt", "unstructured", ready=False)]
    split = seal_split(records)
    assert "broken__no_gt" not in split.train
    assert "broken__no_gt" not in split.val


def test_write_then_load_roundtrips(tmp_path: Path) -> None:
    split = seal_split(_synthetic_corpus())
    path = write_split(split, tmp_path / "split.json")
    loaded = load_split(path)
    assert loaded.train == split.train
    assert loaded.val == split.val
    assert loaded.sha256_all == split.sha256_all


def test_load_detects_tampering(tmp_path: Path) -> None:
    """Editing a stem list after sealing must be caught by the fingerprint check."""
    import json

    split = seal_split(_synthetic_corpus())
    path = write_split(split, tmp_path / "split.json")
    data = json.loads(path.read_text())
    data["val"].append("XML-Rechnung__EN16931__00")  # smuggle a train stem into val
    path.write_text(json.dumps(data))

    try:
        load_split(path)
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("load_split did not detect the tampered stem list")
