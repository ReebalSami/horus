"""rescore.py — offline re-scoring of saved VLM transcripts (ADR-014 + ADR-016).

Re-runs the adapter (Layer 1 preprocess + Layer 2 to_predicted_dict) + scorer
pipeline against saved transcripts WITHOUT invoking any VLM. Two orthogonal
modes compose freely:

  1. **τ-sweep** (legacy mode from `ablation_threshold.py`, ADR-014 Step 8):
     score each transcript at multiple ANLS* thresholds. Quantifies the
     precision-vs-recall tradeoff on STRING fields (seller_name, buyer_name).
     τ only affects STRING — MONEY / DATE / CODE use exact-match-or-bust.

  2. **Adapter A/B** (new in ADR-016, issue #51): score each transcript with
     the canonical baseline `adapters.py` AND a candidate `adapters_candidate.py`
     side-by-side; emit per-field Δ table + cohort Δ. Enables the ~5-15 second
     dev iteration loop on adapter heuristics. Per Google "Rules of Machine
     Learning" §24 ("Measure the delta between models") and MLflow's canonical
     two-runs comparison pattern.

  3. **Stability self-check** (Google §24 sanity test): when the candidate
     file is missing OR byte-identical to the baseline, runs baseline-vs-baseline
     and asserts Δ = 0. Catches non-determinism bugs before they cause silent F1
     drift in the dev loop.

  4. **Opt-in MLflow logging** (ADR-016): with `--log-mlflow`, opens 2 nested
     MLflow runs under an `adapter-iterate-<timestamp>` parent, tagged
     `adapter=baseline` / `adapter=candidate`, with per-field metrics + the diff
     hash between baseline and candidate. The default mode is MLflow-free for
     speed; opt-in keeps the canonical audit trail when promoting a candidate.

Usage:

    # τ-only ablation (legacy ADR-014 behaviour preserved):
    uv run python scripts/rescore.py --thresholds 0.3,0.5,0.7

    # Adapter A/B (new; reads from src/horus/eval/adapters_candidate.py):
    uv run python scripts/rescore.py

    # A/B + opt-in MLflow audit trail when promoting a candidate:
    uv run python scripts/rescore.py --log-mlflow

    # Dev loop over a smaller transcript dir (paired with pilot-13-dev.yaml):
    uv run python scripts/rescore.py \\
        --transcripts-dir docs/sources/transcripts-multipage-dev

Refs: ADR-016 (this script's ratifying ADR — forthcoming, row reserved in
docs/decisions/INDEX.md), ADR-014 §Step 8 (parent τ-ablation), ADR-013
(parent scorer ADR), Google "Rules of Machine Learning" §24, NeurIPS Paper
Checklist 2024/2025. Pairs with `scripts/inspect_pilot_13.py` (MLflow
inspector for the slow path; this script is the fast-path offline re-scorer).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import importlib.util
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from horus.config import EvalConfig
from horus.eval import adapters as baseline_adapters
from horus.eval.harness import (
    _extract_groundtruth_via_facturx,
    _list_paired_invoices,
    _strip_page_separators,
)
from horus.eval.scorer import score

DEFAULT_TRANSCRIPTS_DIR = Path("docs/sources/transcripts-multipage")
DEFAULT_CORPUS_ROOT = Path("data/raw/german/zugferd-corpus")
DEFAULT_CANDIDATE_PATH = Path("src/horus/eval/adapters_candidate.py")


def _csv_paths(value: str) -> list[str]:
    """Argparse type converter for comma-separated YAML path lists.

    Supports the multi-file YAML composition pattern (ADR-016): a single path
    OR `base.yaml,overlay.yaml` (deep-merged left-to-right; later wins). Used
    by `--cfg` to mirror the pattern documented in `configs/README.md`.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclasses.dataclass(frozen=True)
