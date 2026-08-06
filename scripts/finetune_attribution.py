"""Attribution audit: decompose the val F1 loss into reader / structurer / eval-definition.

    uv run python scripts/finetune_attribution.py
    uv run python scripts/finetune_attribution.py --outputs data/finetune/zeroshot-outputs \
        --oracle-report data/finetune/eval-oracle-val.json

Answers the pre-GPU gate question (issue #55 follow-up): is the sub-0.90 zero-shot F1
caused by (a) the reader failing to transcribe values, (b) the structurer failing to map
transcribed values, or (c) the recently-expanded schema (ADR-041 payment-instruction flats
+ ADR-042 repeating groups) dragging the average?

Method — offline, over SAVED structurer generations (no VLM inference):

1. Re-score each saved generation with the canonical scorer (must reproduce the baseline
   report's mean; printed as a determinism cross-check).
2. Classify every signal-bearing outcome (TP/FP/FN) into a cluster:
   ``legacy-16`` (pre-ADR-035 fields) / ``new-flat`` (ADR-035/041 additions) /
   ``group:<name>`` (ADR-042 repeating-group cells).
3. Split every FN by transcript readability (the bake-off's `value_variants` containment):
   *readable-but-missed* = structurer/eval fault; *unreadable* = reader fault.
4. Print the verdict table + write ``data/finetune/attribution-val.json``.

The same split is also reported **per flat field**, which is what makes it usable
alongside `scripts/classify_field_gaps.py`. That script classifies a field by comparing
the reader arm against the perfect-text (oracle) arm, and a field at ceiling on perfect
text is called a reading gap. That inference has one blind spot: the oracle page prints
the registry's own ``printed_label``, while the reader emits whatever wording it read off
the page. When those differ, "at ceiling on the oracle page" does not by itself prove the
prompt copes with the READER's wording. The per-field readable-vs-unreadable FN split
closes it directly: a reader FN whose value IS present in the transcript was available and
not mapped (a prompt/mapping suspect), while a reader FN whose value is ABSENT could not
have been extracted by any prompt.

Refs: ADR-035/037 (legacy field set), ADR-041/042 (schema expansion), ADR-038 (Arm-B),
ADR-064 (the prompt-vs-reader ordering rule this evidence serves).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.config import EvalConfig  # noqa: E402
from horus.eval import structurer  # noqa: E402
from horus.eval.ground_truth import FIELDS, LEGACY_EXPERIMENT_FIELDS  # noqa: E402
from horus.eval.scorer import FieldResult, f1_from_counts, score  # noqa: E402
from horus.finetune.answerability import _canon, value_variants  # noqa: E402
from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.dataset import (  # noqa: E402
    InvoiceRecord,
    build_records,
    reader_text_from_transcript,
)
from horus.finetune.split import load_split  # noqa: E402

_LEGACY_KEYS = frozenset(LEGACY_EXPERIMENT_FIELDS)
_NEW_FLAT_KEYS = frozenset(k for k in FIELDS if k not in _LEGACY_KEYS)


@dataclass
class ClusterTally:
    """Pooled outcome mass for one field cluster across the split."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    fn_readable: int = 0  # value WAS in the transcript — structurer/eval fault
    fn_unreadable: int = 0  # value NOT in the transcript — reader fault
    per_invoice_f1: list[float] = field(default_factory=list)

    @property
    def f1(self) -> float:
        return f1_from_counts(self.tp, self.fp, self.fn)[2]

    @property
    def mean_invoice_f1(self) -> float:
        return sum(self.per_invoice_f1) / len(self.per_invoice_f1) if self.per_invoice_f1 else 0.0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "fn_readable": self.fn_readable,
            "fn_unreadable": self.fn_unreadable,
            "pooled_f1": round(self.f1, 4),
            "mean_invoice_f1": round(self.mean_invoice_f1, 4),
            "n_invoices": len(self.per_invoice_f1),
        }


def _cluster_of_flat(english_key: str) -> str:
    return "legacy-16" if english_key in _LEGACY_KEYS else "new-flat"


def _fn_readable(fr: FieldResult, raw_value: str | None, transcript_canon: str) -> bool:
    """Was this FN's GT value literally findable in the reader transcript?"""
    return any(v in transcript_canon for v in value_variants(raw_value, fr.gt_normalized))


def _tally_outcome(
    tally: ClusterTally, fr: FieldResult, raw_value: str | None, transcript_canon: str
) -> None:
    if fr.outcome == "TP":
        tally.tp += 1
    elif fr.outcome == "FP":
        tally.fp += 1
    elif fr.outcome == "FN":
        tally.fn += 1
        if _fn_readable(fr, raw_value, transcript_canon):
            tally.fn_readable += 1
        else:
            tally.fn_unreadable += 1


