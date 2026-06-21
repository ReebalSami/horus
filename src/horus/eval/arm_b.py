"""Arm B (orchestrated) runner — read-then-structure over cached reader transcripts (ADR-038).

The orchestrated extraction arm: image -> Granite (reader) -> text -> Gemma
(structurer) -> validated fields. This module is the **structuring pass** (Pass 2)
of the two-pass design ratified in ADR-038. It is deliberately decoupled from the
reading pass (Pass 1):

  - **Pass 1 (reading)** is the existing cohort harness run of the reader model
    (e.g. the regex baseline's Granite run), which writes per-invoice transcripts
    to `cohort.transcript_archive_dir`. Not done here.
  - **Pass 2 (structuring, here)** loads each cached reader transcript, has the
    structurer (Gemma) read that *text* (no image, via `extract_text` — the
    text-only path proven in `experiments/arm-b-structurer-probe.py`), parses the
    output through the shared `structurer` module (`validate_and_repair`), scores
    the full 19 fields (default `score()`, per ADR-037), and logs the ADR-027
    metric surface — including the honesty axis `spurious_emission` — per invoice
    to MLflow.

Decoupling Pass 2 lets the structurer prompt be iterated on dev WITHOUT re-running
the reader (the same fast-iterate property the offline `rescore` / `reading_ceiling`
passes have — ADR-016/030). The structurer loads once and loops invoices; the
reader is never loaded here (it ran in Pass 1), so peak memory is the structurer
alone (~7.75 GB for Gemma per the Phase-0 probe — fits the 16 GB envelope).

Single-shot Arm A, by contrast, runs through the cohort harness directly
(`adapter_mode="structurer"`); only Arm B needs this dedicated runner, because the
harness has no two-model-per-invoice path (ADR-038 §Options B).

Refs: ADR-038 (this runner's ratifying ADR), ADR-034 (the two arms), ADR-035
(`validate_and_repair`), ADR-037 (19-field scoring), ADR-027 (the 4 metrics),
ADR-014 (the harness this reuses for reading + the result/aggregation shape),
ADR-030 (`transcripts.py` loader this consumes).
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from horus.config import ExperimentConfig
from horus.eval import structurer
from horus.eval.harness import (
    _CANONICAL_PRODUCTION_EXPERIMENTS,
    HarnessRunResult,
    _aggregate_per_field_scores,
    _invoice_profile,
    _list_paired_invoices,
    _micro_f1_from_counts,
    _model_slug,
)
from horus.eval.scorer import score
from horus.eval.transcripts import build_gt_cache, parse_transcript, split_per_page_texts
from horus.vlm_extractor import COHORT_MANIFEST, MLXVLMExtractor, get_extractor

__all__ = ["run_arm_b"]

_LOGGER = logging.getLogger(__name__)

# Default decode budget for the structuring generation. Matches the cohort
# manifest default (Gemma's 2048) — the dev run surfaced that 1024 truncates the
# JSON mid-object when the model emits a verbose per-field reasoning block before
# the JSON (EN16931_Einfach: every emitted value correct, but the object was cut
# off -> unparseable -> all-null). 2048 fits reasoning + the full 20-key object;
# generations that close the JSON early stop at EOS well under the budget.
_DEFAULT_STRUCTURE_MAX_TOKENS = 2048


def run_arm_b(
    cfg: ExperimentConfig,
    *,
    max_tokens: int = _DEFAULT_STRUCTURE_MAX_TOKENS,
) -> HarnessRunResult:
    """Run the orchestrated structuring pass over cached reader transcripts.

    Reads `<cohort.transcript_archive_dir>/<reader_slug>__<stem>.txt` for each
    invoice in `cohort.invoice_subset` (written by a prior reader cohort run),
    structures it with the single model in `cohort.working_models` via the
    text-only path, scores the full 19 fields, and logs per-invoice + parent
    MLflow runs (tags `approach=arm-b`). Streams per-invoice progress to stdout
    (`long-running-foreground`).

    Args:
        cfg: a Pydantic-validated `ExperimentConfig` whose `cohort` has
            `reader_model_id` set, exactly one structurer in `working_models`,
            and a `prompt_template_override` entry for that structurer.
        max_tokens: decode budget for each structuring generation.

    Returns:
        `HarnessRunResult` (same shape as `run_cohort`) so downstream inspectors
        + make targets treat Arm B uniformly with the cohort runs.

    Raises:
        ValueError: on missing/invalid cohort config (no `reader_model_id`, not
            exactly one structurer, unknown model id, missing structuring prompt,
            empty invoice set, or a `dev_only` config targeting a canonical
            production experiment).
    """
    import mlflow  # noqa: PLC0415 — defer heavy import (matches harness)

    if cfg.cohort is None:
        raise ValueError("cfg.cohort is None — run_arm_b requires a CohortConfig")
    cohort = cfg.cohort

    if cohort.reader_model_id is None:
        raise ValueError(
            "run_arm_b requires cohort.reader_model_id (the Arm-B reader whose "
            "cached transcripts the structurer consumes; per ADR-038)."
        )
    if len(cohort.working_models) != 1:
        raise ValueError(
            "Arm B expects exactly ONE structurer in cohort.working_models; got "
            f"{cohort.working_models}. The structurer is held constant (ADR-034)."
        )
    structurer_model = cohort.working_models[0]
    reader_model = cohort.reader_model_id
    for role, model_id in (("structurer", structurer_model), ("reader", reader_model)):
        if model_id not in COHORT_MANIFEST:
            raise ValueError(
                f"Arm B {role} model {model_id!r} not in COHORT_MANIFEST. "
                f"Known: {sorted(COHORT_MANIFEST)}"
            )
    if cohort.prompt_template_override is None or (
        structurer_model not in cohort.prompt_template_override
    ):
        raise ValueError(
            f"Arm B requires a structuring prompt in cohort.prompt_template_override"
            f"[{structurer_model!r}] (the instruction the structurer applies to the "
            "reader text)."
        )
    structuring_prompt = cohort.prompt_template_override[structurer_model]

    if cohort.dev_only and cfg.mlflow.experiment_name in _CANONICAL_PRODUCTION_EXPERIMENTS:
        raise ValueError(
            f"dev_only=true config refuses to log to canonical production "
            f"experiment {cfg.mlflow.experiment_name!r} (ADR-016 HARKing guard). "
            f"Use a distinct experiment_name (e.g. 'arm-b-dev')."
        )

    eval_cfg = cfg.eval
    archive_dir = cohort.transcript_archive_dir
    reader_slug = _model_slug(reader_model)
    structurer_slug = _model_slug(structurer_model)

    # Resolve the invoice set (reuse the harness's paired-invoice discovery + GT).
    pairs = _list_paired_invoices(cohort.corpus_root)
    if cohort.invoice_subset is not None:
        subset = set(cohort.invoice_subset)
        pairs = [(pdf, cii) for pdf, cii in pairs if pdf.stem in subset]
    if not pairs:
        raise ValueError(
            f"Arm B found 0 invoices under {cohort.corpus_root} "
            f"(subset={cohort.invoice_subset}). Check corpus_root / invoice_subset."
        )
    gt_cache = build_gt_cache(cohort.corpus_root)

    extractor = get_extractor(structurer_model)
    if not isinstance(extractor, MLXVLMExtractor):
        raise ValueError(
            f"Arm B structurer {structurer_model!r} must be an MLX model "
            "(text-only generation via extract_text); got "
            f"{type(extractor).__name__}."
        )

    per_field_scores_acc: dict[str, dict[str, list[float]]] = {structurer_model: {}}
    per_profile: dict[str, dict[str, int]] = {
        "EN16931": {"tp": 0, "fp": 0, "fn": 0},
        "XRECHNUNG": {"tp": 0, "fp": 0, "fn": 0},
        "POOLED": {"tp": 0, "fp": 0, "fn": 0},
    }
    n_completed = 0
    n_failed = 0
    dev_tag = str(cohort.dev_only).lower()

    print(
        f"Arm B: structurer={structurer_model} reader={reader_model} "
        f"invoices={len(pairs)} (transcripts <- {archive_dir})",
        flush=True,
    )

    mlflow.set_experiment(cfg.mlflow.experiment_name)
    parent_run_id = ""
    cohort_pooled = cohort_en = cohort_xr = 0.0
    aggregate: dict[str, dict[str, float]] = {}

    try:
        extractor.load()
        with mlflow.start_run(run_name=cohort.parent_run_name) as parent_run:
            parent_run_id = parent_run.info.run_id
            for key, value in cfg.mlflow.run_tags.items():
                mlflow.set_tag(key, value)
            mlflow.set_tag("approach", "arm-b")
            mlflow.set_tag("reader_model_id", reader_model)
            mlflow.set_tag("structurer_model_id", structurer_model)
            mlflow.set_tag("adapter_mode", "structurer")
            mlflow.set_tag("dev_only", dev_tag)
            mlflow.set_tag("n_invoices", str(len(pairs)))
            mlflow.log_param("seed", cfg.seed)

            for pdf_path, _cii_path in pairs:
                stem = pdf_path.stem
                profile = _invoice_profile(stem)
                reader_path = archive_dir / f"{reader_slug}__{stem}.txt"
                try:
                    if not reader_path.is_file():
                        raise FileNotFoundError(
                            f"reader transcript missing: {reader_path}. Run the "
                            f"reader cohort pass (e.g. the regex baseline's "
                            f"{reader_model} run) first."
                        )
                    gt = gt_cache.get(stem)
                    if gt is None:
                        raise ValueError(f"no factur-x ground truth for {stem}")

                    _read_model, _read_stem, body = parse_transcript(reader_path)
                    reader_text = "\n\n".join(split_per_page_texts(body))
                    full_prompt = structurer.build_structuring_input(
                        structuring_prompt, reader_text
                    )

                    result = extractor.extract_text(full_prompt, max_tokens=max_tokens)
                    if not result.is_ok:
                        raise RuntimeError(f"structurer generation failed: {result.error}")
                    structured_text = result.text

                    # Archive the structurer's output alongside the reader transcript
                    # (distinct slug) for audit + the later Streamlit demo. Header
                    # matches transcripts.parse_transcript so it can be re-read.
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    out_path = archive_dir / f"{structurer_slug}__{stem}.txt"
                    out_path.write_text(
                        f"# Arm-B structured output (ADR-038)\n"
                        f"# Model:    {structurer_model}\n"
                        f"# Invoice:  {stem}\n"
                        f"# Reader:   {reader_model}\n"
                        f"# Seconds:  {result.extract_seconds:.2f}\n"
                        f"\n"
                        f"===== PAGE 1 =====\n"
                        f"{structured_text}",
                        encoding="utf-8",
                    )

                    predicted = structurer.to_predicted_dict(structured_text, structurer_model)
                    # ADR-042: also fold the repeating groups (vat_breakdown /
                    # skonto / line_items) into the score's overall_micro_*.
                    predicted_groups = structurer.to_predicted_groups(structured_text)
                    scores = score(
                        predicted,
                        gt,
                        cfg=eval_cfg,
                        invoice_id=stem,
                        model_id=structurer_model,
                        predicted_groups=predicted_groups,
                    )

                    with mlflow.start_run(
                        run_name=f"{structurer_slug}__{stem}",
                        nested=True,
                    ):
                        mlflow.set_tag("model_id", structurer_model)
                        mlflow.set_tag("reader_model_id", reader_model)
                        mlflow.set_tag("invoice_id", stem)
                        mlflow.set_tag("profile", profile)
                        mlflow.set_tag("approach", "arm-b")
                        mlflow.set_tag("adapter_mode", "structurer")
                        mlflow.set_tag("dev_only", dev_tag)
                        mlflow.set_tag("xml_route", "facturx")
                        mlflow.log_metric("micro_f1", scores.micro_f1)
                        mlflow.log_metric("macro_f1", scores.macro_f1)
                        mlflow.log_metric("micro_precision", scores.micro_precision)
                        mlflow.log_metric("micro_recall", scores.micro_recall)
                        # ADR-042 — whole-schema headline (flat + repeating groups) + per-group F1.
                        mlflow.log_metric("overall_micro_f1", scores.overall_micro_f1)
                        mlflow.log_metric("overall_micro_precision", scores.overall_micro_precision)
                        mlflow.log_metric("overall_micro_recall", scores.overall_micro_recall)
                        for group_key, group_result in scores.repeating.items():
                            mlflow.log_metric(f"group_{group_key}_f1", group_result.f1)
                        # ADR-027 surface incl. the honesty axis — logged as
                        # first-class metrics here (Arm B) for convenience, on top
                        # of the per_field_scores.json the inspector pools.
                        mlflow.log_metric("presence_conditional_f1", scores.presence_conditional_f1)
                        mlflow.log_metric("group_level_f1", scores.group_level_f1)
                        mlflow.log_metric("spurious_emission_rate", scores.spurious_emission_rate)
                        mlflow.log_metric("structure_seconds", result.extract_seconds)
                        for fk, fr in scores.per_field.items():
                            mlflow.log_metric(f"field.{fk}.score", fr.score)
                        mlflow.log_dict(asdict(scores), artifact_file="per_field_scores.json")

                    for fk, fr in scores.per_field.items():
                        per_field_scores_acc[structurer_model].setdefault(fk, []).append(fr.score)
                        if fr.outcome == "TP":
                            per_profile[profile]["tp"] += 1
                            per_profile["POOLED"]["tp"] += 1
                        elif fr.outcome == "FP":
                            per_profile[profile]["fp"] += 1
                            per_profile["POOLED"]["fp"] += 1
                        elif fr.outcome == "FN":
                            per_profile[profile]["fn"] += 1
                            per_profile["POOLED"]["fn"] += 1

                    n_completed += 1
                    print(
                        f"  arm-b {stem}: micro_f1={scores.micro_f1:.3f} "
                        f"spurious={scores.spurious_emission_rate:.3f} "
                        f"({result.extract_seconds:.1f}s)",
                        flush=True,
                    )

                except Exception as exc:  # noqa: BLE001 — per-invoice errors are non-fatal
                    n_failed += 1
                    with mlflow.start_run(
                        run_name=f"{structurer_slug}__{stem}",
                        nested=True,
                    ):
                        mlflow.set_tag("model_id", structurer_model)
                        mlflow.set_tag("invoice_id", stem)
                        mlflow.set_tag("profile", profile)
                        mlflow.set_tag("approach", "arm-b")
                        mlflow.set_tag("dev_only", dev_tag)
                        mlflow.set_tag("error_type", type(exc).__name__)
                        mlflow.log_param("error_message", str(exc)[:500])
                        mlflow.end_run(status="FAILED")
                    print(f"  arm-b {stem}: FAILED {type(exc).__name__}: {exc}", flush=True)

            aggregate = _aggregate_per_field_scores(per_field_scores_acc)
            cohort_pooled = _micro_f1_from_counts(per_profile["POOLED"])
            cohort_en = _micro_f1_from_counts(per_profile["EN16931"])
            cohort_xr = _micro_f1_from_counts(per_profile["XRECHNUNG"])
            mlflow.log_metric("cohort_micro_f1_pooled", cohort_pooled)
            mlflow.log_metric("cohort_micro_f1_en16931", cohort_en)
            mlflow.log_metric("cohort_micro_f1_xrechnung", cohort_xr)
            mlflow.log_dict(
                {
                    "approach": "arm-b",
                    "reader_model_id": reader_model,
                    "structurer_model_id": structurer_model,
                    "n_invoices_total": len(pairs),
                    "n_completed": n_completed,
                    "n_failed": n_failed,
                    "cohort_micro_f1_pooled": cohort_pooled,
                    "cohort_micro_f1_en16931": cohort_en,
                    "cohort_micro_f1_xrechnung": cohort_xr,
                    "per_profile_outcomes": per_profile,
                    "per_field_heatmap": aggregate,
                },
                artifact_file="cohort_summary.json",
            )
    finally:
        try:
            extractor.unload()
        except Exception as exc:  # noqa: BLE001 — cleanup is best-effort
            _LOGGER.warning("Arm B structurer unload() failed: %s", exc)

    print(
        f"Arm B done: {n_completed} scored, {n_failed} failed; pooled micro_f1={cohort_pooled:.4f}",
        flush=True,
    )

    return HarnessRunResult(
        parent_run_id=parent_run_id,
        n_models_attempted=1,
        n_models_loaded=1,
        n_skipped_resume=0,
        n_completed=n_completed,
        n_failed=n_failed,
        n_invoices_total=len(pairs),
        cohort_micro_f1_pooled=cohort_pooled,
        cohort_micro_f1_en16931=cohort_en,
        cohort_micro_f1_xrechnung=cohort_xr,
        per_field_heatmap=aggregate,
    )
