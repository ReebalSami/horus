"""Fine-tuning dataset construction for the Arm-B structurer (issue #55).

This module turns the ZUGFeRD corpus into supervised text→JSON training pairs
for a text-only LoRA fine-tune of the structurer (`google/gemma-4-E4B-it`):

    input  = build_structuring_input(structuring_prompt, reader_text)   # Granite text + instruction
    target = <the GroundTruth serialized as the JSON the structurer should emit>

Two responsibilities, kept separable so the first (cheap, offline) can run before
the second (needs a reader pass):

  1. **Discovery + GT coverage** (`build_records` / `summarize`) — walk the WHOLE
     corpus (not just the 26 wired `XML-Rechnung/FX` pairs that
     `harness._list_paired_invoices` returns) and extract GT for every PDF with an
     embedded factur-x attachment via the canonical `_extract_groundtruth_via_facturx`
     route (handles ZUGFeRD v1 *and* v2 per `_select_schema`/ADR-033). Reports how
     many invoices yield GT and how many already have a cached Granite transcript.

  2. **Target serialization** (`groundtruth_to_target` / `target_scores_clean`) —
     render a `GroundTruth` into the canonical-valued JSON object the structurer
     should emit, and **self-verify** it through the real scorer so a malformed
     target can never silently teach the model a wrong answer (make-sure-it-works).

Per `horus-config-discipline`, the *experiment* (the fine-tune) is config-driven;
this module is pure logic + a diagnostic report (the CLI lives in
`scripts/finetune_corpus_report.py`, plain flags like `scripts/inspect_arms.py`).

Refs: ADR-034/038 (arms), ADR-035/041/042 (schema + repeating-group scoring),
ADR-012/010 (GT parser + factur-x route), ADR-027 (scorer/metrics).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from horus.config import EvalConfig
from horus.eval import structurer
from horus.eval.ground_truth import FIELDS, GroundTruth, GroundTruthField
from horus.eval.harness import _extract_groundtruth_via_facturx, _model_slug
from horus.eval.scorer import InvoiceFieldScores, score
from horus.eval.transcripts import parse_transcript, split_per_page_texts

__all__ = [
    "DEFAULT_READER_MODEL",
    "DEFAULT_TRANSCRIPT_DIR",
    "InvoiceRecord",
    "build_dataset",
    "build_example",
    "build_records",
    "groundtruth_to_target",
    "load_groundtruth",
    "reader_text_from_transcript",
    "summarize",
    "target_self_score",
]

# The Arm-B reader whose cached transcripts the structurer consumes (ADR-034/038).
DEFAULT_READER_MODEL = "ibm-granite/granite-docling-258M-mlx"
# Where the pilot-13 / baseline reader pass archives transcripts (pilot-13.yaml).
DEFAULT_TRANSCRIPT_DIR = Path("docs/sources/transcripts-multipage")

# Repeating groups carried on GroundTruth, in the JSON key the structurer emits.
_REPEATING_GROUPS: tuple[str, ...] = ("vat_breakdown", "skonto", "line_items")


@dataclass(frozen=True)
class InvoiceRecord:
    """One corpus invoice: its PDF, parsed GT (or why not), and transcript status."""

    pdf_path: Path
    stem: str
    subdir: str
    gt: GroundTruth | None
    gt_error: str | None
    transcript_path: Path | None  # set iff a cached reader transcript exists

    @property
    def has_gt(self) -> bool:
        return self.gt is not None

    @property
    def has_transcript(self) -> bool:
        return self.transcript_path is not None

    @property
    def ready(self) -> bool:
        """Has both a parsed answer key and a cached reader transcript → trainable now."""
        return self.has_gt and self.has_transcript


def _quiet_facturx() -> None:
    """Silence factur-x's per-file INFO/WARNING spam (we record failures ourselves).

    The library names its logger ``factur-x`` (with a hyphen) and calls
    ``logging.basicConfig`` at import, so raising that logger's level is what mutes it.
    """
    logging.getLogger("factur-x").setLevel(logging.ERROR)


def discover_invoice_pdfs(corpus_root: Path) -> list[Path]:
    """Return every PDF under ``corpus_root`` (recursive, case-insensitive), sorted."""
    return sorted(p for p in corpus_root.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def load_groundtruth(pdf_path: Path) -> tuple[GroundTruth | None, str | None]:
    """Extract GT via the embedded factur-x route; return ``(gt, error)``.

    Robust by design: a malformed PDF/XML or an unrecognized CII root (v1/v2
    detection in `_select_schema`) yields ``(None, "<reason>")`` rather than
    aborting a whole-corpus scan.
    """
    try:
        gt = _extract_groundtruth_via_facturx(pdf_path)
    except Exception as exc:  # noqa: BLE001 — corpus robustness: one bad PDF must not abort the scan
        return None, f"{type(exc).__name__}: {exc}"
    if gt is None:
        return None, "no factur-x attachment"
    return gt, None


def _top_subdir(pdf_path: Path, corpus_root: Path) -> str:
    rel = pdf_path.relative_to(corpus_root)
    return rel.parts[0] if len(rel.parts) > 1 else "<root>"


def build_records(
    corpus_root: Path,
    *,
    transcript_dir: Path = DEFAULT_TRANSCRIPT_DIR,
    reader_model: str = DEFAULT_READER_MODEL,
) -> list[InvoiceRecord]:
    """Discover every corpus PDF, parse its GT, and record cached-transcript status."""
    _quiet_facturx()
    reader_slug = _model_slug(reader_model)
    records: list[InvoiceRecord] = []
    for pdf in discover_invoice_pdfs(corpus_root):
        gt, err = load_groundtruth(pdf)
        candidate = transcript_dir / f"{reader_slug}__{pdf.stem}.txt"
        records.append(
            InvoiceRecord(
                pdf_path=pdf,
                stem=pdf.stem,
                subdir=_top_subdir(pdf, corpus_root),
                gt=gt,
                gt_error=err,
                transcript_path=candidate if candidate.is_file() else None,
            )
        )
    return records


def summarize(records: list[InvoiceRecord]) -> dict[str, Any]:
    """Aggregate discovery results by subdir + overall, for the coverage report."""
    by_subdir: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pdfs": 0, "gt_ok": 0, "gt_fail": 0, "transcript": 0, "ready": 0}
    )
    for rec in records:
        row = by_subdir[rec.subdir]
        row["pdfs"] += 1
        row["gt_ok"] += int(rec.has_gt)
        row["gt_fail"] += int(not rec.has_gt)
        row["transcript"] += int(rec.has_transcript)
        row["ready"] += int(rec.ready)
    totals = {
        "pdfs": sum(r["pdfs"] for r in by_subdir.values()),
        "gt_ok": sum(r["gt_ok"] for r in by_subdir.values()),
        "gt_fail": sum(r["gt_fail"] for r in by_subdir.values()),
        "transcript": sum(r["transcript"] for r in by_subdir.values()),
        "ready": sum(r["ready"] for r in by_subdir.values()),
    }
    gt_no_transcript = sorted(r.stem for r in records if r.has_gt and not r.has_transcript)
    gt_failures = sorted((r.stem, r.subdir, r.gt_error or "") for r in records if not r.has_gt)
    return {
        "by_subdir": {k: dict(v) for k, v in sorted(by_subdir.items())},
        "totals": totals,
        "gt_no_transcript": gt_no_transcript,
        "gt_failures": gt_failures,
    }


def _field_target(rec: GroundTruthField) -> str | None:
    """Canonical target value for one flat field: the normalized value, or null.

    Absent fields and normalizer-rejected values serialize to ``null`` — the
    honest target for the tax domain. The canonical (normalized) form is used so
    the value is locale-invariant; `target_scores_clean` verifies it scores TP.
    """
    if not rec.is_present or rec.normalized_value is None or rec.normalized_value == "":
        return None
    return rec.normalized_value


def _row_target(row: dict[str, GroundTruthField]) -> dict[str, str | None]:
    return {sub_key: _field_target(field_rec) for sub_key, field_rec in row.items()}


def groundtruth_to_target(gt: GroundTruth) -> dict[str, Any]:
    """Serialize a `GroundTruth` into the JSON object the structurer should emit.

    Flat fields use the canonical normalized value (null when absent); repeating
    groups serialize to row lists (or null). ``purpose_summary`` is non-scored and
    is intentionally null (the answer key carries no summary). The result is keyed
    exactly like the structurer's requested JSON (flat FIELDS + the three groups +
    purpose_summary), so it can be fed straight back through the scorer.
    """
    target: dict[str, Any] = {key: _field_target(gt.header[key]) for key in FIELDS}
    for group in _REPEATING_GROUPS:
        rows = getattr(gt, group)
        target[group] = [_row_target(r) for r in rows] if rows else None
    target["purpose_summary"] = None
    return target


def target_self_score(gt: GroundTruth, *, eval_cfg: EvalConfig | None = None) -> InvoiceFieldScores:
    """Score the GT-derived target against the GT itself (the self-consistency check).

    A correct target must score ~1.0 overall with zero spurious emission. Anything
    less flags a serialization or normalizer-idempotency problem — caught BEFORE the
    target is ever used to teach the model a wrong answer (make-sure-it-works).
    """
    cfg = eval_cfg or EvalConfig()
    target = groundtruth_to_target(gt)
    predicted: dict[str, str | None] = {key: target[key] for key in FIELDS}
    predicted_groups: dict[str, list[dict[str, str | None]]] = {
        group: target[group] for group in _REPEATING_GROUPS if target.get(group)
    }
    return score(
        predicted,
        gt,
        cfg=cfg,
        invoice_id="<self>",
        model_id="<gt-target>",
        predicted_groups=predicted_groups,
    )


def reader_text_from_transcript(transcript_path: Path) -> str:
    """Load a cached reader transcript and return its page-joined text.

    Mirrors `arm_b.run_arm_b` exactly (`split_per_page_texts` joined on blank
    lines) so the training input distribution matches Arm-B inference.
    """
    _model_id, _stem, body = parse_transcript(transcript_path)
    return "\n\n".join(split_per_page_texts(body))


def build_example(rec: InvoiceRecord, *, structuring_prompt: str) -> dict[str, str]:
    """Build one supervised (question, answer) training pair for a ready invoice.

    ``question`` is composed EXACTLY as `arm_b.run_arm_b` composes the structurer
    input (`build_structuring_input` on the raw prompt + reader text) so training
    input == inference input. ``answer`` is the canonical target JSON (JSON-only,
    no reasoning — fine-tuning teaches a clean, parse-stable object).
    """
    if rec.gt is None or rec.transcript_path is None:
        raise ValueError(f"build_example requires a ready record; {rec.stem} is not ready")
    reader_text = reader_text_from_transcript(rec.transcript_path)
    question = structurer.build_structuring_input(structuring_prompt, reader_text)
    answer = json.dumps(groundtruth_to_target(rec.gt), ensure_ascii=False)
    return {"stem": rec.stem, "question": question, "answer": answer}


def build_dataset(
    records: list[InvoiceRecord],
    *,
    structuring_prompt: str,
    eval_cfg: EvalConfig | None = None,
    min_self_overall: float = 0.95,
) -> tuple[list[dict[str, str]], list[tuple[str, float]], list[tuple[str, float, float]]]:
    """Build (question, answer) pairs for every ready invoice, gated by self-consistency.

    Returns ``(examples, flagged, excluded)``:

      - ``examples`` — the kept training pairs.
      - ``flagged`` — ``(stem, overall_micro_f1)`` for KEPT targets that self-score
        in ``[min_self_overall, 1.0)``. These hold the correct answer but the scorer
        under-credits them (the known `seller_iban` CODE-vs-string normalizer
        asymmetry); the eval asymmetry is symmetric across zero-shot vs fine-tuned,
        so keeping them is correct. Surfaced for transparency, never silently.
      - ``excluded`` — ``(stem, overall_micro_f1, spurious)`` for targets dropped
        because they are genuinely broken: spurious emission (a value for an absent
        field) or an overall self-score below ``min_self_overall``.
    """
    cfg = eval_cfg or EvalConfig()
    examples: list[dict[str, str]] = []
    flagged: list[tuple[str, float]] = []
    excluded: list[tuple[str, float, float]] = []
    for rec in records:
        if not rec.ready or rec.gt is None:
            continue
        scores = target_self_score(rec.gt, eval_cfg=cfg)
        if scores.spurious_emission_rate > 0.0 or scores.overall_micro_f1 < min_self_overall:
            excluded.append((rec.stem, scores.overall_micro_f1, scores.spurious_emission_rate))
            continue
        if scores.overall_micro_f1 < 0.999:
            flagged.append((rec.stem, scores.overall_micro_f1))
        examples.append(build_example(rec, structuring_prompt=structuring_prompt))
    return examples, flagged, excluded
