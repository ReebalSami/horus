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
│   │   ├── inv-cdip-tobacco/      # github.com/salesforce/inv-cdip (CC-BY-NC-4.0); annotations only
│   │   └── parsee-ai-invoices-example/  # HF parsee-ai/invoices-example (MIT)
│   ├── korean/
│   │   └── cord-v2/               # HF naver-clova-ix/cord-v2 (CC-BY-4.0)
│   ├── multilingual/
│   │   └── omnidocbench/          # HF opendatalab/OmniDocBench
│   └── (gi-2021-de-invoices/ — deferred; revisit only if pilot surfaces insufficient German variety)
├── finetune/                      # adaptation-study artefacts (#55); see below
├── self-collected/                # PRIVATE held-out Belege set (ADR-040); see below
└── processed/                     # intermediate artefacts (conversions, splits, etc.)
```

## `finetune/` — adaptation-study artefacts (#55)

Mixed tracking. The **tracked** exceptions (force-added per the rule above) are the
small, sanitized evidence files the thesis asset pipeline consumes: the sealed split
(`split.json`), the reader bake-off transcripts over synthetic ZUGFeRD invoices
(`bakeoff/`, `bakeoff-local-m1/`), and the per-run eval/attribution JSONs
(`eval-*.json`, `attribution-*.json`, …). Everything else — GPU transcripts, LoRA
adapter weights, per-invoice model outputs — stays gitignored and regenerable
(recipes: `scripts/gpu/README.md` + the `finetune_*` scripts).

## `self-collected/` — the private held-out Belege set (ADR-040)

**Never committed** — belt-and-braces gitignore rule; even `!` un-ignores must not
countermand it. Contains the 39 real invoices (`german/`, `english/`), the
hand-verified answer keys (`gt/` drafts, `_promoted/` signed-off), the local
`index.json` freeze record, and the GT-adjudication working trees (`_judge/`,
`_azure/`, `_transcripts/`, …). The only tracked representations are **sanitized
aggregates**: `docs/architecture/belege-heldout-datasheet.md` (id ↔ sha256 freeze
table) and `eval/heldout-breakdown.json` (pooled scores).

Examiners restore this tree from the encrypted release asset via
`make get-frozen-testset` (ADR-075; see the README's "Held-out test set" section).

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

Tracked as a checklist in issue #12 (closed 2026-05-13). After M2D.5 step 3 closure,
the pilot (`#13`) runs against data already on disk; the previously-pending sub-issues
were resolved as: `#25` (SROIE) closed not-planned, `#26` (GI 2021) closed deferred,
`#28` (inv-cdip-tobacco PDF images) closed not-planned.

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
- Sub-issues (all closed 2026-05-13): #25 SROIE (not-planned), #26 GI 2021 (deferred), #28 inv-cdip-tobacco PDF images (not-planned)
