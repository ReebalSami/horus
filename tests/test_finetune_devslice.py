"""Tests for the ADR-067 checkpoint-selection apparatus: dev carve, LR schedule, checkpoints.

Three pieces, all pure-logic (no model, no corpus):

* `carve_dev` — the dev slice that lets an epoch be CHOSEN without spending a look at the
  sealed validation set. Its invariants are the methodological ones: disjoint from the fit
  side, a strict subset of what it was given, deterministic, and never starving a stratum.
* `build_lr_schedule` — cosine + warmup. Pinned because a silently-constant LR would look
  identical in every log line the trainer prints.
* `checkpoint_path` / `materialize_checkpoint` — mlx_vlm writes per-epoch checkpoints as
  sibling files that `apply_lora_layers` cannot load; these make them loadable.

Synthetic `InvoiceRecord`s mirror `test_finetune_split.py`: the carve only reads `.stem`
and `.subdir`, never the ground-truth contents.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from horus.eval.ground_truth import GroundTruth
from horus.finetune.dataset import InvoiceRecord
from horus.finetune.split import carve_dev
from horus.finetune.train import build_lr_schedule, checkpoint_path, materialize_checkpoint

# `mlx` is Apple-Silicon-only and platform-gated in pyproject.toml so `uv sync` works on the
# rented CUDA box (ADR-068), which means it is absent on CI's ubuntu-latest. Only the cosine
# branch of `build_lr_schedule` reaches `mlx.optimizers`; `constant` returns a bare float and
# is asserted unguarded below, which is what keeps that path honest on Linux.
requires_mlx = pytest.mark.skipif(
    importlib.util.find_spec("mlx") is None,
    reason="Requires `mlx` (Apple-Silicon only, platform-gated per ADR-007/ADR-068).",
)


def _rec(stem: str, subdir: str) -> InvoiceRecord:
    return InvoiceRecord(
        pdf_path=Path(f"{stem}.pdf"),
        stem=stem,
        subdir=subdir,
        gt=GroundTruth(header={}),
        gt_error=None,
        transcript_path=Path(f"{stem}.txt"),
    )


def _train_records(per_stratum: int = 10) -> list[InvoiceRecord]:
    return [
        _rec(f"{subdir}__{profile}__{i:02d}", subdir)
        for subdir in ("XML-Rechnung", "ZUGFeRDv2")
        for profile in ("EN16931", "BASIC")
        for i in range(per_stratum)
    ]


# --------------------------------------------------------------------------- carve_dev


def test_dev_and_fit_are_disjoint_and_cover_the_input() -> None:
    records = _train_records()
    slice_ = carve_dev(records, dev_fraction=0.2, seed=7)
    fit, dev = set(slice_.train), set(slice_.dev)

    assert fit.isdisjoint(dev)
    assert fit | dev == {r.stem for r in records}


def test_carve_is_deterministic_for_a_fixed_seed() -> None:
    records = _train_records()
    a = carve_dev(records, dev_fraction=0.2, seed=7)
    b = carve_dev(records, dev_fraction=0.2, seed=7)
    assert a.dev == b.dev
    assert a.sha256_dev == b.sha256_dev


def test_different_seeds_carve_different_slices() -> None:
    records = _train_records()
    assert carve_dev(records, seed=1).dev != carve_dev(records, seed=2).dev


def test_carve_stratifies_every_segment() -> None:
    """round(10 x 0.2) = 2 to dev in EACH of the 4 strata — no segment over-represented."""
    slice_ = carve_dev(_train_records(per_stratum=10), dev_fraction=0.2, seed=7)
    assert len(slice_.strata) == 4
    for counts in slice_.strata.values():
        assert counts == {"train": 8, "dev": 2}


def test_a_stratum_is_never_emptied_into_dev() -> None:
    """A 2-member stratum at a high fraction must still leave one record to train on."""
    records = [_rec("XML-Rechnung__EN16931__00", "XML-Rechnung")] + [
        _rec(f"ZUGFeRDv2__BASIC__{i:02d}", "ZUGFeRDv2") for i in range(2)
    ]
    slice_ = carve_dev(records, dev_fraction=0.9, seed=7)
    for stratum, counts in slice_.strata.items():
        assert counts["train"] >= 1, f"{stratum} was emptied into dev"


def test_rejects_out_of_range_fraction() -> None:
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="dev_fraction"):
            carve_dev(_train_records(), dev_fraction=bad)


def test_rejects_a_fraction_that_yields_no_dev_records() -> None:
    """Silently training with an empty dev slice would leave nothing to select on."""
    with pytest.raises(ValueError, match="empty dev slice"):
        carve_dev([_rec("only__EN16931__00", "XML-Rechnung")], dev_fraction=0.15)


# -------------------------------------------------------------------- build_lr_schedule


def test_constant_schedule_returns_the_bare_rate() -> None:
    assert build_lr_schedule(
        learning_rate=1e-4, iters=100, schedule="constant", warmup_ratio=0.03, min_ratio=0.1
    ) == pytest.approx(1e-4)


@requires_mlx
def test_cosine_schedule_warms_up_then_decays() -> None:
    lr, iters = 1e-4, 600
    sched = build_lr_schedule(
        learning_rate=lr, iters=iters, schedule="cosine", warmup_ratio=0.05, min_ratio=0.1
    )
    warmup_steps = round(iters * 0.05)

    start = float(sched(0))
    peak = float(sched(warmup_steps))
    end = float(sched(iters))

    assert start < peak, "warmup must ramp up from near zero"
    assert start <= lr * 0.1, f"first step should be near zero, got {start}"
    assert peak == pytest.approx(lr, rel=0.05), "should reach the configured rate after warmup"
    assert end < peak, "cosine tail must decay below the peak"
    assert end == pytest.approx(lr * 0.1, rel=0.25), "should land near the configured floor"


@requires_mlx
def test_cosine_schedule_survives_a_tiny_run() -> None:
    """A smoke run has single-digit iters; warmup/decay windows must not collapse to zero."""
    sched = build_lr_schedule(
        learning_rate=1e-4, iters=2, schedule="cosine", warmup_ratio=0.03, min_ratio=0.1
    )
    assert float(sched(0)) >= 0.0
    assert float(sched(2)) >= 0.0


# ------------------------------------------------------------------ checkpoint plumbing


def test_checkpoint_path_matches_the_mlx_vlm_naming() -> None:
    assert checkpoint_path("/tmp/a", 117).name == "0000117_adapters.safetensors"


def test_materialize_lays_out_a_loadable_adapter_dir(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "0000117_adapters.safetensors").write_bytes(b"epoch-1-weights")
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"rank": 8}), encoding="utf-8")

    dest = materialize_checkpoint(adapter_dir, 117, tmp_path / "epoch1")

    # apply_lora_layers reads exactly these two names.
    assert (dest / "adapters.safetensors").read_bytes() == b"epoch-1-weights"
    assert json.loads((dest / "adapter_config.json").read_text())["rank"] == 8
    # Copy, never move: the original must survive for the other epochs.
    assert (adapter_dir / "0000117_adapters.safetensors").exists()


def test_materialize_names_the_available_checkpoints_when_one_is_missing(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "0000117_adapters.safetensors").write_bytes(b"x")
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="0000117_adapters.safetensors"):
        materialize_checkpoint(adapter_dir, 999, tmp_path / "out")


def test_materialize_refuses_without_the_shared_config(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "0000117_adapters.safetensors").write_bytes(b"x")

    with pytest.raises(FileNotFoundError, match="adapter_config.json"):
        materialize_checkpoint(adapter_dir, 117, tmp_path / "out")
