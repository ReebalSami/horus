"""Generate every table and figure the thesis reports, from committed evidence.

The thesis authoring decision (ADR-055) forbids hand-copying measured numbers into the
manuscript: figures are generated into `thesis/figures/` and tables into `thesis/tables/`,
and the chapters `\\input` them. This script is that generator.

    make thesis-assets          # regenerate everything, then `make thesis`

Why it exists rather than typing the numbers once. The project's own record carries two
superseded held-out figures and one retracted one, and the authoring handoff that preceded
this script mixed two aggregations across two scoring rulers in a single table. Numbers that
live in one place cannot drift; numbers that are typed in nine places do.

Sources, all committed unless marked:

* `data/finetune/eval-*.json`     -- per-arm structurer eval reports (29 sealed val invoices)
* `data/finetune/attribution-*.json` -- reader-vs-structurer error attribution
* `data/finetune/adapter*/horus_training_provenance.json` -- recipe + dev-loss curve
* `data/finetune/split.json`      -- the sealed split and its hashes
* `data/self-collected/_eval/*.json` -- held-out reports (PRIVATE, git-ignored)
* `eval/heldout-breakdown.json`   -- sanitised cache of the held-out per-channel breakdown

Privacy (ADR-040). Held-out inputs are client documents and never leave the git-ignored
tree. This script emits aggregate counts and scores only -- never a field value, a filename,
or an invoice identifier. That is the same disclosure class as the committed datasheet, which
already publishes these rates. When the private corpus is absent the per-channel breakdown is
read from the sanitised cache instead, so the thesis rebuilds on a clean checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

FINETUNE_DIR = Path("data/finetune")
HELDOUT_CORPUS = Path("data/self-collected")
HELDOUT_EVAL = HELDOUT_CORPUS / "_eval"
HELDOUT_REPORT = HELDOUT_EVAL / "eval-zeroshot-heldout-adr065.json"
HELDOUT_SUPERSEDED = HELDOUT_EVAL / "eval-zeroshot-heldout-signed.json"
HELDOUT_OUTPUTS = HELDOUT_EVAL / "outputs-zeroshot"
HELDOUT_CACHE = Path("eval/heldout-breakdown.json")
TABLES_DIR = Path("thesis/tables")
FIGURES_DIR = Path("thesis/figures")

BANNER = (
    "% GENERATED FILE -- DO NOT EDIT BY HAND.\n"
    "% Regenerate with: make thesis-assets  (scripts/thesis_assets.py)\n"
    "% Editing this file by hand breaks the guarantee that every number in the\n"
    "% manuscript is derived from committed evidence (ADR-055).\n"
)


# --------------------------------------------------------------------------- helpers


def _read_json(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _num(value: float | None, digits: int = 4) -> str:
    """Format a score. An absent value prints as an em-dash rather than 0.0000."""
    if value is None:
        return "---"
    return f"{value:.{digits}f}"


def _signed(value: float | None, digits: int = 4) -> str:
    """Format a delta with an explicit sign, so a regression cannot read as a gain."""
    if value is None:
        return "---"
    return f"{value:+.{digits}f}"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"  wrote {path}")


def _table(
    *,
    caption: str,
    label: str,
    colspec: str,
    header: list[str],
    rows: list[list[str]],
    note: str,
    sources: list[str],
    midrules_before: tuple[int, ...] = (),
    font_size: str = "",
) -> str:
    """Assemble one booktabs table with a mandatory protocol note.

    The note is not decoration. Every table in this thesis reports a score computed under a
    specific corpus, model stack, numeric precision, scoring ruler and aggregation, and two
    tables that differ in any of those are not comparable. Stating them under the table is
    what makes the comparison checkable instead of assumed.
    """
    lines = [BANNER, "% Source(s): " + "; ".join(sources), ""]
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"  \centering")
    lines.append(rf"  \caption{{{caption}}}")
    lines.append(rf"  \label{{{label}}}")
    if font_size:
        lines.append("  " + font_size)
    lines.append(rf"  \begin{{tabular}}{{{colspec}}}")
    lines.append(r"    \toprule")
    lines.append("    " + " & ".join(header) + r" \\")
    lines.append(r"    \midrule")
    for index, row in enumerate(rows):
        if index in midrules_before:
            lines.append(r"    \midrule")
        lines.append("    " + " & ".join(row) + r" \\")
    lines.append(r"    \bottomrule")
    lines.append(r"  \end{tabular}")
    lines.append("")
    lines.append(r"  \vspace{4pt}")
    lines.append(r"  \begin{minipage}{0.95\linewidth}\footnotesize")
    lines.append(rf"  \textbf{{Protocol note.}} {note}")
    lines.append(r"  \end{minipage}")
    lines.append(r"\end{table}")
    lines.append("")
    return "\n".join(lines)


def _arm(name: str) -> dict[str, Any]:
    return _read_json(FINETUNE_DIR / f"eval-{name}-val.json")


def _overall(report: dict[str, Any]) -> float:
    return float(report["mean_overall_micro_f1"])


def _flat(report: dict[str, Any]) -> float:
    return float(report["mean_micro_f1"])


def _spurious(report: dict[str, Any]) -> float:
    return float(report["mean_spurious_emission_rate"])


# --------------------------------------------------------------------------- tables


def build_sealed_val_arms() -> str:
    """Every arm measured on the sealed 29-invoice validation split, both stacks."""
    bf16_zero = _arm("zeroshot-bf16")
    bf16_oracle = _arm("oracle-bf16")
    mlx_zero = _arm("zeroshot-qwen-adr059")
    mlx_oracle = _arm("oracle-adr059")

    def row(title: str, report: dict[str, Any]) -> list[str]:
        return [
            title,
            _num(_overall(report)),
            _num(_flat(report)),
            _num(_spurious(report)),
        ]

    rows = [
        row(r"bf16 / CUDA \quad reader transcript", bf16_zero),
        row(r"bf16 / CUDA \quad perfect text", bf16_oracle),
        row(r"4-bit / Apple silicon \quad reader transcript", mlx_zero),
        row(r"4-bit / Apple silicon \quad perfect text", mlx_oracle),
    ]
    return _table(
        caption=(
            "Zero-shot structurer performance on the sealed validation split, in both "
            "numeric precisions and on both input conditions."
        ),
        label="tab:sealed-val-arms",
        colspec="lrrr",
        header=[
            "Arm",
            "Overall F$_1$",
            "Flat F$_1$",
            "Spurious rate",
        ],
        rows=rows,
        midrules_before=(2,),
        note=(
            "Corpus: the 29 sealed synthetic invoices, never used for fitting or selection. "
            "Structurer: \\texttt{google/gemma-4-E4B-it}, greedy decoding, 29/29 parsed in "
            "every arm. Ground truth is extracted from each invoice's own embedded XML and is "
            "exact by construction. \\emph{Reader transcript} is the deployed pipeline: the "
            "structurer reads what the vision model transcribed. \\emph{Perfect text} replaces "
            "that transcript with text rendered from the ground truth, so it measures the "
            "structurer with the reading stage removed --- an instrument, not a deliverable. "
            "Both aggregations are means over the 29 per-invoice scores. Overall pools flat "
            "fields with repeating-group cells; flat covers the header fields only. Spurious "
            "rate is the share of emitted values for fields the document does not carry."
        ),
        sources=[
            "data/finetune/eval-zeroshot-bf16-val.json",
            "data/finetune/eval-oracle-bf16-val.json",
            "data/finetune/eval-zeroshot-qwen-adr059-val.json",
            "data/finetune/eval-oracle-adr059-val.json",
        ],
    )


def build_finetune_grid() -> str:
    """The 2x2 adaptation grid, with every delta taken against the matched-stack baseline."""
    baseline_reader = _overall(_arm("zeroshot-bf16"))
    baseline_oracle = _overall(_arm("oracle-bf16"))
    arms = {
        "reader-on-reader": _arm("ft-reader-on-reader"),
        "reader-on-oracle": _arm("ft-reader-on-oracle"),
        "oracle-on-reader": _arm("ft-oracle-on-reader"),
        "oracle-on-oracle": _arm("ft-oracle-on-oracle"),
    }
    rows: list[list[str]] = [
        [
            r"\emph{no adapter} (baseline)",
            "reader transcript",
            _num(baseline_reader),
            "---",
            _num(_spurious(_arm("zeroshot-bf16"))),
        ],
        [
            r"\emph{no adapter} (baseline)",
            "perfect text",
            _num(baseline_oracle),
            "---",
            _num(_spurious(_arm("oracle-bf16"))),
        ],
    ]
    for trained_on, condition, key in (
        ("reader transcripts", "reader transcript", "reader-on-reader"),
        ("reader transcripts", "perfect text", "reader-on-oracle"),
        ("perfect text", "reader transcript", "oracle-on-reader"),
        ("perfect text", "perfect text", "oracle-on-oracle"),
    ):
        report = arms[key]
        baseline = baseline_reader if condition == "reader transcript" else baseline_oracle
        rows.append(
            [
                f"adapter: {trained_on}",
                condition,
                _num(_overall(report)),
                _signed(_overall(report) - baseline),
                _num(_spurious(report)),
            ]
        )
    return _table(
        caption=(
            "The 2$\\times$2 adaptation grid: two adapters (named by the input distribution "
            "they were trained on), each evaluated on both input conditions. All four cells "
            "regress against the matched-stack baseline."
        ),
        label="tab:finetune-grid",
        colspec="llrrr",
        header=[
            "Model",
            "Evaluated on",
            "Overall F$_1$",
            r"$\Delta$",
            "Spurious",
        ],
        rows=rows,
        midrules_before=(2, 4),
        font_size=r"\small",
        note=(
            "Corpus and structurer as in Table~\\ref{tab:sealed-val-arms}. Every arm here is "
            "bf16 on CUDA, including the baseline: comparing a bf16 adapter against the "
            "4-bit deployment baseline would measure the adapter \\emph{and} a precision "
            "change at once. The two adapters differ only in the input distribution they were "
            "trained on; rank, scaling, dropout, schedule, seed and target modules are "
            "identical, and both selected the same checkpoint. Deltas are against the "
            "baseline in the same evaluation condition, never across conditions. The adapter "
            "trained on perfect text is an instrument for attributing the shortfall, not a "
            "candidate for deployment."
        ),
        sources=[
            "data/finetune/eval-zeroshot-bf16-val.json",
            "data/finetune/eval-oracle-bf16-val.json",
            "data/finetune/eval-ft-reader-on-reader-val.json",
            "data/finetune/eval-ft-reader-on-oracle-val.json",
            "data/finetune/eval-ft-oracle-on-reader-val.json",
            "data/finetune/eval-ft-oracle-on-oracle-val.json",
        ],
    )


def build_precision_confound() -> str:
    """The near-miss: an unmatched comparison reports the opposite of the truth."""
    matched = _overall(_arm("zeroshot-bf16"))
    deployed = _overall(_arm("zeroshot-qwen-adr059"))
    adapter = _overall(_arm("ft-reader-on-reader"))
    naive = adapter - deployed
    correct = adapter - matched
    ratio = correct / naive if naive else 0.0
    rows = [
        [
            "unmatched: bf16 vs 4-bit",
            _num(adapter),
            _num(deployed),
            _signed(naive),
            r"``no measurable harm''",
        ],
        [
            "matched: both bf16",
            _num(adapter),
            _num(matched),
            _signed(correct),
            r"\textbf{a real regression}",
        ],
    ]
    return _table(
        caption=(
            "Why the baseline had to be re-measured in the adapter's own numeric precision "
            "(adapter always bf16; the unmatched row compares it against the 4-bit "
            "deployment baseline). The unmatched comparison understates the regression by "
            f"a factor of {abs(ratio):.0f}."
        ),
        label="tab:precision-confound",
        colspec="lrrrl",
        header=[
            "Comparison",
            "Adapter",
            "Baseline",
            r"$\Delta$",
            "Reads as",
        ],
        rows=rows,
        font_size=r"\small",
        note=(
            "Both rows use the same adapter and the same sealed corpus; only the baseline "
            "changes. The deployed baseline runs 4-bit on Apple silicon, the adapter runs bf16 "
            "on CUDA, and full precision is worth "
            f"{matched - deployed:+.4f} on this corpus. Because the adapter costs roughly what "
            "the precision gain is worth, the two nearly cancel: the unmatched difference is "
            "small enough to read as neutral. The regression is only visible once the baseline "
            "is re-measured in the adapter's own precision, which is why that re-measurement "
            "was made a precondition of the study rather than an afterthought."
        ),
        sources=[
            "data/finetune/eval-ft-reader-on-reader-val.json",
            "data/finetune/eval-zeroshot-bf16-val.json",
            "data/finetune/eval-zeroshot-qwen-adr059-val.json",
        ],
    )


def build_devloss_table() -> str:
    """Both arms' dev-loss curves. Selection took epoch 1 in both cases."""
    reader = _read_json(FINETUNE_DIR / "adapter" / "horus_training_provenance.json")
    oracle = _read_json(FINETUNE_DIR / "adapter-oracle" / "horus_training_provenance.json")
    reader_curve = {int(e): float(v) for e, v in reader["selection"]["eval_loss_by_epoch"]}
    oracle_curve = {int(e): float(v) for e, v in oracle["selection"]["eval_loss_by_epoch"]}
    epochs = sorted(set(reader_curve) | set(oracle_curve))
    rows = []
    for epoch in epochs:
        reader_value = reader_curve.get(epoch)
        oracle_value = oracle_curve.get(epoch)
        marker = r"\quad$\leftarrow$ selected" if epoch == 1 else ""
        rows.append(
            [
                str(epoch),
                _num(reader_value),
                _num(oracle_value),
                marker,
            ]
        )
    reader_ratio = reader_curve[2] / reader_curve[1]
    oracle_ratio = oracle_curve[2] / oracle_curve[1]
    return _table(
        caption=(
            "Held-back dev-slice loss by epoch for both adapters. Both minimise after one "
            "epoch and never recover."
        ),
        label="tab:devloss",
        colspec="rrrl",
        header=["Epoch", "Reader arm", "Perfect-text arm", ""],
        rows=rows,
        note=(
            "Loss is measured on a 17-invoice dev slice carved out of the training split, "
            "disjoint from both the fitting set and the sealed validation split, so selecting "
            "on it leaks nothing into the reported score. The two arms share the same dev "
            "slice. The selection rule --- lowest dev loss --- was fixed before the runs and "
            "is enforced by the trainer rather than applied by hand. Loss rises by "
            f"{reader_ratio:.2f}$\\times$ (reader) and {oracle_ratio:.2f}$\\times$ (perfect "
            "text) at the second epoch and stays above the epoch-one value for the remaining "
            "budget, so the six-epoch budget was never a target: it existed to make the turn "
            "visible."
        ),
        sources=[
            "data/finetune/adapter/horus_training_provenance.json",
            "data/finetune/adapter-oracle/horus_training_provenance.json",
        ],
    )


