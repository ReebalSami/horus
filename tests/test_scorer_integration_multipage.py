"""Multi-page scorer integration tests — locks in PR(c) ADR-014 empirical evidence.

Mirror-pair of `tests/test_scorer_integration.py`:

  - `test_scorer_integration.py`           — page-1-only baseline (PR(b), ADR-013)
  - `test_scorer_integration_multipage.py` — multi-page lift (PR(c), ADR-014)

Both files share scoring infrastructure (load transcript → preprocess →
to_predicted_dict → score against factur-x GT). They differ only in the
source transcripts (page-1 vs multi-page) — the divergence captures the
single architectural change (rasterizer.py + harness multi-page concat).

Per-test rationale:

  - **`test_minero_multipage_lift_einfach`** — MinerU 2.5 Pro on multi-page
    EN16931_Einfach hits F1 ≥ 0.70 (Step 7 observed: 0.750), vs the PR(b)
    page-1 baseline of 0.636. The +0.114 lift comes from `due_payable_amount`
    flipping FN → TP because page 2 of the PDF carries the "Zahlbetrag 529,87"
    label that PR(b)'s page-1-only scope hid.

  - **`test_multipage_due_payable_tp_minero`** — pins the specific MONEY-field
    flip: MinerU gets due_payable_amount = TP via the page-2 totals block.
    This is the one MONEY field that PR(b)'s Layer 2 heuristics catch on
    multi-page concat (the other 4 MONEY fields remain a Layer 2 follow-up).

  - **`test_xrechnung_issue_date_tp_minero_factur_x_route`** — locks in the
    ADR-012 §"Probe 5" mitigation: the harness uses factur-x-extracted GT
    (2018 dates) rather than the FeRD-shipped `.cii.xml` sidecar (2024-11-15
    dates). MinerU outputs 2018-03-05 from the visible PDF; the GT route MUST
    be factur-x so the values match.

  - **`test_multipage_money_field_gap_documented`** — the regression-baseline
    for the known limitation: 4 of 5 MONEY fields remain FN on MinerU
    multi-page (line_total_amount, tax_basis_total_amount, tax_total_amount,
    grand_total_amount). If/when the Layer 2 heuristic follow-up lands and
    these flip to TP, this test will FAIL — that's the desired regression
    signal saying "update the baseline because the limitation is gone".

Refs: ADR-014 (this PR's enabling ADR), ADR-013 §"Decision + integration
thoughts" (parent scorer ADR), ADR-012 §"Probe 5" (sidecar drift mitigation),
`docs/sources/transcripts-multipage/` (Step 7 saved evidence base).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from horus.config import EvalConfig
from horus.eval.adapters import preprocess, to_predicted_dict
from horus.eval.ground_truth import GroundTruth
from horus.eval.harness import _extract_groundtruth_via_facturx, _strip_page_separators
from horus.eval.scorer import score
from tests.conftest import EINFACH_PDF, ZUGFERD_FX_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_MULTIPAGE_DIR = REPO_ROOT / "docs" / "sources" / "transcripts-multipage"

# Per-transcript header lines (match the multi-page transcript format):
#   # Multi-page transcript (ADR-014 PR(c))
#   # Model:    <model_id>
#   # Invoice:  <invoice_stem>
#   ...
_HEADER_LINE_RE = re.compile(r"^# (Model|Invoice):\s+(.+)$")


def _load_multipage_transcript(model_slug: str, invoice_stem: str) -> tuple[str, str]:
    """Load a saved multi-page transcript file.

    Returns:
        ``(scorer_input, model_id)`` where ``scorer_input`` is the multi-page
        concat text with `===== PAGE N =====` separators stripped (matching
        what the harness passes to the adapter).

    Skips with `pytest.skip` if the transcript file is missing.
    """
    transcript_path = TRANSCRIPTS_MULTIPAGE_DIR / f"{model_slug}__{invoice_stem}.txt"
    if not transcript_path.is_file():
        pytest.skip(f"Multi-page transcript missing: {transcript_path.name}")
    text = transcript_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    model_id: str | None = None
    body_start: int | None = None
    for i, line in enumerate(lines):
        m = _HEADER_LINE_RE.match(line)
        if m and m.group(1) == "Model":
            model_id = m.group(2).strip()
        if not line.startswith("#") and line.strip() != "" and body_start is None:
            body_start = i
            break
    assert model_id is not None, f"{transcript_path.name} missing # Model: header"
    assert body_start is not None, f"{transcript_path.name} missing body"
    body = "\n".join(lines[body_start:])
    return _strip_page_separators(body), model_id


# ===========================================================================
# Module-scoped fixtures: GT via factur-x route (NOT sidecar — per ADR-012 Probe 5)
# ===========================================================================


@pytest.fixture(scope="module")
def einfach_gt_facturx() -> GroundTruth:
    """Parse EN16931_Einfach GT via factur-x route. Used by all multi-page tests."""
    if not EINFACH_PDF.is_file():
        pytest.skip(f"Missing PDF fixture: {EINFACH_PDF}")
    gt = _extract_groundtruth_via_facturx(EINFACH_PDF)
    assert gt is not None, "EN16931_Einfach.pdf must carry a factur-x XML attachment"
    return gt


@pytest.fixture(scope="module")
def xrechnung_einfach_gt_facturx() -> GroundTruth:
    """Parse XRECHNUNG_Einfach GT via factur-x route — confirms 2018 dates not 2024.

    The FeRD-shipped `.cii.xml` sidecar carries `IssueDateTime = 2024-11-15`
    (the FeRD test corpus's release-date stamp). The PDF's embedded factur-x
    XML carries the canonical invoice issue date `2018-...`. The harness MUST
    read the factur-x route; reading the sidecar silently misaligns GT with
    every model's visible-PDF output (which the model reads correctly).
    """
    xrechnung_pdf = ZUGFERD_FX_DIR / "XRECHNUNG_Einfach.pdf"
    if not xrechnung_pdf.is_file():
        pytest.skip(f"Missing XRECHNUNG fixture: {xrechnung_pdf}")
    gt = _extract_groundtruth_via_facturx(xrechnung_pdf)
    assert gt is not None, "XRECHNUNG_Einfach.pdf must carry a factur-x XML attachment"
    return gt


# ===========================================================================
# Test 1 — MinerU's multi-page F1 lift on EN16931_Einfach
# ===========================================================================


def test_minero_multipage_lift_einfach(einfach_gt_facturx: GroundTruth) -> None:
    """MinerU 2.5 Pro on multi-page EN16931_Einfach: micro_F1 in [0.65, 0.85].

    Step 7 evidence (parent_run_id=df6bce67369c47948d10dfa0d2624490):
    MinerU EN16931_Einfach micro_F1 = 0.750. PR(b) page-1 baseline was 0.636.
    Lift of +0.114 captured via `due_payable_amount` flipping FN → TP from
    the page-2 totals block (Zahlbetrag 529,87 / Bruttosumme 529,87).
    """
    scorer_input, model_id = _load_multipage_transcript(
        "opendatalab__mineru2.5-pro-2604-1.2b",
        "EN16931_Einfach",
    )
    preprocessed = preprocess(scorer_input, model_id)
    predicted = to_predicted_dict(preprocessed, model_id)
    result = score(
        predicted,
        einfach_gt_facturx,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    assert 0.65 <= result.micro_f1 <= 0.85, (
        f"MinerU multi-page EN16931_Einfach micro_F1 = {result.micro_f1:.3f} "
        f"outside [0.65, 0.85]. Step 7 baseline: 0.750. If drift is intentional "
        f"(adapter improvement / model update), update the range."
    )


# ===========================================================================
# Test 2 — MinerU's `due_payable_amount` flips FN → TP via page-2 totals
# ===========================================================================


def test_multipage_due_payable_tp_minero(einfach_gt_facturx: GroundTruth) -> None:
    """MinerU TP on `due_payable_amount` (BT-115) via multi-page concat.

    This is the canonical regression guard for the multi-page MONEY-field lift:
    the "Zahlbetrag 529,87" label sits on page 2 of EN16931_Einfach.pdf, which
    PR(b)'s page-1-only rasterization could NEVER see. PR(c) feeds the model
    all pages → MinerU's Layer 2 heuristic finds the label-value pair → TP.

    Note: the other 4 MONEY fields (line_total_amount, tax_basis_total_amount,
    tax_total_amount, grand_total_amount) remain FN even on multi-page because
    PR(b)'s Layer 2 heuristics for those labels don't anchor on the concat
    shape (see `test_multipage_money_field_gap_documented`).
    """
    scorer_input, model_id = _load_multipage_transcript(
        "opendatalab__mineru2.5-pro-2604-1.2b",
        "EN16931_Einfach",
    )
    preprocessed = preprocess(scorer_input, model_id)
    predicted = to_predicted_dict(preprocessed, model_id)
    result = score(
        predicted,
        einfach_gt_facturx,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    due = result.per_field["due_payable_amount"]
    assert due.outcome == "TP", (
        f"MinerU multi-page EN16931_Einfach due_payable_amount outcome = {due.outcome} "
        f"(expected TP — page-2 'Zahlbetrag 529,87' should anchor the value). "
        f"predicted={due.predicted_normalized!r} gt={due.gt_normalized!r}"
    )


# ===========================================================================
# Test 3 — XRECHNUNG factur-x route delivers 2018 dates (NOT 2024 sidecar)
# ===========================================================================


def test_xrechnung_issue_date_tp_minero_factur_x_route(
    xrechnung_einfach_gt_facturx: GroundTruth,
) -> None:
    """MinerU TP on XRECHNUNG_Einfach issue_date — locks the factur-x GT route.

    Step 7 evidence: ALL 7 models score TP on XRECHNUNG_Einfach issue_date
    via the factur-x route. This is empirically impossible against the
    FeRD-shipped `.cii.xml` sidecar (which carries 2024-11-15 dates that
    every model reads as 2018-* from the visible PDF → silent FN). The
    harness's choice to read GT via `facturx.get_xml_from_pdf()` rather
    than the sidecar is what enables Probe 2's universal-TP result.

    See ADR-012 §"Probe 5" for the sidecar-drift discovery; ADR-014 §"Step 7"
    for the empirical confirmation across the 7-model cohort.
    """
    scorer_input, model_id = _load_multipage_transcript(
        "opendatalab__mineru2.5-pro-2604-1.2b",
        "XRECHNUNG_Einfach",
    )
    preprocessed = preprocess(scorer_input, model_id)
    predicted = to_predicted_dict(preprocessed, model_id)
    result = score(
        predicted,
        xrechnung_einfach_gt_facturx,
        cfg=EvalConfig(),
        invoice_id="XRECHNUNG_Einfach",
        model_id=model_id,
    )
    issue_date = result.per_field["issue_date"]
    assert issue_date.outcome == "TP", (
        f"MinerU multi-page XRECHNUNG_Einfach issue_date outcome = "
        f"{issue_date.outcome} (expected TP via factur-x route per ADR-012 "
        f"Probe 5). predicted={issue_date.predicted_normalized!r} "
        f"gt={issue_date.gt_normalized!r}. If GT shows 2024-* dates, the "
        f"harness has regressed to reading the .cii.xml sidecar — fix in "
        f"`harness._extract_groundtruth_via_facturx`."
    )
    # Belt-and-suspenders: assert the GT explicitly starts with 2018-* (the
    # canonical XRECHNUNG_Einfach invoice date in the embedded factur-x XML).
    gt_iso = xrechnung_einfach_gt_facturx.header["issue_date"].normalized_value
    assert gt_iso is not None and gt_iso.startswith("2018-"), (
        f"XRECHNUNG_Einfach factur-x GT issue_date should start with '2018-'; "
        f"got {gt_iso!r}. If it starts with '2024-' the sidecar is being read."
    )


# ===========================================================================
# Test 4 — known limitation regression-baseline
# ===========================================================================


def test_multipage_money_field_gap_documented(einfach_gt_facturx: GroundTruth) -> None:
    """4 of 5 MONEY fields remain FN on MinerU multi-page EN16931_Einfach.

    Step 7 evidence: PR(c)'s multi-page rasterization feeds page-2 content to
    the adapter, but PR(b)'s Layer 2 heuristics for line_total_amount /
    tax_basis_total_amount / tax_total_amount / grand_total_amount don't match
    the concat shape (`<otsl>` / `<fcel>` table tokens for DocTags-format
    models; markdown `|` separators for others). Only `due_payable_amount`
    flips to TP because its "Zahlbetrag" label is unambiguous; the other 4
    labels collide with line-item subtotals and the heuristic stays
    conservative (prefer FN over silent FP).

    This test captures the known limitation as the regression baseline:

      - If a Layer 2 heuristic follow-up lands and these flip TP, this test
        FAILS — that's the desired "limitation is gone" signal. Update the
        expected_fn set to whatever still remains FN at that point.
      - If the multi-page extraction regresses (e.g., page-2 content stops
        reaching the adapter), this test ALSO fails because
        due_payable_amount won't be TP — caught upstream by
        `test_multipage_due_payable_tp_minero`.

    See `test_scorer_integration.py::test_monetary_fields_uniformly_fn_across_cohort`
    for the parallel page-1 baseline (5/5 FN — no MONEY field lifts on page-1
    inputs because the totals block is page-2 content).
    """
    scorer_input, model_id = _load_multipage_transcript(
        "opendatalab__mineru2.5-pro-2604-1.2b",
        "EN16931_Einfach",
    )
    preprocessed = preprocess(scorer_input, model_id)
    predicted = to_predicted_dict(preprocessed, model_id)
    result = score(
        predicted,
        einfach_gt_facturx,
        cfg=EvalConfig(),
        invoice_id="EN16931_Einfach",
        model_id=model_id,
    )
    expected_fn_money = {
        "line_total_amount",
        "tax_basis_total_amount",
        "tax_total_amount",
        "grand_total_amount",
    }
    expected_tp_money = {"due_payable_amount"}
    actual_money_outcomes = {
        fk: result.per_field[fk].outcome for fk in expected_fn_money | expected_tp_money
    }

    fn_observed = {fk for fk, o in actual_money_outcomes.items() if o == "FN"}
    tp_observed = {fk for fk, o in actual_money_outcomes.items() if o == "TP"}

    assert fn_observed == expected_fn_money, (
        f"MinerU multi-page EN16931_Einfach MONEY FN set drifted from baseline. "
        f"Expected FN: {expected_fn_money}. Actual FN: {fn_observed}. "
        f"All MONEY outcomes: {actual_money_outcomes}. "
        f"If the Layer 2 follow-up landed and these are now TP, update the "
        f"baseline; if outcomes regressed (TP→FN), investigate adapter or "
        f"transcript-archival drift."
    )
    assert tp_observed == expected_tp_money, (
        f"MinerU multi-page EN16931_Einfach MONEY TP set drifted from baseline. "
        f"Expected TP: {expected_tp_money}. Actual TP: {tp_observed}. "
        f"due_payable_amount must remain TP — it's the canonical page-2 "
        f"multi-page lift signal."
    )
