"""Train/validation split sealing for the structurer fine-tune (issue #55, no-HARKing).

The split is **sealed before any fine-tuning**: trainable invoices (those with both an answer
key and a reader transcript) are assigned deterministically — seeded, stratified by
``subdir × profile`` so every corpus segment is represented on both sides — and written to
``data/finetune/split.json`` (committed via ``git add -f`` since ``data/*`` is gitignored).

The committed file, with its per-side SHA-256 fingerprint, is the methodological guarantee that
the validation set was fixed *before* any zero-shot-vs-fine-tuned result was seen. Re-sealing
with the same seed + corpus state is idempotent.

Refs: ADR-034 §"no-HARKing" (held-out discipline); plan
``~/.windsurf/plans/horus-finetune-structurer-55a1c3.md``.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from horus.finetune.dataset import InvoiceRecord

__all__ = ["DevSlice", "Split", "carve_dev", "load_split", "seal_split", "write_split"]

DEFAULT_SPLIT_PATH = Path("data/finetune/split.json")
_DEFAULT_VAL_FRACTION = 0.2
_DEFAULT_SEED = 42
# Distinct from _DEFAULT_SEED so the dev carve is independent of the original
# train/val shuffle rather than replaying the same permutation one level down.
_DEFAULT_DEV_SEED = 4242
_DEFAULT_DEV_FRACTION = 0.15

# Profile keywords probed in order; first hit wins. "BASICWL" before "BASIC" so the
# without-lines variant isn't swallowed by the "BASIC" prefix.
_PROFILE_TAGS = (
    "EN16931",
    "XRECHNUNG",
    "EXTENDED",
    "BASICWL",
    "BASIC",
    "MINIMUM",
    "COMFORT",
)


def _profile(stem: str) -> str:
    upper = stem.upper()
    for tag in _PROFILE_TAGS:
        if tag in upper:
            return tag
    return "OTHER"


def _stratum(rec: InvoiceRecord) -> str:
    """Stratification key: ``<subdir>/<profile>`` (e.g., ``ZUGFeRDv2/EN16931``)."""
    return f"{rec.subdir}/{_profile(rec.stem)}"


def _sha256_of_stems(stems: list[str]) -> str:
    """Stable fingerprint of a stem set: SHA-256 of the sorted, newline-joined stems."""
    joined = "\n".join(sorted(stems))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Split:
    """A sealed train/validation partition over trainable invoice stems."""

    seed: int
    val_fraction: float
    train: list[str]
    val: list[str]
    strata: dict[str, dict[str, int]]

    @property
    def sha256_train(self) -> str:
        return _sha256_of_stems(self.train)

    @property
    def sha256_val(self) -> str:
        return _sha256_of_stems(self.val)

    @property
    def sha256_all(self) -> str:
        return _sha256_of_stems(self.train + self.val)

    def to_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "val_fraction": self.val_fraction,
            "n_total": len(self.train) + len(self.val),
            "n_train": len(self.train),
            "n_val": len(self.val),
            "sha256_all": self.sha256_all,
            "sha256_train": self.sha256_train,
            "sha256_val": self.sha256_val,
            "strata": self.strata,
            "train": sorted(self.train),
            "val": sorted(self.val),
        }


@dataclass(frozen=True)
class DevSlice:
    """A development slice carved out of the sealed TRAIN side.

    Exists so a checkpoint can be chosen without looking at the sealed validation set.
    Selecting an epoch on ``Split.val`` and then reporting ``Split.val`` as the headline
    would be HARKing: the number would be the best of N looks, not one honest look.

    This is a *derivation*, not a re-seal. ``split.json`` is never rewritten, so its
    ``sha256_train`` / ``sha256_val`` fingerprints keep verifying and the original sealing
    guarantee is undisturbed. ``dev`` ⊂ ``Split.train``, and ``Split.val`` is untouched.
    """

    seed: int
    dev_fraction: float
    train: list[str]
    dev: list[str]
    strata: dict[str, dict[str, int]]

    @property
    def sha256_train(self) -> str:
        return _sha256_of_stems(self.train)

    @property
    def sha256_dev(self) -> str:
        return _sha256_of_stems(self.dev)

    def to_dict(self) -> dict[str, object]:
        return {
            "dev_seed": self.seed,
            "dev_fraction": self.dev_fraction,
            "n_train": len(self.train),
            "n_dev": len(self.dev),
            "sha256_train_after_carve": self.sha256_train,
            "sha256_dev": self.sha256_dev,
            "strata": self.strata,
            "train": sorted(self.train),
            "dev": sorted(self.dev),
        }


def carve_dev(
    train_records: list[InvoiceRecord],
    *,
    dev_fraction: float = _DEFAULT_DEV_FRACTION,
    seed: int = _DEFAULT_DEV_SEED,
) -> DevSlice:
    """Split already-sealed TRAIN records into (smaller train, dev), stratified and seeded.

    Same stratified-shuffle procedure as `seal_split`, one level down, so both carves have
    identical behaviour and neither can silently over-represent a corpus segment.

    Pass only records whose stems are in ``Split.train``. Passing validation records would
    defeat the entire point, so the caller is responsible for that — `run_finetune` derives
    them from `build_split_records`, which reads the two sides separately.
    """
    if not 0.0 < dev_fraction < 1.0:
        raise ValueError(f"dev_fraction must be in (0, 1), got {dev_fraction}")

    by_stratum: dict[str, list[InvoiceRecord]] = defaultdict(list)
    for rec in sorted(train_records, key=lambda r: r.stem):
        by_stratum[_stratum(rec)].append(rec)

    rng = random.Random(seed)
    train: list[str] = []
    dev: list[str] = []
    strata: dict[str, dict[str, int]] = {}
    for stratum in sorted(by_stratum):
        members = sorted(by_stratum[stratum], key=lambda r: r.stem)
        rng.shuffle(members)
        n_dev = round(len(members) * dev_fraction)
        # Never empty a stratum's training side to fill dev: a stratum of 1 keeps its
        # single member in train (round(1 * 0.15) == 0 already, but a larger fraction
        # or a 2-member stratum could otherwise take everything).
        n_dev = min(n_dev, len(members) - 1) if len(members) > 1 else 0
        dev_members = members[:n_dev]
        train_members = members[n_dev:]
        dev.extend(r.stem for r in dev_members)
        train.extend(r.stem for r in train_members)
        strata[stratum] = {"train": len(train_members), "dev": len(dev_members)}

    if not dev:
        raise ValueError(
            f"dev_fraction={dev_fraction} produced an empty dev slice over "
            f"{len(train_records)} records — raise it or shrink the stratification"
        )
    return DevSlice(
        seed=seed,
        dev_fraction=dev_fraction,
        train=sorted(train),
        dev=sorted(dev),
        strata=strata,
    )


def seal_split(
    records: list[InvoiceRecord],
    *,
    val_fraction: float = _DEFAULT_VAL_FRACTION,
    seed: int = _DEFAULT_SEED,
) -> Split:
    """Deterministically partition trainable records into train/val, stratified by stratum.

    Only ``ready`` records (answer key + transcript) participate. Within each stratum the
    members are shuffled with a fixed seed and the first ``round(val_fraction · n)`` go to
    validation; the remainder to train. Stems are sorted in the result for a stable fingerprint.
    """
    trainable = sorted((r for r in records if r.ready), key=lambda r: r.stem)
    by_stratum: dict[str, list[InvoiceRecord]] = defaultdict(list)
    for rec in trainable:
        by_stratum[_stratum(rec)].append(rec)

    rng = random.Random(seed)
    train: list[str] = []
    val: list[str] = []
    strata: dict[str, dict[str, int]] = {}
    for stratum in sorted(by_stratum):
        members = sorted(by_stratum[stratum], key=lambda r: r.stem)
        rng.shuffle(members)
        n_val = round(len(members) * val_fraction)
        val_members = members[:n_val]
        train_members = members[n_val:]
        val.extend(r.stem for r in val_members)
        train.extend(r.stem for r in train_members)
        strata[stratum] = {"train": len(train_members), "val": len(val_members)}

    return Split(
        seed=seed,
        val_fraction=val_fraction,
        train=sorted(train),
        val=sorted(val),
        strata=strata,
    )


def write_split(split: Split, path: Path = DEFAULT_SPLIT_PATH) -> Path:
    """Serialize the sealed split to ``path`` (creating parent dirs). Returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(split.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def load_split(path: Path = DEFAULT_SPLIT_PATH) -> Split:
    """Load a sealed split, verifying the per-side SHA-256 fingerprints still hold."""
    data = json.loads(path.read_text(encoding="utf-8"))
    split = Split(
        seed=int(data["seed"]),
        val_fraction=float(data["val_fraction"]),
        train=list(data["train"]),
        val=list(data["val"]),
        strata=dict(data["strata"]),
    )
    if split.sha256_train != data["sha256_train"] or split.sha256_val != data["sha256_val"]:
        raise ValueError(
            f"split fingerprint mismatch at {path}: the stem lists were edited after sealing "
            f"(train {split.sha256_train[:12]} vs {data['sha256_train'][:12]}, "
            f"val {split.sha256_val[:12]} vs {data['sha256_val'][:12]})"
        )
    return split