def audit_invoice(
    rec: InvoiceRecord,
    raw_generation: str,
    *,
    structurer_model: str,
    cfg: EvalConfig,
    tallies: dict[str, ClusterTally],
    field_tallies: dict[str, ClusterTally] | None = None,
) -> float:
    """Score one saved generation, classify its outcome mass, return overall F1.

    ``field_tallies``, when given, receives the SAME outcome mass keyed by flat field
    name instead of by cluster. It reuses `ClusterTally` for its tp/fp/fn + FN-readability
    counters; its ``per_invoice_f1`` list stays empty because a single field on a single
    invoice has no meaningful per-invoice F1 (one outcome would score 0.0 or 1.0 and the
    mean of those is not interpretable).
    """
    assert rec.gt is not None and rec.transcript_path is not None
    transcript_canon = _canon(reader_text_from_transcript(rec.transcript_path))

    predicted = structurer.to_predicted_dict(raw_generation, structurer_model)
    predicted_groups = structurer.to_predicted_groups(raw_generation)
    scores = score(
        predicted,
        rec.gt,
        cfg=cfg,
        invoice_id=rec.stem,
        model_id=structurer_model,
        predicted_groups=predicted_groups,
    )

    # Flat fields — raw GT value is available for readability variants.
    per_invoice_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for key, fr in scores.per_field.items():
        cluster = _cluster_of_flat(key)
        raw_value = rec.gt.header[key].raw_value
        _tally_outcome(tallies[cluster], fr, raw_value, transcript_canon)
        if field_tallies is not None:
            _tally_outcome(field_tallies[key], fr, raw_value, transcript_canon)
        if fr.outcome in ("TP", "FP", "FN"):
            idx = ("TP", "FP", "FN").index(fr.outcome)
            per_invoice_counts[cluster][idx] += 1

    # Repeating-group cells — FieldResult carries gt_normalized only.
    for group_key, grp in scores.repeating.items():
        cluster = f"group:{group_key}"
        for fr in grp.cell_results:
            _tally_outcome(tallies[cluster], fr, None, transcript_canon)
            if fr.outcome in ("TP", "FP", "FN"):
                idx = ("TP", "FP", "FN").index(fr.outcome)
                per_invoice_counts[cluster][idx] += 1

    for cluster, (tp, fp, fn) in per_invoice_counts.items():
        if tp + fp + fn > 0:
            tallies[cluster].per_invoice_f1.append(f1_from_counts(tp, fp, fn)[2])

    return scores.overall_micro_f1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="finetune_attribution")
    parser.add_argument("--config", default="configs/finetune-structurer.yaml")
    parser.add_argument("--split", choices=["val", "train"], default="val")
    parser.add_argument(
        "--outputs",
        default="data/finetune/zeroshot-outputs",
        help="Dir of saved raw structurer generations (<stem>.txt) from "
        "finetune_evaluate --save-outputs.",
    )
    parser.add_argument(
        "--baseline-report",
        default="data/finetune/eval-zeroshot-val.json",
        help="Baseline eval report to reproduce (determinism cross-check).",
    )
    parser.add_argument(
        "--oracle-report",
        default="data/finetune/eval-oracle-val.json",
        help="Oracle-transcript eval report (structurer ceiling); skipped if absent.",
    )
    parser.add_argument("--out", default="data/finetune/attribution-val.json")
    args = parser.parse_args(argv[1:])

    cfg = FinetuneConfig.from_yaml(args.config)
    split = load_split(Path(cfg.split_path))
    stems = set(split.val if args.split == "val" else split.train)
    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    ready = sorted(
        (r for r in records if r.stem in stems and r.ready and r.gt is not None),
        key=lambda r: r.stem,
    )
    outputs_dir = Path(args.outputs)
    if not outputs_dir.is_dir():
        print(
            f"Outputs dir {outputs_dir} missing — run finetune_evaluate --save-outputs first.",
            file=sys.stderr,
        )
        return 1

    eval_cfg = EvalConfig()
    tallies: dict[str, ClusterTally] = defaultdict(ClusterTally)
    field_tallies: dict[str, ClusterTally] = defaultdict(ClusterTally)
    overall_f1s: list[float] = []
    missing: list[str] = []
    for rec in ready:
        out_path = outputs_dir / f"{rec.stem}.txt"
        if not out_path.is_file():
            missing.append(rec.stem)
            continue
        overall_f1s.append(
            audit_invoice(
                rec,
                out_path.read_text(encoding="utf-8"),
                structurer_model=cfg.structurer_model,
                cfg=eval_cfg,
                tallies=tallies,
                field_tallies=field_tallies,
            )
        )
    if missing:
        print(f"WARN: {len(missing)} stems without saved outputs: {missing}", file=sys.stderr)
    if not overall_f1s:
        print("No invoices scored — nothing to attribute.", file=sys.stderr)
        return 1

    reproduced_mean = sum(overall_f1s) / len(overall_f1s)

    # --- Determinism cross-check against the baseline report -----------------
    baseline_mean: float | None = None
    baseline_path = Path(args.baseline_report)
    if baseline_path.is_file():
        baseline_mean = json.loads(baseline_path.read_text(encoding="utf-8"))[
            "mean_overall_micro_f1"
        ]

    oracle_mean: float | None = None
    oracle_path = Path(args.oracle_report)
    if oracle_path.is_file():
        oracle_mean = json.loads(oracle_path.read_text(encoding="utf-8"))["mean_overall_micro_f1"]

    # --- Verdict table --------------------------------------------------------
    total_fn = sum(t.fn for t in tallies.values())
    total_fp = sum(t.fp for t in tallies.values())
    total_loss = total_fn + total_fp
    fn_reader = sum(t.fn_unreadable for t in tallies.values())
    fn_structurer = sum(t.fn_readable for t in tallies.values())

    print()
    print(f"## Attribution audit — {args.split} split ({len(overall_f1s)} invoices)")
    print()
    print(f"mean overall_micro_f1 (recomputed) : {reproduced_mean:.4f}")
    if baseline_mean is not None:
        print(f"mean overall_micro_f1 (report)     : {baseline_mean:.4f}  (cross-check)")
    if oracle_mean is not None:
        print(
            f"oracle-transcript ceiling          : {oracle_mean:.4f}  "
            "(structurer on perfect reading)"
        )
    print()
    print(
        "| cluster | pooled F1 | mean inv F1 | TP | FP | FN "
        "| FN readable (structurer) | FN unreadable (reader) |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for cluster in sorted(tallies):
        t = tallies[cluster]
        print(
            f"| {cluster} | {t.f1:.3f} | {t.mean_invoice_f1:.3f} | {t.tp} | {t.fp} | {t.fn} "
            f"| {t.fn_readable} | {t.fn_unreadable} |"
        )
    print()
    print("## Loss-mass shares (FN+FP pooled across clusters)")
    print(f"  total signal errors : {total_loss}  ({total_fn} FN + {total_fp} FP)")
    if total_loss:
        print(
            f"  reader-attributed   : {fn_reader}  ({100 * fn_reader / total_loss:.0f}% — "
            "GT value absent from transcript)"
        )
        print(
            f"  structurer/eval     : {fn_structurer + total_fp}  "
            f"({100 * (fn_structurer + total_fp) / total_loss:.0f}% — "
            "readable-but-missed FNs + hallucinated FPs)"
        )
    print()

    # Per-field FN readability. Ordered by readable-but-missed count, because that is the
    # column that can contradict a `classify_field_gaps` reading-gap verdict: the value was
    # in the transcript and the model still did not emit it.
    print("## Per-field FN readability (reader arm)")
    print("| field | TP | FP | FN | FN readable (available, not mapped) | FN unreadable |")
    print("|---|---|---|---|---|---|")
    for key in sorted(
        field_tallies,
        key=lambda k: (-field_tallies[k].fn_readable, -field_tallies[k].fn, k),
    ):
        t = field_tallies[key]
        if t.tp + t.fp + t.fn == 0:
            continue
        print(f"| {key} | {t.tp} | {t.fp} | {t.fn} | {t.fn_readable} | {t.fn_unreadable} |")
    print()

    artifact = {
        "split": args.split,
        "n_invoices": len(overall_f1s),
        "mean_overall_micro_f1_recomputed": round(reproduced_mean, 4),
        "mean_overall_micro_f1_report": baseline_mean,
        "oracle_mean_overall_micro_f1": oracle_mean,
        "clusters": {k: tallies[k].to_dict() for k in sorted(tallies)},
        "per_field": {k: field_tallies[k].to_dict() for k in sorted(field_tallies)},
        "loss_shares": {
            "total_signal_errors": total_loss,
            "fn_reader_unreadable": fn_reader,
            "fn_structurer_readable": fn_structurer,
            "fp_structurer": total_fp,
        },
        "missing_outputs": missing,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote artifact -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