def build_hyperparameters() -> str:
    """The recipe, read from the provenance the training run itself wrote."""
    reader = _read_json(FINETUNE_DIR / "adapter" / "horus_training_provenance.json")
    oracle = _read_json(FINETUNE_DIR / "adapter-oracle" / "horus_training_provenance.json")
    reader_hp = reader["hyperparameters"]
    oracle_hp = oracle["hyperparameters"]
    labels = {
        "lora_rank": "Rank",
        "lora_alpha": "Scaling factor",
        "lora_dropout": "Dropout",
        "learning_rate": "Learning rate",
        "lr_schedule": "Schedule",
        "warmup_ratio": "Warm-up fraction",
        "epochs": "Epoch budget",
        "batch_size": "Batch size",
        "gradient_accumulation_steps": "Gradient accumulation",
        "max_length": "Sequence budget (auto-sized)",
        "seed": "Seed",
    }
    rows = []
    for key, label in labels.items():
        left, right = reader_hp.get(key), oracle_hp.get(key)
        rows.append([label, str(left), str(right) if right != left else "identical"])
    rows.append(["Fitting examples", str(reader["n_train"]), str(oracle["n_train"])])
    rows.append(
        ["Adapted modules", str(reader["n_target_modules"]), str(oracle["n_target_modules"])]
    )
    rows.append(
        [
            "Dev-slice size",
            str(reader["dev_slice"]["n_dev"]),
            str(oracle["dev_slice"]["n_dev"]),
        ]
    )
    return _table(
        caption="The adaptation recipe, as recorded by the training runs themselves.",
        label="tab:hyperparameters",
        colspec="lrr",
        header=["Setting", "Reader arm", "Perfect-text arm"],
        rows=rows,
        note=(
            "Read from the provenance file each run wrote, not from the configuration it was "
            "asked to use, so the table reports what executed. The sequence budget is the one "
            "setting that differs, and it is derived rather than chosen: the trainer sizes it "
            "to the longest example in that arm's own training set, rounded up to a "
            "256-token boundary and capped at 8192. Neither cap binds, so no training example "
            "was truncated in either arm. The difference is therefore a consequence of the "
            "variable under study --- reader transcripts are longer than rendered text --- "
            "and not an independent second variable. Adapted modules are confined to the text "
            "tower; the vision tower stays frozen throughout."
        ),
        sources=[
            "data/finetune/adapter/horus_training_provenance.json",
            "data/finetune/adapter-oracle/horus_training_provenance.json",
        ],
    )


