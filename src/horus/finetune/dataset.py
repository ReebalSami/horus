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
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from horus.config import EvalConfig
from horus.eval import structurer
from horus.eval.ground_truth import (
    FIELDS,
    REPEATING_GROUPS,
    FieldSpec,
    GroundTruth,
    GroundTruthField,
)
from horus.eval.harness import _extract_groundtruth_via_facturx, _model_slug
from horus.eval.heldout import build_groundtruth_from_json, load_heldout_index
from horus.eval.promotion import PROMOTED_DIRNAME
from horus.eval.scorer import InvoiceFieldScores, score
from horus.eval.transcripts import parse_transcript, split_per_page_texts

__all__ = [
    "DEFAULT_HELDOUT_CORPUS_ROOT",
    "DEFAULT_HELDOUT_GT_DIRNAME",
    "DEFAULT_HELDOUT_RASTER_CACHE",
    "DEFAULT_HELDOUT_TRANSCRIPT_DIR",
    "DEFAULT_READER_MODEL",
    "DEFAULT_TRANSCRIPT_DIR",
    "InvoiceRecord",
    "build_dataset",
    "build_example",
    "build_heldout_records",
    "build_records",
    "groundtruth_to_target",
    "load_groundtruth",
    "reader_text_from_transcript",
    "render_oracle_transcript",
    "summarize",
    "target_self_score",
]

# The Arm-B reader whose cached transcripts the structurer consumes (ADR-034/038),
# switched to ADR-057's bake-off winner. Kept in step with
# `FinetuneConfig.reader_model` and configs/finetune-structurer.yaml: this constant
# and that field name the SAME concept, so leaving one on the superseded granite
# lineage made "the default reader" ambiguous (ADR-058 finding 4, ADR-059).
# The superseded granite transcripts remain on disk per ADR-011 retention and are
# still selectable via `--reader-model`.
#
# Note `scripts/finetune_seal_split.py` takes its `--reader-model` default from here.
# The split is already SEALED and committed (data/finetune/split.json); it must not be
# re-derived, or the no-HARKing guarantee is void. Both lineages happen to yield the
# same 146 GT-bearing ready records, so this change cannot silently reshape it.
DEFAULT_READER_MODEL = "Qwen/Qwen3-VL-4B-Instruct"
# Where the pilot-13 / baseline reader pass archives transcripts (pilot-13.yaml).
DEFAULT_TRANSCRIPT_DIR = Path("docs/sources/transcripts-multipage")

# The PRIVATE held-out Belege set (ADR-040) and its two derived artifact dirs.
# All three sit under `data/self-collected/`, which `.gitignore` blocks in full with
# no `!` un-ignore permitted. This placement is load-bearing, not incidental: a real
# invoice's reader transcript reproduces the document's content verbatim (vendor,
# addresses, amounts), so it must NEVER land in the tracked `docs/sources/`
# transcript tree the synthetic corpus uses. Rasterized pages carry the same
# exposure, hence the cache lives inside the ignored tree too.
DEFAULT_HELDOUT_CORPUS_ROOT = Path("data/self-collected")
DEFAULT_HELDOUT_TRANSCRIPT_DIR = DEFAULT_HELDOUT_CORPUS_ROOT / "_transcripts"
DEFAULT_HELDOUT_RASTER_CACHE = DEFAULT_HELDOUT_CORPUS_ROOT / "_pagecache"

# The answer-key tree a held-out grading run reads (ADR-062). `_promoted/` holds the
# author-signed-off key; `gt/` holds the superseded draft, which is still an input
# CHANNEL to adjudication and must never be graded against.
DEFAULT_HELDOUT_GT_DIRNAME = PROMOTED_DIRNAME

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