class AdapterPair:
    """A loaded baseline + candidate adapter pair for A/B re-scoring.

    The `is_identical` flag flips True when the candidate file is missing
    OR byte-identical to the baseline; in that case `candidate` IS the
    baseline (same module reference), and the run becomes a stability
    self-check (Δ should be 0; non-zero signals a non-determinism bug).
    """

    baseline: ModuleType
    candidate: ModuleType
    is_identical: bool
    baseline_path: Path
    candidate_path: Path
    diff_sha256: str  # SHA-256 of the candidate file's content; "" if identical


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


def load_adapter_pair(
    *,
    candidate_path: Path = DEFAULT_CANDIDATE_PATH,
) -> AdapterPair:
    """Load the baseline + candidate adapter modules into an `AdapterPair`.

    The baseline is always `horus.eval.adapters` (the canonical version on
    `main`). The candidate is loaded from `candidate_path` via
    `importlib.util.spec_from_file_location` (the canonical
    load-by-string-path pattern per Python stdlib docs).

    Stability semantics (Google Rules of ML §24 self-test):

      - Candidate file MISSING → `AdapterPair(candidate=baseline, is_identical=True,
        diff_sha256="")`. The run becomes baseline-vs-baseline; Δ must be 0.
      - Candidate file PRESENT but byte-identical to baseline → same result
        (is_identical=True, diff_sha256="").
      - Candidate file PRESENT and differs → loads candidate module;
        `is_identical=False`; `diff_sha256` is the SHA-256 of the candidate
        file's bytes (for MLflow audit-trail tagging when --log-mlflow).

    Validation: the loaded candidate module MUST expose `preprocess` and
    `to_predicted_dict` callables matching the baseline API. Raises ValueError
    if either is missing or not callable.
    """
    baseline_path = Path(baseline_adapters.__file__).resolve()
    candidate_abs = candidate_path.resolve() if candidate_path.exists() else candidate_path

    if not candidate_abs.exists():
        return AdapterPair(
            baseline=baseline_adapters,
            candidate=baseline_adapters,
            is_identical=True,
            baseline_path=baseline_path,
            candidate_path=candidate_path,
            diff_sha256="",
        )

    baseline_bytes = baseline_path.read_bytes()
    candidate_bytes = candidate_abs.read_bytes()
    if baseline_bytes == candidate_bytes:
        return AdapterPair(
            baseline=baseline_adapters,
            candidate=baseline_adapters,
            is_identical=True,
            baseline_path=baseline_path,
            candidate_path=candidate_abs,
            diff_sha256="",
        )

    # Candidate differs — load it as a separate module via importlib.
    spec = importlib.util.spec_from_file_location("horus.eval.adapters_candidate", candidate_abs)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"importlib could not build a spec for {candidate_abs}; "
            "is the file a valid Python module?"
        )
    candidate_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_mod)

    # Contract check: candidate must expose the public adapter API.
    for fn_name in ("preprocess", "to_predicted_dict"):
        fn = getattr(candidate_mod, fn_name, None)
        if not callable(fn):
            raise ValueError(
                f"Candidate adapter at {candidate_abs} is missing required "
                f"public callable {fn_name!r}. Candidate adapters must mirror "
                f"the `horus.eval.adapters` public API: "
                f"preprocess(raw: str, model_id: str) -> str + "
                f"to_predicted_dict(raw: str, model_id: str) -> dict."
            )

    diff_sha256 = hashlib.sha256(candidate_bytes).hexdigest()
    return AdapterPair(
        baseline=baseline_adapters,
        candidate=candidate_mod,
        is_identical=False,
        baseline_path=baseline_path,
        candidate_path=candidate_abs,
        diff_sha256=diff_sha256,
    )


def _per_field_outcome_counts(
    per_model_scores: dict[str, list],
) -> dict[str, dict[str, dict[str, int]]]:
    """Count {TP, FP, FN, TN, EXCLUDED} per (model_id, field_key) across invoices.

    Returns:
        ``{model_id: {field_key: {"TP": int, "FP": int, "FN": int, "TN": int, "EXCLUDED": int}}}``
        Used to compute per-field Δ between baseline and candidate in A/B mode.
    """
    counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "EXCLUDED": 0})
    )
    for model_id, inv_scores_list in per_model_scores.items():
        for inv_scores in inv_scores_list:
            for field_key, per_field_outcome in inv_scores.per_field.items():
                outcome = per_field_outcome.outcome
                counts[model_id][field_key][outcome] += 1
    # Convert defaultdicts to plain dicts for cleaner JSON serialization.
    return {m: {f: dict(o) for f, o in field_dict.items()} for m, field_dict in counts.items()}