_CLUSTER_LABELS = {
    "legacy-16": "Core header fields",
    "new-flat": "Extended header fields",
    "group:line_items": "Line items",
    "group:vat_breakdown": "Tax breakdown",
    "group:skonto": "Early-payment discount",
}


def build_attribution_clusters() -> str:
    """Where the shortfall sits, and how much of it perfect text recovers."""
    reader = _read_json(FINETUNE_DIR / "attribution-val.json")
    perfect = _read_json(FINETUNE_DIR / "attribution-oracle-val.json")
    clusters = reader["clusters"]
    perfect_clusters = perfect["clusters"]
    rows = []
    for key, label in _CLUSTER_LABELS.items():
        entry = clusters.get(key)
        if entry is None:
            continue
        reader_f1 = float(entry["pooled_f1"])
        perfect_entry = perfect_clusters.get(key)
        perfect_f1 = float(perfect_entry["pooled_f1"]) if perfect_entry else None
        gap = perfect_f1 - reader_f1 if perfect_f1 is not None else None
        rows.append(
            [
                label,
                str(entry["n_invoices"]),
                _num(reader_f1),
                _num(perfect_f1),
                _signed(gap),
                str(entry["fn_readable"]),
                str(entry["fn_unreadable"]),
            ]
        )
    return _table(
        caption=(
            "Error attribution by field cluster. The gap column is the part of the shortfall "
            "that disappears when the reading stage is removed."
        ),
        label="tab:attribution-clusters",
        colspec="lrrrrrr",
        header=[
            "Cluster",
            "$n$",
            "Reader",
            "Perfect text",
            "Gap",
            r"FN\textsubscript{readable}",
            r"FN\textsubscript{unreadable}",
        ],
        rows=rows,
        note=(
            "Measured with a superseded reader (\\texttt{granite-docling-258M}), which was "
            "replaced afterwards. These figures therefore establish \\emph{where} the loss "
            "sits and \\emph{which stage} causes it; they are not a system score and must not "
            "be read as one. Both score columns are cell-pooled within the cluster and come "
            "from the same structurer on the same documents --- only the text it was given "
            "differs, so the gap is attributable to reading. A miss is "
            "\\emph{unreadable} when the expected value is absent from the transcript the "
            "structurer received: no structurer could have recovered it. It is "
            "\\emph{readable} when the value was present and the structurer still failed to "
            "place it. That split is what makes the two stages separately accountable, and it "
            "is measured per miss rather than inferred from the totals."
        ),
        sources=[
            "data/finetune/attribution-val.json",
            "data/finetune/attribution-oracle-val.json",
        ],
    )


def build_attribution_shares() -> str:
    """The headline attribution split, stated as counts rather than an impression."""
    reader = _read_json(FINETUNE_DIR / "attribution-val.json")
    shares = reader["loss_shares"]
    total = int(shares["total_signal_errors"])
    reader_share = int(shares["fn_reader_unreadable"])
    structurer_fn = int(shares["fn_structurer_readable"])
    structurer_fp = int(shares["fp_structurer"])
    structurer_share = structurer_fn + structurer_fp
    baseline = float(reader["mean_overall_micro_f1_report"])
    oracle = float(reader["oracle_mean_overall_micro_f1"])
    rows = [
        [
            "Reading: value absent from the transcript",
            str(reader_share),
            f"{100 * reader_share / total:.1f}\\,\\%",
        ],
        [
            "Structuring: value present, not placed",
            str(structurer_fn),
            f"{100 * structurer_fn / total:.1f}\\,\\%",
        ],
        [
            "Structuring: value emitted for an absent field",
            str(structurer_fp),
            f"{100 * structurer_fp / total:.1f}\\,\\%",
        ],
        [
            r"\textbf{Structuring, combined}",
            r"\textbf{" + str(structurer_share) + "}",
            r"\textbf{" + f"{100 * structurer_share / total:.1f}\\,\\%" + "}",
        ],
        [
            r"\textbf{All signal-bearing errors}",
            r"\textbf{" + str(total) + "}",
            r"\textbf{100.0\,\%}",
        ],
    ]
    return _table(
        caption=(
            "Every signal-bearing error on the sealed split, attributed to the stage that "
            "caused it."
        ),
        label="tab:attribution-shares",
        colspec="lrr",
        header=["Cause", "Errors", "Share"],
        rows=rows,
        midrules_before=(3, 4),
        note=(
            "Same superseded-reader caveat as Table~\\ref{tab:attribution-clusters}: this "
            "attributes a shortfall, it does not score a system. Signal-bearing means the "
            "cell contributes to F$_1$; correct absences are excluded, because counting them "
            "would make the split a function of how often fields are empty. Two "
            "decompositions follow from these counts, and they answer different questions. "
            "By the per-miss test above, the errors split roughly evenly "
            f"({100 * reader_share / total:.1f}\\,\\% reading against "
            f"{100 * structurer_share / total:.1f}\\,\\% structuring) --- but that test "
            "credits the structurer with every value that was readable yet mangled in "
            "transit, so it is a lower bound on the reading share. At the pipeline level the "
            f"split is starker: the pipeline scored {baseline:.4f} against {oracle:.4f} for "
            "the same structurer on perfect text, so of the "
            f"{1 - baseline:.4f} shortfall from a perfect score, the "
            f"{oracle - baseline:.4f} between the two arms is attributable to reading (only "
            f"the input text differs) and the {1 - oracle:.4f} the structurer leaves even "
            "on perfect text bounds its own capability gap."
        ),
        sources=["data/finetune/attribution-val.json"],
    )