def build_heldout_records(
    corpus_root: Path = DEFAULT_HELDOUT_CORPUS_ROOT,
    *,
    transcript_dir: Path = DEFAULT_HELDOUT_TRANSCRIPT_DIR,
    reader_model: str = DEFAULT_READER_MODEL,
    gt_dirname: str | None = DEFAULT_HELDOUT_GT_DIRNAME,
) -> list[InvoiceRecord]:
    """Discover the private held-out Belege set as `InvoiceRecord`s (ADR-040).

    The held-out counterpart of `build_records`, returning the SAME record type so
    `run_reader_pass` and the evaluator consume real invoices through the identical
    code path as the synthetic corpus. That identity is the point: this measurement
    changes the DATA, not the instrument, so any difference in the resulting score
    is attributable to the invoices rather than to a second pipeline.

    Two differences from the ZUGFeRD path, both forced by the data:

      - **GT route** — real invoices carry no embedded factur-x XML, so ground truth
        comes from the hand-authored `<id>.gt.json` via `build_groundtruth_from_json`
        rather than `load_groundtruth`'s factur-x extraction. `gt_dirname` selects the
        tree; it defaults to the SIGNED-OFF `_promoted/` key (ADR-062), not the `gt/`
        draft. The draft is one of the channels adjudication reads, so grading against
        it means grading against an answer key nobody verified — the cause of the
        retracted held-out figure. Pass `gt_dirname="gt"` only to reproduce that
        superseded measurement deliberately.
      - **stem** — the sanitized index id (`belege-de-email-001`), never the source
        filename. `stem` names the output transcript, and source filenames are
        private (they carry vendor and subject); the id is the only identifier
        ADR-040 permits to leave the ignored tree.

    Returns `[]` when the corpus is absent (no `index.json`), mirroring the
    corpus-absent auto-skip of the synthetic path (ADR-023) so CI and fresh clones
    are unaffected.
    """
    reader_slug = _model_slug(reader_model)
    records: list[InvoiceRecord] = []
    for item in load_heldout_index(corpus_root, gt_dirname=gt_dirname):
        try:
            gt: GroundTruth | None = build_groundtruth_from_json(item.gt_path)
            gt_error: str | None = None
        except (OSError, ValueError) as exc:
            # One malformed or missing hand-authored GT must not abort the set — the
            # same per-invoice robustness contract `load_groundtruth` gives the
            # factur-x route. `ValueError` covers `json.JSONDecodeError`.
            gt, gt_error = None, f"{type(exc).__name__}: {exc}"
        candidate = transcript_dir / f"{reader_slug}__{item.id}.txt"
        records.append(
            InvoiceRecord(
                pdf_path=item.pdf_path,
                stem=item.id,
                # Language/channel is the split that matters for this set: an
                # email-native PDF and a phone photo of the same invoice are
                # different difficulty regimes, and the coverage report groups on it.
                subdir=f"{item.language}/{item.channel}",
                gt=gt,
                gt_error=gt_error,
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


def _oracle_print_form(rec: GroundTruthField, spec: FieldSpec) -> str | None:
    """Render one GT value the way a German invoice page prints it.

    DATE → ``dd.mm.yyyy``; MONEY → thousand-dot + decimal-comma + ``€``;
    RATE → ``19 %``. Controlled-vocabulary CODEs that never print verbatim
    (document_type token, VAT category letter) stay canonical — the oracle
    isolates structuring capability, not page-to-code inference. ``None`` for
    absent / empty / normalizer-rejected fields (they don't appear on the page).
    """
    if not rec.is_present or not rec.normalized_value:
        return None
    v = rec.normalized_value
    if spec.field_type == "DATE":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            y, mo, d = m.groups()
            return f"{d}.{mo}.{y}"
        return v
    if spec.field_type == "MONEY":
        m = re.fullmatch(r"(-?)(\d+)\.(\d{2})", v)
        if m:
            sign, euros, cents = m.groups()
            grouped = ""
            while len(euros) > 3:
                grouped = "." + euros[-3:] + grouped
                euros = euros[:-3]
            return f"{sign}{euros}{grouped},{cents} €"
        return v
    if spec.field_type == "RATE":
        return f"{v} %"
    return v


# Repeating groups whose rows are numbered on a real page, mapped to the sub-field
# holding that number. Such a row leads with the GT value bare and unlabelled, the
# way the column reads, instead of also emitting it as a "<label>: <value>" cell —
# the structurer returned the labelled form verbatim (line_id="Pos: 1", 65 FNs).
# `line_items` qualifies because BT-126 IS the printed "Pos" column; the VAT
# breakdown and Skonto tiers have no position column, so numbering their rows would
# put a number on the page that is not a value (ADR-059).
_ROW_ORDINAL_CELL: Final[dict[str, str]] = {"line_items": "line_id"}


def render_oracle_transcript(gt: GroundTruth) -> str:
    """Render the GT as the text a PERFECT reader would produce (attribution audit).

    Emulates an ideal reader transcript of the invoice page: one
    ``<printed label>: <printed value>`` line per present flat field, plus one
    labeled line per repeating-group row. Feeding this to the structurer measures
    the structurer + predicted-normalizer ceiling INDEPENDENT of reading quality —
    the gap to `target_self_score` (≈0.9975) is pure downstream loss.

    Labels come from ``FieldSpec.rendered_label`` — the corpus-MEASURED
    ``printed_label`` where one exists, else the canonical ``german_label``
    (ADR-059). Rendering the spec term unconditionally, as this function
    originally did, made the "perfect" page print wordings that occur in 0/146
    real transcripts and cost the ceiling arm real accuracy: the structurer scored
    0.000 on ``charge_total_amount`` here while scoring 0.889 on genuine reader
    text, because it recognises "Gesamtbetrag der Zuschläge" (88/146) and not the
    spec's "Summe Zuschläge" (0/146). 5 fields keep a synthetic label because no
    printed form exists for them at all; ``make audit-prompts`` enumerates them.

    Repeating-group rows render as ``<label>: <value>`` cells joined by ``" | "``.
    Groups listed in `_ROW_ORDINAL_CELL` lead with their GT row position, bare and
    unlabelled, because that is how a position column reads on a page; every other
    group leads with a dash so the row carries no number that is not a value.

    Remaining honesty caveats (documented for the audit report):
      - DATE / MONEY / RATE values are German-print-formatted, so the structurer's
        locale conversion IS exercised (that's part of its real job).
      - One label per field, one field per line, and group labels repeated on every
        row: a real page prints the billing period as ONE range under ONE heading,
        and line items as a TABLE with column headers stated once. So this remains
        an UPPER bound on layout, even though the label WORDING is now
        corpus-grounded.
    """
    lines: list[str] = []
    for key, spec in FIELDS.items():
        printed = _oracle_print_form(gt.header[key], spec)
        if printed is not None:
            lines.append(f"{spec.rendered_label}: {printed}")
    group_titles = {
        "vat_breakdown": "Umsatzsteueraufstellung",
        "skonto": "Zahlungsbedingungen (Skonto)",
        "line_items": "Rechnungspositionen",
    }
    for group, (_row_xpath, sub_fields) in REPEATING_GROUPS.items():
        rows = getattr(gt, group)
        if not rows:
            continue
        lines.append("")
        lines.append(f"{group_titles[group]}:")
        ordinal_key = _ROW_ORDINAL_CELL.get(group)
        for row in rows:
            # Groups with a real position column lead with that GT position, bare, the
            # way the column reads on the page; the rest lead with a dash. Never
            # `enumerate`: it fabricated positions that CONTRADICT the GT (on
            # EN16931_Physiotherapeut the GT line_ids are "0"/"1" and enumerate printed
            # "1."/"2."), and on groups with no position column the bare ordinal was
            # read as data — the structurer returned it as rate_percent on VAT rows
            # whose "Steuersatz" cell is absent (rate_percent FP 2 -> 7). See ADR-059.
            prefix = "  - "
            cells = []
            for sub_key, sub_spec in sub_fields.items():
                rec = row.get(sub_key)
                if rec is None:
                    continue
                printed = _oracle_print_form(rec, sub_spec)
                if printed is None:
                    continue
                # A row is ONE line, so a value containing newlines would split it
                # and the block would stop parsing as rows entirely. Some CII
                # `name` elements hold a whole product block ("GTIN 4123456000014\n
                # Art-Nr-Lieferant ZS9997\nZitronensäure 100ml\n…"), which broke the
                # line-item table on 1 of 29 val invoices. Flat fields deliberately
                # keep their newlines: a multi-line address block under one label is
                # what a page actually prints, and there is no row contract to break.
                printed = " ".join(printed.split())
                if sub_key == ordinal_key:
                    prefix = f"  {printed}. "
                    continue
                # Colon-separated, exactly like the flat lines above. Without it the
                # cell is "<label> <value>", which only reads correctly while the
                # labels are long German compounds: once ADR-059 replaced them with
                # the SHORT forms real pages print, "Positionsnummer 1" became
                # "Pos 1" and the structurer faithfully returned line_id="Pos 1"
                # (65 FNs), while "Umsatzsteuer S" made it give up and emit
                # category_code=null (38 FNs) — 103 cells lost on PERFECT input,
                # purely to punctuation. A label must be separable from its value by
                # construction, not by being too wordy to mistake for one.
                cells.append(f"{sub_spec.rendered_label}: {printed}")
            if cells:
                lines.append(prefix + " | ".join(cells))
    return "\n".join(lines)


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
