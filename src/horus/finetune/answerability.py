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

Ruler-honesty fix (#114 bake-off investigation): a text-layer probe (the PDF's own
embedded text = perfect reading) scored only 0.794 under the original variant set —
the ruler's ceiling, not any reader's. The dominant phantom-miss classes fixed here:
comma-joined composite addresses vs multi-line page blocks (component-wise check),
`document_type` tokens vs printed German/French words ("Rechnung"/"Avoir"),
currency code `EUR` vs the printed `€` sign, spaced-IBAN GT vs compact print, and
`DD/MM/YYYY` slash dates on French invoices. All representation-only: variants
recognize true renderings; a wrong value still counts as missing.

Refs: ADR-038 (Arm-B), ADR-034 (sealed split), issue #55, #114 (ruler fix).
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

# document_type token -> printed surface forms (German / French / English).
# The page renders the WORD, never the UNTDID-1001 code nor the English token
# (same as-printed-vs-as-stored class as ADR-046; #114 ruler fix).
_DOCTYPE_SURFACE: dict[str, tuple[str, ...]] = {
    "invoice": ("rechnung", "invoice", "facture"),
    "credit_note": ("gutschrift", "credit note", "avoir"),
    "correction": ("rechnungskorrektur", "korrekturrechnung", "correction"),
}

# Currency code -> printed symbol (the corpus renders €; EUR often never appears).
_CURRENCY_SYMBOL: dict[str, str] = {"EUR": "€", "USD": "$", "GBP": "£"}

# Composite address fields get component-wise containment (see `_composite_findable`).
_COMPOSITE_FIELDS = frozenset({"seller_address", "buyer_address"})


_MD_MARKS_RE = re.compile(r"[*`]+")


# German transliteration fold (both sides of the containment check get it, so it is
# information-preserving): pages print DUESSELDORF, models often normalize to
# Düsseldorf (and vice versa) — #114 audit, buyer_address on 4 intarsys fixtures.
def _fold_german(s: str) -> str:
    return s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _canon(s: str) -> str:
    """Lowercase, strip markdown emphasis, fold German transliterations, collapse WS.

    Markdown ``**bold**``/backticks are the MODEL's formatting, not page content —
    stripping them is transcript-format normalization, not content alteration
    (#114 audit: bold markers broke the MVM seller_name containment).
    """
    s = _MD_MARKS_RE.sub("", s.lower())
    return _WS_RE.sub(" ", _fold_german(s)).strip()


def _german_grouped(euros: str, cents: str) -> str:
    grouped = ""
    while len(euros) > 3:
        grouped = "." + euros[-3:] + grouped
        euros = euros[:-3]
    return f"{euros}{grouped},{cents}"


def _anglo_grouped(euros: str, cents: str) -> str:
    """Anglo print shape ``2,076.76`` (comma thousands, dot decimals).

    The FNFE French fixtures print totals Anglo-style (#114 audit: Facture_UE
    prints ``2,076.76 €`` — 4 of its phantom misses were this exact shape).
    """
    grouped = ""
    while len(euros) > 3:
        grouped = "," + euros[-3:] + grouped
        euros = euros[:-3]
    return f"{euros}{grouped}.{cents}"


def value_variants(
    raw: str | None, normalized: str | None, field_key: str | None = None
) -> set[str]:
    """Canonicalized textual shapes a GT value may take inside a transcript.

    Covers the shapes German invoices actually print: ISO date -> ``dd.mm.yyyy``
    (zero-padded + unpadded) + ``dd/mm/yyyy`` (French prints slash dates),
    normalized amount ``1234.56`` -> ``1234,56`` + ``1.234,56``, and IBAN ->
    4-char-grouped + compact (a spaced GT IBAN is frequently printed compact).
    Raw and normalized forms are both seeded so either side of the normalizer
    can match. ``field_key`` unlocks field-aware variants (#114 ruler fix):
    ``document_type`` tokens map to printed German/French/English words and
    ``invoice_currency_code`` maps to the printed symbol (``EUR`` -> ``€``).
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
            out.add(f"{d}/{mo}/{y}")
            # US month-first print shape (FNFE fixtures print 11/03/2017 for
            # 2017-11-03 — #114 audit, Facture_UE issue/due dates).
            out.add(f"{mo}/{d}/{y}")
        m = _AMOUNT_RE.fullmatch(v)
        if m:
            euros, cents = m.groups()
            out.add(f"{euros},{cents}")
            if len(euros) > 3:
                out.add(_german_grouped(euros, cents))
                out.add(_anglo_grouped(euros, cents))
        if _IBAN_RE.fullmatch(v):
            out.add(" ".join(v[i : i + 4] for i in range(0, len(v), 4)))
        despaced = v.replace(" ", "")
        if despaced != v and _IBAN_RE.fullmatch(despaced):
            out.add(despaced)
            out.add(" ".join(despaced[i : i + 4] for i in range(0, len(despaced), 4)))
        if field_key == "document_type":
            out.update(_DOCTYPE_SURFACE.get(v.lower(), ()))
        if field_key == "invoice_currency_code" and v.upper() in _CURRENCY_SYMBOL:
            out.add(_CURRENCY_SYMBOL[v.upper()])
    return {_canon(v) for v in out}


def _composite_findable(text: str, raw: str | None, normalized: str | None) -> bool:
    """Component-wise containment for comma-joined composite GT values (addresses).

    The GT stores ``'Lieferantenstraße 20, 80333, München, DE'`` as ONE string but
    the page prints a multi-line block, often reordered (``DE 80333 München``) — so
    full-string containment can never match (#114 ruler fix: this artifact alone
    zeroed the address fields on 28/29 val invoices for EVERY reader, including the
    PDF's own text layer). Findable = every component of length >= 3 is contained
    (2-char country codes like ``DE`` are skipped — as substrings they match
    almost any text, adding noise, not signal).
    """
    for source in (raw, normalized):
        if not source:
            continue
        parts = [p for p in (_canon(p) for p in source.split(",")) if len(p) >= 3]
        if parts and all(p in text for p in parts):
            return True
    return False


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

    def _findable(key: str, f) -> bool:  # noqa: ANN001 — GroundTruthField
        if key in _COMPOSITE_FIELDS:
            return _composite_findable(text, f.raw_value, f.normalized_value)
        return any(v in text for v in value_variants(f.raw_value, f.normalized_value, key))

    missing = tuple(key for key, f in present if not _findable(key, f))
    return InvoiceAnswerability(
        stem=rec.stem,
        subdir=rec.subdir,
        n_present=len(present),
        n_found=len(present) - len(missing),
        missing_fields=missing,
    )
