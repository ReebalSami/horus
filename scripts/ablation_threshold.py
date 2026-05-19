"""Threshold-sensitivity ablation — re-score saved transcripts at τ∈{0.3, 0.5, 0.7}.

ADR-014 PR(c) Step 8 evidence. The 182 saved transcripts in
`docs/sources/transcripts-multipage/` are the model outputs from Step 7
(pooled F1 = 0.4908 at the default τ=0.5). This script re-runs the
adapter + scorer pipeline against each transcript at three different
ANLS\\* thresholds without re-invoking any model.

The ablation answers: "how sensitive is the cohort F1 to the τ knob?"

  - Stable F1 across τ → metric is robust; thresholds are interchangeable
    in the literature-defensible range [0.3, 0.7]
  - Volatile F1 across τ → metric is fragile; the choice of τ dominates
    the result and the thesis must explicitly defend τ=0.5

τ only affects STRING fields (seller_name, buyer_name) per ADR-013. MONEY /
DATE / CODE use exact-match-or-bust irrespective of τ. So the ablation
quantifies the precision-vs-recall tradeoff on the 2 STRING fields:

  - τ↓ (e.g., 0.3) → more partial-match TPs → recall up + precision down
  - τ↑ (e.g., 0.7) → only near-exact matches → precision up + recall down

Usage:

    uv run python scripts/ablation_threshold.py
        # ablation against docs/sources/transcripts-multipage/ at default
        # corpus + thresholds {0.3, 0.5, 0.7}

    uv run python scripts/ablation_threshold.py --thresholds 0.2,0.4,0.5,0.6,0.8
        # custom threshold sweep

Refs: ADR-013 (parent scorer ADR), ADR-014 §"Step 8 — threshold-sensitivity
ablation". Pairs with `scripts/inspect_pilot_13.py` (MLflow inspector for
the live run; this script is the offline re-scorer).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from horus.config import EvalConfig
from horus.eval.adapters import preprocess, to_predicted_dict
from horus.eval.harness import (
    _extract_groundtruth_via_facturx,
    _list_paired_invoices,
    _strip_page_separators,
)
from horus.eval.scorer import score

DEFAULT_TRANSCRIPTS_DIR = Path("docs/sources/transcripts-multipage")
DEFAULT_CORPUS_ROOT = Path("data/raw/german/zugferd-corpus")

# Per-transcript header lines:
#   # Multi-page transcript (ADR-014 PR(c))
#   # Model:    <model_id>
#   # Invoice:  <invoice_stem>
#   # Pages:    <N>
#   ...
#   <blank line>
#   ===== PAGE 1 =====
#   ...
_HEADER_LINE_RE = re.compile(r"^# (Model|Invoice):\s+(.+)$")


def _parse_transcript(path: Path) -> tuple[str, str, str]:
    """Parse a saved transcript file.

    Returns:
        ``(model_id, invoice_stem, body)`` where ``body`` is the multi-page
        concat text *with* `===== PAGE N =====` separators (caller strips
        before passing to the adapter).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    model_id: str | None = None
    invoice_stem: str | None = None
    body_start: int | None = None
    for i, line in enumerate(lines):
        m = _HEADER_LINE_RE.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "Model":
                model_id = val
            elif key == "Invoice":
                invoice_stem = val
        # Body starts at the first non-comment, non-empty line.
        if not line.startswith("#") and line.strip() != "" and body_start is None:
            body_start = i
            break
    if model_id is None or invoice_stem is None or body_start is None:
        raise ValueError(f"Transcript {path} missing Model:/Invoice: header or body")
    body = "\n".join(lines[body_start:])
    return model_id, invoice_stem, body


def _aggregate_micro_f1(per_invoice_scores: list) -> float:
    """Pool TP / FP / FN across invoices → micro F1.

    Mirrors `_micro_f1_from_counts` in the harness; reproduced here to avoid
    coupling the ablation to private harness internals.
    """
    tp = fp = fn = 0
    for inv_scores in per_invoice_scores:
        for per_field_outcome in inv_scores.per_field.values():
            outcome = per_field_outcome.outcome
            if outcome == "TP":
                tp += 1
            elif outcome == "FP":
                fp += 1
            elif outcome == "FN":
                fn += 1
            # TN / EXCLUDED don't count toward F1
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _build_gt_cache(corpus_root: Path) -> dict:
    """One-shot: extract GT for every invoice via factur-x.

    Cached so the τ-sweep doesn't re-parse the same XML 3 times per invoice.
    """
    cache: dict = {}
    pairs = _list_paired_invoices(corpus_root)
    print(f"Building GT cache from {len(pairs)} paired invoices...", flush=True)
    for pdf_path, _cii_sidecar in pairs:
        gt = _extract_groundtruth_via_facturx(pdf_path)
        if gt is None:
            print(f"  WARN: {pdf_path.stem} has no factur-x GT; skipping", flush=True)
            continue
        cache[pdf_path.stem] = gt
    print(f"  GT cache: {len(cache)} invoices loaded.", flush=True)
    return cache


