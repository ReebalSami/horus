"""Tests for `scripts/reading_ceiling.py` — HND-3 read-quality diagnostic (ADR-030).

Two tiers:
  - **Pure unit** (run everywhere, incl. CI): surface-form generation, the
    reading-ceiling logic + its `readable ⊇ extracted(TP)` invariant, the
    parser-loss/read-miss classification, and the ADR-027 metric pooling.
  - **Integration** (auto-skip without the corpus): the JSON arm reproduces the
    canonical ADR-029 `json-baseline-metrics.txt` numbers (the determinism
    cross-check), and the free-form arm processes the full 182-tuple archive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus.config import EvalConfig, ExperimentConfig
from horus.eval import adapters_json
from horus.eval.ground_truth import FIELDS, LEGACY_EXPERIMENT_FIELDS, GroundTruth, GroundTruthField
from horus.eval.scorer import score
from horus.eval.transcripts import build_gt_cache

# ADR-022: `scripts/` is a package; `from scripts import ...` resolves via
# pytest's `pythonpath = ["."]`.
from scripts import reading_ceiling as rc
from tests._corpus import TRANSCRIPTS_DIR, skip_if_no_corpus, skip_if_no_fixtures

JSON_TRANSCRIPTS_DIR = Path("docs/sources/transcripts-json-baseline")


# ---------------------------------------------------------------------------
# Helpers — build a full 16-field GroundTruth + a scored TupleResult
# ---------------------------------------------------------------------------


def _make_gt(present: dict[str, str]) -> GroundTruth:
    """Full 16-key GroundTruth; keys in `present` are present-with-value, rest absent."""
    header: dict[str, GroundTruthField] = {}
    for key, spec in FIELDS.items():
        if key in present:
            header[key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=present[key],
                normalized_value=present[key],
                xpath=spec.xpath,
                is_present=True,
            )
        else:
            header[key] = GroundTruthField(
                bt_code=spec.bt_code,
                raw_value=None,
                normalized_value=None,
                xpath=spec.xpath,
                is_present=False,
            )
    return GroundTruth(header=header)


def _make_tuple(
    present: dict[str, str], predicted: dict[str, str | None], raw: str
) -> rc.TupleResult:
    gt = _make_gt(present)
    inv = score(predicted, gt, cfg=EvalConfig(), invoice_id="inv", model_id="m")
    return rc.TupleResult("m", "inv", inv, rc._field_diags(inv, gt, raw))


# ---------------------------------------------------------------------------
# Surface-form generation
# ---------------------------------------------------------------------------


def test_group_thousands() -> None:
    assert rc._group_thousands("1234", ".") == "1.234"
    assert rc._group_thousands("1234567", ".") == "1.234.567"
    assert rc._group_thousands("12", ".") == "12"
    assert rc._group_thousands("999", ",") == "999"


def test_money_surface_forms_covers_locales() -> None:
    forms = rc._money_surface_forms("1234.56")
    assert "1234.56" in forms  # canonical
    assert "1234,56" in forms  # German, no thousands
    assert "1.234,56" in forms  # German thousands
    assert "1,234.56" in forms  # US thousands


def test_money_surface_forms_negative_and_no_frac() -> None:
    assert "-529.87" in rc._money_surface_forms("-529.87")
    assert "-529,87" in rc._money_surface_forms("-529.87")


def test_date_surface_forms_german_and_iso() -> None:
    forms = rc._date_surface_forms("2018-03-05")
    assert "2018-03-05" in forms  # ISO
    assert "05.03.2018" in forms  # German padded
    assert "5.3.2018" in forms  # German unpadded
    assert "05/03/2018" in forms


# ---------------------------------------------------------------------------
# _value_readable
# ---------------------------------------------------------------------------


def _readable(gt_field: GroundTruthField, field_type: str, raw: str) -> bool:
    import re
    import unicodedata

    raw_nfc_lower = unicodedata.normalize("NFC", raw).lower()
    raw_despaced = re.sub(r"\s+", "", raw_nfc_lower)
    return rc._value_readable(gt_field, field_type, raw_nfc_lower, raw_despaced)  # type: ignore[arg-type]


def _gt_field(value: str) -> GroundTruthField:
    return GroundTruthField(
        bt_code="BT-x", raw_value=value, normalized_value=value, xpath="/x", is_present=True
    )


def test_value_readable_string_case_insensitive() -> None:
    assert _readable(_gt_field("Lieferant GmbH"), "STRING", "... lieferant gmbh ...")
    assert not _readable(_gt_field("Lieferant GmbH"), "STRING", "no such name here")


def test_value_readable_money_german_format() -> None:
    # GT canonical 529.87; raw has the German rendering → readable via surface form.
    assert _readable(_gt_field("529.87"), "MONEY", "Bruttosumme 529,87 EUR")
    assert _readable(_gt_field("1234.56"), "MONEY", "Summe: 1.234,56")


def test_value_readable_code_despaced() -> None:
    # Spaced VAT id in raw text matches the despaced surface form.
    assert _readable(_gt_field("DE123456789"), "CODE", "USt-IdNr.: DE 123 456 789")


# ---------------------------------------------------------------------------
# _field_diags + the readable ⊇ extracted invariant
# ---------------------------------------------------------------------------


def test_field_diags_classifies_tp_parserloss_readmiss() -> None:
    tr = _make_tuple(
        present={
            "seller_name": "Lieferant GmbH",  # TP (extracted)
            "invoice_number": "471102",  # FN but value in raw -> parser-loss
            "buyer_vat_id": "DE999999999",  # FN and value NOT in raw -> read-miss
        },
        predicted={"seller_name": "Lieferant GmbH"},  # others -> None
        raw="Lieferant GmbH  Rechnungsnummer 471102",
    )
    d = tr.field_diags
    assert d["seller_name"].is_tp and d["seller_name"].readable
    assert (not d["invoice_number"].is_tp) and d["invoice_number"].readable  # parser-loss
    assert (not d["buyer_vat_id"].is_tp) and (not d["buyer_vat_id"].readable)  # read-miss


def test_field_diags_tp_is_always_readable_even_if_surface_absent() -> None:
    """The `readable ⊇ extracted(TP)` invariant: a TP counts as readable by construction."""
    tr = _make_tuple(
        present={"seller_name": "X GmbH"},
        predicted={"seller_name": "X GmbH"},
        raw="",  # empty raw text — no surface form present
    )
    assert tr.field_diags["seller_name"].is_tp
    assert tr.field_diags["seller_name"].readable


def test_field_diags_absent_gt_not_counted() -> None:
    """Absent-GT fields are never `gt_present_content` (excluded from the ceiling)."""
    tr = _make_tuple(present={"seller_name": "X GmbH"}, predicted={}, raw="")
    assert tr.field_diags["buyer_name"].gt_present_content is False


# ---------------------------------------------------------------------------
# _ceiling_agg
# ---------------------------------------------------------------------------


def test_ceiling_agg_counts_and_invariants() -> None:
    tr = _make_tuple(
        present={
            "seller_name": "Lieferant GmbH",  # TP
            "invoice_number": "471102",  # parser-loss
            "buyer_vat_id": "DE999999999",  # read-miss
        },
        predicted={"seller_name": "Lieferant GmbH"},
        raw="Lieferant GmbH 471102",
    )
    agg = rc._ceiling_agg([tr])
    assert agg.n_present == 3
    assert agg.n_extracted == 1
    assert agg.n_readable == 2
    assert agg.n_parser_loss == 1
    assert agg.n_read_miss == 1
    # Structural invariants.
    assert agg.n_readable == agg.n_extracted + agg.n_parser_loss
    assert agg.n_present == agg.n_readable + agg.n_read_miss


def test_ceiling_agg_money_only_filter() -> None:
    tr = _make_tuple(
        present={"seller_name": "X GmbH", "grand_total_amount": "529.87"},
        predicted={"seller_name": "X GmbH"},
        raw="X GmbH Bruttosumme 529,87",
    )
    money = rc._ceiling_agg([tr], money_only=True)
    assert money.n_present == 1  # only grand_total_amount is MONEY
    assert money.n_parser_loss == 1  # 529,87 readable but not extracted
    assert money.n_extracted == 0


# ---------------------------------------------------------------------------
# _extended_metrics
# ---------------------------------------------------------------------------


def test_extended_metrics_perfect_extraction() -> None:
    tr = _make_tuple(
        present={"seller_name": "X GmbH", "invoice_number": "471102"},
        predicted={"seller_name": "X GmbH", "invoice_number": "471102"},
        raw="X GmbH 471102",
    )
    em = rc._extended_metrics([tr])
    assert em.n_inv == 1
    assert em.mean_micro_f1 == pytest.approx(1.0)
    assert em.presence_f1 == pytest.approx(1.0)
    assert em.spurious == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Integration — determinism cross-check + full free-form archive
# ---------------------------------------------------------------------------


@skip_if_no_corpus
def test_json_arm_reproduces_baseline_metrics() -> None:
    """The JSON arm MUST reproduce docs/sources/json-baseline-metrics.txt exactly.

    ADR-037: scores the frozen 16-field `LEGACY_EXPERIMENT_FIELDS`. The committed
    `json-baseline-metrics.txt` is the ADR-029 milestone archive (16-field); the
    ADR-035 schema extension (16 → 19) must NOT shift it — the JSON-baseline
    transcripts were produced by models prompted for 16 fields, so scoring them
    against the 3 new fields would be a meaningless hybrid. The new fields are
    evaluated on the structurer arms going forward, not retroactively here.
    """
    cfg = ExperimentConfig.from_yaml(["configs/pilot-13.yaml", "configs/json-baseline.yaml"])
    assert cfg.cohort is not None
    gt_cache = build_gt_cache(cfg.cohort.corpus_root)
    results = rc._process_dir(
        JSON_TRANSCRIPTS_DIR,
        adapters_json,
        gt_cache,
        cfg.eval or EvalConfig(),
        fields=LEGACY_EXPERIMENT_FIELDS,
    )
    assert len(results) == 18, "3 JSON-capable models × 6 invoices = 18 tuples"
    ok, lines = rc._determinism_check(results)
    assert ok, "JSON arm drifted from json-baseline-metrics.txt:\n" + "\n".join(lines)


@skip_if_no_fixtures
def test_freeform_arm_processes_full_archive() -> None:
    """The free-form arm scores the full 182-tuple archive; ceiling ≥ extracted."""
    from horus.eval import adapters

    cfg = ExperimentConfig.from_yaml(["configs/pilot-13.yaml"])
    assert cfg.cohort is not None
    gt_cache = build_gt_cache(cfg.cohort.corpus_root)
    results = rc._process_dir(TRANSCRIPTS_DIR, adapters, gt_cache, cfg.eval or EvalConfig())
    assert len(results) == 182, "7 models × 26 invoices = 182 tuples"
    assert len({r.model_id for r in results}) == 7
    agg = rc._ceiling_agg(results)
    # The core invariant must hold cohort-wide: a parser cannot extract more than
    # the model emitted.
    assert agg.n_readable >= agg.n_extracted
