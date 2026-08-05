"""Report held-out ground-truth sign-off progress (ADR-062).

Answers two questions the sign-off page cannot: *how far along is the whole corpus*, and
*is what was written actually readable by the scorer*. The second matters more than it
sounds — a promoted document that the evaluation cannot parse is worse than no document,
because the sign-off page would keep reporting success while the answer key stayed unusable.

Run it any time:

    uv run python scripts/promotion_status.py

Add `--verbose` for a per-document line.

Privacy (ADR-040): prints counts, ids, field NAMES, and provenance classes only. Never a
field VALUE. The held-out set is real client invoices.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from horus.eval.heldout import build_groundtruth_from_json, load_heldout_index  # noqa: E402
from horus.eval.promotion import (  # noqa: E402
    DECIDED_BY_AUTHOR,
    PROMOTED_SCHEMA_VERSION,
    load_promoted,
    promoted_path,
)

DEFAULT_CORPUS_ROOT = Path("data/self-collected")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument("--verbose", action="store_true", help="One line per document.")
    args = parser.parse_args(argv[1:])

    corpus_root = Path(args.corpus)
    items = load_heldout_index(corpus_root)
    if not items:
        print(f"no held-out index under {corpus_root}", file=sys.stderr)
        return 1

    signed = 0
    started = 0
    untouched = 0
    author_cells = 0
    pending_cells = 0
    unreadable: list[str] = []
    classes: Counter[str] = Counter()

    for item in items:
        document = load_promoted(corpus_root, item.id)
        if document is None:
            untouched += 1
            if args.verbose:
                print(f"  {item.id:26s} not started")
            continue

        sign_off = document.get("sign_off") or {}
        decided = int(sign_off.get("decided", 0) or 0)
        escalated = int(sign_off.get("escalated", 0) or 0)
        pending = int(sign_off.get("pending", 0) or 0)
        verified = bool(document.get("verified", False))
        pending_cells += pending

        provenance = document.get("provenance") or {}
        for entry in provenance.values():
            if not isinstance(entry, dict):
                continue
            classes[str(entry.get("class"))] += 1
            if entry.get("decided_by") == DECIDED_BY_AUTHOR:
                author_cells += 1

        # The load-bearing check: can the evaluation read this back? `verified` means
        # nothing if the scorer chokes on the file.
        try:
            gt = build_groundtruth_from_json(promoted_path(corpus_root, item.id))
            n_present = sum(1 for f in gt.header.values() if f.raw_value is not None)
        except Exception as exc:  # noqa: BLE001 — any failure means unusable, report it
            unreadable.append(f"{item.id}: {type(exc).__name__}: {exc}")
            n_present = -1

        if verified:
            signed += 1
        else:
            started += 1

        if args.verbose:
            state = "SIGNED OFF" if verified else f"in progress ({pending} left)"
            schema = document.get("schema_version")
            flag = "" if schema == PROMOTED_SCHEMA_VERSION else f"  [schema {schema}!]"
            print(
                f"  {item.id:26s} {state:24s} {decided}/{escalated} decided  "
                f"{n_present} fields present{flag}"
            )

    total = len(items)
    print(f"\nheld-out sign-off  ({corpus_root})")
    print(f"  documents            {total}")
    print(f"  signed off           {signed}")
    print(f"  in progress          {started}")
    print(f"  not started          {untouched}")
    print(f"  cells you decided    {author_cells}")
    print(f"  cells still pending  {pending_cells}")

    if classes:
        print("\n  provenance across promoted documents:")
        for name, count in classes.most_common():
            print(f"    {name:24s} {count}")

    if unreadable:
        print("\n  UNREADABLE by the scorer (must be fixed before evaluation):")
        for line in unreadable:
            print(f"    {line}")
        return 1

    if signed:
        print("\n  all promoted documents parse cleanly through build_groundtruth_from_json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
