"""reading_ceiling.py — HND-3 read-quality + approach-comparison diagnostic (ADR-030).

Offline (NO VLM inference). Reuses the saved-transcript loader
(`horus.eval.transcripts`) + the canonical scorer (`horus.eval.scorer`) + both
Layer-2 adapters. Answers three questions the existing tools cannot:

  (A) **Reading ceiling** — for each GT-present field, does a surface form of the
      GT value appear *anywhere* in the model's raw transcript text? This upper-
      bounds what *any* parser could extract ("did the model read it?").

  (B) **Parser-loss vs read-miss** — split every GT-present miss into
      `parser-loss` (value WAS in the raw text but the Layer-2 adapter dropped
      it) vs `read-miss` (value absent from the raw text → a model problem).
      Quantifies the long-standing "the parser was the bottleneck" hypothesis,
      per model and per field, separately for the MONEY totals.

  (C) **Same-tuple 4-metric comparison** — on the IDENTICAL 3 JSON-capable
      models × 6 shared invoices, score the free-form arm (post-ADR-028 adapter,
      from `transcripts-multipage`) AND the JSON arm (from
      `transcripts-json-baseline`) with the SAME scorer, and report the ADR-027
      4-metric surface per-model + pooled. **Diagnostic, NOT a verdict.**

Defuses the ADR-028 landmine by construction: the free-form arm is re-scored
live from transcripts through the *current* `adapters.py`, never read from the
stale `pilot-13-full` MLflow run (where the MONEY totals are F1=0.000 pre-fix).

The reading ceiling is an **upper-bound proxy**: substring presence of a surface
form ≠ correct field association, and coincidental matches are possible
(especially short MONEY/DATE values). It bounds "could a parser have extracted
this," not "the model understood the field." Framed honestly in the report. The
invariant `readable ⊇ extracted(TP)` holds by construction (a TP is, by
definition, extractable), so the ceiling is never below the achieved recall.

In-sample (ZUGFeRD corpus). NO real-world-accuracy claim — that is deferred to
the held-out Belege split (#78), per ADR-028 §A.

Usage:

    make reading-ceiling
    uv run python scripts/reading_ceiling.py \\
        --freeform-cfg configs/pilot-13.yaml \\
        --json-cfg configs/pilot-13.yaml,configs/json-baseline.yaml \\
        --out eval/reading-ceiling-and-approach-comparison.md

Both `--*-cfg` reuse the ALREADY pre-registered configs (no new knobs, No-HARKing
preserved): the free-form cfg supplies the 7-model cohort + corpus + free-form
transcript dir; the JSON cfg supplies the 3 JSON-capable models + the 6-invoice
subset + the JSON transcript dir.

Refs: ADR-030 (this tool's ratifying ADR), ADR-027 (the 4 metrics), ADR-028
(the MONEY adapter fix + landmine), ADR-029 (the JSON baseline this reproduces),
ADR-016/014 (transcript archive + offline-rescore precedent), ADR-018 (the 3
JSON-capable models), issue #76 (HND-3 approach gate).
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from types import ModuleType

from horus.config import EvalConfig, ExperimentConfig
from horus.eval import adapters, adapters_json
from horus.eval.ground_truth import FIELDS, FieldType, GroundTruth, GroundTruthField
from horus.eval.scorer import (
    FieldResult,
    InvoiceFieldScores,
    f1_from_counts,
    group_level_counts,
    presence_conditional_counts,
    score,
    spurious_emission_counts,
)
from horus.eval.transcripts import build_gt_cache, parse_transcript, split_per_page_texts

DEFAULT_FREEFORM_CFG = "configs/pilot-13.yaml"
DEFAULT_JSON_CFG = "configs/pilot-13.yaml,configs/json-baseline.yaml"
DEFAULT_OUT = Path("eval/reading-ceiling-and-approach-comparison.md")

# The 5 MONEY fields (BT-106/109/110/112 totals + BT-115 due-payable); the
# Belegsummen totals ADR-028 recovers are the headline of the parser-loss split.
MONEY_FIELDS: frozenset[str] = frozenset(
    k for k, spec in FIELDS.items() if spec.field_type == "MONEY"
)

# Determinism reference: the JSON arm MUST reproduce the canonical ADR-029
# `json-baseline` run as reported in docs/sources/json-baseline-metrics.txt
# (same scorer + same transcripts + same GT ⇒ identical numbers). Mismatch ⇒
# a wiring bug in this tool. Values are 3-dp as printed by inspect_pilot_13.
_JSON_BASELINE_REF_MEAN_MICRO_F1: dict[str, float] = {
    "google/gemma-4-E4B-it": 0.707,
    "allenai/olmOCR-2-7B-1025": 0.660,
    "zai-org/GLM-OCR": 0.475,
}
_JSON_BASELINE_REF_COHORT: dict[str, float] = {
    "presence_f1": 0.643,
    "group_f1": 0.019,
    "spurious": 0.458,
}
_DETERMINISM_TOL = 0.005  # refs are 3-dp rounded; this absorbs rounding only


def _csv_paths(value: str) -> list[str]:
    """Argparse converter for `a.yaml,b.yaml` multi-file YAML composition (ADR-016)."""
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Surface-form generation — per-field-type plausible renderings of a GT value
# ---------------------------------------------------------------------------


def _group_thousands(int_part: str, sep: str) -> str:
    """Insert `sep` every 3 digits from the right (e.g. '1234' -> '1.234')."""
    if len(int_part) <= 3:
        return int_part
    parts: list[str] = []
    i = len(int_part)
    while i > 3:
        parts.append(int_part[i - 3 : i])
        i -= 3
    parts.append(int_part[:i])
    return sep.join(reversed(parts))


def _money_surface_forms(canonical: str) -> set[str]:
    """Plausible renderings of a canonical 2-dp money string in raw VLM text.

    The GT side is canonical (`1234.56`); models emit German (`1.234,56` /
    `1234,56`), US (`1,234.56`), or canonical. Returns all four families so the
    substring ceiling check catches the value regardless of locale formatting.
    """
    forms: set[str] = {canonical}
    neg = canonical.startswith("-")
    body = canonical[1:] if neg else canonical
    int_part, _, frac = body.partition(".")
    sign = "-" if neg else ""
    de_int = _group_thousands(int_part, ".")
    us_int = _group_thousands(int_part, ",")
    if frac:
        forms.update(
            {
                f"{sign}{int_part}.{frac}",  # 1234.56 (canonical)
                f"{sign}{int_part},{frac}",  # 1234,56 (German, no thousands)
                f"{sign}{de_int},{frac}",  # 1.234,56 (German)
                f"{sign}{us_int}.{frac}",  # 1,234.56 (US)
            }
        )
    else:
        forms.update({f"{sign}{int_part}", f"{sign}{de_int}", f"{sign}{us_int}"})
    return forms


def _date_surface_forms(iso: str) -> set[str]:
    """Plausible renderings of an ISO `YYYY-MM-DD` GT date in raw VLM text.

    Covers ISO + German/EU numeric forms (DD.MM.YYYY, D.M.YYYY, DD/MM/YYYY,
    DD-MM-YYYY, DD.MM.YY). Month-name forms are intentionally omitted (rare in
    this corpus; the `readable ⊇ TP` invariant still credits any extracted case).
    """
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso)
    if not m:
        return {iso}
    y, mo, d = m.groups()
    di, moi = str(int(d)), str(int(mo))
    return {
        iso,
        f"{d}.{mo}.{y}",
        f"{di}.{moi}.{y}",
        f"{d}/{mo}/{y}",
        f"{d}-{mo}-{y}",
        f"{d}.{mo}.{y[2:]}",
    }


def _surface_forms(gt_field: GroundTruthField, field_type: FieldType) -> set[str]:
    """All plausible raw-text renderings of a GT field's value.

    Always includes the normalized + raw XML value; adds locale variants for
    MONEY and DATE. STRING / CODE rely on the normalized + raw forms (CODE also
    gets a despaced match in :func:`_value_readable`).
    """
    forms: set[str] = set()
    for v in (gt_field.normalized_value, gt_field.raw_value):
        if v:
            forms.add(v)
    norm = gt_field.normalized_value
    if norm:
        if field_type == "MONEY":
            forms |= _money_surface_forms(norm)
        elif field_type == "DATE":
            forms |= _date_surface_forms(norm)
    return forms


def _value_readable(
    gt_field: GroundTruthField,
    field_type: FieldType,
    raw_nfc_lower: str,
    raw_despaced: str,
) -> bool:
    """Is a surface form of the GT value present in the raw transcript text?

    NFC + case-insensitive substring match. For CODE fields, additionally tries
    a whitespace-stripped match (catches `DE 123 456 789` vs `DE123456789`).
    """
    forms = _surface_forms(gt_field, field_type)
    for f in forms:
        fl = unicodedata.normalize("NFC", f).lower()
        if fl and fl in raw_nfc_lower:
            return True
    if field_type == "CODE":
        for f in forms:
            despaced = re.sub(r"\s+", "", unicodedata.normalize("NFC", f)).lower()
            if despaced and despaced in raw_despaced:
                return True
    return False


# ---------------------------------------------------------------------------
# Per-tuple analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldDiag:
    """Per-(tuple, field) reading-ceiling diagnosis (GT-present fields only)."""

    english_key: str
    field_type: FieldType
    gt_present_content: bool  # is_present AND normalized_value not in (None, "")
    is_tp: bool  # adapter extracted it correctly (scorer outcome == TP)
    readable: bool  # value present in raw text (TP ⇒ readable, by construction)


@dataclass(frozen=True)
class TupleResult:
    """One (model, invoice) tuple: scorer output + per-field ceiling diagnosis."""

    model_id: str
    invoice_stem: str
    inv_scores: InvoiceFieldScores
    field_diags: dict[str, FieldDiag]


def _field_diags(inv: InvoiceFieldScores, gt: GroundTruth, raw_text: str) -> dict[str, FieldDiag]:
    """Diagnose every field's reading ceiling for one tuple."""
    raw_nfc_lower = unicodedata.normalize("NFC", raw_text).lower()
    raw_despaced = re.sub(r"\s+", "", raw_nfc_lower)
    out: dict[str, FieldDiag] = {}
    for key, fr in inv.per_field.items():
        gt_field = gt.header[key]
        present_content = gt_field.is_present and gt_field.normalized_value not in (None, "")
        is_tp = fr.outcome == "TP"
        readable = bool(
            present_content
            and (is_tp or _value_readable(gt_field, fr.field_type, raw_nfc_lower, raw_despaced))
        )
        out[key] = FieldDiag(
            english_key=key,
            field_type=fr.field_type,
            gt_present_content=present_content,
            is_tp=is_tp,
            readable=readable,
        )
    return out


