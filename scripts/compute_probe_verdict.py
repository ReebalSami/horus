"""compute_probe_verdict.py — orchestrate ADR-019 W3.2 verdict matrix from rescore output.

Combines per-arm rescore output (via :mod:`scripts.rescore`) into per-model
``ModelScore`` records, feeds them to :func:`horus.eval.probe_verdict.compute_verdict_matrix`,
and renders the 2 × 2 verdict matrix as a markdown table.

Usage:

    uv run python scripts/compute_probe_verdict.py \\
        --arm-a-transcripts docs/sources/transcripts-structured-probe-uniform \\
        --arm-b-transcripts docs/sources/transcripts-structured-probe-native-json \\
        --corpus-root data/raw/german/zugferd-corpus \\
        --output eval/probe-verdict-matrix.md

Pipeline (per ADR-019 Phase 5):

    1. Load the fixed JSON adapter (``horus.eval.adapters_json``).
    2. For each arm: walk transcripts, parse per-page, score against GT,
       compute (json_validity, canonical_keys, micro_f1) per (model, arm).
    3. Build per-model ``ModelScore`` (arm_a, arm_b).
    4. Call ``compute_verdict_matrix(per_model_scores)`` → 4-cell matrix.
    5. Render markdown table to stdout / --output file.

The output table is the load-bearing artefact for the ADR-018 amendment
(forthcoming in Phase 6 — ADR-021 will ratify the dual-verdict surface).

Refs: ADR-019 Phase 4 + Phase 5 (this script's ratifying sections),
ADR-018 (parent probe), ADR-021 (forthcoming — verdict matrix
ratification), :mod:`horus.eval.probe_verdict` (the matrix engine),
:mod:`scripts.rescore` (the per-arm rescore engine).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import ModuleType

from horus.eval.probe_verdict import (
    DEFAULT_PALIGEMMA_MODEL_ID,
    CellVerdict,
    ModelArmScore,
    ModelScore,
    VerdictMatrix,
    compute_verdict_matrix,
)

# scripts/ is not a package — load sibling modules via sys.path injection.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rescore  # noqa: E402 — sibling module via SCRIPTS_DIR path injection


def _build_per_model_arm_score(
    *,
    arm_results: dict[str, list],
    baseline_module: ModuleType,
    arm_transcripts_dir: Path,
) -> dict[str, ModelArmScore]:
    """Build ``{model_id: ModelArmScore}`` for one arm.

    Inputs:

      - ``arm_results``: ``{model_id: list[InvoiceFieldScores]}`` from
        :func:`rescore.rescore_transcripts` at one threshold (we pick τ=0.5).
      - ``baseline_module``: the fixed adapter module (``horus.eval.adapters_json``).
      - ``arm_transcripts_dir``: needed to re-extract the predicted_dict shape
        for ``canonical_keys`` (count of non-None values in predicted_dict)
        and ``json_validity`` (canonical_keys > 0).

    For each model, computes:

      - ``json_validity``: True iff the multipage adapter recovered ≥ 1
        non-None value (i.e., at least one page produced parseable JSON
        with at least one canonical key).
      - ``canonical_keys``: count of non-None values in the predicted_dict.
      - ``micro_f1``: pooled micro F1 across the invoice's per-field
        outcomes (from ``rescore._aggregate_micro_f1``).

    Returns:
        dict mapping model_id → ModelArmScore.
    """
    per_model_score: dict[str, ModelArmScore] = {}

    # Walk transcripts once more to extract per-(model, arm) predicted_dicts
    # for canonical_keys + json_validity. We re-parse using the same fixed
    # adapter to ensure consistency with the rescore.
    transcripts = sorted(arm_transcripts_dir.glob("*.txt"))
    for tp in transcripts:
        try:
            model_id, _invoice_stem, body = rescore._parse_transcript(tp)
        except ValueError:
            continue
        per_page_texts = rescore._split_per_page_texts(body)
        predicted_dict = baseline_module.to_predicted_dict_multipage(per_page_texts, model_id)
        canonical_keys = sum(1 for v in predicted_dict.values() if v is not None)
        json_validity = canonical_keys > 0

        # Pull the per-invoice F1 from arm_results.
        inv_scores_list = arm_results.get(model_id, [])
        if not inv_scores_list:
            micro_f1 = 0.0
        else:
            micro_f1 = rescore._aggregate_micro_f1(inv_scores_list)

        per_model_score[model_id] = ModelArmScore(
            json_validity=json_validity,
            canonical_keys=canonical_keys,
            micro_f1=micro_f1,
        )

    return per_model_score


def _build_per_model_scores(
    arm_a_per_model: dict[str, ModelArmScore],
    arm_b_per_model: dict[str, ModelArmScore],
) -> dict[str, ModelScore]:
    """Combine per-arm scores into ``{model_id: ModelScore}`` for the matrix."""
    all_models = set(arm_a_per_model.keys()) | set(arm_b_per_model.keys())
    return {
        model_id: ModelScore(
            model_id=model_id,
            arm_a=arm_a_per_model.get(model_id),
            arm_b=arm_b_per_model.get(model_id),
        )
        for model_id in all_models
    }


def _render_cell_summary(cell: CellVerdict) -> str:
    """Render one cell as a compact ``<verdict> (n_passing of n_total)`` string."""
    return f"{cell.verdict} ({cell.n_passing} of {cell.n_total})"


def _render_per_model_table(
    per_model_scores: dict[str, ModelScore],
    *,
    paligemma_model_id: str,
) -> str:
    """Render the per-(model, arm) breakdown table.

    Per-row format:

        | model | A.json | A.keys | A.F1 | B.json | B.keys | B.F1 | flagged |

    Sorted alphabetically by model_id for determinism.
    """
    lines: list[str] = []
    lines.append(
        "| Model | Arm A: JSON | Arm A: keys/16 | Arm A: F1 | "
        "Arm B: JSON | Arm B: keys/16 | Arm B: F1 | Note |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|"
    )
    for model_id in sorted(per_model_scores.keys()):
        score = per_model_scores[model_id]
        flag = " (base-VLM; N-of-6 excluded)" if model_id == paligemma_model_id else ""
        a = score.arm_a
        b = score.arm_b
        a_json = "✓" if (a is not None and a.json_validity) else "✗"
        a_keys = f"{a.canonical_keys}" if a is not None else "-"
        a_f1 = f"{a.micro_f1:.4f}" if a is not None else "-"
        b_json = "✓" if (b is not None and b.json_validity) else "✗"
        b_keys = f"{b.canonical_keys}" if b is not None else "-"
        b_f1 = f"{b.micro_f1:.4f}" if b is not None else "-"
        lines.append(
            f"| `{model_id}` | {a_json} | {a_keys} | {a_f1} | "
            f"{b_json} | {b_keys} | {b_f1} |{flag} |"
        )
    return "\n".join(lines)


def _render_matrix_table(matrix: VerdictMatrix) -> str:
    """Render the 2 × 2 verdict matrix as a markdown table."""
    lines: list[str] = []
    lines.append("| Denominator | Pre-registered threshold | Amended threshold (F1≥0.1) |")
    lines.append("|---|---|---|")
    lines.append(
        f"| **N of 7** (PaliGemma counted) | "
        f"{_render_cell_summary(matrix.pre_registered_n_of_7)} | "
        f"{_render_cell_summary(matrix.amended_n_of_7)} |"
    )
    lines.append(
        f"| **N of 6** (PaliGemma flagged) | "
        f"{_render_cell_summary(matrix.pre_registered_n_of_6)} | "
        f"{_render_cell_summary(matrix.amended_n_of_6)} |"
    )
    return "\n".join(lines)


def _render_cell_models(label: str, cell: CellVerdict) -> str:
    """Render the passing/failing-models list for one cell."""
    lines: list[str] = []
    lines.append(f"### {label}")
    lines.append("")
    lines.append(f"- Verdict: **{cell.verdict}** ({cell.n_passing} of {cell.n_total})")
    if cell.passing_models:
        lines.append(f"- Passing: {', '.join(f'`{m}`' for m in cell.passing_models)}")
    else:
        lines.append("- Passing: (none)")
    if cell.failing_models:
        lines.append(f"- Failing: {', '.join(f'`{m}`' for m in cell.failing_models)}")
    else:
        lines.append("- Failing: (none)")
    return "\n".join(lines)


def render_full_report(
    per_model_scores: dict[str, ModelScore],
    matrix: VerdictMatrix,
    *,
    paligemma_model_id: str,
    arm_a_transcripts: Path,
    arm_b_transcripts: Path,
) -> str:
    """Render the full markdown verdict report."""
    lines: list[str] = []
    lines.append("# ADR-019 W3.2 — Structured-output probe verdict matrix")
    lines.append("")
    lines.append(
        "Generated by `scripts/compute_probe_verdict.py` from the FIXED JSON adapter "
        "(`horus.eval.adapters_json`) rescoring the saved probe transcripts against the "
        "XML-grounded F1 ground-truth (`horus.eval.harness._extract_groundtruth_via_facturx`). "
        "Replaces the buggy DEFER #54 verdict committed at `d01afd1` per ADR-019."
    )
    lines.append("")
    lines.append(f"**Arm A transcripts**: `{arm_a_transcripts}`")
    lines.append("")
    lines.append(f"**Arm B transcripts**: `{arm_b_transcripts}`")
    lines.append("")
    lines.append("## Per-model breakdown (per arm)")
    lines.append("")
    lines.append(
        "Combined-max-per-arm rule (ADR-018): a model passes if EITHER arm "
        "satisfies the threshold."
    )
    lines.append("")
    lines.append(_render_per_model_table(per_model_scores, paligemma_model_id=paligemma_model_id))
    lines.append("")
    lines.append("## Verdict matrix (2 × 2)")
    lines.append("")
    lines.append(_render_matrix_table(matrix))
    lines.append("")
    lines.append(
        "Pre-registered threshold per ADR-018: `(json_validity=True ∧ canonical_keys≥12)`. "
        "Amended threshold per ADR-019 §B4: adds `micro_F1≥0.1` to defend against schema-mimicry."
    )
    lines.append("")
    lines.append("## Cell details")
    lines.append("")
    lines.append(
        _render_cell_models("Pre-registered × N of 7 (cell A)", matrix.pre_registered_n_of_7)
    )
    lines.append("")
    lines.append(_render_cell_models("Amended × N of 7 (cell B)", matrix.amended_n_of_7))
    lines.append("")
    lines.append(
        _render_cell_models("Pre-registered × N of 6 (cell C)", matrix.pre_registered_n_of_6)
    )
    lines.append("")
    lines.append(_render_cell_models("Amended × N of 6 (cell D)", matrix.amended_n_of_6))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="compute_probe_verdict")
    parser.add_argument(
        "--arm-a-transcripts",
        default="docs/sources/transcripts-structured-probe-uniform",
        help="Arm A (uniform JSON prompt) transcripts directory.",
    )
    parser.add_argument(
        "--arm-b-transcripts",
        default="docs/sources/transcripts-structured-probe-native-json",
        help="Arm B (native task prefix + JSON suffix) transcripts directory.",
    )
    parser.add_argument(
        "--corpus-root",
        default="data/raw/german/zugferd-corpus",
        help="ZUGFeRD corpus root (for factur-x GT extraction).",
    )
    parser.add_argument(
        "--baseline-adapter-module",
        default="horus.eval.adapters_json",
        help=(
            "Fixed adapter module to rescore against (default: horus.eval.adapters_json; "
            "the ADR-019 W3.1 fixed JSON adapter)."
        ),
    )
    parser.add_argument(
        "--paligemma-model-id",
        default=DEFAULT_PALIGEMMA_MODEL_ID,
        help=(
            f"Model ID to flag out of the N-of-6 cells (default: {DEFAULT_PALIGEMMA_MODEL_ID}). "
            "Per ADR-019 §B8: PaliGemma2 is a base VLM (HF model card knowable at probe-"
            "design time per ADR-009 §smoke); inclusion in the 7-of-7 denominator was a "
            "pre-registration error. The N-of-6 cells exclude this model from BOTH "
            "passing and failing lists."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional: write the markdown verdict report to this file. When omitted, "
            "the report is printed to stdout."
        ),
    )
    args = parser.parse_args(argv[1:])

    baseline_module = importlib.import_module(args.baseline_adapter_module)
    pair = rescore.load_adapter_pair(
        candidate_path=Path("/no/such/file.py"),  # stability mode: candidate = baseline
        baseline_module=baseline_module,
    )

    arm_a_path = Path(args.arm_a_transcripts)
    arm_b_path = Path(args.arm_b_transcripts)
    corpus_root = Path(args.corpus_root)

    print("=" * 80)
    print(f"Computing verdict matrix using baseline={args.baseline_adapter_module}")
    print(f"  Arm A: {arm_a_path}")
    print(f"  Arm B: {arm_b_path}")
    print(f"  Corpus: {corpus_root}")
    print(f"  PaliGemma flag ID: {args.paligemma_model_id}")
    print("=" * 80)
    print()

    print("--- Rescoring Arm A ---")
    arm_a_results = rescore.rescore_transcripts(
        transcripts_dir=arm_a_path,
        corpus_root=corpus_root,
        thresholds=[0.5],
        adapters_pair=pair,
    )

    print("\n--- Rescoring Arm B ---")
    arm_b_results = rescore.rescore_transcripts(
        transcripts_dir=arm_b_path,
        corpus_root=corpus_root,
        thresholds=[0.5],
        adapters_pair=pair,
    )

    arm_a_per_model = _build_per_model_arm_score(
        arm_results=arm_a_results["baseline"][0.5],
        baseline_module=baseline_module,
        arm_transcripts_dir=arm_a_path,
    )
    arm_b_per_model = _build_per_model_arm_score(
        arm_results=arm_b_results["baseline"][0.5],
        baseline_module=baseline_module,
        arm_transcripts_dir=arm_b_path,
    )

    per_model_scores = _build_per_model_scores(arm_a_per_model, arm_b_per_model)

    matrix = compute_verdict_matrix(
        per_model_scores,
        paligemma_model_id=args.paligemma_model_id,
    )

    report = render_full_report(
        per_model_scores,
        matrix,
        paligemma_model_id=args.paligemma_model_id,
        arm_a_transcripts=arm_a_path,
        arm_b_transcripts=arm_b_path,
    )

    if args.output is None:
        print()
        print(report)
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"\nVerdict report written to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
