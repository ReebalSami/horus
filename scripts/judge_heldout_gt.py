"""Author held-out GT with a cloud vision judge; diff it against the current draft (ADR-060).

The default `--sample` mode is the ADR-060 scope gate: it judges a small, deliberately
chosen subset and writes a three-way comparison (current GT vs judge GT vs page-image
reference) so the true error rate is MEASURED before committing to a full re-author.
Deciding scope from the two invoices audited by hand would repeat the mistake that
produced the retracted 0.5692 — acting on an unvalidated answer key.

Two invoices are always included as CALIBRATION ANCHORS, because their truth is already
established by hand-adjudication against the page rasters:

- `belege-de-scan-010` — current GT is provably WRONG (printed total 63,97 vs GT 53,97;
  printed date 28.09.2022 vs GT 28.01.2022). A judge worth trusting must find these.
- `belege-en-email-001` — current GT is provably CORRECT on all 14 non-null fields. A
  judge worth trusting must NOT manufacture disagreements here.

Together they measure both error directions: miss the first and the judge is too weak to
be an authority; break the second and it is too noisy. A sample without anchors would
produce disagreement counts with no way to tell which side is wrong.

Usage:
    export ANTHROPIC_API_KEY=...        # or put it in the git-ignored .env
    uv run python scripts/judge_heldout_gt.py --sample          # the ADR-060 gate
    uv run python scripts/judge_heldout_gt.py --ids belege-de-scan-010
    uv run python scripts/judge_heldout_gt.py --all             # full re-author

Nothing is overwritten: judged GT lands in a separate directory
(`data/self-collected/_judge/gt/`) and the live `gt/` tree is untouched until the author
promotes it. Everything stays inside the git-ignored private tree (ADR-040).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS  # noqa: E402
from horus.eval.heldout import load_heldout_index  # noqa: E402
from horus.eval.judge import (  # noqa: E402
    DEFAULT_EFFORT,
    JudgeConfig,
    JudgeVerdict,
    judge_invoice,
    resolve_judge_model,
    verdict_to_gt_document,
)
from horus.eval.rasterize import rasterize_pdf  # noqa: E402
from horus.finetune.dataset import (  # noqa: E402
    DEFAULT_HELDOUT_CORPUS_ROOT,
    DEFAULT_HELDOUT_RASTER_CACHE,
)

DEFAULT_JUDGE_DIR = DEFAULT_HELDOUT_CORPUS_ROOT / "_judge"

#: See module docstring — hand-adjudicated invoices that calibrate BOTH error
#: directions. Hardcoded deliberately: they are specific historical evidence, not a
#: tunable parameter.
CALIBRATION_ANCHORS: tuple[str, ...] = ("belege-de-scan-010", "belege-en-email-001")


def _select_sample(all_ids: list[str], channels: dict[str, str], per_channel: int) -> list[str]:
    """Anchors first, then evenly spread additional ids from each channel.

    Spread rather than first-N: consecutive ids tend to share a vendor and layout, so
    taking the head of the list would under-sample the variety the set exists to cover.
    """
    picked: list[str] = [i for i in CALIBRATION_ANCHORS if i in all_ids]
    for channel in sorted(set(channels.values())):
        pool = [i for i in all_ids if channels[i] == channel and i not in picked]
        if not pool:
            continue
        needed = max(0, per_channel - sum(1 for p in picked if channels.get(p) == channel))
        if needed == 0:
            continue
        if needed >= len(pool):
            picked.extend(pool)
            continue
        step = len(pool) / needed
        picked.extend(pool[int(k * step)] for k in range(needed))
    return sorted(dict.fromkeys(picked))


def _norm(value: object) -> str:
    """Render a GT value for display/comparison ('' for absent)."""
    if value is None:
        return ""
    return str(value).strip()


def _diff_rows(
    current: Mapping[str, object], judged: Mapping[str, object]
) -> list[tuple[str, str, str]]:
    """Flat-field disagreements as (field, current, judged), excluding agreements."""
    rows: list[tuple[str, str, str]] = []
    for key in FIELDS:
        cur, jud = _norm(current.get(key)), _norm(judged.get(key))
        if cur != jud:
            rows.append((key, cur, jud))
    return rows


def _load_current_gt(gt_path: Path) -> Mapping[str, object]:
    if not gt_path.is_file():
        return {}
    try:
        data = json.loads(gt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    fields = data.get("fields", data)
    return fields if isinstance(fields, dict) else {}


def _report(
    verdicts: list[JudgeVerdict],
    current_by_id: Mapping[str, Mapping[str, object]],
    coverage_by_id: Mapping[str, tuple[str, str]],
) -> str:
    """Three-way comparison report (markdown), written into the private tree."""
    out: list[str] = [
        "# Held-out GT — judge vs current draft (ADR-060 sample gate)",
        "",
        "PRIVATE — contains invoice field values. Lives in the git-ignored tree; never commit.",
        "",
        "`current` = text-layer draft (`drafted_by: cascade`, `verified: false`). "
        "`judge` = vision judge reading the 300 DPI rasters. Neither is author-verified; "
        "the page image is the arbiter.",
        "",
    ]
    for verdict in verdicts:
        current = current_by_id.get(verdict.invoice_id, {})
        language, channel = coverage_by_id.get(verdict.invoice_id, ("?", "?"))
        rows = _diff_rows(current, verdict.fields)
        n_cur = sum(1 for k in FIELDS if _norm(current.get(k)))
        n_jud = sum(1 for k in FIELDS if _norm(verdict.fields.get(k)))
        anchor = "  **[CALIBRATION ANCHOR]**" if verdict.invoice_id in CALIBRATION_ANCHORS else ""
        out += [
            f"## `{verdict.invoice_id}` ({language}/{channel}, {verdict.n_pages} page(s)){anchor}",
            "",
            f"- non-null flat fields: current **{n_cur}** / judge **{n_jud}** (of {len(FIELDS)})",
            "- groups from judge: "
            + ", ".join(f"{g} {len(getattr(verdict, g))}" for g in REPEATING_GROUPS)
            + " (current draft has none for any invoice)",
            f"- disagreements on flat fields: **{len(rows)}**",
        ]
        if verdict.illegible_fields:
            out.append(f"- judge reported ILLEGIBLE: {', '.join(sorted(verdict.illegible_fields))}")
        if verdict.notes:
            out.append(f"- judge notes: {verdict.notes}")
        out.append("")
        if rows:
            out += ["| field | current draft | judge | who is right? |", "|---|---|---|---|"]
            out += [f"| `{k}` | {c or '_(null)_'} | {j or '_(null)_'} |  |" for k, c, j in rows]
        else:
            out.append("No flat-field disagreements.")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="judge_heldout_gt",
        description="Author held-out GT with a cloud vision judge (ADR-060).",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_HELDOUT_CORPUS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_JUDGE_DIR)
    parser.add_argument("--raster-cache", type=Path, default=DEFAULT_HELDOUT_RASTER_CACHE)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--model", default=None, help="Judge model id (default: strongest available)."
    )
    parser.add_argument(
        "--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"]
    )
    parser.add_argument("--no-thinking", action="store_true", help="Disable extended thinking.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--sample", action="store_true", help="ADR-060 scope gate (anchors + spread)."
    )
    group.add_argument("--all", action="store_true", help="Judge every invoice in the set.")
    group.add_argument("--ids", nargs="+", default=None, help="Judge these ids only.")
    parser.add_argument(
        "--per-channel", type=int, default=3, help="Sample size per channel (default 3)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show selection + cost surface; no API calls."
    )
    args = parser.parse_args(argv)

    items = load_heldout_index(args.corpus)
    if not items:
        print(f"No held-out index at {args.corpus / 'index.json'}.", file=sys.stderr)
        return 1
    by_id = {item.id: item for item in items}
    all_ids = sorted(by_id)
    channels = {i: by_id[i].channel for i in all_ids}

    if args.ids:
        unknown = [i for i in args.ids if i not in by_id]
        if unknown:
            print(f"Unknown ids: {', '.join(unknown)}", file=sys.stderr)
            return 1
        selected = sorted(args.ids)
    elif args.all:
        selected = all_ids
    else:
        selected = _select_sample(all_ids, channels, args.per_channel)

    print(f"Selected {len(selected)} of {len(all_ids)} invoice(s):", flush=True)
    total_pages = 0
    page_map: dict[str, list[Path]] = {}
    for sid in selected:
        pages = rasterize_pdf(
            by_id[sid].pdf_path, dpi=args.dpi, cache_dir=args.raster_cache, image_format="png"
        )
        page_map[sid] = pages
        total_pages += len(pages)
        anchor = "  [ANCHOR]" if sid in CALIBRATION_ANCHORS else ""
        print(f"  {sid:<24} {channels[sid]:<18} {len(pages)} page(s){anchor}", flush=True)
    print(f"Total page images to judge: {total_pages}", flush=True)

    if args.dry_run:
        print("Dry run — no API calls made.", flush=True)
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. Export it, or put it in the git-ignored .env.\n"
            "The judge cannot run without it; re-run with --dry-run to inspect the selection.",
            file=sys.stderr,
        )
        return 2

    from anthropic import Anthropic  # local import: only needed once a run is real

    client = Anthropic()
    cfg = JudgeConfig(model=args.model, effort=args.effort, thinking=not args.no_thinking)
    model = cfg.model or resolve_judge_model(client, cfg.model_preference)
    print(
        f"Judge model: {model} (effort={cfg.effort}, thinking={not args.no_thinking})", flush=True
    )

    gt_out = args.out_dir / "gt"
    gt_out.mkdir(parents=True, exist_ok=True)
    verdicts: list[JudgeVerdict] = []
    failures: list[str] = []
    in_tok = out_tok = 0

    for idx, sid in enumerate(selected, start=1):
        try:
            verdict = judge_invoice(
                client,
                page_map[sid],
                invoice_id=sid,
                config=JudgeConfig(model=model, effort=cfg.effort, thinking=cfg.thinking),
            )
        except Exception as exc:  # noqa: BLE001 — one bad invoice must not lose the rest
            failures.append(sid)
            print(
                f"  [{idx}/{len(selected)}] {sid}: FAILED {type(exc).__name__}: {exc}", flush=True
            )
            continue
        verdicts.append(verdict)
        in_tok += verdict.input_tokens
        out_tok += verdict.output_tokens
        item = by_id[sid]
        doc = verdict_to_gt_document(verdict, language=item.language, channel=item.channel)
        (gt_out / f"{sid}.gt.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        n_jud = sum(1 for k in FIELDS if _norm(verdict.fields.get(k)))
        print(
            f"  [{idx}/{len(selected)}] {sid}: {n_jud}/{len(FIELDS)} flat fields, "
            f"{len(verdict.line_items)} line item(s), "
            f"{len(verdict.illegible_fields)} illegible "
            f"({verdict.input_tokens}+{verdict.output_tokens} tok)",
            flush=True,
        )

    if not verdicts:
        print("No verdicts produced.", file=sys.stderr)
        return 1

    current_by_id = {sid: _load_current_gt(by_id[sid].gt_path) for sid in selected}
    coverage = {sid: (by_id[sid].language, by_id[sid].channel) for sid in selected}
    report_path = args.out_dir / "comparison.md"
    report_path.write_text(_report(verdicts, current_by_id, coverage), encoding="utf-8")

    total_diffs = sum(
        len(_diff_rows(current_by_id.get(v.invoice_id, {}), v.fields)) for v in verdicts
    )
    print(
        f"\nJudged {len(verdicts)} invoice(s); {len(failures)} failed. "
        f"Flat-field disagreements vs current draft: {total_diffs}. "
        f"Tokens: {in_tok} in / {out_tok} out.",
        flush=True,
    )
    print(f"Judged GT -> {gt_out}", flush=True)
    print(f"Comparison -> {report_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