def build_oracle_renderer_correction() -> str:
    """A ruler repair, measured on frozen generations so the model cannot be the cause."""
    before = _arm("oracle-tier1")
    after = _arm("oracle-adr059")
    rows = [
        [
            "Overall F$_1$",
            _num(_overall(before)),
            _num(_overall(after)),
            _signed(_overall(after) - _overall(before)),
        ],
        [
            "Flat F$_1$",
            _num(_flat(before)),
            _num(_flat(after)),
            _signed(_flat(after) - _flat(before)),
        ],
        [
            "Presence-conditional F$_1$",
            _num(float(before["mean_presence_conditional_f1"])),
            _num(float(after["mean_presence_conditional_f1"])),
            _signed(
                float(after["mean_presence_conditional_f1"])
                - float(before["mean_presence_conditional_f1"])
            ),
        ],
        [
            "Spurious rate",
            _num(_spurious(before)),
            _num(_spurious(after)),
            _signed(_spurious(after) - _spurious(before)),
        ],
    ]
    return _table(
        caption=(
            "Repairing the perfect-text renderer. Measured on identical archived generations, "
            "so the whole difference is attributable to the measuring instrument."
        ),
        label="tab:oracle-renderer-correction",
        colspec="lrrr",
        header=["Metric", "Before", "After", r"$\Delta$"],
        rows=rows,
        note=(
            "No inference ran. Both columns score the same stored model outputs; only the "
            "renderer that produces the perfect-text input, and the scoring rules applied to "
            "it, changed. This is the discipline that makes an apparatus repair "
            "distinguishable from a model improvement: had these outputs been regenerated, "
            "the two causes would have been inseparable. Presence-conditional F$_1$ scores "
            "only fields the document actually carries, so it is insensitive to how often "
            "fields are absent."
        ),
        sources=[
            "data/finetune/eval-oracle-tier1-val.json",
            "data/finetune/eval-oracle-adr059-val.json",
        ],
    )


def build_reader_lineage() -> str:
    """End-to-end score by reader, on one fixed structurer and one fixed corpus."""
    rows = [
        ["granite-docling-258M", _num(_overall(_arm("zeroshot")))],
        ["Qwen3-VL-4B-Instruct", _num(_overall(_arm("zeroshot-qwen")))],
        ["olmOCR-2-7B", _num(_overall(_arm("zeroshot-olmocr")))],
        [
            r"Qwen3-VL-4B-Instruct \emph{(after ruler repairs)}",
            _num(_overall(_arm("zeroshot-qwen-adr059"))),
        ],
    ]
    return _table(
        caption=(
            "End-to-end score by reading model, with the structurer and the corpus held fixed."
        ),
        label="tab:reader-lineage",
        colspec="lr",
        header=["Reader", "Overall F$_1$"],
        rows=rows,
        midrules_before=(3,),
        note=(
            "One structurer, one corpus, one prompt: the reader is the only thing that "
            "changes across the first three rows. The fourth row is the same reader as the "
            "second, re-scored after the scoring defects of "
            "Chapter~\\ref{ch:measurement-validity} were repaired --- so the gap between rows "
            "two and four is instrument, not model. The lineage is asymmetric by design: "
            "after the repairs, only the selected reader was re-measured end-to-end. "
            "olmOCR-2-7B's transcripts are retained, but its post-repair end-to-end score "
            "was never taken, because by then selection had moved to instruments this score "
            "cannot provide (\\S\\ref{sec:results-reader})."
        ),
        sources=[
            "data/finetune/eval-zeroshot-val.json",
            "data/finetune/eval-zeroshot-qwen-val.json",
            "data/finetune/eval-zeroshot-olmocr-val.json",
            "data/finetune/eval-zeroshot-qwen-adr059-val.json",
        ],
    )


_READER_LABELS = {
    "<PDF text layer — ceiling>": r"Embedded text layer \emph{(ceiling)}",
    "Qwen/Qwen3-VL-4B-Instruct": "Qwen3-VL-4B-Instruct",
    "Qwen/Qwen3-VL-8B-Instruct": "Qwen3-VL-8B-Instruct",
    "allenai/olmOCR-2-7B-1025": "olmOCR-2-7B",
    "opendatalab/MinerU2.5-Pro-2604-1.2B": "MinerU2.5-Pro (2604)",
    "opendatalab/MinerU2.5-Pro-2605-1.2B": "MinerU2.5-Pro (2605)",
}


