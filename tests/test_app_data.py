"""Unit tests for the dashboard's read-only data layer (`app/data`).

The pure helpers (approach resolution, per-field parsing, live metric pooling,
field display metadata, and the JSON/transcript helpers) run everywhere. The
live-store smoke test auto-skips when `mlflow.db` is absent (fresh clone / CI),
mirroring the corpus-skip pattern in `tests/_corpus.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.components import charts, field_table
from app.data import approaches as approach_data
from app.data import fields as field_meta
from app.data import invoices, metrics, mlflow_store, results
from horus.eval.ground_truth import FIELDS, FieldType
from horus.eval.scorer import FieldResult, Outcome

skip_if_no_store = pytest.mark.skipif(
    not mlflow_store.store_exists(),
    reason="requires a local MLflow store (mlflow.db); absent on CI / fresh clones",
)


def _fr(
    english_key: str,
    outcome: Outcome,
    *,
    gt_present: bool,
    score: float = 1.0,
    field_type: FieldType = "STRING",
    predicted: str | None = "x",
    gt: str | None = "x",
) -> FieldResult:
    return FieldResult(
        english_key=english_key,
        bt_code="BT-0",
        field_type=field_type,
        outcome=outcome,
        score=score,
        predicted_normalized=predicted,
        gt_normalized=gt,
        gt_present=gt_present,
    )


def test_load_approaches_resolves_three() -> None:
    approaches = approach_data.load_approaches()
    by_key = {approach.key: approach for approach in approaches}
    assert set(by_key) == {"baseline", "arm_a", "arm_b"}
    assert by_key["baseline"].experiment_name == "baseline-regex-dev"
    assert by_key["arm_a"].experiment_name == "arm-a-dev"
    assert by_key["arm_b"].experiment_name == "arm-b-dev"
    assert by_key["arm_b"].reader_model_id  # Arm B reads first, then structures
    assert by_key["arm_a"].reader_model_id is None  # single-shot, no reader


def test_fields_partition_and_labels() -> None:
    assert set(field_meta.FIELD_ORDER) == set(FIELDS)
    assert field_meta.label("seller_name") == "Seller name"
    assert field_meta.group_display("seller_name") == "Seller"
    assert field_meta.group_display("grand_total_amount") == "Totals"
    assert field_meta.german_label("invoice_number")  # non-empty German rendering


def test_parse_field_results_tolerant() -> None:
    payload = {
        "per_field": {
            "seller_name": {
                "english_key": "seller_name",
                "bt_code": "BT-27",
                "field_type": "STRING",
                "outcome": "TP",
                "score": 1.0,
                "predicted_normalized": "ACME GmbH",
                "gt_normalized": "ACME GmbH",
                "gt_present": True,
            },
            "broken": {"english_key": "x"},  # missing keys → skipped, not fatal
        }
    }
    parsed = results.parse_field_results(payload)
    assert len(parsed) == 1
    assert parsed[0].english_key == "seller_name"
    assert parsed[0].outcome == "TP"


def test_pool_metrics_known_example() -> None:
    invoice = [
        _fr("seller_name", "TP", gt_present=True),
        _fr("seller_vat_id", "FN", gt_present=True, score=0.0),
        _fr("invoice_number", "FP", gt_present=False, gt=None, score=0.0),
        _fr("delivery_date", "TN", gt_present=False, predicted=None, gt=None),
    ]
    pooled = metrics.pool_metrics([invoice])
    assert pooled.n_invoices == 1
    assert pooled.overall_f1 == pytest.approx(0.5)  # TP=1, FP=1, FN=1
    assert pooled.spurious_rate == pytest.approx(0.5)  # 1 invented of 2 absent
    assert pooled.presence_f1 == pytest.approx(2 / 3)  # TP=1, FN=1 over present
    assert pooled.group_f1 == pytest.approx(0.0)  # seller group not all-correct


def test_pool_metrics_empty() -> None:
    pooled = metrics.pool_metrics([])
    assert pooled.n_invoices == 0
    assert pooled.overall_f1 == 0.0


def test_last_json_object_and_purpose_summary() -> None:
    body = 'reasoning here\n{"invoice_number": "1", "purpose_summary": "Office supplies"}'
    obj = invoices.last_json_object(body)
    assert obj is not None
    assert obj["invoice_number"] == "1"
    assert invoices.purpose_summary(body) == "Office supplies"
    assert invoices.purpose_summary("no json at all") is None


def test_find_pdf_missing(tmp_path: object) -> None:
    from pathlib import Path

    assert invoices.find_pdf(Path(str(tmp_path)), "does_not_exist") is None


def test_tracking_uri_is_absolute() -> None:
    assert mlflow_store.TRACKING_URI.startswith("sqlite:////")  # four slashes = absolute path


def test_grouped_metric_bar_builds() -> None:
    figure = charts.grouped_metric_bar(["Overall", "Presence"], [("A", "#0E4D45", [0.5, 0.6])])
    assert figure.data  # at least one trace was added


def test_build_value_dataframe_is_unscored_field_value_view() -> None:
    """The live value table covers the 19 scored fields (not purpose_summary), no verdict."""
    frame = field_table.build_value_dataframe(
        {"invoice_number": "R-1", "purpose_summary": "shown elsewhere, not a row"}
    )
    assert len(frame) == len(field_meta.FIELD_ORDER)  # 19 scored fields; summary is not a row
    assert list(frame.columns) == ["Field", "Extracted value", "German"]  # no GT/verdict/score
    values = frame["Extracted value"].tolist()
    assert "R-1" in values  # the extracted value is shown
    assert "—" in values  # missing fields render as an em dash, not blank/None


@skip_if_no_store
def test_load_invoice_runs_smoke() -> None:
    runs = results.load_invoice_runs(approach_data.get_approach("baseline"))
    assert runs  # baseline-regex-dev has runs in the local store
    sample = next(iter(runs.values()))
    assert sample.invoice_id
    assert sample.field_results  # per-field scores were reconstructed from the artifact


def test_heldout_save_draft_persists_repeating_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_draft persists the repeating grids; blank rows drop; round-trips to GroundTruth."""
    from app.data import heldout as heldout_data
    from horus.eval.heldout import HeldoutItem, build_groundtruth_from_json

    # Redirect CORPUS_ROOT so the index-flag refresh cannot touch real private data.
    monkeypatch.setattr(heldout_data, "CORPUS_ROOT", tmp_path)
    item = HeldoutItem(
        id="belege-de-email-001",
        pdf_path=tmp_path / "x.pdf",
        gt_path=tmp_path / "belege-de-email-001.gt.json",
        language="german",
        channel="email",
        verified=False,
    )
    blank_line = dict.fromkeys(heldout_data.repeating_subkeys("line_items"), "")
    heldout_data.save_draft(
        item,
        fields={"invoice_number": "R-1"},
        verified=True,
        vat_breakdown=[
            {
                "category_code": "S",
                "rate_percent": "19 %",
                "taxable_amount": "100,00",
                "tax_amount": "19,00",
            }
        ],
        line_items=[{"line_id": "1", "name": "Beratung", "line_amount": "100,00"}, blank_line],
    )
    gt = build_groundtruth_from_json(item.gt_path)
    assert gt.vat_breakdown is not None
    assert gt.vat_breakdown[0]["rate_percent"].normalized_value == "19"
    # The all-blank second line-item row is dropped (honest absence).
    assert gt.line_items is not None
    assert len(gt.line_items) == 1
    assert gt.line_items[0]["name"].normalized_value == "Beratung"
    assert gt.skonto is None
