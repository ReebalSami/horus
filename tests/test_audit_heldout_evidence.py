"""Tests for the held-out evidence audit's tier assignment.

The load-bearing behaviour is that a tier is decided by whether the text layer actually
EVIDENCES the invoice, not by whether the PDF happens to contain any extractable words.
`belege-de-email-014` is the case that forced this: 102 words of a covering email page,
GT internally consistent, and almost nothing evidenced — a presence-only test files it as
deterministically settleable when nothing in it can be settled.
"""

from __future__ import annotations

from horus.eval.printed_evidence import (
    EvidencePolicy,
    EvidenceResult,
    EvidenceStatus,
    prepare_text_layer,
)
from scripts.audit_heldout_evidence import (
    LOW_YIELD_THRESHOLD,
    MIN_ASSERTED_FOR_YIELD,
    InvoiceAudit,
)


def _proven(key: str) -> EvidenceResult:
    return EvidenceResult(
        key, "value", EvidencePolicy.TEXT, EvidenceStatus.FOUND, matched="value", weak=False
    )


def _unevidenced(key: str) -> EvidenceResult:
    return EvidenceResult(key, "value", EvidencePolicy.TEXT, EvidenceStatus.NOT_FOUND)


def _null(key: str) -> EvidenceResult:
    return EvidenceResult(key, None, EvidencePolicy.TEXT, EvidenceStatus.NULL_CLAIM)


def _audit(*, words: int, proven: int, unevidenced: int, nulls: int = 0) -> InvoiceAudit:
    results = (
        [_proven(f"p{i}") for i in range(proven)]
        + [_unevidenced(f"u{i}") for i in range(unevidenced)]
        + [_null(f"n{i}") for i in range(nulls)]
    )
    return InvoiceAudit(
        invoice_id="synthetic",
        language="german",
        channel="email",
        layer=prepare_text_layer(" ".join(["wort"] * words)),
        results=results,
        gt_present=True,
    )


def test_no_text_layer_is_tier_b() -> None:
    audit = _audit(words=0, proven=0, unevidenced=10)
    assert audit.layer.exists is False
    assert audit.text_layer_authoritative is False
    assert audit.tier == "B"


def test_authoritative_text_layer_is_tier_a() -> None:
    audit = _audit(words=400, proven=13, unevidenced=2)
    assert audit.tier == "A"
    assert audit.text_layer_authoritative is True


def test_text_layer_present_but_low_yield_is_flagged() -> None:
    """The email-014 shape: words exist, but they are not the invoice's words."""
    audit = _audit(words=102, proven=3, unevidenced=14)
    assert audit.layer.exists is True
    assert audit.text_layer_authoritative is False
    assert audit.tier == "A?"


def test_yield_is_withheld_when_gt_asserts_too_little() -> None:
    """A 2-cell sample cannot condemn a text layer, so the doc is not downgraded."""
    audit = _audit(words=300, proven=0, unevidenced=MIN_ASSERTED_FOR_YIELD - 1)
    assert audit.evidence_yield is None
    assert audit.tier == "A"


def test_evidence_yield_counts_only_asserted_cells() -> None:
    """Nulls are not evidence failures; including them would fake a low yield."""
    audit = _audit(words=300, proven=8, unevidenced=2, nulls=24)
    assert audit.evidence_yield == 0.8
    assert audit.tier == "A"


def test_threshold_boundary_is_inclusive() -> None:
    audit = _audit(words=300, proven=5, unevidenced=5)
    assert audit.evidence_yield == LOW_YIELD_THRESHOLD
    assert audit.tier == "A"


def test_unevidenced_excludes_nulls_and_includes_missing_text_layer() -> None:
    audit = _audit(words=0, proven=0, unevidenced=3, nulls=5)
    assert len(audit.asserted) == 3
    assert len(audit.unevidenced) == 3
