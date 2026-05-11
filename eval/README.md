# eval/

Evaluation-harness scripts and ground-truth reference data for HORUS.

## Tracking status

`eval/` is **tracked** (not gitignored). Unlike `data/`, evaluation scripts
and small reference ground-truth files are committed here. Large GT corpora
that exceed reasonable git size should be placed in `data/raw/` instead and
loaded at eval time.

## Canonical contents

```
eval/
├── harness/        # evaluation-harness scripts (Python)
├── ground_truth/   # small curated GT reference sets (JSON / XML)
└── results/        # output metrics per experiment run (gitignored via .gitignore additions if needed)
```

Concrete harness design is deferred to the experiment phase. This directory is
scaffolded now so that import paths and Makefile targets can reference a stable
location.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §8 step 1
- Issue #8: Repo structural prep (M2D.5 step 1)
