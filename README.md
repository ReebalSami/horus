# HORUS

**H**ybrid **O**CR-free **R**eading & **U**nderstanding **S**ystem.

Master's thesis project (FH Wedel, SS 2026): privacy-first document intelligence for German tax/accounting professionals via local vision-language models. Documents stay inside the firm; the analyst keeps full audit-trail visibility.

## Why HORUS?

**Backronym**: **H**ybrid **O**CR-free **R**eading & **U**nderstanding **S**ystem.

**Symbolic anchor**: Horus is the Egyptian falcon-headed god of vision and kingship. The **Eye of Horus** — the *wedjat* — is one of antiquity's most enduring symbols of perception, protection, and restoration. Vision-language models *see* documents holistically without an OCR transcription step; the mythology maps directly to the central methodological commitment of this thesis (OCR-free, VLM-first; ratified at `docs/decisions/ADR-003-brand-naming-horus.md`).

## What's in this repository

HORUS is designed as a three-layer system — **(1) reading**: OCR-free extraction of structured invoice data with local vision-language models; **(2) knowledge graph**: entities and relations over extracted data; **(3) analytical queries** over that graph. The thesis implements and evaluates **Layer 1** end-to-end; Layers 2–3 are design and future work (the manuscript's scope guard, ADR-054).

Everything reported in the thesis is reproducible from this repository:

| Artifact | Where |
|---|---|
| Thesis manuscript (LaTeX; `make thesis`) | `thesis/` |
| Evaluation harness, scorer, ground-truth machinery | `src/horus/` |
| Experiments (jupytext-paired, papermill-run) | `experiments/` + `configs/` |
| Committed evaluation evidence + audit reports | `eval/`, `data/finetune/` |
| Architecture decision records (indexed) | `docs/decisions/` |
| Manuscript review records | `docs/reviews/` |
| Archived primary sources (papers, tools, datasets, legal) | `docs/sources/` |
| Observability dashboard (Streamlit; `make app`) | `app/` |
| Sanitized datasheet of the private held-out set | `docs/architecture/belege-heldout-datasheet.md` |

## Quick start

```sh
make install     # uv sync (creates .venv, installs deps + dev group)
make test        # pytest — corpus-dependent tests auto-skip when data is absent
make lint        # ruff check + format check
make typecheck   # mypy
```

Requirements: Python 3.14+ (pinned in `.python-version`) and [`uv`](https://docs.astral.sh/uv/). Every runnable entry point is a Make target — **`make help`** lists all of them.

## Reproducing the results

| Area | Targets |
|---|---|
| Evidence pipeline | `pilot-13`, `adapter-iterate`, `arm-b`, `reading-ceiling`, `inspect-pilot-13` |
| Instrument audits | `audit-prompts`, `audit-heldout-exclusions`, `glossary` |
| Held-out set | `get-frozen-testset` (examiner restore), `heldout-index`, `heldout-datasheet` |
| Tracking / UI | `mlflow-ui`, `app` |
| Thesis | `thesis-assets` (regenerate every reported table + figure from committed evidence), `thesis`, `thesis-clean` |
| Smokes | `zugferd-smoke`, `inference-smoke`, `cohort-smoke`, `orchestrated-smoke` |

No measured number in the manuscript is hand-copied: `make thesis-assets` regenerates all tables and figures from the committed measurement artifacts, and `make thesis` builds the PDF (see `thesis/README.md`).

Experiment runs are tracked locally in MLflow (SQLite metadata + filesystem artifacts, both gitignored — every run stays on the analyst's machine). Browse with `make mlflow-ui` at `http://127.0.0.1:8080`.

## Held-out test set (examiner access)

The final evaluation runs on a **private held-out set of 39 real invoices** (ADR-040). It is never committed — the repo tracks only the sanitized datasheet ([`docs/architecture/belege-heldout-datasheet.md`](docs/architecture/belege-heldout-datasheet.md)), whose id ↔ sha256 freeze table is reproduced in the thesis appendix. Examiners receive the set as an **encrypted GitHub Release asset** (AES-256-GCM; ADR-075):

```sh
git clone https://github.com/ReebalSami/horus && cd horus
make install
make get-frozen-testset    # asks for the password (handed over by the author directly to the examiners, out-of-band from the public release)
```

The command downloads the blob from the GitHub Release, decrypts it, restores `data/self-collected/`, and verifies every invoice's sha256 against the frozen datasheet — proving the restored set is **byte-identical** to the one the thesis evaluated. After restore, the held-out targets run locally (`make audit-heldout-exclusions`, `make heldout-datasheet`, …).

## Repository layout

```
.
├── pyproject.toml          # uv-managed project + dependency groups
├── Makefile                # every runnable entry point (`make help`)
├── .python-version         # 3.14
├── .env.example            # optional env knobs (torch backend; GT-authoring keys — never on the inference path)
├── .github/workflows/ci.yml  # lint + typecheck + test on every push/PR (ADR-023)
├── src/horus/              # main package: config schema, eval harness, fine-tune, EDA, CLI
├── scripts/                # operational scripts, grouped in scripts/README.md
├── experiments/            # jupytext-paired .py experiments (papermill + Quarto)
├── configs/                # per-experiment YAML, Pydantic-validated at boot (configs/README.md)
├── tests/                  # pytest suite; corpus-dependent tests auto-skip (ADR-023)
├── eval/                   # committed audit reports + sanitized result JSONs (eval/README.md)
├── data/                   # gitignored corpora; tracked MANIFESTs + fine-tune evidence (data/README.md)
├── app/                    # Streamlit observability dashboard (`make app`)
├── thesis/                 # LaTeX manuscript (`make thesis`; thesis/README.md)
└── docs/                   # decision records, review records, archived sources, datasheets
```

## License

Proprietary — all rights reserved (thesis project). Source code, models, datasets, and derived artifacts are not licensed for external use, redistribution, or commercial adaptation. The thesis text itself is governed by FH Wedel's Prüfungsordnung.