def build_reader_findability() -> str | None:
    """Corrected reading quality per candidate, from the canonical script's own output.

    The computation is NOT reimplemented here. `scripts/findability_corrected.py` is the one
    implementation, and a parallel copy in this file would be free to drift from it -- the
    exact failure this project already recorded once for the perfect-text renderer. This
    function therefore invokes it and parses its two-column report.
    """
    import subprocess

    try:
        completed = subprocess.run(
            ["uv", "run", "python", "scripts/findability_corrected.py"],
            capture_output=True,
            text=True,
            timeout=900,
            check=True,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as error:
        print(f"  skipping reader-findability table: {error}", file=sys.stderr)
        return None

    rows: list[list[str]] = []
    for line in completed.stdout.splitlines():
        parts = line.rsplit(None, 2)
        if len(parts) != 3:
            continue
        name, score, misses = parts
        name = name.strip()
        if name in {"reader", ""} or name.startswith("<canonical"):
            # The canonical-lineage row duplicates the selected model under an alias.
            continue
        if name not in _READER_LABELS:
            continue
        try:
            rows.append([_READER_LABELS[name], _num(float(score), 3), str(int(misses))])
        except ValueError:
            continue
    if not rows:
        print("  skipping reader-findability table: no parsable rows", file=sys.stderr)
        return None
    rows.sort(key=lambda row: float(row[1]), reverse=True)
    return _table(
        caption=(
            "Reading quality per candidate after every miss was judged by hand against the "
            "page image."
        ),
        label="tab:reader-findability",
        colspec="lrr",
        header=["Reader", "Corrected findability", "Real misses"],
        rows=rows,
        note=(
            "Measured on the sealed validation split. Findability asks a question of the "
            "transcript alone --- for each reference value, is it present at all, allowing the "
            "formatting variants a German invoice actually uses --- so it isolates reading from "
            "structuring. \\emph{Corrected} means that 23 reference values which no channel "
            "could locate anywhere on the page, including the embedded text layer, are excluded "
            "as unanswerable rather than charged to every candidate equally. The embedded text "
            "layer is the ceiling: it is what the document itself contains, so no vision system "
            "can exceed it. This metric has a known blind spot --- a value can be present as a "
            "string while the surrounding structure is destroyed --- which is why it decided "
            "nothing on its own."
        ),
        sources=["scripts/findability_corrected.py (over data/finetune/bakeoff/)"],
    )


def build_corpus_composition() -> str:
    """The sealed split, its strata and its hashes."""
    split = _read_json(FINETUNE_DIR / "split.json")
    strata = split["strata"]
    rows = []
    for name in sorted(strata):
        entry = strata[name]
        rows.append(
            [
                name.replace("_", r"\_"),
                str(entry["train"]),
                str(entry["val"]),
                str(entry["train"] + entry["val"]),
            ]
        )
    rows.append(
        [
            r"\textbf{Total}",
            r"\textbf{" + str(split["n_train"]) + "}",
            r"\textbf{" + str(split["n_val"]) + "}",
            r"\textbf{" + str(split["n_total"]) + "}",
        ]
    )
    return _table(
        caption=(
            "The synthetic corpus and its stratified split into a fitting set and a sealed "
            "validation set."
        ),
        label="tab:corpus-composition",
        colspec="lrrr",
        header=["Profile", "Fitting", "Sealed", "Total"],
        rows=rows,
        midrules_before=(len(rows) - 1,),
        note=(
            "Stratified by electronic-invoice profile so that no profile appears only on one "
            "side of the split. The split is recorded with a seed and a content hash for each "
            "side, so a later run can prove it scored the same documents rather than "
            f"asserting it: seed {split['seed']}, validation-set hash "
            f"\\texttt{{{str(split['sha256_val'])[:16]}\\dots}}. Ground truth for every "
            "document is extracted from its own embedded XML, so it is exact rather than "
            "annotated. The dev slice used for checkpoint selection is carved from the "
            "fitting column only."
        ),
        sources=["data/finetune/split.json"],
    )


# ------------------------------------------------------------------ held-out breakdown


def _pooled_from_outcomes(outcomes: dict[str, dict[str, int]]) -> tuple[float, int, int, int]:
    """Cell-pooled F1 over signal-bearing outcomes only, mirroring heldout_breakdown.py."""
    tp = sum(counts.get("TP", 0) for counts in outcomes.values())
    fp = sum(counts.get("FP", 0) for counts in outcomes.values())
    fn = sum(counts.get("FN", 0) for counts in outcomes.values())
    denominator = 2 * tp + fp + fn
    return (2 * tp / denominator if denominator else 0.0), tp, fp, fn


def compute_heldout_breakdown() -> dict[str, Any] | None:
    """Derive the per-channel breakdown from the private corpus, or return None.

    Emits aggregate counts and scores only. Both aggregations come from the same report and
    the same scoring ruler, which is the property an earlier draft of this table lacked.
    """
    if not HELDOUT_REPORT.exists() or not HELDOUT_OUTPUTS.exists():
        return None

    from horus.eval.heldout import load_heldout_index
    from horus.finetune.dataset import build_heldout_records
    from horus.finetune.evaluate import score_saved_outputs

    report = _read_json(HELDOUT_REPORT)
    index = {item.id: item for item in load_heldout_index(HELDOUT_CORPUS)}
    if not index:
        return None

    per_invoice_means: dict[str, list[float]] = {}
    for entry in report.get("per_invoice") or []:
        if not entry.get("ok"):
            continue
        item = index.get(str(entry.get("stem", "")))
        if item is None:
            continue
        key = f"{item.language}/{item.channel}"
        per_invoice_means.setdefault(key, []).append(float(entry.get("micro_f1", 0.0)))

    structurer = str(report.get("structurer_model", ""))
    records = [rec for rec in build_heldout_records(HELDOUT_CORPUS) if rec.ready]
    grouped: dict[str, list[Any]] = {}
    for rec in records:
        grouped.setdefault(rec.subdir, []).append(rec)

    channels: list[dict[str, Any]] = []
    for name in sorted(grouped):
        scored = score_saved_outputs(
            grouped[name],
            HELDOUT_OUTPUTS,
            structurer_model=structurer,
            label=f"thesis-assets:{name}",
            progress=False,
            score_groups=False,
        )
        pooled, tp, fp, fn = _pooled_from_outcomes(scored.per_field_outcomes)
        means = per_invoice_means.get(name, [])
        channels.append(
            {
                "channel": name,
                "n": len(grouped[name]),
                "mean_per_invoice_f1": sum(means) / len(means) if means else None,
                "min_per_invoice_f1": min(means) if means else None,
                "pooled_f1": pooled,
                "precision": tp / (tp + fp) if tp + fp else 0.0,
                "recall": tp / (tp + fn) if tp + fn else 0.0,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )

    whole = score_saved_outputs(
        records,
        HELDOUT_OUTPUTS,
        structurer_model=structurer,
        label="thesis-assets:all",
        progress=False,
        score_groups=False,
    )
    pooled, tp, fp, fn = _pooled_from_outcomes(whole.per_field_outcomes)
    superseded = _read_json(HELDOUT_SUPERSEDED) if HELDOUT_SUPERSEDED.exists() else {}
    return {
        "_comment": (
            "GENERATED by scripts/thesis_assets.py from the git-ignored held-out corpus. "
            "Aggregate scores and counts only -- no field value, filename or invoice id. "
            "Committed so the thesis rebuilds on a clean checkout without the private data, "
            "the same pattern as docs/architecture/belege-heldout-datasheet.md."
        ),
        "report_label": report.get("label"),
        "structurer_model": report.get("structurer_model"),
        "n_total": report.get("n_total"),
        "n_ok": report.get("n_ok"),
        "mean_per_invoice_f1": report.get("mean_micro_f1"),
        "pooled_f1": pooled,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "superseded_mean_per_invoice_f1": superseded.get("mean_micro_f1"),
        "channels": channels,
    }


def load_heldout_breakdown(*, refresh: bool) -> dict[str, Any] | None:
    """Prefer the private corpus when present; fall back to the sanitised cache."""
    if refresh:
        computed = compute_heldout_breakdown()
        if computed is not None:
            HELDOUT_CACHE.parent.mkdir(parents=True, exist_ok=True)
            HELDOUT_CACHE.write_text(json.dumps(computed, indent=2) + "\n", encoding="utf-8")
            print(f"  wrote {HELDOUT_CACHE}  (sanitised cache)")
            return computed
        print(
            "  held-out corpus absent; falling back to the sanitised cache",
            file=sys.stderr,
        )
    if HELDOUT_CACHE.exists():
        return _read_json(HELDOUT_CACHE)
    return None


_CHANNEL_LABELS = {
    "english/email": "English, email-native PDF",
    "german/email": "German, email-native PDF",
    "german/iphone-pdf-scan": "German, phone scan",
}


def _channel_label(name: str) -> str:
    return _CHANNEL_LABELS.get(name, name.replace("_", r"\_"))


def build_heldout_headline(data: dict[str, Any]) -> str:
    """The single number the thesis claims for real invoices, with its error profile."""
    mean = float(data["mean_per_invoice_f1"])
    superseded = data.get("superseded_mean_per_invoice_f1")
    rows = [
        ["Documents scored", f"{data['n_ok']} / {data['n_total']}"],
        ["Mean per-invoice F$_1$", _num(mean)],
        ["Cell-pooled F$_1$", _num(float(data["pooled_f1"]))],
        ["Precision", _num(float(data["precision"]))],
        ["Recall", _num(float(data["recall"]))],
        ["True positives", str(data["tp"])],
        ["False positives", str(data["fp"])],
        ["False negatives", str(data["fn"])],
    ]
    superseded_note = ""
    if superseded is not None:
        superseded_note = (
            " An earlier ruler scored the same stored generations at "
            f"{float(superseded):.4f}; the difference is the instrument, not the system, and "
            "is accounted for in Chapter~\\ref{ch:measurement-validity}."
        )
    return _table(
        caption=(
            "Header-field extraction on the held-out corpus of real invoices, zero-shot, "
            "with open-weights models only."
        ),
        label="tab:heldout-headline",
        colspec="lr",
        header=["Quantity", "Value"],
        rows=rows,
        midrules_before=(5,),
        note=(
            "Corpus: real invoices collected from the author's own correspondence, never used "
            "for fitting, prompt design or selection. Answer key: the signed-off key, "
            "adjudicated across three independent reading channels and confirmed document by "
            "document by the author. Scope: the 34 registered header fields; repeating groups "
            "are excluded structurally, because their rows were never author-reviewed. "
            "Precision above recall means roughly four errors in five are a field left empty "
            "rather than a field invented --- for an accounting tool, the safer direction to "
            "fail in, because a gap is visible to a reviewer and a fabrication is not. "
            "\\textbf{Venue.} Every model here is open-weights and no inference path makes a "
            "network call. Reading ran at full precision and native resolution on "
            "target-class hardware (a single 24\\,GB graphics processor); structuring ran at "
            "the floor, on a 16\\,GB laptop in its deployed 4-bit precision "
            "(\\S\\ref{sec:method-repro}). The figure is the pipeline's accuracy on the "
            "hardware class a firm would buy for it; the floor's capped-resolution reading "
            "is not measured on this corpus (\\S\\ref{sec:lim-hardware})." + superseded_note
        ),
        sources=[
            str(HELDOUT_CACHE),
            "data/self-collected/_eval/eval-zeroshot-heldout-adr065.json (private)",
        ],
    )


def build_heldout_by_channel(data: dict[str, Any]) -> str:
    """The finding the corpus exists to produce: what degraded capture costs."""
    rows = []
    for entry in data["channels"]:
        rows.append(
            [
                _channel_label(str(entry["channel"])),
                str(entry["n"]),
                _num(entry.get("mean_per_invoice_f1")),
                _num(float(entry["pooled_f1"])),
                _num(float(entry["precision"])),
                _num(float(entry["recall"])),
            ]
        )
    rows.append(
        [
            r"\textbf{All documents}",
            r"\textbf{" + str(data["n_ok"]) + "}",
            r"\textbf{" + _num(float(data["mean_per_invoice_f1"])) + "}",
            r"\textbf{" + _num(float(data["pooled_f1"])) + "}",
            r"\textbf{" + _num(float(data["precision"])) + "}",
            r"\textbf{" + _num(float(data["recall"])) + "}",
        ]
    )
    email = [e for e in data["channels"] if str(e["channel"]).endswith("/email")]
    scan = [e for e in data["channels"] if "scan" in str(e["channel"])]
    gap_note = ""
    if email and scan:
        email_weighted = sum(float(e["mean_per_invoice_f1"]) * int(e["n"]) for e in email) / sum(
            int(e["n"]) for e in email
        )
        scan_mean = float(scan[0]["mean_per_invoice_f1"])
        gap_note = (
            f" Email-native documents average {email_weighted:.4f} against {scan_mean:.4f} "
            f"for photographs, a gap of {100 * (email_weighted - scan_mean):.1f} points."
        )
    return _table(
        caption=(
            "Held-out performance by language and capture channel. Photographed documents "
            "cost far more than language does."
        ),
        label="tab:heldout-by-channel",
        colspec="lrrrrr",
        header=[
            "Channel",
            "$n$",
            "Mean/invoice",
            "Pooled",
            "Precision",
            "Recall",
        ],
        rows=rows,
        midrules_before=(len(rows) - 1,),
        note=(
            "Both aggregations are derived from the same scoring run under the same ruler, so "
            "the row totals and the whole-corpus row are mutually consistent. Mean per invoice "
            "counts every document once regardless of how many fields it carries, and answers "
            "how the system behaves on a document handed to it. Cell-pooled sums all outcomes "
            "before computing one score, so field-dense documents pull harder, and answers "
            "what share of extracted cells is correct. Neither is a maximum over documents. "
            "Precision holds up on phone scans while recall falls, meaning degraded input "
            "makes the system abstain rather than invent." + gap_note
        ),
        sources=[
            str(HELDOUT_CACHE),
            "data/self-collected/_eval/eval-zeroshot-heldout-adr065.json (private)",
        ],
    )


# ------------------------------------------------------------------ appendix assets

DATASHEET_MD = Path("docs/architecture/belege-heldout-datasheet.md")


def _tex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def _longtable(
    *,
    caption: str,
    label: str,
    colspec: str,
    header: list[str],
    rows: list[list[str]],
    note: str,
    sources: list[str],
    font_size: str = r"\small",
) -> str:
    """A multi-page booktabs longtable with the same mandatory protocol note as `_table`."""
    head = "    " + " & ".join(header) + r" \\"
    lines = [BANNER, "% Source(s): " + "; ".join(sources), ""]
    lines.append(r"\begingroup" + font_size)
    lines.append(rf"\begin{{longtable}}{{{colspec}}}")
    lines.append(rf"  \caption{{{caption}}}\label{{{label}}}\\")
    lines.append(r"    \toprule")
    lines.append(head)
    lines.append(r"    \midrule")
    lines.append(r"  \endfirsthead")
    lines.append(r"    \toprule")
    lines.append(head)
    lines.append(r"    \midrule")
    lines.append(r"  \endhead")
    lines.append(r"    \bottomrule")
    lines.append(r"  \endfoot")
    for row in rows:
        lines.append("    " + " & ".join(row) + r" \\")
    lines.append(r"\end{longtable}")
    lines.append(r"\endgroup")
    lines.append(r"\begin{minipage}{0.95\linewidth}\footnotesize")
    lines.append(rf"\textbf{{Protocol note.}} {note}")
    lines.append(r"\end{minipage}")
    lines.append("")
    return "\n".join(lines)


def build_field_registry() -> str:
    """The full 34-field flat registry plus the three repeating groups, from the code.

    Generated from `horus.eval.ground_truth.FIELDS` so the appendix cannot drift from
    the registry that actually drives the prompt, the scorer and the ground-truth
    extractor.
    """
    from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS

    rows: list[list[str]] = []
    for spec in FIELDS.values():
        rows.append(
            [
                r"\texttt{" + _tex_escape(spec.english_key) + "}",
                _tex_escape(spec.bt_code),
                _tex_escape(spec.german_label),
                spec.field_type.lower(),
            ]
        )
    for group_name, (_, leaves) in REPEATING_GROUPS.items():
        rows.append(
            [
                r"\multicolumn{4}{l}{\emph{repeating group: \texttt{"
                + _tex_escape(group_name)
                + r"}}}"
            ]
        )
        for spec in leaves.values():
            rows.append(
                [
                    r"\quad\texttt{" + _tex_escape(spec.english_key) + "}",
                    _tex_escape(spec.bt_code),
                    _tex_escape(spec.german_label),
                    spec.field_type.lower(),
                ]
            )
    n_flat = len(FIELDS)
    n_groups = len(REPEATING_GROUPS)
    return _longtable(
        caption=(
            f"The field registry: {n_flat} flat header fields and {n_groups} repeating "
            "groups, aligned to EN~16931 business terms."
        ),
        label="tab:field-registry",
        colspec="llll",
        header=["Field", "BT", "German label (EN~16931 term)", "Type"],
        rows=rows,
        font_size=r"\footnotesize\setlength{\tabcolsep}{4pt}",
        note=(
            "Generated directly from the registry in "
            r"\texttt{src/horus/eval/ground\_truth.py}, the single structure that drives "
            "the structurer's field specification, the scorer and the reference "
            "extractor, so this listing cannot drift from the code. The German label is "
            "the canonical EN~16931 term, which is not always the wording a real page "
            "prints; corpus-measured printed labels are tracked separately "
            r"(\S\ref{sec:validity-specification}). Types: \emph{money} and "
            r"\emph{rate} are decimal-normalised, \emph{date} is ISO-normalised, "
            r"\emph{code} is vocabulary-mapped and \emph{string} is "
            "whitespace-normalised, symmetrically on both reference and prediction."
        ),
        sources=["src/horus/eval/ground_truth.py (FIELDS, REPEATING_GROUPS)"],
    )


def _datasheet_tables(text: str) -> dict[str, list[list[str]]]:
    """Parse the pipe tables out of the committed datasheet markdown, keyed by section."""
    sections: dict[str, list[list[str]]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            continue
        if current is None or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            continue
        sections.setdefault(current, []).append(cells)
    return sections


def _dequote(cell: str) -> str:
    return cell.strip("`")


def build_heldout_datasheet_tables() -> tuple[str, str, str]:
    """Composition, field-presence and freeze tables from the committed datasheet.

    The datasheet (`docs/architecture/belege-heldout-datasheet.md`) is itself generated
    by `scripts/heldout_manifest.py datasheet` from the private corpus and is the
    sanitised public record: counts, presence rates and hashes only. This function is a
    format conversion, not a re-derivation, so the appendix and the datasheet cannot
    disagree.
    """
    text = DATASHEET_MD.read_text(encoding="utf-8")
    sections = _datasheet_tables(text)

    composition_rows = [
        [_tex_escape(axis), _tex_escape(_dequote(value)), _tex_escape(count)]
        for axis, value, count in sections["Composition"][1:]
    ]
    composition = _table(
        caption="Held-out corpus composition (sanitised datasheet extract).",
        label="tab:heldout-composition",
        colspec="lll",
        header=["Axis", "Value", "Count"],
        rows=composition_rows,
        note=(
            "Converted verbatim from the committed sanitised datasheet, which is "
            "generated from the private corpus and publishes counts only --- no "
            "filenames, no field values, no invoice content. The channel named "
            r"\texttt{iphone-pdf-scan} is scanning-app output: camera captures deskewed "
            "and contrast-enhanced into a PDF without a text layer "
            r"(\S\ref{sec:method-data})."
        ),
        sources=[str(DATASHEET_MD)],
    )

    presence_header = sections["Field-presence rate (signed-off GT)"][0]
    assert presence_header[0].lower() == "field", presence_header
    presence_rows = [
        [r"\texttt{" + _tex_escape(_dequote(field)) + "}", present, rate.replace("%", r"\,\%")]
        for field, present, rate in sections["Field-presence rate (signed-off GT)"][1:]
    ]
    presence = _longtable(
        caption=(
            "Per-field presence in the signed-off held-out answer key: on how many of "
            "the 39 invoices each registry field is present at all."
        ),
        label="tab:heldout-presence",
        colspec="lrr",
        header=["Field", "Present", "Rate"],
        rows=presence_rows,
        note=(
            "Presence, not accuracy: a field absent from an invoice is an honest null in "
            "the answer key (\\S\\ref{sec:method-heldout-gt}), and per-field "
            "\\emph{scores} on so small a corpus would carry denominators this thesis "
            "does not consider reportable. Converted verbatim from the committed "
            "sanitised datasheet."
        ),
        sources=[str(DATASHEET_MD)],
    )

    freeze_section = next(k for k in sections if k.startswith("Freeze table"))
    freeze_body = sections[freeze_section][1:]
    n_unverified = sum(1 for row in freeze_body if row[3] != "yes")
    assert n_unverified == 0, f"{n_unverified} freeze rows unverified; note text is wrong"
    freeze_rows = [
        [
            r"\texttt{" + _tex_escape(_dequote(doc_id)) + "}",
            pages,
            r"{\ttfamily\tiny " + _tex_escape(_dequote(sha)) + "}",
        ]
        for doc_id, pages, sha, _verified in freeze_body
    ]
    freeze = _longtable(
        caption=(
            "Freeze table: SHA-256 of every held-out source PDF at seal time. Any "
            "change to a document changes its hash; filenames are withheld as private."
        ),
        label="tab:heldout-freeze",
        colspec="lrl",
        header=["Corpus id", "Pages", "SHA-256 (source PDF)"],
        rows=freeze_rows,
        note=(
            "The hash commits the evaluation to a fixed set of documents without "
            "disclosing them: a reader with access to the private corpus can verify "
            "integrity, and nobody else learns anything an aggregate does not already "
            "say. Every row is marked verified in the source datasheet (asserted at "
            "generation time). Converted verbatim from the committed sanitised "
            "datasheet."
        ),
        sources=[str(DATASHEET_MD)],
        font_size=r"\scriptsize\setlength{\tabcolsep}{4pt}",
    )
    return composition, presence, freeze


# --------------------------------------------------------------------------- figures

_INK = "#1f2933"
_ACCENT = "#3c6997"
_WARN = "#b7472a"
_MUTED = "#9aa5b1"


def _new_axes(width: float, height: float) -> tuple[Any, Any]:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(width, height))
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    axes.spines["left"].set_color(_MUTED)
    axes.spines["bottom"].set_color(_MUTED)
    axes.tick_params(colors=_INK, labelsize=9)
    axes.yaxis.label.set_color(_INK)
    axes.xaxis.label.set_color(_INK)
    return figure, axes


def _save(figure: Any, name: str) -> None:
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.pdf"
    figure.tight_layout()
    figure.savefig(path, bbox_inches="tight")
    print(f"  wrote {path}")
    plt.close(figure)


def figure_attribution() -> None:
    """The same structurer on reader transcripts and on perfect text, per field cluster.

    The two bars differ in one thing only: the text the structurer was given. The gap
    between them is therefore the part of the shortfall that reading causes, read directly
    off the chart rather than inferred.
    """
    reader = _read_json(FINETUNE_DIR / "attribution-val.json")
    perfect = _read_json(FINETUNE_DIR / "attribution-oracle-val.json")
    short = {
        "legacy-16": "Core\nheader",
        "new-flat": "Extended\nheader",
        "group:line_items": "Line\nitems",
        "group:vat_breakdown": "Tax\nbreakdown",
        "group:skonto": "Early-payment\ndiscount",
    }
    present = [key for key in short if key in reader["clusters"]]
    labels = [short[key] for key in present]
    reader_scores = [float(reader["clusters"][key]["pooled_f1"]) for key in present]
    perfect_scores = [
        float(perfect["clusters"][key]["pooled_f1"]) if key in perfect["clusters"] else 0.0
        for key in present
    ]

    figure, axes = _new_axes(6.4, 3.3)
    positions = list(range(len(labels)))
    axes.bar(
        [p - 0.2 for p in positions],
        reader_scores,
        width=0.4,
        color=_ACCENT,
        label="on the reader's transcript",
    )
    axes.bar(
        [p + 0.2 for p in positions],
        perfect_scores,
        width=0.4,
        color=_MUTED,
        label="on perfect text",
    )
    for position, low, high in zip(positions, reader_scores, perfect_scores, strict=True):
        if high <= low:
            continue
        axes.annotate(
            f"+{high - low:.2f}",
            xy=(position, high),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=7.5,
            color=_WARN,
        )
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, fontsize=8)
    axes.set_ylim(0, 1.14)
    axes.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axes.set_ylabel("cell-pooled F$_1$")
    # Above the axes: every bar starts at zero, so no in-axes corner is reliably free.
    axes.legend(
        frameon=False,
        fontsize=8,
        ncol=2,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
    )
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "attribution-by-cluster")


