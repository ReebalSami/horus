"""Attribute held-out misses to the reader or the structurer (ADR-054 gate evidence).

The question this answers: **is a structurer fine-tune the right lever on the held-out
set?** A fine-tune can only recover a field the reader actually transcribed. A field the
reader never put in the transcript can be "extracted" only by hallucination, so handing
that loss to a LoRA run credits the fine-tune with a reading fix it cannot perform — the
generalized form of the ADR-048 / ADR-058 rule that a prompt-fixable gap must never be
handed to a fine-tune.

So every missed cell (`FN`) is cross-tabulated against transcript answerability:

- **reader-capped** — the GT value is not findable in the reader transcript. No structurer
  change recovers it. Fixing this means a better reader, not a fine-tune.
- **structurer-recoverable** — the value IS in the transcript and the structurer still
  missed it. This is the only population a LoRA run can address, and therefore the real
  ceiling on what fine-tuning can buy.

Answerability containment is a heuristic LOWER bound (see `answerability` module): a value
the reader reformatted beyond the variant set counts as not-findable even though the
structurer might still map it. That biases the split *toward* "reader-capped", so a large
structurer-recoverable count is trustworthy while a small one is a soft signal.

    uv run python scripts/heldout_attribution.py --outputs <saved-generations-dir>

Privacy (ADR-040): prints ids, field names and counts only. Never a field value.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from horus.config import EvalConfig  # noqa: E402
from horus.eval import structurer  # noqa: E402
from horus.eval.scorer import score  # noqa: E402
from horus.finetune.answerability import score_answerability  # noqa: E402
from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_HELDOUT_CORPUS_ROOT,
    build_heldout_records,
)

DEFAULT_STRUCTURER = "google/gemma-4-E4B-it"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", required=True, help="Saved-generations dir.")
    parser.add_argument("--corpus", default=str(DEFAULT_HELDOUT_CORPUS_ROOT))
    parser.add_argument("--structurer", default=DEFAULT_STRUCTURER)
    args = parser.parse_args(argv[1:])

    outputs = Path(args.outputs)
    if not outputs.is_dir():
        parser.error(f"saved-outputs dir not found: {outputs}")

    records = [rec for rec in build_heldout_records(Path(args.corpus)) if rec.ready]
    if not records:
        parser.error(f"no ready held-out records under {args.corpus}")

    cfg = EvalConfig()
    reader_capped: Counter[str] = Counter()
    recoverable: Counter[str] = Counter()
    per_group: dict[str, Counter[str]] = {}
    n_answerable = n_present_total = 0
    skipped: list[str] = []

    for rec in records:
        generation = outputs / f"{rec.stem}.txt"
        answerability = score_answerability(rec)
        if not generation.is_file() or answerability is None or rec.gt is None:
            skipped.append(rec.stem)
            continue
        n_present_total += answerability.n_present
        n_answerable += answerability.n_found
        unreadable = set(answerability.missing_fields)

        predicted = structurer.to_predicted_dict(
            generation.read_text(encoding="utf-8"), args.structurer
        )
        scores = score(
            predicted,
            rec.gt,
            cfg=cfg,
            invoice_id=rec.stem,
            model_id=args.structurer,
            predicted_groups=None,
        )
        bucket = per_group.setdefault(rec.subdir, Counter())
        for field_key, result in scores.per_field.items():
            if result.outcome != "FN":
                continue
            if field_key in unreadable:
                reader_capped[field_key] += 1
                bucket["reader_capped"] += 1
            else:
                recoverable[field_key] += 1
                bucket["structurer_recoverable"] += 1

    n_capped, n_recoverable = sum(reader_capped.values()), sum(recoverable.values())
    total = n_capped + n_recoverable

    print(f"\nHeld-out miss attribution — {len(records) - len(skipped)} invoices\n")
    print(f"  reader answerability : {n_answerable}/{n_present_total} GT-present cells findable")
    print(f"                         ({n_answerable / n_present_total:.4f}) = the recall ceiling")
    print(f"\n  missed cells (FN)    : {total}")
    if total:
        print(
            f"    reader-capped         {n_capped:4d} ({n_capped / total:.1%}) — not fine-tunable"
        )
        print(
            f"    structurer-recoverable{n_recoverable:4d} ({n_recoverable / total:.1%}) "
            "— the LoRA target"
        )

    print("\n  by group:")
    for name, counts in sorted(per_group.items()):
        capped, rec_n = counts["reader_capped"], counts["structurer_recoverable"]
        print(f"    {name:28s} reader-capped={capped:4d}  structurer-recoverable={rec_n:4d}")

    for title, counter in (
        ("reader-capped (better reader, not a fine-tune)", reader_capped),
        ("structurer-recoverable (a fine-tune could reach these)", recoverable),
    ):
        print(f"\n  top fields — {title}:")
        for field_key, count in counter.most_common(8):
            print(f"    {count:4d}  {field_key}")

    if skipped:
        print(f"\n  WARN: skipped {len(skipped)} (no generation or no transcript): {skipped}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