def rescore_transcripts(
    *,
    transcripts_dir: Path,
    corpus_root: Path,
    thresholds: list[float],
    adapters_pair: AdapterPair,
) -> dict[str, dict[float, dict[str, list]]]:
    """Re-score all transcripts with both baseline and candidate adapters, at each threshold.

    Returns:
        ``{adapter_label: {threshold: {model_id: list[InvoiceFieldScores]}}}``
        with `adapter_label` in {"baseline", "candidate"}.

    If `adapters_pair.is_identical` is True, the "candidate" key holds the same
    scores as "baseline" (the run is a stability self-check; Δ should be 0).

    Performance: preprocess + to_predicted_dict run TWICE per transcript (once
    per adapter), once each — the scorer then runs `n_thresholds` times against
    each predicted_dict (cheap per-field comparisons). For the dev cohort
    (3 invoices × 1 model × 2 adapters × 1 threshold) this is ~3-5 seconds.
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

    # results[adapter_label][τ][model_id] = list of InvoiceFieldScores
    results: dict[str, dict[float, dict[str, list]]] = {
        "baseline": {tau: defaultdict(list) for tau in thresholds},
        "candidate": {tau: defaultdict(list) for tau in thresholds},
    }

    adapter_funcs: dict[str, tuple[Callable[[str, str], str], Callable[[str, str], dict]]] = {
        "baseline": (
            adapters_pair.baseline.preprocess,
            adapters_pair.baseline.to_predicted_dict,
        ),
        "candidate": (
            adapters_pair.candidate.preprocess,
            adapters_pair.candidate.to_predicted_dict,
        ),
    }

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

        scorer_input = _strip_page_separators(body)

        for adapter_label, (preprocess_fn, to_predicted_dict_fn) in adapter_funcs.items():
            preprocessed = preprocess_fn(scorer_input, model_id)
            predicted_dict = to_predicted_dict_fn(preprocessed, model_id)

            for tau in thresholds:
                eval_cfg = EvalConfig(anls_threshold=tau)
                inv_scores = score(
                    predicted_dict,
                    gt,
                    cfg=eval_cfg,
                    invoice_id=invoice_stem,
                    model_id=model_id,
                )
                results[adapter_label][tau][model_id].append(inv_scores)

        if tp_idx % 25 == 0 or tp_idx == len(transcript_paths):
            print(f"  [{tp_idx}/{len(transcript_paths)}] scored {tp.name}", flush=True)

    return results


def _print_threshold_table(
    results_per_tau: dict[float, dict[str, list]],
    thresholds: list[float],
    *,
    title: str,
) -> tuple[list[str], list[float]]:
    """Tabulate per-model + cohort F1 across thresholds for one adapter.

    Returns:
        ``(model_ids_sorted, cohort_f1_per_tau)`` for downstream A/B Δ computation.
    """
    print()
    print("=" * 110)
    print(title)
    print(f"{'model':<55}" + "".join(f"  τ={t:.2f}" for t in thresholds) + "    Δ(τmax-τmin)")
    print("-" * 110)
    all_models = sorted({m for t in thresholds for m in results_per_tau[t]})
    for model_id in all_models:
        per_tau_f1 = []
        for tau in thresholds:
            inv_scores = results_per_tau[tau].get(model_id, [])
            per_tau_f1.append(_aggregate_micro_f1(inv_scores))
        delta = max(per_tau_f1) - min(per_tau_f1) if per_tau_f1 else 0.0
        bar = "".join(f"  {f:.4f}" for f in per_tau_f1)
        print(f"{model_id:<55}{bar}    {delta:.4f}")

    print()
    print("Cohort pooled micro_F1:")
    print(f"{'metric':<55}" + "".join(f"  τ={t:.2f}" for t in thresholds))
    print("-" * 95)
    cohort_per_tau = []
    for tau in thresholds:
        all_inv_scores: list = []
        for inv_list in results_per_tau[tau].values():
            all_inv_scores.extend(inv_list)
        cohort_per_tau.append(_aggregate_micro_f1(all_inv_scores))
    bar = "".join(f"  {f:.4f}" for f in cohort_per_tau)
    print(f"{'cohort pooled':<55}{bar}")
    return all_models, cohort_per_tau


def _print_ab_delta_table(
    baseline_results: dict[float, dict[str, list]],
    candidate_results: dict[float, dict[str, list]],
    thresholds: list[float],
    *,
    pair: AdapterPair,
) -> None:
    """Print the baseline-vs-candidate per-field Δ table at the primary threshold.

    Uses the first threshold (typically 0.5) as the "headline" for the A/B
    comparison. Per Google Rules of ML §24 ("Measure the delta between models").
    """
    primary_tau = thresholds[0] if thresholds else 0.5

    print()
    print("=" * 110)
    print(f"Adapter A/B Δ at τ={primary_tau:.2f}")
    if pair.is_identical:
        reason = "missing" if not pair.candidate_path.exists() else "byte-identical to baseline"
        print(
            f"  STABILITY MODE: candidate {reason}; "
            f"running baseline-vs-baseline (Google §24 sanity check)"
        )
    else:
        print(f"  baseline:   {pair.baseline_path}")
        print(f"  candidate:  {pair.candidate_path}")
        print(f"  candidate SHA-256: {pair.diff_sha256[:16]}…")
    print("-" * 110)

    baseline_counts = _per_field_outcome_counts(baseline_results[primary_tau])
    candidate_counts = _per_field_outcome_counts(candidate_results[primary_tau])

    all_models = sorted(set(baseline_counts.keys()) | set(candidate_counts.keys()))
    header = (
        f"{'model':<55} {'field':<28} {'baseline TP/FP/FN':>20}   {'candidate TP/FP/FN':>20}   Δ TP"
    )
    print(header)
    print("-" * 130)
    for model_id in all_models:
        base_fields = baseline_counts.get(model_id, {})
        cand_fields = candidate_counts.get(model_id, {})
        all_fields = sorted(set(base_fields.keys()) | set(cand_fields.keys()))
        for field_key in all_fields:
            b = base_fields.get(field_key, {"TP": 0, "FP": 0, "FN": 0})
            c = cand_fields.get(field_key, {"TP": 0, "FP": 0, "FN": 0})
            b_str = f"{b['TP']:>3}/{b['FP']:>3}/{b['FN']:>3}"
            c_str = f"{c['TP']:>3}/{c['FP']:>3}/{c['FN']:>3}"
            delta_tp = c["TP"] - b["TP"]
            marker = "  " if delta_tp == 0 else (" ↑" if delta_tp > 0 else " ↓")
            print(
                f"{model_id:<55} {field_key:<28} {b_str:>20}   {c_str:>20}  {delta_tp:+3d}{marker}"
            )

    print()
    # Cohort Δ headline.
    base_cohort = _aggregate_micro_f1(
        [s for inv_list in baseline_results[primary_tau].values() for s in inv_list]
    )
    cand_cohort = _aggregate_micro_f1(
        [s for inv_list in candidate_results[primary_tau].values() for s in inv_list]
    )
    delta_cohort = cand_cohort - base_cohort
    sign = "+" if delta_cohort >= 0 else ""
    print(
        f"Cohort pooled micro_F1: baseline={base_cohort:.4f}  "
        f"candidate={cand_cohort:.4f}  Δ={sign}{delta_cohort:.4f}"
    )

    if pair.is_identical:
        # Stability self-check: Δ must be exactly 0 (modulo numeric noise).
        if abs(delta_cohort) > 1e-9:
            print(
                "  ✗ STABILITY CHECK FAILED — baseline-vs-baseline Δ ≠ 0; "
                "this signals a non-determinism bug in the adapter or scorer."
            )
        else:
            print("  ✓ stability check OK (baseline-vs-baseline Δ = 0).")
    elif delta_cohort > 0.0:
        print("  → candidate improves cohort F1; review per-field Δ before promoting.")
    elif delta_cohort < 0.0:
        print("  → candidate regresses cohort F1; do NOT promote without further investigation.")
    else:
        print(
            "  → cohort F1 unchanged; per-field Δ may still show shifts "
            "(precision-vs-recall tradeoff)."
        )


def _log_to_mlflow_runs(
    *,
    baseline_results: dict[float, dict[str, list]],
    candidate_results: dict[float, dict[str, list]],
    thresholds: list[float],
    pair: AdapterPair,
) -> None:
    """Log a parent + 2 nested MLflow runs (baseline + candidate) per ADR-016.

    The opt-in audit trail when promoting a candidate adapter to canonical.
    Parent run name: `adapter-iterate-<UTC-timestamp>`. Nested runs tagged
    `adapter=baseline` / `adapter=candidate` with per-field metrics +
    `candidate_diff_sha256` tag for cross-referencing the candidate file
    even if it gets deleted post-promotion.
    """
    import mlflow  # noqa: PLC0415 — defer heavy import

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    parent_name = f"adapter-iterate-{timestamp}"

    mlflow.set_experiment("adapter-iterate")
    print(f"\n[mlflow] logging adapter-iterate run as {parent_name!r}", flush=True)

    with mlflow.start_run(run_name=parent_name) as parent_run:
        mlflow.set_tag("adr", "ADR-016")
        mlflow.set_tag("script", "scripts/rescore.py")
        mlflow.set_tag("candidate_diff_sha256", pair.diff_sha256)
        mlflow.set_tag("is_identical", str(pair.is_identical).lower())
        mlflow.log_param("thresholds", ",".join(f"{t:.2f}" for t in thresholds))

        for adapter_label, results_per_tau in (
            ("baseline", baseline_results),
            ("candidate", candidate_results),
        ):
            with mlflow.start_run(run_name=f"{parent_name}__{adapter_label}", nested=True):
                mlflow.set_tag("adapter", adapter_label)
                mlflow.set_tag("parent_run_id", parent_run.info.run_id)
                mlflow.set_tag("candidate_diff_sha256", pair.diff_sha256)
                for tau in thresholds:
                    all_inv_scores: list = []
                    for inv_list in results_per_tau[tau].values():
                        all_inv_scores.extend(inv_list)
                    cohort_f1 = _aggregate_micro_f1(all_inv_scores)
                    # Metric name uses 3-digit τ so 0.5 → tau050 (MLflow metric
                    # names disallow dots).
                    metric_name = f"cohort_micro_f1.tau{int(tau * 100):03d}"
                    mlflow.log_metric(metric_name, cohort_f1)

    print(
        f"[mlflow] logged 1 parent + 2 nested runs under experiment 'adapter-iterate' "
        f"(parent_run_id={parent_run.info.run_id})",
        flush=True,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rescore")
    parser.add_argument(
        "--cfg",
        type=_csv_paths,
        default=None,
        metavar="PATH[,OVERLAY,...]",
        help=(
            "Comma-separated YAML config path(s) to deep-merge (ADR-016 multi-file "
            "composition). When set, `transcripts-dir` defaults to "
            "`cohort.transcript_archive_dir` and `corpus-root` defaults to "
            "`cohort.corpus_root` from the merged config. The canonical "
            "adapter-iterate invocation: --cfg configs/pilot-13.yaml,configs/pilot-13-dev.yaml"
        ),
    )
    parser.add_argument(
        "--transcripts-dir",
        default=None,
        help=(
            f"Directory of saved transcripts. Defaults: (a) `cohort.transcript_archive_dir` "
            f"from --cfg if set; (b) {DEFAULT_TRANSCRIPTS_DIR} otherwise. "
            f"Explicit --transcripts-dir overrides the YAML."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        default=None,
        help=(
            f"ZUGFeRD corpus root. Defaults: (a) `cohort.corpus_root` from --cfg if set; "
            f"(b) {DEFAULT_CORPUS_ROOT} otherwise. Explicit --corpus-root overrides the YAML."
        ),
    )
    parser.add_argument(
        "--thresholds",
        default="0.5",
        help=(
            "Comma-separated list of ANLS thresholds (default: 0.5; the canonical "
            "ANLS* literature default per Biten+ ICCV'19). Pass '0.3,0.5,0.7' to "
            "reproduce the ADR-014 §Step 8 τ-sweep ablation."
        ),
    )
    parser.add_argument(
        "--adapter-candidate-path",
        default=str(DEFAULT_CANDIDATE_PATH),
        help=(
            "Path to the candidate adapter module (default: "
            f"{DEFAULT_CANDIDATE_PATH}). When missing or byte-identical to the "
            "baseline, runs in stability self-check mode (Google Rules of ML §24)."
        ),
    )
    parser.add_argument(
        "--log-mlflow",
        action="store_true",
        help=(
            "Opt-in: log 2 nested MLflow runs (baseline + candidate) under an "
            "'adapter-iterate' experiment for audit trail. Off by default (dev "
            "loop stays fast); turn on when promoting a candidate adapter to "
            "the canonical baseline."
        ),
    )
    args = parser.parse_args(argv[1:])

    thresholds = sorted(float(t.strip()) for t in args.thresholds.split(",") if t.strip())
    for tau in thresholds:
        if not 0.0 <= tau <= 1.0:
            print(f"ERROR: threshold {tau} not in [0.0, 1.0]", file=sys.stderr)
            return 2

    # Derive transcripts_dir + corpus_root from --cfg when provided; explicit
    # CLI flags override. Per ADR-016: the canonical adapter-iterate flow is
    # `--cfg configs/pilot-13.yaml,configs/pilot-13-dev.yaml` (transcripts +
    # corpus paths come from the dev config's `cohort.transcript_archive_dir`
    # + `cohort.corpus_root` automatically).
    transcripts_dir_str = args.transcripts_dir
    corpus_root_str = args.corpus_root
    if args.cfg:
        # Defer the import so the unit tests (which don't load configs) stay fast.
        from horus.config import ExperimentConfig  # noqa: PLC0415

        cfg = ExperimentConfig.from_yaml(args.cfg)
        if cfg.cohort is not None:
            if transcripts_dir_str is None:
                transcripts_dir_str = str(cfg.cohort.transcript_archive_dir)
            if corpus_root_str is None:
                corpus_root_str = str(cfg.cohort.corpus_root)
    if transcripts_dir_str is None:
        transcripts_dir_str = str(DEFAULT_TRANSCRIPTS_DIR)
    if corpus_root_str is None:
        corpus_root_str = str(DEFAULT_CORPUS_ROOT)

    pair = load_adapter_pair(candidate_path=Path(args.adapter_candidate_path))

    results = rescore_transcripts(
        transcripts_dir=Path(transcripts_dir_str),
        corpus_root=Path(corpus_root_str),
        thresholds=thresholds,
        adapters_pair=pair,
    )

    _print_threshold_table(
        results["baseline"],
        thresholds,
        title="Per-model micro_F1 by threshold τ (BASELINE adapter):",
    )

    if not pair.is_identical:
        _print_threshold_table(
            results["candidate"],
            thresholds,
            title="Per-model micro_F1 by threshold τ (CANDIDATE adapter):",
        )

    _print_ab_delta_table(results["baseline"], results["candidate"], thresholds, pair=pair)

    if args.log_mlflow:
        _log_to_mlflow_runs(
            baseline_results=results["baseline"],
            candidate_results=results["candidate"],
            thresholds=thresholds,
            pair=pair,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
