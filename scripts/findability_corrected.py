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
"""

from __future__ import annotations

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
    val = set(json.loads(SPLIT_PATH.read_text(encoding="utf-8"))["val"])
    excl = _load_exclusions()
    records = [
        r
        for r in build_records(REPO_ROOT / "data" / "raw" / "german" / "zugferd-corpus")
        if r.stem in val
    ]
    records.sort(key=lambda r: r.stem)

    def corrected_mean(transcript_for) -> tuple[float, int, int]:  # noqa: ANN001
        ratios: list[float] = []
        n_excluded = 0
        n_missing = 0
        for rec in records:
            path = transcript_for(rec)
            ans = score_answerability(rec, transcript_path=path)
            if ans is None:
                continue
            keep_missing = [f for f in ans.missing_fields if (rec.stem, f) not in excl]
            excluded_here = sum(1 for f in rec.gt.header if (rec.stem, f) in excl)
            n_present = ans.n_present - excluded_here
            n_found = n_present - len(keep_missing)
            ratios.append(n_found / n_present if n_present else 1.0)
            n_excluded += excluded_here
            n_missing += len(keep_missing)
        return (sum(ratios) / len(ratios) if ratios else 0.0, n_missing, n_excluded)

    print(
        f"Corrected findability — sealed val ({len(records)} invoices), "
        f"{len(excl)} audited exclusions\n"
    )
    print(f"{'reader':44} {'corrected':>10} {'real misses':>12}")

    tmp = Path("/tmp/_textlayer_corr.txt")
    mean, missing, _ = corrected_mean(lambda rec: _text_layer_transcript(rec, tmp))
    print(f"{'<PDF text layer — ceiling>':44} {mean:10.3f} {missing:12d}")

    canonical = corrected_mean(lambda rec: rec.transcript_path)
    print(
        f"{'granite-docling-258M (canonical baseline)':44} {canonical[0]:10.3f} {canonical[1]:12d}"
    )

    for model in CANDIDATES:
        slug = _model_slug(model)
        mean, missing, _ = corrected_mean(lambda rec, s=slug: BAKEOFF / s / f"{s}__{rec.stem}.txt")
        print(f"{model:44} {mean:10.3f} {missing:12d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