def _process_dir(
    transcripts_dir: Path,
    adapter_module: ModuleType,
    gt_cache: dict[str, GroundTruth],
    eval_cfg: EvalConfig,
) -> list[TupleResult]:
    """Score every transcript in a dir + diagnose its reading ceiling.

    Mirrors the harness/rescore transcript→adapter→scorer path EXACTLY (the
    multipage adapter API per ADR-019 W3.1) so the JSON arm reproduces the
    canonical `json-baseline` numbers (the determinism cross-check).
    """
    if not transcripts_dir.is_dir():
        raise FileNotFoundError(f"Transcripts dir not found: {transcripts_dir}")
    paths = sorted(transcripts_dir.glob("*.txt"))
    if not paths:
        raise RuntimeError(f"No transcripts in {transcripts_dir}")
    print(f"  scoring {len(paths)} transcripts from {transcripts_dir} ...", flush=True)

    results: list[TupleResult] = []
    for tp in paths:
        model_id, invoice_stem, body = parse_transcript(tp)
        gt = gt_cache.get(invoice_stem)
        if gt is None:
            print(f"    SKIP {tp.name}: no GT for {invoice_stem!r}", flush=True)
            continue
        per_page = split_per_page_texts(body)
        predicted = adapter_module.to_predicted_dict_multipage(per_page, model_id)
        inv = score(predicted, gt, cfg=eval_cfg, invoice_id=invoice_stem, model_id=model_id)
        diags = _field_diags(inv, gt, "\n".join(per_page))
        results.append(TupleResult(model_id, invoice_stem, inv, diags))
    return results


