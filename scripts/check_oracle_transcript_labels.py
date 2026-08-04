#!/usr/bin/env python3
"""Verify a field's label+value actually appear in the oracle transcript.

Diagnostic for ADR-058. When a field scores 0.000 on the *oracle* arm (perfect
GT-rendered text), there are only three possible causes:

1. the value is **absent from the input** — no reader could win it, so the field
   is mis-specified or the renderer drops it (a GT/renderer bug);
2. the value **is** in the input but the prompt never names its label — the model
   cannot map label→key, so it emits a structural zero (a prompt/glossary gap);
3. the value is in the input and named, but the normalizer rejects the model's
   representation (a scorer bug).

Cause 2 is fixable by prompt work alone and must NOT be handed to a LoRA (ADR-048's
lesson). This script separates (1) from (2): for each invoice whose GT has the
field present, it renders the oracle transcript and reports whether the German
label and the printed value are in it, plus what the model actually emitted.

    uv run python scripts/check_oracle_transcript_labels.py allowance_total_amount \
        --outputs data/finetune/oracle-outputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horus.eval.ground_truth import FIELDS  # noqa: E402
from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.dataset import (  # noqa: E402
    _oracle_print_form,
    build_records,
    render_oracle_transcript,
)
from horus.finetune.split import load_split  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("field", help="flat FIELDS key to inspect")
    parser.add_argument("--split", default="val", choices=("train", "val"))
    # See scripts/audit_field_prompts.py: a bare FinetuneConfig() selects the
    # SUPERSEDED granite-258M reader; ADR-057's canonical Qwen3-VL-4B lives in YAML.
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/finetune-structurer.yaml"),
        help="finetune config selecting the reader lineage",
    )
    parser.add_argument(
        "--outputs",
        type=Path,
        default=None,
        help="dir of saved raw generations, to report what the model emitted",
    )
    args = parser.parse_args()

    key = args.field
    if key not in FIELDS:
        raise SystemExit(f"unknown field {key!r}")
    spec = FIELDS[key]

    cfg = FinetuneConfig.from_yaml(args.config)
    split = load_split(Path(cfg.split_path))
    stems = set(getattr(split, args.split))
    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    subset = [r for r in records if r.stem in stems and r.ready and r.gt is not None]

    print(f"field   : {key}  ({spec.bt_code})")
    # `rendered_label` is what the transcript actually prints (printed_label when
    # measured, german_label otherwise). Checking german_label here would report a
    # FALSE absence for every ADR-059-corrected field.
    print(f"label   : {spec.rendered_label!r}  (canonical german_label={spec.german_label!r})")
    print(f"glossed : {spec.description is not None}   aliases={spec.prompt_aliases}")
    print()

    n_present = 0
    for rec in sorted(subset, key=lambda r: r.stem):
        assert rec.gt is not None
        gt_rec = rec.gt.header[key]
        if not gt_rec.is_present:
            continue
        n_present += 1

        printed = _oracle_print_form(gt_rec, spec)
        transcript = render_oracle_transcript(rec.gt)
        label_in = spec.rendered_label in transcript
        value_in = printed is not None and printed in transcript

        emitted = "<no saved output>"
        if args.outputs is not None:
            path = args.outputs / f"{rec.stem}.txt"
            if path.is_file():
                raw = path.read_text(encoding="utf-8")
                emitted = "<not in JSON>"
                for line in raw.splitlines():
                    if f'"{key}"' in line:
                        emitted = line.strip().rstrip(",")
                        break

        print(f"  {rec.stem}")
        print(f"     gt={gt_rec.normalized_value!r} printed_as={printed!r}")
        print(f"     label_in_transcript={label_in}  value_in_transcript={value_in}")
        print(f"     model_emitted: {emitted}")

    print()
    print(f"{n_present} invoice(s) with {key} present in GT ({args.split} split)")
    print(json.dumps({"field": key, "n_present": n_present}))


if __name__ == "__main__":
    main()
