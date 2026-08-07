#!/usr/bin/env python3
"""Corrected findability table — post-audit ruler + page-level exclusions (#114).

Scores every bake-off candidate (plus the canonical granite baseline and the
PDF-text-layer ceiling) over the sealed val split with the CURRENT ruler
(`horus.finetune.answerability`, ADR-056/ADR-057 variants) while excluding the
(invoice, field) pairs the manual audit proved un-findable on the rendered page
(`data/finetune/findability-exclusions.json`; evidence:
`eval/reader-findability-audit.md`).

Usage:
    uv run python scripts/findability_corrected.py
    uv run python scripts/findability_corrected.py --detail Qwen/Qwen3-VL-8B-Instruct

``--detail`` enumerates one reader's surviving misses as ``stem\tfield\texpected``.
ADR-057 clause (b) ("no new failure class under the same audit protocol") is a
statement about the *shape* of the misses, not their count, so adjudicating it needs
the individual rows — see ``eval/reader-findability-audit.md`` for the 4B's classes.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

logging.disable(logging.WARNING)

import pypdfium2 as pdfium  # noqa: E402

from horus.eval.harness import _model_slug  # noqa: E402
from horus.finetune.answerability import score_answerability  # noqa: E402
from horus.finetune.dataset import build_records  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BAKEOFF = REPO_ROOT / "data" / "finetune" / "bakeoff"
SPLIT_PATH = REPO_ROOT / "data" / "finetune" / "split.json"
EXCLUSIONS_PATH = REPO_ROOT / "data" / "finetune" / "findability-exclusions.json"

CANDIDATES = [
    "allenai/olmOCR-2-7B-1025",
    "Qwen/Qwen3-VL-4B-Instruct",
    # ADR-057 Decision 2: the one pre-registered sibling test. Judged against the 4B's
    # 16 audited true misses (clause a) under this same corrected ruler.
    "Qwen/Qwen3-VL-8B-Instruct",
    "opendatalab/MinerU2.5-Pro-2604-1.2B",
    "opendatalab/MinerU2.5-Pro-2605-1.2B",
]
_WS_RE = re.compile(r"\s+")


def _load_exclusions() -> set[tuple[str, str]]:
    data = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
    return {(e["stem"], e["field"]) for e in data["exclusions"]}


def _text_layer_transcript(rec, tmp: Path) -> Path:  # noqa: ANN001 — InvoiceRecord
    pdf = pdfium.PdfDocument(rec.pdf_path)
    pages = [p.get_textpage().get_text_bounded() for p in pdf]
    body = "\n".join(f"===== PAGE {i} =====\n{t}" for i, t in enumerate(pages, start=1))
    tmp.write_text(
        f"# text-layer probe\n# Model:    text-layer\n# Invoice:  {rec.stem}\n\n{body}",
        encoding="utf-8",
    )
    return tmp


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detail",
        default=None,
        help="Enumerate this reader's surviving misses (exact model id from CANDIDATES).",
    )
    detail = parser.parse_args().detail
    if detail is not None and detail not in CANDIDATES:
        raise SystemExit(f"--detail {detail!r} is not in CANDIDATES: {CANDIDATES}")

    val = set(json.loads(SPLIT_PATH.read_text(encoding="utf-8"))["val"])
    excl = _load_exclusions()
    records = [
        r
        for r in build_records(REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus")
        if r.stem in val
    ]
    records.sort(key=lambda r: r.stem)

    def corrected_mean(transcript_for) -> tuple[float, int, int, list[tuple[str, str, str]]]:  # noqa: ANN001
        ratios: list[float] = []
        n_excluded = 0
        n_missing = 0
        misses: list[tuple[str, str, str]] = []
        n_scored = 0
        for rec in records:
            path = transcript_for(rec)
            ans = score_answerability(rec, transcript_path=path)
            if ans is None:
                continue
            keep_missing = [f for f in ans.missing_fields if (rec.stem, f) not in excl]
            gt = rec.gt
            if gt is None:  # a non-None `ans` implies parsed GT; narrowed for mypy
                continue
            excluded_here = len([f for f in gt.header if (rec.stem, f) in excl])
            n_present = ans.n_present - excluded_here
            n_found = n_present - len(keep_missing)
            ratios.append(n_found / n_present if n_present else 1.0)
            n_excluded += excluded_here
            n_missing += len(keep_missing)
            n_scored += 1
            misses.extend((rec.stem, f, str(gt.header.get(f, ""))) for f in keep_missing)
        # A reader with no transcript for an invoice is skipped silently by the loop
        # above, which would quietly compute the mean over a SUBSET and make a partial
        # run look like a good score. Refuse to report that.
        if n_scored != len(records):
            raise SystemExit(
                f"scored {n_scored}/{len(records)} invoices — transcripts are incomplete; "
                f"the corrected-findability figure would be computed over a subset."
            )
        return (sum(ratios) / len(ratios) if ratios else 0.0, n_missing, n_excluded, misses)

    print(
        f"Corrected findability — sealed val ({len(records)} invoices), "
        f"{len(excl)} audited exclusions\n"
    )
    print(f"{'reader':44} {'corrected':>10} {'real misses':>12}")

    tmp = Path("/tmp/_textlayer_corr.txt")
    mean, missing, _, _ = corrected_mean(lambda rec: _text_layer_transcript(rec, tmp))
    print(f"{'<PDF text layer — ceiling>':44} {mean:10.3f} {missing:12d}")

    # `rec.transcript_path` points at the CANONICAL transcript lineage, which ADR-057
    # Decision 3 regenerated with Qwen3-VL-4B. This row therefore reports the canonical
    # lineage, NOT granite — it was mislabelled as granite after the switch, which made
    # the table read as though the 258M baseline scored 0.970/16 when it scores 0.830/92
    # (`eval/reader-findability-audit.md`). Label corrected; the number was always right.
    canonical = corrected_mean(lambda rec: rec.transcript_path)
    print(f"{'<canonical lineage — ADR-057 reader>':44} {canonical[0]:10.3f} {canonical[1]:12d}")

    for model in CANDIDATES:
        slug = _model_slug(model)
        mean, missing, _, misses = corrected_mean(
            lambda rec, s=slug: BAKEOFF / s / f"{s}__{rec.stem}.txt"
        )
        print(f"{model:44} {mean:10.3f} {missing:12d}")
        if detail == model:
            for stem, field, expected in misses:
                print(f"    {stem}\t{field}\t{expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
