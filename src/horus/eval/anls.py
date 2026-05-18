"""Average Normalized Levenshtein Similarity (ANLS) — OCR-tolerant string metric.

Implements the **NLS** (Normalized Levenshtein Similarity) and **ANLS** (NLS
with threshold) used by PR(b)'s `STRING`-type field comparator per ADR-013.

Literature anchors:

  - **Biten et al. ICCV'19** — "Scene Text Visual Question Answering" — defines
    ANLS = `max(0, 1 - LD(pred, gt) / max(|pred|, |gt|))` with a threshold of
    **0.5** below which the score collapses to 0. Source archival:
    `docs/sources/papers/biten-2019-anls-iccv.md`.
  - **Peer et al. 2024 (arXiv 2402.03848)** — "ANLS\\* — A Universal Document
    Processing Metric for Generative LLMs" — extends ANLS to dict-structured
    outputs with missing-key semantics. On flat string pairs (HORUS's per-field
    case), ANLS\\* reduces to plain ANLS. Source archival:
    `docs/sources/papers/peer-2024-anls-star-arxiv-2402-03848.md`.

Implementation choice: **hand-rolled Wagner-Fischer dynamic-programming
Levenshtein distance** in `_levenshtein`. We deliberately do NOT use
`difflib.SequenceMatcher.ratio()` because SequenceMatcher computes a
longest-common-subsequence-based similarity (`2·M / T` where M = matches,
T = sum of lengths), which is NOT equivalent to NLS in pathological cases
(e.g., transpositions count as 2 substitutions in Levenshtein but as a
single transposition in LCS — yielding different similarity numbers). True
Levenshtein is ~20 LOC of DP with no new dependency.

Forward-compat: this module exposes scalar string-vs-string functions. For
dict-structured outputs (relevant if HORUS adds line items per BG-25 in a
future ADR), an `anls_dict()` function implementing Peer+ 2024 §3 semantics
would land here as an additive extension; the scalar functions stay stable.

Refs: ADR-013 (this PR's enabling ADR), ADR-012 (parent of the eval/ subpackage),
`horus-config-discipline.md` (the `anls_threshold` knob lives in EvalConfig
YAML, not hardcoded here — this module accepts threshold as a function argument
so callers can inject the config value).
"""

from __future__ import annotations

__all__ = ["anls", "nls"]


def _levenshtein(s1: str, s2: str) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Wagner-Fischer dynamic programming over a two-row buffer. Time: O(|s1|·|s2|).
    Memory: O(min(|s1|, |s2|)) — we always iterate over the shorter string in
    the inner loop to bound the row width.

    The three edit operations are equally weighted at cost 1:

      - insertion of a character into ``s1``
      - deletion of a character from ``s1``
      - substitution of one character for another

    Empty-string edge cases short-circuit before the DP table is allocated.

    Args:
        s1: first string (treated as the "source" for the operation count).
        s2: second string (treated as the "target").

    Returns:
        Non-negative integer edit distance. Bounded above by
        ``max(len(s1), len(s2))``.

    Example:
        >>> _levenshtein("kitten", "sitting")
        3
        >>> _levenshtein("Lieferant", "Lieferent")
        1
        >>> _levenshtein("", "abc")
        3
    """
    # Trivial short-circuits
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    # Ensure s1 is the shorter string to bound row width
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    # Two-row DP. `prev` holds row j-1 of the (|s2|+1) × (|s1|+1) table.
    prev = list(range(len(s1) + 1))
    for j, c2 in enumerate(s2, start=1):
        curr = [j]  # leftmost column: distance from empty s1 to s2[:j]
        for i, c1 in enumerate(s1, start=1):
            insertions = curr[i - 1] + 1
            deletions = prev[i] + 1
            substitutions = prev[i - 1] + (0 if c1 == c2 else 1)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr

    return prev[-1]


def nls(s1: str, s2: str) -> float:
    """Compute the Normalized Levenshtein Similarity between two strings.

    Definition (Biten+ ICCV'19):

        NLS(a, b) = 1 - LD(a, b) / max(|a|, |b|)

    where ``LD`` is Levenshtein distance. NLS ∈ [0.0, 1.0]:

      - **1.0** ↔ exact match (``a == b``)
      - **0.0** ↔ no characters in common in the same edit positions
      - intermediate values reflect partial similarity

    Both-empty edge case (``s1 == s2 == ""``) returns ``1.0`` (vacuous match).
    Single-empty case (one string empty, the other not) returns ``0.0``
    because ``LD`` equals ``max(|s1|, |s2|)``.

    Args:
        s1: first string. Compared as-is (no normalization — callers should
            apply NFC + whitespace strip first via `_normalize_predicted_string`).
        s2: second string.

    Returns:
        Float in [0.0, 1.0] representing string similarity.

    Example:
        >>> nls("Lieferant", "Lieferant")
        1.0
        >>> nls("Lieferant", "Lieferent")  # one substitution out of 9 chars
        0.8888888888888888
        >>> nls("Lieferant", "Lederart")  # severe drift
        0.4444444444444444
        >>> nls("", "")
        1.0
        >>> nls("", "abc")
        0.0
    """
    # Both-empty → exact match (vacuous case; avoids 0/0 in the divisor below)
    if not s1 and not s2:
        return 1.0

    distance = _levenshtein(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - distance / max_len


def anls(s1: str, s2: str, *, threshold: float = 0.5) -> float:
    """Compute the Average Normalized Levenshtein Similarity (thresholded NLS).

    Definition (Biten+ ICCV'19):

        ANLS(a, b, τ) = NLS(a, b)  if NLS(a, b) ≥ τ
                       0.0         otherwise

    The threshold τ=0.5 (the literature default) penalizes severe OCR errors
    that nonetheless share some characters with the ground truth — without it,
    a 30%-similar prediction would contribute a positive score that's hard to
    distinguish from a real partial match.

    HORUS pipes this into PR(b)'s `STRING`-type field comparator
    (``seller_name`` + ``buyer_name``). Field-type ``CODE`` / ``MONEY`` /
    ``DATE`` use exact-on-normalized matching instead of ANLS — codes need
    legal correctness, not OCR tolerance. The threshold is exposed via
    `EvalConfig.anls_threshold` (YAML knob per `horus-config-discipline`).

    Args:
        s1: first string (predicted value, post-normalization).
        s2: second string (ground-truth value, post-normalization).
        threshold: minimum NLS below which the score collapses to 0.
            Must be in [0.0, 1.0]. Default 0.5 per Biten+ ICCV'19.

    Returns:
        Float in [0.0, 1.0]. Either ``nls(s1, s2)`` (if at or above threshold)
        or ``0.0`` (if below).

    Example:
        >>> anls("Lieferant", "Lieferant")
        1.0
        >>> anls("Lieferant", "Lieferent")  # NLS ≈ 0.89, above threshold
        0.8888888888888888
        >>> anls("Lieferant", "Lederart")  # NLS ≈ 0.44, below threshold
        0.0
        >>> anls("Lieferant", "Lederart", threshold=0.3)  # custom threshold
        0.4444444444444444
    """
    similarity = nls(s1, s2)
    return similarity if similarity >= threshold else 0.0
