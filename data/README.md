# data/

Raw and intermediate dataset corpora for HORUS experiments.

## ⚠ Gitignore status

`data/*` is gitignored. Only this `README.md` is tracked. Dataset downloads
belong here; they are large and must not be committed. To allow a specific
small reference file to be tracked, use `git add -f data/<path>`.

## Canonical layout (per brainstorm §6.2 + §9; M2D.5 step 3)

Flat one level under language; provider info lives in `MANIFEST.md` frontmatter.

```
data/
├── raw/
│   ├── german/
│   │   └── zugferd-corpus/        # github.com/ZUGFeRD/corpus
│   ├── english/
│   │   ├── funsd/                 # guillaumejaume.github.io/FUNSD
│   │   ├── fatura2-invoices/      # HF mathieu1256/FATURA2-invoices (CC-BY-4.0)
│   │   ├── inv-cdip-tobacco/      # github.com/salesforce/inv-cdip (CC-BY-NC-4.0)
│   │   ├── sroie/                 # ICDAR 2019 RRC (user-action: registration req'd)
│   │   └── parsee-ai-invoices-example/  # HF parsee-ai/invoices-example (MIT)
│   ├── korean/
│   │   └── cord-v2/               # HF naver-clova-ix/cord-v2 (CC-BY-4.0)
│   ├── multilingual/
│   │   └── omnidocbench/          # HF opendatalab/OmniDocBench
│   └── (gi-2021-de-invoices/ — user-action: see issue #26)
└── processed/                     # intermediate artefacts (conversions, splits, etc.)
```

## Per-dataset audit record

Each downloaded dataset has a **git-tracked `MANIFEST.md`** at its root:

```
data/raw/<lang>/<slug>/
├── MANIFEST.md      ← git-tracked; sha256_aggregate, file_count, sample_load, recipe
├── sha256.txt       ← gitignored; per-file sha256 list (regeneratable)
└── ...              ← gitignored raw files
```

Generate or refresh a MANIFEST:

```sh
make data-manifest SLUG=<slug> LANG=<lang> SOURCE_URL=<url> LICENSE_SPDX=<spdx>
# For large datasets (slow sha256): add SKIP_SHA256=1
```

## Downloads

Tracked as a checklist in issue #12. Sub-issues #25 (SROIE) and #26 (GI 2021) are
user-action items assigned to @ReebalSami.

## `acquisition_status` field semantics

Each dataset stub at `docs/sources/datasets/<slug>.md` and each downloaded MANIFEST
carries an `acquisition_status` field with one of these values (locked in
during the M2D.5 issue #12 Q&A round, Q5):

| Value | Meaning |
|---|---|
| `completed` | Files are downloaded under `data/raw/<lang>/<slug>/`, sample-load passed, MANIFEST exists. |
| `pending-user-action` | Requires human action (registration, author request, manual permission). Tracked via a sub-issue of #12. |
| `deferred` | Tier-3 dataset; not in scope for the current milestone. Re-evaluate at next sprint review. |
| `skipped` | Explicitly de-scoped. Reason captured in the stub body. Won't be acquired without an ADR change. |

Stubs with status `completed` link to their MANIFEST via the `data_manifest:` field.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §6.2 (dataset table) + §9 + §9 amendments
- Issue #8: Repo structural prep (M2D.5 step 1)
- Issue #12: Dataset downloads (M2D.5 step 3)
- Sub-issues: #25 (SROIE), #26 (GI 2021), #28 (inv-cdip-tobacco images) — all `pending-user-action`