def figure_finetune_grid() -> None:
    """The 2x2 grid as grouped bars against the matched baseline."""
    figure, axes = _new_axes(6.2, 3.4)
    positions = [0, 1]
    axes.bar(
        [p - 0.26 for p in positions],
        [_overall(_arm("zeroshot-bf16")), _overall(_arm("oracle-bf16"))],
        width=0.24,
        color=_MUTED,
        label="no adapter (baseline)",
    )
    axes.bar(
        positions,
        [_overall(_arm("ft-reader-on-reader")), _overall(_arm("ft-reader-on-oracle"))],
        width=0.24,
        color=_ACCENT,
        label="adapter trained on reader transcripts",
    )
    axes.bar(
        [p + 0.26 for p in positions],
        [_overall(_arm("ft-oracle-on-reader")), _overall(_arm("ft-oracle-on-oracle"))],
        width=0.24,
        color=_WARN,
        label="adapter trained on perfect text",
    )
    axes.set_xticks(positions)
    axes.set_xticklabels(["evaluated on\nreader transcript", "evaluated on\nperfect text"])
    axes.set_ylim(0.7, 1.02)
    axes.set_ylabel("overall F$_1$")
    axes.legend(frameon=False, fontsize=8, ncol=1, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "finetune-grid")


def figure_devloss() -> None:
    """Both dev-loss curves, with the selected epoch marked."""
    reader = _read_json(FINETUNE_DIR / "adapter" / "horus_training_provenance.json")
    oracle = _read_json(FINETUNE_DIR / "adapter-oracle" / "horus_training_provenance.json")
    reader_curve = [(int(e), float(v)) for e, v in reader["selection"]["eval_loss_by_epoch"]]
    oracle_curve = [(int(e), float(v)) for e, v in oracle["selection"]["eval_loss_by_epoch"]]

    figure, axes = _new_axes(6.0, 3.2)
    axes.plot(
        [e for e, _ in reader_curve],
        [v for _, v in reader_curve],
        marker="o",
        color=_ACCENT,
        label="reader-transcript arm",
    )
    axes.plot(
        [e for e, _ in oracle_curve],
        [v for _, v in oracle_curve],
        marker="s",
        color=_WARN,
        label="perfect-text arm",
    )
    axes.axvline(1, color=_MUTED, linestyle="--", linewidth=0.9)
    axes.annotate(
        "selected",
        xy=(1, max(reader_curve[0][1], oracle_curve[0][1])),
        xytext=(1.3, max(v for _, v in reader_curve) * 0.7),
        fontsize=8,
        color=_INK,
        arrowprops={"arrowstyle": "->", "color": _MUTED, "linewidth": 0.8},
    )
    axes.set_xlabel("epoch")
    axes.set_ylabel("dev-slice loss")
    axes.legend(frameon=False, fontsize=8)
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "devloss-curve")


