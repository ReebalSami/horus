"""Unit tests for `src/horus/eval/anls.py` (ANLS\\* implementation per ADR-013).

Covers:
  - `_levenshtein` — distance correctness on canonical pairs from the literature
  - `nls` — normalized similarity, including empty-string + edge cases
  - `anls` — threshold collapse behavior + literature-default τ=0.5
  - German diacritics — NFC pre-normalization is the caller's responsibility,
    but we verify that NFC-equivalent strings score 1.0 once normalized

Refs: ADR-013 §"Decision + integration thoughts", Biten+ ICCV'19, Peer+ 2024.
"""

from __future__ import annotations

import unicodedata

import pytest

from horus.eval.anls import _levenshtein, anls, nls

# ---------------------------------------------------------------------------
# 1. Levenshtein distance — canonical pairs
# ---------------------------------------------------------------------------


def test_levenshtein_identity() -> None:
    """LD(s, s) == 0 for any string (including empty)."""
    assert _levenshtein("", "") == 0
    assert _levenshtein("foo", "foo") == 0
    assert _levenshtein("Lieferant GmbH", "Lieferant GmbH") == 0


def test_levenshtein_one_string_empty() -> None:
    """LD('', s) == LD(s, '') == |s| (must insert/delete every character)."""
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("abc", "") == 3
    assert _levenshtein("", "Lieferant") == len("Lieferant")


def test_levenshtein_single_substitution() -> None:
    """LD differs by 1 when exactly one character is substituted."""
    assert _levenshtein("Lieferant", "Lieferent") == 1  # a → e
    assert _levenshtein("foo", "boo") == 1  # f → b
    assert _levenshtein("kitten", "sitten") == 1  # k → s


def test_levenshtein_canonical_textbook_example() -> None:
    """LD('kitten', 'sitting') == 3 (Wagner-Fischer textbook example)."""
    # k→s, e→i, +g — three operations
    assert _levenshtein("kitten", "sitting") == 3


def test_levenshtein_mild_ocr_drift() -> None:
    """PaddleOCR-VL-style mild OCR drift ('Lederart' vs 'Lieferant') = 3 edits.

    Operations: insert 'i' after 'L' → substitute 'd'→'f' → substitute 'r'→'n'.
    Despite looking visually quite different, the LCS-aligned edit count is
    only 3 — which is why this pair is a 'mild drift' that ANLS\\* with the
    literature-default τ=0.5 will ACCEPT, not reject. The real severe-drift
    cases from the cohort (e.g., PaddleOCR-VL's Thai-script hallucination)
    are covered separately.
    """
    distance = _levenshtein("Lederart", "Lieferant")
    assert distance == 3, f"Got LD={distance}, expected 3"


def test_levenshtein_severe_drift_real_cohort_example() -> None:
    """PaddleOCR-VL's actual hallucination: 'Unhmd QmbH' vs GT 'Lieferant GmbH'.

    From `docs/sources/transcripts/paddleocr-vl.txt` line 30 (the model emitted
    'Un\u0e2b\u0e21\u0e14 QmbH' with Thai diacritics; we ASCII-flatten to 'Unhmd QmbH' for
    test determinism). LD=10 over max_len=14 → NLS≈0.286 — well below the
    literature-default τ=0.5 threshold.
    """
    distance = _levenshtein("Unhmd QmbH", "Lieferant GmbH")
    assert distance == 10, f"Got LD={distance}, expected 10"


def test_levenshtein_symmetry() -> None:
    """LD is symmetric: LD(a, b) == LD(b, a) for all (a, b)."""
    pairs = [
        ("foo", "bar"),
        ("Lieferant", "Lieferent"),
        ("", "abc"),
        ("München", "Munchen"),
        ("Lederart", "Lieferant"),
    ]
    for a, b in pairs:
        assert _levenshtein(a, b) == _levenshtein(b, a), f"LD asymmetry on ({a!r}, {b!r})"


def test_levenshtein_triangle_inequality() -> None:
    """LD satisfies the triangle inequality (metric axiom)."""
    a, b, c = "Lieferant", "Lieferent", "Lederart"
    ab = _levenshtein(a, b)
    bc = _levenshtein(b, c)
    ac = _levenshtein(a, c)
    assert ac <= ab + bc, (
        f"Triangle inequality violation: LD({a!r}, {c!r})={ac} > "
        f"LD({a!r}, {b!r})={ab} + LD({b!r}, {c!r})={bc}"
    )


# ---------------------------------------------------------------------------
# 2. NLS — normalized similarity
# ---------------------------------------------------------------------------


def test_nls_identity() -> None:
    """NLS(s, s) == 1.0 for any string."""
    assert nls("Lieferant GmbH", "Lieferant GmbH") == 1.0
    assert nls("471102", "471102") == 1.0
    assert nls("München", "München") == 1.0


def test_nls_both_empty() -> None:
    """NLS('', '') == 1.0 — vacuous match (avoids 0/0 in the divisor)."""
    assert nls("", "") == 1.0


def test_nls_one_empty() -> None:
    """NLS('', s) == 0.0 when only one string is empty."""
    assert nls("", "Lieferant") == 0.0
    assert nls("471102", "") == 0.0


