#!/usr/bin/env python3
"""Paired significance test for the two reader finalists (thesis ch. 7, reader selection).

The manuscript claims the finalists are statistically tied on corrected reading
quality. This script supplies the statistic instead of the adjective: an exact
McNemar test over paired per-cell findability outcomes for the two finalists, on
the sealed val split, under the current ruler (``horus.finetune.answerability``,
ADR-056/057 variants) and the audited page-level exclusions
(``data/finetune/findability-exclusions.json``; evidence:
``eval/reader-findability-audit.md``).

Per cell (invoice, field) with the value present in GT and not audit-excluded:
"found" means the ruler locates the GT value in that reader's retained bake-off
transcript (``data/finetune/bakeoff/``). The discordant pairs are

    b = Qwen found, olmOCR missed
    c = Qwen missed, olmOCR found

and the exact two-sided McNemar p-value is ``min(1, 2 * BinomCDF(min(b, c); b+c, 0.5))``.
McNemar conditions on the discordant pairs, so concordant cells (both found / both
missed) carry no information about the ordering — which is exactly the right
behaviour for two readers that share failure cells (e.g. the FR-VAT digit-run slips
both finalists make).

No model inference runs: transcripts are the frozen bake-off artifacts, so the test
is reproducible from the repository alone.

Usage:
    uv run python scripts/finalist_significance.py

Writes ``eval/finalist-significance.json`` (consumed by the thesis prose; the
number in ch. 7 must match this artifact).
"""

from __future__ import annotations

import json
import logging
from math import comb
from pathlib import Path

logging.disable(logging.WARNING)

from horus.eval.harness import _model_slug  # noqa: E402
from horus.finetune.answerability import score_answerability  # noqa: E402
from horus.finetune.dataset import build_records  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BAKEOFF = REPO_ROOT / "data" / "finetune" / "bakeoff"
SPLIT_PATH = REPO_ROOT / "data" / "finetune" / "split.json"
EXCLUSIONS_PATH = REPO_ROOT / "data" / "finetune" / "findability-exclusions.json"
OUT_PATH = REPO_ROOT / "eval" / "finalist-significance.json"

QWEN = "Qwen/Qwen3-VL-4B-Instruct"
OLMOCR = "allenai/olmOCR-2-7B-1025"


def _load_exclusions() -> set[tuple[str, str]]:
    data = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
    return {(e["stem"], e["field"]) for e in data["exclusions"]}


def _missing_cells(model: str, records: list, excl: set[tuple[str, str]]) -> dict[str, set[str]]:  # noqa: ANN001
    """Per invoice: the set of GT-present fields the ruler could NOT find in the transcript."""
    slug = _model_slug(model)
    out: dict[str, set[str]] = {}
    for rec in records:
        path = BAKEOFF / slug / f"{slug}__{rec.stem}.txt"
        ans = score_answerability(rec, transcript_path=path)
        if ans is None:
            raise SystemExit(f"{model}: no scorable transcript for {rec.stem} at {path}")
        out[rec.stem] = {f for f in ans.missing_fields if (rec.stem, f) not in excl}
    return out


def _present_cells(records: list, excl: set[tuple[str, str]]) -> list[tuple[str, str]]:  # noqa: ANN001
    """Every (stem, field) pair that is present in GT and survives the audit exclusions."""
    cells: list[tuple[str, str]] = []
    for rec in records:
        gt = rec.gt
        if gt is None:
            raise SystemExit(f"unparsed GT for {rec.stem}")
        for field, value in gt.header.items():
            if value is None or (rec.stem, field) in excl:
                continue
            cells.append((rec.stem, field))
    return cells


def _mcnemar_exact_p(b: int, c: int) -> float:
    """Exact two-sided McNemar: 2 * BinomCDF(min(b, c); b+c, 0.5), capped at 1."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2.0 * tail)


def main() -> int:
    val = set(json.loads(SPLIT_PATH.read_text(encoding="utf-8"))["val"])
    excl = _load_exclusions()
    records = [
        r
        for r in build_records(REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus")
        if r.stem in val
    ]
    records.sort(key=lambda r: r.stem)
    print(f"sealed val: {len(records)} invoices, {len(excl)} audited exclusions")

    cells = _present_cells(records, excl)
    qwen_missing = _missing_cells(QWEN, records, excl)
    olmocr_missing = _missing_cells(OLMOCR, records, excl)

    both_found = both_missed = b = c = 0
    discordant: list[dict[str, str]] = []
    for stem, field in cells:
        q_found = field not in qwen_missing[stem]
        o_found = field not in olmocr_missing[stem]
        if q_found and o_found:
            both_found += 1
        elif not q_found and not o_found:
            both_missed += 1
        elif q_found:
            b += 1
            discordant.append({"stem": stem, "field": field, "found_by": "qwen"})
        else:
            c += 1
            discordant.append({"stem": stem, "field": field, "found_by": "olmocr"})

    p = _mcnemar_exact_p(b, c)
    result = {
        "test": "exact McNemar, two-sided, over paired per-cell findability outcomes",
        "ruler": "horus.finetune.answerability (ADR-056/057 variants) + audited exclusions",
        "corpus": "sealed val split",
        "n_invoices": len(records),
        "n_cells": len(cells),
        "n_excluded_cells": len(excl),
        "readers": {"qwen": QWEN, "olmocr": OLMOCR},
        "qwen_misses": sum(len(v) for v in qwen_missing.values()),
        "olmocr_misses": sum(len(v) for v in olmocr_missing.values()),
        "both_found": both_found,
        "both_missed": both_missed,
        "discordant_qwen_found_olmocr_missed": b,
        "discordant_qwen_missed_olmocr_found": c,
        "p_value": round(p, 4),
        "discordant_cells": discordant,
    }
    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"cells={len(cells)}  both_found={both_found}  both_missed={both_missed}  "
        f"b(qwen-only-found)={b}  c(olmocr-only-found)={c}  p={p:.4f}"
    )
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