def _filter(
    results: list[TupleResult],
    *,
    models: set[str] | None = None,
    invoices: set[str] | None = None,
) -> list[TupleResult]:
    """Restrict tuples to the given model and/or invoice subset (None = all)."""
    return [
        r
        for r in results
        if (models is None or r.model_id in models)
        and (invoices is None or r.invoice_stem in invoices)
    ]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CeilingAgg:
    """Reading-ceiling / parser-loss aggregate over a set of GT-present fields."""

    n_inv: int
    n_present: int
    n_readable: int
    n_extracted: int  # TP
    n_parser_loss: int  # readable AND NOT TP
    n_read_miss: int  # NOT readable

    @property
    def ceiling_rate(self) -> float:
        return self.n_readable / self.n_present if self.n_present else 0.0

    @property
    def extracted_rate(self) -> float:
        return self.n_extracted / self.n_present if self.n_present else 0.0

    @property
    def parser_loss_rate(self) -> float:
        return self.n_parser_loss / self.n_present if self.n_present else 0.0

    @property
    def read_miss_rate(self) -> float:
        return self.n_read_miss / self.n_present if self.n_present else 0.0


def _ceiling_agg(results: list[TupleResult], *, money_only: bool = False) -> CeilingAgg:
    """Pool the reading-ceiling counts over GT-present fields across tuples."""
    n_present = n_readable = n_extracted = n_parser_loss = n_read_miss = 0
    for r in results:
        for key, d in r.field_diags.items():
            if not d.gt_present_content:
                continue
            if money_only and key not in MONEY_FIELDS:
                continue
            n_present += 1
            if d.is_tp:
                n_extracted += 1
            if d.readable:
                n_readable += 1
                if not d.is_tp:
                    n_parser_loss += 1
            else:
                n_read_miss += 1
    return CeilingAgg(
        n_inv=len(results),
        n_present=n_present,
        n_readable=n_readable,
        n_extracted=n_extracted,
        n_parser_loss=n_parser_loss,
        n_read_miss=n_read_miss,
    )