def figure_heldout_channels(data: dict[str, Any]) -> None:
    """Per-channel score, and the precision-versus-recall split behind it."""
    channels = data["channels"]
    labels = [_channel_label(str(e["channel"])).replace(", ", ",\n") for e in channels]
    positions = list(range(len(labels)))

    figure, axes = _new_axes(6.2, 3.2)
    axes.bar(
        [p - 0.2 for p in positions],
        [float(e["mean_per_invoice_f1"]) for e in channels],
        width=0.4,
        color=_ACCENT,
        label="mean per invoice",
    )
    axes.bar(
        [p + 0.2 for p in positions],
        [float(e["pooled_f1"]) for e in channels],
        width=0.4,
        color=_MUTED,
        label="cell-pooled",
    )
    axes.axhline(
        float(data["mean_per_invoice_f1"]),
        color=_WARN,
        linestyle="--",
        linewidth=0.9,
        label="whole corpus",
    )
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, fontsize=8)
    axes.set_ylim(0.6, 1.0)
    axes.set_ylabel("F$_1$")
    # Bars span the whole plot area (the axis starts at 0.6), so the legend goes outside.
    axes.legend(frameon=False, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "heldout-by-channel")

    figure, axes = _new_axes(6.2, 3.2)
    axes.bar(
        [p - 0.2 for p in positions],
        [float(e["precision"]) for e in channels],
        width=0.4,
        color=_ACCENT,
        label="precision",
    )
    axes.bar(
        [p + 0.2 for p in positions],
        [float(e["recall"]) for e in channels],
        width=0.4,
        color=_WARN,
        label="recall",
    )
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, fontsize=8)
    axes.set_ylim(0.6, 1.0)
    axes.set_ylabel("proportion")
    axes.legend(frameon=False, fontsize=8, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "heldout-precision-recall")


