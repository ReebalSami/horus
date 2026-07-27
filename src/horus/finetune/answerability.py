"""Transcript answerability — can the structurer even find the GT values in its input?

The orchestrated arm (ADR-038) is a two-stage pipeline: reader (image -> text) then
structurer (text -> JSON). The structurer's recall is CAPPED by what the reader
transcribed: a value absent from the transcript can only be "extracted" by hallucination.
This module measures that cap per invoice: the fraction of GT-present header fields whose
value is literally findable in the reader transcript (with German/ISO date, decimal-comma
amount, and grouped-IBAN format variants).

Diagnostic finding that motivated banking this (zero-shot val baseline, 2026-07-11):
Pearson(answerability, flat micro_f1) = 0.927 over the 29 sealed val invoices — reader
recall, not structurer capability, dominates the F1 spread across corpus subdirs. The
XML-Rechnung subdir sits at 0.84-0.90 answerability; ZUGFeRDv1/v2 test-suite and French
docs collapse as low as 0.10 (`ZUGFeRD_1p0_EXTENDED_Kostenrechnung`).

Containment is a HEURISTIC lower bound: a value the reader re-formatted beyond the
variant set counts as missing even though the structurer might still map it. Use the
score comparatively (reader A vs reader B, subdir vs subdir), not as an absolute.

Refs: ADR-038 (Arm-B), ADR-034 (sealed split), issue #55.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from horus.finetune.dataset import InvoiceRecord, reader_text_from_transcript

__all__ = [
    "InvoiceAnswerability",
    "score_answerability",
    "value_variants",
]


_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_AMOUNT_RE = re.compile(r"-?(\d+)\.(\d{2})")
_IBAN_RE = re.compile(r"[A-Z]{2}[0-9A-Z]{10,32}")
_WS_RE = re.compile(r"\s+")


def _canon(s: str) -> str:
    return _WS_RE.sub(" ", s.lower()).strip()


def _german_grouped(euros: str, cents: str) -> str:
    grouped = ""
    while len(euros) > 3:
        grouped = "." + euros[-3:] + grouped
        euros = euros[:-3]
    return f"{euros}{grouped},{cents}"


def value_variants(raw: str | None, normalized: str | None) -> set[str]:
    """Canonicalized textual shapes a GT value may take inside a transcript.

    Covers the shapes German invoices actually print: ISO date -> ``dd.mm.yyyy``
    (zero-padded + unpadded), normalized amount ``1234.56`` -> ``1234,56`` +
    ``1.234,56``, and IBAN -> 4-char-grouped. Raw and normalized forms are both
    seeded so either side of the normalizer can match.
    """
    out: set[str] = set()
    for v in (raw, normalized):
        if not v:
            continue
        v = v.strip()
        if not v:
            continue
        out.add(v)
        m = _ISO_DATE_RE.fullmatch(v)
        if m:
            y, mo, d = m.groups()
            out.add(f"{d}.{mo}.{y}")
            out.add(f"{int(d)}.{int(mo)}.{y}")
        m = _AMOUNT_RE.fullmatch(v)
        if m:
            euros, cents = m.groups()
            out.add(f"{euros},{cents}")
            if len(euros) > 3:
                out.add(_german_grouped(euros, cents))
        if _IBAN_RE.fullmatch(v):
            out.add(" ".join(v[i : i + 4] for i in range(0, len(v), 4)))
    return {_canon(v) for v in out}


@dataclass(frozen=True)
class InvoiceAnswerability:
    """Per-invoice answerability: which GT-present header values the transcript contains."""

    stem: str
    subdir: str
    n_present: int
    n_found: int
    missing_fields: tuple[str, ...]

    @property
    def ratio(self) -> float:
        return self.n_found / self.n_present if self.n_present else 1.0


def score_answerability(
    rec: InvoiceRecord,
    *,
    transcript_path: Path | None = None,
) -> InvoiceAnswerability | None:
    """Score one record's transcript answerability; None when GT or transcript is missing.

    ``transcript_path`` overrides the record's own cached transcript — the reader
    bake-off scores candidate transcripts living outside the canonical transcript dir.
    """
    path = transcript_path or rec.transcript_path
    if rec.gt is None or path is None or not path.exists():
        return None
    text = _canon(reader_text_from_transcript(path))
    present = [(key, f) for key, f in rec.gt.header.items() if f.is_present and f.normalized_value]
    missing = tuple(
        key
        for key, f in present
        if not any(v in text for v in value_variants(f.raw_value, f.normalized_value))
    )
    return InvoiceAnswerability(
        stem=rec.stem,
        subdir=rec.subdir,
        n_present=len(present),
        n_found=len(present) - len(missing),
        missing_fields=missing,
    )
