"""HORUS evaluation harness — pilot #13's per-field F1 substrate.

This subpackage hosts the eval-harness code for pilot #13 (the first data
loop per `docs/prompts/stages/02-brainstorm.md` v2 §5.5): VLM extraction →
XML-grounded ground truth → per-field F1 + heatmap. Module additions land
incrementally as the 3-PR split progresses:

  - PR(a) — ADR-012 — ground_truth: CII XML → 16-field English-keyed dict.
            Ships `parse_cii_xml`, `GroundTruth`, `GroundTruthField`,
            `FieldSpec`, `FIELDS`, `CII_NAMESPACES`.
  - PR(b) — ADR-013 — scorer: VLM output → predicted dict → per-field F1
            against `GroundTruth`. Ships `score`, `InvoiceFieldScores`,
            `FieldResult`, `preprocess`, `to_predicted_dict`,
            `extract_transcript_body`, `anls`, `nls`.
  - PR(c) — ADR-014 — harness: multi-page rasterizer + (model × invoice) MLflow
            cohort orchestrator. Ships `rasterize_pdf` (this re-export) +
            `run_cohort` + `HarnessRunResult` (re-exported when harness lands).

Public surface (re-exported from `horus.eval.ground_truth`):
"""

from __future__ import annotations

from horus.eval.adapters import extract_transcript_body, preprocess, to_predicted_dict
from horus.eval.anls import anls, nls
from horus.eval.ground_truth import (
    CII_NAMESPACES,
    FIELDS,
    FieldSpec,
    FieldType,
    GroundTruth,
    GroundTruthField,
    parse_cii_xml,
)
from horus.eval.harness import HarnessRunResult, run_cohort
from horus.eval.rasterize import rasterize_pdf
from horus.eval.scorer import FieldResult, InvoiceFieldScores, score

__all__ = [
    "CII_NAMESPACES",
    "FIELDS",
    "FieldResult",
    "FieldSpec",
    "FieldType",
    "GroundTruth",
    "GroundTruthField",
    "HarnessRunResult",
    "InvoiceFieldScores",
    "anls",
    "extract_transcript_body",
    "nls",
    "parse_cii_xml",
    "preprocess",
    "rasterize_pdf",
    "run_cohort",
    "score",
    "to_predicted_dict",
]