def test_nls_one_substitution_in_long_string() -> None:
    """NLS('Lieferant', 'Lieferent') == 1 - 1/9 ≈ 0.889 (one sub out of 9 chars)."""
    similarity = nls("Lieferant", "Lieferent")
    expected = 1.0 - 1.0 / 9.0
    assert similarity == pytest.approx(expected), f"Got NLS={similarity}, expected ≈ {expected}"
    assert similarity > 0.5, "Should be above threshold 0.5 (tolerable OCR error)"


def test_nls_mild_drift_stays_above_default_threshold() -> None:
    """NLS('Lieferant', 'Lederart') = 1 - 3/9 ≈ 0.667 — ABOVE the default 0.5 threshold.

    This documents the actual behavior of mild OCR-style drift: the visual
    impression is 'these look very different' but the LCS-aligned edit count
    is small enough that ANLS\\* (with τ=0.5) accepts the prediction. The
    severe-drift case that genuinely collapses is covered separately.
    """
    similarity = nls("Lieferant", "Lederart")
    expected = 1.0 - 3.0 / 9.0
    assert similarity == pytest.approx(expected)
    assert similarity > 0.5, "Lederart vs Lieferant is mild drift, should stay above 0.5"


def test_nls_severe_drift_falls_below_default_threshold() -> None:
    """NLS('Unhmd QmbH', 'Lieferant GmbH') ≈ 0.286 — below the default 0.5 threshold.

    Real example from PaddleOCR-VL transcript: severe character-substitution
    + script confusion. LD=10 over max_len=14.
    """
    similarity = nls("Unhmd QmbH", "Lieferant GmbH")
    expected = 1.0 - 10.0 / 14.0
    assert similarity == pytest.approx(expected)
    assert similarity < 0.5, "Severe hallucination should fall below 0.5"


def test_nls_in_range_for_arbitrary_inputs() -> None:
    """NLS ∈ [0.0, 1.0] for every pair of strings."""
    pairs = [
        ("", ""),
        ("a", ""),
        ("", "a"),
        ("a", "a"),
        ("a", "b"),
        ("abc", "xyz"),
        ("Lieferant GmbH", "Lieferent GmbH"),
        ("München", "Munchen"),
        ("Lieferant", "completely-different-string"),
    ]
    for a, b in pairs:
        s = nls(a, b)
        assert 0.0 <= s <= 1.0, f"NLS({a!r}, {b!r})={s} is out of [0, 1]"


def test_nls_symmetry() -> None:
    """NLS is symmetric (inherits from LD symmetry + symmetric divisor)."""
    pairs = [
        ("foo", "bar"),
        ("Lieferant", "Lieferent"),
        ("Lederart", "Lieferant"),
        ("München", "Munchen"),
    ]
    for a, b in pairs:
        assert nls(a, b) == nls(b, a), f"NLS asymmetry on ({a!r}, {b!r})"


# ---------------------------------------------------------------------------
# 3. ANLS — thresholded NLS
# ---------------------------------------------------------------------------


def test_anls_default_threshold_is_0_5() -> None:
    """Default threshold is τ=0.5 per Biten+ ICCV'19."""
    # NLS≈0.889 (one-sub in 9 chars) is above threshold → unchanged
    assert anls("Lieferant", "Lieferent") == pytest.approx(1.0 - 1.0 / 9.0)
    # NLS≈0.286 (severe Thai-script drift) is below threshold → collapses to 0
    assert anls("Unhmd QmbH", "Lieferant GmbH") == 0.0


def test_anls_at_threshold_boundary_keeps_score() -> None:
    """NLS exactly at threshold should keep its value (>= comparison)."""
    # Construct a pair where NLS is exactly 0.5:
    # |s1|=2, |s2|=2, LD=1 → NLS = 1 - 1/2 = 0.5
    assert nls("ab", "ac") == 0.5
    assert anls("ab", "ac", threshold=0.5) == 0.5  # boundary INCLUDED
    assert anls("ab", "ac", threshold=0.51) == 0.0  # just above threshold


def test_anls_custom_threshold_lenient() -> None:
    """Lower threshold permits more severe hallucinations to count as a soft match."""
    # NLS('Unhmd QmbH', 'Lieferant GmbH') ≈ 0.286 — below default 0.5 but above 0.2
    similarity = anls("Unhmd QmbH", "Lieferant GmbH", threshold=0.2)
    assert similarity == pytest.approx(1.0 - 10.0 / 14.0)
    assert similarity > 0.0, "At τ=0.2 the severe drift should NOT collapse"
    # Same pair at default τ=0.5 → collapses
    assert anls("Unhmd QmbH", "Lieferant GmbH", threshold=0.5) == 0.0


def test_anls_custom_threshold_strict() -> None:
    """Higher threshold rejects mild OCR errors that default threshold accepts."""
    # NLS('Lieferant', 'Lieferent') ≈ 0.889
    similarity = anls("Lieferant", "Lieferent", threshold=0.95)
    assert similarity == 0.0, "τ=0.95 should reject one-substitution drift"


