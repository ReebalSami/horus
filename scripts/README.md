# scripts/

One-off and reusable utility scripts for HORUS.

## Tracking status

Tracked. Scripts here are committed as ordinary Python files (no jupytext
pairing required).

## Canonical contents

```
scripts/
├── dataset_prep/   # dataset download helpers, format conversions
└── utils/          # shared utilities reused across scripts
```

The first expected script is the ZUGFeRD XML extraction helper (brainstorm §8;
scoped in issue #15 "XML-extraction script + script-architecture ADR").

Scripts that grow into a reusable library component are graduated to `src/horus/`
via a standard refactor + ADR.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §8 step 1
- Issue #8: Repo structural prep (M2D.5 step 1)
- Issue #15: XML-extraction script + script-architecture ADR (next reference)