def figure_ruler_correction() -> None:
    """What the ruler repairs did to the score, on frozen generations."""
    reader_stages = [_overall(_arm("zeroshot-qwen")), _overall(_arm("zeroshot-qwen-adr059"))]
    oracle_stages = [_overall(_arm("oracle-tier1")), _overall(_arm("oracle-adr059"))]

    figure, axes = _new_axes(6.0, 3.0)
    positions = [0, 1]
    axes.plot(positions, reader_stages, marker="o", color=_ACCENT, label="reader-transcript arm")
    axes.plot(positions, oracle_stages, marker="s", color=_WARN, label="perfect-text arm")
    for index, value in enumerate(reader_stages):
        axes.annotate(
            f"{value:.4f}",
            xy=(index, value),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=_INK,
        )
    for index, value in enumerate(oracle_stages):
        axes.annotate(
            f"{value:.4f}",
            xy=(index, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=_INK,
        )
    axes.set_xticks(positions)
    axes.set_xticklabels(["before repair", "after repair"])
    axes.set_xlim(-0.3, 1.3)
    axes.set_ylabel("overall F$_1$")
    axes.legend(frameon=False, fontsize=8, loc="center right")
    axes.grid(axis="y", color=_MUTED, alpha=0.25, linewidth=0.6)
    axes.set_axisbelow(True)
    _save(figure, "ruler-correction")


# --------------------------------------------------------------------------- entry point


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-refresh-heldout",
        action="store_true",
        help="Read the sanitised held-out cache instead of re-scoring the private corpus.",
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Skip figure rendering.",
    )
    args = parser.parse_args(argv[1:])

    print("tables:")
    _write(TABLES_DIR / "sealed-val-arms.tex", build_sealed_val_arms())
    _write(TABLES_DIR / "finetune-grid.tex", build_finetune_grid())
    _write(TABLES_DIR / "precision-confound.tex", build_precision_confound())
    _write(TABLES_DIR / "devloss.tex", build_devloss_table())
    _write(TABLES_DIR / "hyperparameters.tex", build_hyperparameters())
    _write(TABLES_DIR / "attribution-clusters.tex", build_attribution_clusters())
    _write(TABLES_DIR / "attribution-shares.tex", build_attribution_shares())
    _write(
        TABLES_DIR / "oracle-renderer-correction.tex",
        build_oracle_renderer_correction(),
    )
    _write(TABLES_DIR / "reader-lineage.tex", build_reader_lineage())
    _write(TABLES_DIR / "corpus-composition.tex", build_corpus_composition())
    findability = build_reader_findability()
    if findability is not None:
        _write(TABLES_DIR / "reader-findability.tex", findability)

    heldout = load_heldout_breakdown(refresh=not args.no_refresh_heldout)
    if heldout is None:
        print(
            "  WARNING: no held-out data and no cache; held-out tables not generated",
            file=sys.stderr,
        )
    else:
        _write(TABLES_DIR / "heldout-headline.tex", build_heldout_headline(heldout))
        _write(TABLES_DIR / "heldout-by-channel.tex", build_heldout_by_channel(heldout))

    _write(TABLES_DIR / "field-registry.tex", build_field_registry())
    composition, presence, freeze = build_heldout_datasheet_tables()
    _write(TABLES_DIR / "heldout-composition.tex", composition)
    _write(TABLES_DIR / "heldout-presence.tex", presence)
    _write(TABLES_DIR / "heldout-freeze.tex", freeze)

    if args.tables_only:
        return 0

    import matplotlib

    matplotlib.use("Agg")

    print("figures:")
    figure_attribution()
    figure_finetune_grid()
    figure_devloss()
    figure_ruler_correction()
    if heldout is not None:
        figure_heldout_channels(heldout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
