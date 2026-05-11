# data/

Raw and intermediate dataset corpora for HORUS experiments.

## ⚠ Gitignore status

`data/*` is gitignored. Only this `README.md` is tracked. Dataset downloads
belong here; they are large and must not be committed. To allow a specific
small reference file to be tracked, use `git add -f data/<path>`.

## Canonical layout (per brainstorm §6)

```
data/
├── raw/
│   ├── zugferd-corpus/         # ZUGFeRD/corpus clone (hundreds of MB)
│   ├── cord-v2/                # naver-clova-ix/cord-v2 via HF datasets (~1 GB)
│   ├── sroie/                  # SROIE challenge corpus (hundreds of MB)
│   ├── funsd/                  # FUNSD form-understanding dataset
│   ├── omnidocbench/           # opendatalab/OmniDocBench (several GB)
│   ├── gi-2021-de-invoices/    # GI 2021 German invoice dataset (locate at M2D.5)
│   └── inv-cdip-tobacco/       # inv-cdip Tobacco (locate at M2D.5)
└── processed/                  # intermediate artefacts (conversions, splits, etc.)
```

Downloads are tracked as a user-action checklist in issue #12.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §6 (dataset table) + §8 step 1
- Issue #8: Repo structural prep (M2D.5 step 1)