def test_anls_identity_at_any_threshold() -> None:
    """Exact match (NLS=1.0) always returns 1.0 regardless of threshold."""
    for tau in (0.0, 0.5, 0.95, 1.0):
        assert anls("Lieferant", "Lieferant", threshold=tau) == 1.0, f"Identity broken at τ={tau}"


def test_anls_zero_threshold_equals_nls() -> None:
    """At τ=0.0, ANLS == NLS (no collapse possible)."""
    pairs = [
        ("Lieferant", "Lieferent"),
        ("Lieferant", "Lederart"),
        ("471102", "471103"),
    ]
    for a, b in pairs:
        assert anls(a, b, threshold=0.0) == nls(a, b), f"τ=0 should be identity on ({a!r}, {b!r})"


# ---------------------------------------------------------------------------
# 4. German diacritics + Unicode normalization
# ---------------------------------------------------------------------------


def test_nls_distinguishes_nfc_vs_nfd() -> None:
    """NFC and NFD forms of 'München' have different byte sequences → NLS < 1.

    The caller must NFC-normalize both sides before scoring; this test
    documents the requirement (and would catch a regression where the caller
    forgets to normalize).
    """
    nfc_form = "M\u00fcnchen"  # M, ü (composed), n, c, h, e, n
    nfd_form = "Mu\u0308nchen"  # M, u, combining diaeresis, n, c, h, e, n
    assert nfc_form != nfd_form  # bytewise different
    assert nls(nfc_form, nfd_form) < 1.0, (
        "Expected NLS<1 on unnormalized NFC vs NFD — caller must NFC-normalize"
    )


def test_nls_identity_after_nfc_normalization() -> None:
    """After NFC normalization, NFC and NFD forms compare equal (NLS=1)."""
    nfc_form = unicodedata.normalize("NFC", "M\u00fcnchen")
    nfd_form = unicodedata.normalize("NFC", "Mu\u0308nchen")
    assert nls(nfc_form, nfd_form) == 1.0


def test_anls_german_diacritic_drop_via_ocr() -> None:
    """OCR dropping the ü diacritic ('Munchen' vs 'München') — NLS ≈ 0.857."""
    # LD('Munchen', 'München') = 1 (u → ü substitution)
    # max_len = 7 → NLS = 1 - 1/7 ≈ 0.857 — above default threshold
    similarity = anls("Munchen", "München")
    assert similarity == pytest.approx(1.0 - 1.0 / 7.0)
    assert similarity > 0.5


# ---------------------------------------------------------------------------
# 5. Real-cohort-derived strings (smoke evidence — values from saved transcripts)
# ---------------------------------------------------------------------------


def test_anls_mineru_minor_ocr_error_passes_threshold() -> None:
    """MinerU 2.5 Pro transcript: 'Lieferent GmbH' vs GT 'Lieferant GmbH' — one sub."""
    # MinerU output (from docs/sources/transcripts/mineru-2-5-pro-vlm.txt): "Lieferent GmbH"
    # GT (from EN16931_Einfach.cii.xml): "Lieferant GmbH"
    # LD = 1, max_len = 14 → NLS ≈ 0.929 — above threshold, scores ~0.93
    similarity = anls("Lieferent GmbH", "Lieferant GmbH")
    assert similarity > 0.85, f"MinerU minor OCR drift should pass; got {similarity}"


def test_anls_mineru_lederart_drift_stays_above_threshold() -> None:
    """PaddleOCR-VL minor drift 'Lederart GmbH' vs GT 'Lieferant GmbH' — mild, kept.

    Despite looking visually distinct, the LCS-aligned edit count is 3 over
    14 chars → NLS≈0.786, well above the default threshold. ANLS\\* with τ=0.5
    accepts this prediction — which is the **correct** behavior per Biten+
    ICCV'19: tolerable OCR drift on a name field should not be punished.
    The truly-severe PaddleOCR-VL case is the Thai-script 'Un\u0e2b\u0e21\u0e14 QmbH'
    hallucination (covered above).
    """
    similarity = anls("Lederart GmbH", "Lieferant GmbH")
    expected = 1.0 - 3.0 / 14.0  # LD=3 over max_len=14
    assert similarity == pytest.approx(expected)
    assert similarity > 0.5, "Mild OCR drift on names should pass τ=0.5"


def test_anls_paddleocr_thai_script_hallucination_collapses() -> None:
    """PaddleOCR-VL transcript severe drift: ASCII-flattened 'Unhmd QmbH' vs 'Lieferant GmbH'.

    LD=10 over max_len=14 → NLS≈0.286, below default τ=0.5 → collapses to 0.
    Original cohort output (per `docs/sources/transcripts/paddleocr-vl.txt`)
    was 'Un\u0e2b\u0e21\u0e14 QmbH' with Thai diacritics; we ASCII-flatten the test
    fixture for determinism across locales.
    """
    similarity = anls("Unhmd QmbH", "Lieferant GmbH")
    assert similarity == 0.0, (
        f"Severe Thai-script hallucination should collapse to 0; got {similarity}"
    )
