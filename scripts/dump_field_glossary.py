#!/usr/bin/env python3
"""Print the rendered structurer field glossary, with per-alias corpus grounding.

The glossary is the text the structuring model actually reads, so it deserves to be
inspectable directly rather than inferred from the registry source. For each glossed
field this prints the description, then every ``prompt_alias`` annotated with the
number of corpus transcripts that literally contain it — the evidence that decides
whether an alias earns its place in the prompt (ADR-048 measured over-glossing as
net-negative, so an alias with 0 hits is a pure cost).

    uv run python scripts/dump_field_glossary.py            # annotated audit view
    uv run python scripts/dump_field_glossary.py --raw      # exact prompt text

Companion to ``scripts/audit_field_prompts.py`` (which gates) — this one explains.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horus.eval import structurer  # noqa: E402
from horus.eval.ground_truth import FIELDS  # noqa: E402
from horus.finetune.answerability import _canon  # noqa: E402
from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.dataset import build_records, reader_text_from_transcript  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        action="store_true",
        help="print the exact glossary text sent to the model, nothing else",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/finetune-structurer.yaml"),
        help="finetune config selecting the reader lineage used for grounding",
    )
    args = parser.parse_args()

    if args.raw:
        print(structurer.render_field_glossary())
        return

    cfg = FinetuneConfig.from_yaml(args.config)
    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    usable = [r for r in records if r.ready and r.gt is not None]
    folded = []
    for rec in usable:
        assert rec.transcript_path is not None
        folded.append(
            _canon(unicodedata.normalize("NFC", reader_text_from_transcript(rec.transcript_path)))
        )

    glossed = [(k, s) for k, s in FIELDS.items() if s.description is not None]
    print(f"glossed fields: {len(glossed)} / {len(FIELDS)}")
    print(f"grounding corpus: {len(folded)} transcripts ({cfg.reader_model})")
    print(f"rendered glossary: {len(structurer.render_field_glossary())} chars")
    print()

    for key, spec in glossed:
        n_present = sum(1 for r in usable if r.gt is not None and r.gt.header[key].is_present)
        print(f"{key}  [{spec.bt_code}]  present in {n_present}/{len(usable)} invoices")
        print(f"    {spec.description}")
        for alias in spec.prompt_aliases or ():
            hits = sum(1 for f in folded if _canon(unicodedata.normalize("NFC", alias)) in f)
            flag = "  <-- 0 HITS, UNGROUNDED" if hits == 0 else ""
            print(f"      {hits:>3} hits  {alias!r}{flag}")
        print()


if __name__ == "__main__":
    main()