def run_ablation(
    *,
    transcripts_dir: Path,
    corpus_root: Path,
    thresholds: list[float],
) -> dict[float, dict[str, list]]:
    """Re-score all transcripts at each threshold.

    Returns:
        ``{threshold: {model_id: list[InvoiceFieldScores]}}`` for downstream
        per-model + cohort aggregation.
    """
    if not transcripts_dir.is_dir():
        raise FileNotFoundError(f"Transcripts dir not found: {transcripts_dir}")
    if not corpus_root.is_dir():
        raise FileNotFoundError(f"Corpus root not found: {corpus_root}")

    transcript_paths = sorted(transcripts_dir.glob("*.txt"))
    print(f"Found {len(transcript_paths)} transcript files in {transcripts_dir}.", flush=True)
    if not transcript_paths:
        raise RuntimeError(f"No transcripts in {transcripts_dir}")

    gt_cache = _build_gt_cache(corpus_root)

    # results[τ][model_id] = list of InvoiceFieldScores
    results: dict[float, dict[str, list]] = {tau: defaultdict(list) for tau in thresholds}

    for tp_idx, tp in enumerate(transcript_paths, 1):
        try:
            model_id, invoice_stem, body = _parse_transcript(tp)
        except ValueError as exc:
            print(f"  [{tp_idx}/{len(transcript_paths)}] SKIP {tp.name}: {exc}", flush=True)
            continue

        gt = gt_cache.get(invoice_stem)
        if gt is None:
            print(
                f"  [{tp_idx}/{len(transcript_paths)}] SKIP {tp.name}: no GT for {invoice_stem!r}",
                flush=True,
            )
            continue

        # Run Layer 1 + Layer 2 ONCE per transcript (model-text → predicted_dict
        # is τ-independent — only the scorer cares about τ).
        scorer_input = _strip_page_separators(body)
        preprocessed = preprocess(scorer_input, model_id)
        predicted_dict = to_predicted_dict(preprocessed, model_id)

        # Score at each threshold. The scorer is fast (per-field comparisons);
        # the slow part is preprocess/to_predicted_dict which we do once.
        for tau in thresholds:
            eval_cfg = EvalConfig(anls_threshold=tau)
            inv_scores = score(
                predicted_dict,
                gt,
                cfg=eval_cfg,
                invoice_id=invoice_stem,
                model_id=model_id,
            )
            results[tau][model_id].append(inv_scores)

        if tp_idx % 25 == 0 or tp_idx == len(transcript_paths):
            print(f"  [{tp_idx}/{len(transcript_paths)}] scored {tp.name}", flush=True)

    return results


def _print_results(results: dict[float, dict[str, list]], thresholds: list[float]) -> None:
    """Tabulate per-model + cohort F1 across thresholds."""
    print()
    print("=" * 110)
    print("Per-model micro_F1 by threshold τ:")
    print(f"{'model':<55}" + "".join(f"  τ={t:.2f}" for t in thresholds) + "    delta(τmax-τmin)")
    print("-" * 110)
    all_models = sorted({m for t in thresholds for m in results[t]})
    for model_id in all_models:
        per_tau_f1 = []
        for tau in thresholds:
            inv_scores = results[tau].get(model_id, [])
            per_tau_f1.append(_aggregate_micro_f1(inv_scores))
        delta = max(per_tau_f1) - min(per_tau_f1)
        bar = "".join(f"  {f:.4f}" for f in per_tau_f1)
        print(f"{model_id:<55}{bar}    {delta:.4f}")

    print()
    print("Cohort pooled micro_F1 by threshold τ:")
    print(f"{'metric':<55}" + "".join(f"  τ={t:.2f}" for t in thresholds))
    print("-" * 95)
    cohort_per_tau = []
    for tau in thresholds:
        all_inv_scores = []
        for inv_list in results[tau].values():
            all_inv_scores.extend(inv_list)
        cohort_per_tau.append(_aggregate_micro_f1(all_inv_scores))
    bar = "".join(f"  {f:.4f}" for f in cohort_per_tau)
    print(f"{'cohort pooled':<55}{bar}")

    print()
    delta_cohort = max(cohort_per_tau) - min(cohort_per_tau)
    print(f"Cohort F1 range across τ ∈ {thresholds}: Δ = {delta_cohort:.4f}")
    if delta_cohort < 0.02:
        print("Conclusion: F1 STABLE across τ — metric is τ-robust in [0.3, 0.7].")
    elif delta_cohort < 0.05:
        print("Conclusion: F1 MODERATELY SENSITIVE to τ — defensible but worth noting in thesis.")
    else:
        print("Conclusion: F1 VOLATILE to τ — thesis must explicitly defend τ=0.5 choice.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ablation_threshold")
    parser.add_argument(
        "--transcripts-dir",
        default=str(DEFAULT_TRANSCRIPTS_DIR),
        help=f"Directory of saved transcripts (default: {DEFAULT_TRANSCRIPTS_DIR})",
    )
    parser.add_argument(
        "--corpus-root",
        default=str(DEFAULT_CORPUS_ROOT),
        help=f"ZUGFeRD corpus root (default: {DEFAULT_CORPUS_ROOT})",
    )
    parser.add_argument(
        "--thresholds",
        default="0.3,0.5,0.7",
        help="Comma-separated list of ANLS thresholds (default: 0.3,0.5,0.7)",
    )
    args = parser.parse_args(argv[1:])

    thresholds = sorted(float(t.strip()) for t in args.thresholds.split(",") if t.strip())
    for tau in thresholds:
        if not 0.0 <= tau <= 1.0:
            print(f"ERROR: threshold {tau} not in [0.0, 1.0]", file=sys.stderr)
            return 2

    results = run_ablation(
        transcripts_dir=Path(args.transcripts_dir),
        corpus_root=Path(args.corpus_root),
        thresholds=thresholds,
    )
    _print_results(results, thresholds)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
