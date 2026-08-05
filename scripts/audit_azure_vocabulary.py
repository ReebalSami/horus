"""Measure the Azure `prebuilt-invoice` vocabulary actually observed in our corpus (ADR-061).

`AZURE_FIELD_MAP` is a *hypothesis* about what the service returns. Microsoft documents the
authoritative field list behind a link rather than inline, so a table written from the
quickstart samples is an unverified claim about data — exactly the mistake ADR-058 was
written to stop after 34 invented `prompt_alias` entries turned out to match 0/146 documents.

This script is the forcing function that keeps the table honest. It reads the archived raw
responses under `_azure/raw/` and reports:

- every Azure field name observed, with page-count and wire type;
- the row-cell names inside each array field (`Items`, `TaxDetails`, `PaymentDetails`);
- how each observed name is currently treated — mapped, deliberately unused, or **unknown**;
- which HORUS registry fields have no Azure candidate at all.

Unknown names are the actionable output: each one is either a mapping we are missing or a
field we should consciously record as unused. Leaving one unclassified means a reading the
service offered is being silently discarded.

Prints names, counts and types only — never values (ADR-040), so the output is safe to paste
into an ADR or a commit message.

Usage:
    uv run python scripts/audit_azure_vocabulary.py
    uv run python scripts/audit_azure_vocabulary.py --raw-dir path/to/raw
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horus.eval.azure_invoice import (  # noqa: E402
    AZURE_ARRAY_FIELD_MAP,
    AZURE_FIELD_MAP,
    KNOWN_UNUSED_AZURE_FIELDS,
    array_source_fields,
    not_covered_fields,
)
from horus.eval.ground_truth import FIELDS  # noqa: E402

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "self-collected" / "_azure" / "raw"

#: Array fields whose row cells are worth enumerating.
_ARRAY_FIELDS = ("Items", "TaxDetails", "PaymentDetails")


def iter_documents(raw_dir: Path) -> Iterator[Mapping[str, Any]]:
    """Yield every analyzed document from every archived per-page response."""
    for path in sorted(raw_dir.glob("*.json")):
        try:
            pages = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  !! {path.name}: unreadable ({exc})", file=sys.stderr)
            continue
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            for document in page.get("documents") or []:
                if isinstance(document, Mapping):
                    yield document


def _fields_of(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = document.get("fields")
    if not isinstance(raw, Mapping):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, Mapping)}


def collect(raw_dir: Path) -> tuple[Counter[str], dict[str, str], dict[str, Counter[str]]]:
    """Observed field counts, wire type per field, and row-cell counts per array field."""
    counts: Counter[str] = Counter()
    types: dict[str, str] = {}
    cells: dict[str, Counter[str]] = {name: Counter() for name in _ARRAY_FIELDS}

    for document in iter_documents(raw_dir):
        for name, payload in _fields_of(document).items():
            counts[name] += 1
            types.setdefault(name, str(payload.get("type", "?")))
            if name not in cells:
                continue
            for row in payload.get("valueArray") or []:
                if not isinstance(row, Mapping):
                    continue
                row_cells = row.get("valueObject")
                if isinstance(row_cells, Mapping):
                    for cell in row_cells:
                        cells[name][str(cell)] += 1
    return counts, types, cells


def classify(name: str) -> str:
    """How the mapping layer currently treats an observed Azure field."""
    for horus_key, candidates in AZURE_FIELD_MAP.items():
        if name in candidates:
            return f"-> {horus_key}"
    nested = sorted(
        horus_key for horus_key, (source, _cell) in AZURE_ARRAY_FIELD_MAP.items() if source == name
    )
    if nested:
        return f"-> {', '.join(nested)}"
    if name in array_source_fields():
        return "-> repeating group"
    if name in KNOWN_UNUSED_AZURE_FIELDS:
        return "unused (deliberate)"
    return "UNKNOWN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_azure_vocabulary",
        description="Measure the observed Azure prebuilt-invoice vocabulary (ADR-061).",
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args(argv)

    if not args.raw_dir.is_dir():
        print(
            f"No archived responses at {args.raw_dir}. Run scripts/azure_heldout_gt.py first.",
            file=sys.stderr,
        )
        return 1

    counts, types, cells = collect(args.raw_dir)
    if not counts:
        print(f"No analyzed documents found under {args.raw_dir}.", file=sys.stderr)
        return 1

    print(f"Observed Azure fields ({len(counts)} distinct, {args.raw_dir}):\n")
    print(f"  {'FIELD':<28} {'PAGES':>5}  {'TYPE':<12} TREATMENT")
    unknown: list[str] = []
    for name, count in counts.most_common():
        treatment = classify(name)
        if treatment == "UNKNOWN":
            unknown.append(name)
        print(f"  {name:<28} {count:>5}  {types.get(name, '?'):<12} {treatment}")

    for array_name in _ARRAY_FIELDS:
        row_cells = cells.get(array_name) or Counter()
        if not row_cells:
            continue
        rendered = ", ".join(f"{cell} ({n})" for cell, n in row_cells.most_common())
        print(f"\n{array_name}[] row cells: {rendered}")

    uncovered = not_covered_fields()
    print(
        f"\nHORUS fields with no Azure candidate ({len(uncovered)} of {len(FIELDS)}): "
        f"{', '.join(uncovered) if uncovered else '(none)'}"
    )

    if unknown:
        print(
            f"\nUNKNOWN — observed but neither mapped nor deliberately unused "
            f"({len(unknown)}): {', '.join(sorted(unknown))}\n"
            "Each is a reading the service offered that we are discarding silently. "
            "Map it in AZURE_FIELD_MAP or record it in KNOWN_UNUSED_AZURE_FIELDS with "
            "the reason."
        )
        return 1

    print("\nNo unknown fields — every observed name is mapped or deliberately unused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