@dataclass(frozen=True)
class ExtMetrics:
    """ADR-027 4-metric surface pooled over a set of tuples."""

    n_inv: int
    mean_micro_f1: float  # mean of per-invoice micro_f1 (matches inspect_pilot_13 grid)
    presence_f1: float
    group_f1: float
    spurious: float


def _extended_metrics(results: list[TupleResult]) -> ExtMetrics:
    """Pool the ADR-027 metrics the SAME way inspect_pilot_13 / rescore do."""
    pc = [0, 0, 0]
    gl = [0, 0, 0]
    sp_fp = 0
    sp_absent = 0
    for r in results:
        frs: list[FieldResult] = list(r.inv_scores.per_field.values())
        pt, pf, pn = presence_conditional_counts(frs)
        pc[0] += pt
        pc[1] += pf
        pc[2] += pn
        gt_, gf, gn = group_level_counts(frs)
        gl[0] += gt_
        gl[1] += gf
        gl[2] += gn
        xfp, xab = spurious_emission_counts(frs)
        sp_fp += xfp
        sp_absent += xab
    mean_micro = fmean(r.inv_scores.micro_f1 for r in results) if results else 0.0
    return ExtMetrics(
        n_inv=len(results),
        mean_micro_f1=mean_micro,
        presence_f1=f1_from_counts(pc[0], pc[1], pc[2])[2],
        group_f1=f1_from_counts(gl[0], gl[1], gl[2])[2],
        spurious=sp_fp / sp_absent if sp_absent else 0.0,
    )


# ---------------------------------------------------------------------------
# Determinism cross-check
# ---------------------------------------------------------------------------


def _determinism_check(json_results: list[TupleResult]) -> tuple[bool, list[str]]:
    """Verify the JSON arm reproduces docs/sources/json-baseline-metrics.txt."""
    lines: list[str] = []
    ok = True
    models = sorted({r.model_id for r in json_results})
    for model_id in models:
        got = _extended_metrics(_filter(json_results, models={model_id})).mean_micro_f1
        ref = _JSON_BASELINE_REF_MEAN_MICRO_F1.get(model_id)
        if ref is None:
            continue
        delta = abs(got - ref)
        flag = "OK" if delta <= _DETERMINISM_TOL else "MISMATCH"
        ok = ok and delta <= _DETERMINISM_TOL
        lines.append(f"  mean micro_F1 {model_id:<28} got {got:.3f}  ref {ref:.3f}  [{flag}]")
    cohort = _extended_metrics(json_results)
    for name, got, ref in (
        ("presence_F1", cohort.presence_f1, _JSON_BASELINE_REF_COHORT["presence_f1"]),
        ("group_F1", cohort.group_f1, _JSON_BASELINE_REF_COHORT["group_f1"]),
        ("spurious", cohort.spurious, _JSON_BASELINE_REF_COHORT["spurious"]),
    ):
        delta = abs(got - ref)
        flag = "OK" if delta <= _DETERMINISM_TOL else "MISMATCH"
        ok = ok and delta <= _DETERMINISM_TOL
        lines.append(f"  cohort {name:<22} got {got:.3f}  ref {ref:.3f}  [{flag}]")
    return ok, lines


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _ceiling_table(rows: list[tuple[str, list[TupleResult]]]) -> list[str]:
    """Render a per-model reading-ceiling table (+ COHORT row) as markdown."""
    out = [
        "| model | n_inv | present | ceiling | extracted | parser-loss | read-miss "
        "| MONEY present | MONEY ceiling | MONEY extracted | MONEY parser-loss |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, results in rows:
        a = _ceiling_agg(results)
        m = _ceiling_agg(results, money_only=True)
        out.append(
            f"| {label} | {a.n_inv} | {a.n_present} | {a.ceiling_rate:.2f} "
            f"| {a.extracted_rate:.2f} | {a.parser_loss_rate:.2f} | {a.read_miss_rate:.2f} "
            f"| {m.n_present} | {m.ceiling_rate:.2f} | {m.extracted_rate:.2f} "
            f"| {m.parser_loss_rate:.2f} |"
        )
    return out


def _comparison_table(
    freeform: list[TupleResult], json_arm: list[TupleResult], models: list[str]
) -> list[str]:
    """Render the same-tuple free-form-vs-JSON 4-metric table as markdown."""
    out = [
        "| model | arm | n_inv | mean micro_F1 | presence_F1 | group_F1 | spurious |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for model_id in [*models, "COHORT"]:
        if model_id == "COHORT":
            ff, jj = freeform, json_arm
        else:
            ff = _filter(freeform, models={model_id})
            jj = _filter(json_arm, models={model_id})
        for arm_label, res in (("free-form+adapter", ff), ("native JSON", jj)):
            em = _extended_metrics(res)
            name = f"**{model_id}**" if model_id == "COHORT" else model_id
            out.append(
                f"| {name} | {arm_label} | {em.n_inv} | {em.mean_micro_f1:.3f} "
                f"| {em.presence_f1:.3f} | {em.group_f1:.3f} | {em.spurious:.3f} |"
            )
    return out


def _render_report(
    *,
    freeform_full: list[TupleResult],
    json_full: list[TupleResult],
    freeform_subset: list[TupleResult],
    subset_models: list[str],
    determinism_ok: bool,
    determinism_lines: list[str],
) -> str:
    """Assemble the full markdown diagnostic report."""
    ff_models = sorted({r.model_id for r in freeform_full})
    json_models = sorted({r.model_id for r in json_full})

    lines: list[str] = [
        "# Reading-Ceiling & Approach Comparison — HND-3 diagnostic (ADR-030)",
        "",
        "_Generated by `make reading-ceiling` (`scripts/reading_ceiling.py`). "
        "DO NOT EDIT BY HAND — re-run to regenerate._",
        "",
        "> **Diagnostic, NOT a verdict.** This characterizes both extraction "
        "approaches on identical cached data to inform — not decide — the Layer-1 "
        "choice (carried into fine-tuning per #76; exploratory→confirmatory "
        "diagnostic, arXiv 2503.08124 — not a §6 hypothesis test, per ADR-031). "
        "No approach is pre-bet.",
        ">",
        "> **In-sample.** ZUGFeRD synthetic corpus; NO real-world-accuracy claim. "
        "Out-of-sample reporting is deferred to the held-out Belege split (#78) "
        "per ADR-028 §A.",
        ">",
        "> **Free-form is re-scored live** from transcripts through the current "
        "`adapters.py` (post-ADR-028), NOT read from the stale `pilot-13-full` "
        "MLflow run — defusing the ADR-028 landmine by construction.",
        "",
        "## 1. Reading ceiling & parser-loss (per model, native arm)",
        "",
        "For each **GT-present** field: `ceiling` = a surface form of the value "
        "appears in the raw transcript text (upper bound on what any parser could "
        "extract); `extracted` = the Layer-2 adapter scored it TP; "
        "`parser-loss` = readable but NOT extracted (a *parser* problem — the "
        "value was there); `read-miss` = not in the raw text (a *model* problem). "
        "By construction `ceiling ≥ extracted`. The MONEY columns restrict to the "
        f"{len(MONEY_FIELDS)} MONEY fields (the Belegsummen totals ADR-028 targets).",
        "",
        "_Reading ceiling is an upper-bound proxy: substring presence of a surface "
        "form, not verified field association. Coincidental matches are possible "
        "(short MONEY/DATE values). It bounds extractability, not understanding._",
        "",
        f"### 1a. Free-form arm — `adapters.py` ({len(ff_models)} models, full corpus)",
        "",
        *_ceiling_table(
            [(m, _filter(freeform_full, models={m})) for m in ff_models]
            + [("**COHORT**", freeform_full)]
        ),
        "",
        f"### 1b. JSON arm — `adapters_json.py` ({len(json_models)} models, 6-invoice subset)",
        "",
        *_ceiling_table(
            [(m, _filter(json_full, models={m})) for m in json_models] + [("**COHORT**", json_full)]
        ),
        "",
        "## 2. Same-tuple 4-metric comparison (3 JSON-capable models × 6 shared invoices)",
        "",
        "Identical `(model × invoice)` tuples on both arms; free-form "
        "(post-ADR-028) vs native JSON; scored by the SAME ADR-027 scorer. "
        "`mean micro_F1` is the mean of per-invoice micro-F1 (matches "
        "`inspect_pilot_13`); `presence_F1` conditions on GT-present fields "
        "(recall-faithful); `spurious` is the hallucination rate on absent fields "
        "(lower = more honest).",
        "",
        *_comparison_table(freeform_subset, json_full, subset_models),
        "",
        "## 3. Determinism cross-check",
        "",
        "The JSON arm here MUST reproduce the canonical ADR-029 `json-baseline` "
        "run (`docs/sources/json-baseline-metrics.txt`) — same scorer + same "
        "transcripts + same GT. A mismatch signals a wiring bug in this tool.",
        "",
        "```",
        *determinism_lines,
        f"  => {'PASS' if determinism_ok else 'FAIL'}",
        "```",
        "",
        "## 4. How to read this (caveats)",
        "",
        "- **Not a winner-pick.** Both approaches are carried forward; the final "
        "Layer-1 choice is made post-fine-tuning with out-of-sample evidence.",
        "- **`parser-loss` is the actionable signal.** Where it is high, the model "
        "read the value but the adapter dropped it → adapter/JSON-instruction work "
        "(cheap). Where `read-miss` dominates → a model/fine-tuning problem.",
        "- **`spurious` is the honesty axis.** A low rate means the model emits "
        "null for genuinely-absent fields instead of inventing values — critical "
        "for a tax/audit tool where a wrong number is worse than a missing one.",
        "- **MONEY columns** isolate the invoice totals that matter most to a "
        "Steuerberater and that ADR-028's Belegsummen fallback targets.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _require_cohort(cfg: ExperimentConfig, label: str) -> None:
    if cfg.cohort is None:
        raise ValueError(f"{label} config has no `cohort:` section; cannot resolve models/paths.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="reading_ceiling")
    parser.add_argument("--freeform-cfg", type=_csv_paths, default=_csv_paths(DEFAULT_FREEFORM_CFG))
    parser.add_argument("--json-cfg", type=_csv_paths, default=_csv_paths(DEFAULT_JSON_CFG))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv[1:])

    freeform_cfg = ExperimentConfig.from_yaml(args.freeform_cfg)
    json_cfg = ExperimentConfig.from_yaml(args.json_cfg)
    _require_cohort(freeform_cfg, "free-form")
    _require_cohort(json_cfg, "JSON")
    assert freeform_cfg.cohort is not None and json_cfg.cohort is not None  # for type-narrowing

    corpus_root = freeform_cfg.cohort.corpus_root
    freeform_dir = freeform_cfg.cohort.transcript_archive_dir
    json_dir = json_cfg.cohort.transcript_archive_dir
    subset_models = list(json_cfg.cohort.working_models)
    subset_invoices = set(json_cfg.cohort.invoice_subset or [])
    freeform_eval = freeform_cfg.eval or EvalConfig()
    json_eval = json_cfg.eval or EvalConfig()

    if not subset_invoices:
        raise ValueError(
            "JSON config has no `cohort.invoice_subset`; cannot build the same-tuple set."
        )

    print("reading-ceiling diagnostic (ADR-030) — offline, no VLM", flush=True)
    gt_cache = build_gt_cache(corpus_root)

    print("free-form arm:", flush=True)
    freeform_full = _process_dir(freeform_dir, adapters, gt_cache, freeform_eval)
    print("JSON arm:", flush=True)
    json_full = _process_dir(json_dir, adapters_json, gt_cache, json_eval)

    freeform_subset = _filter(freeform_full, models=set(subset_models), invoices=subset_invoices)
    _warn_missing_subset(freeform_subset, subset_models, subset_invoices)

    determinism_ok, determinism_lines = _determinism_check(json_full)

    report = _render_report(
        freeform_full=freeform_full,
        json_full=json_full,
        freeform_subset=freeform_subset,
        subset_models=subset_models,
        determinism_ok=determinism_ok,
        determinism_lines=determinism_lines,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"\nwrote {args.out}", flush=True)
    print("\n".join(["determinism cross-check:", *determinism_lines]), flush=True)
    if not determinism_ok:
        print(
            "\nERROR: determinism cross-check FAILED — JSON arm did not reproduce "
            "json-baseline-metrics.txt; investigate before trusting the report.",
            file=sys.stderr,
        )
        return 1
    print("\ndeterminism cross-check PASSED.", flush=True)
    return 0


def _warn_missing_subset(
    freeform_subset: list[TupleResult], models: list[str], invoices: set[str]
) -> None:
    """Warn if any expected (model × invoice) free-form tuple is missing."""
    found = {(r.model_id, r.invoice_stem) for r in freeform_subset}
    expected = {(m, inv) for m in models for inv in invoices}
    missing = sorted(expected - found)
    if missing:
        print(f"  WARN: {len(missing)} expected free-form subset tuples missing:", flush=True)
        for m, inv in missing:
            print(f"    - {m} × {inv}", flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
