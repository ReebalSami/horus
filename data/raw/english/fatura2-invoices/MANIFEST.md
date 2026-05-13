---
slug: fatura2-invoices
language: english
source_url: "https://huggingface.co/datasets/mathieu1256/FATURA2-invoices"
source_type: hf_git_clone
license_spdx: "CC-BY-4.0"
license_url: "https://huggingface.co/datasets/mathieu1256/FATURA2-invoices"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "bcbb2fbb3c4701b87f5659ecbfbc55ad695aac21"
commit_date: "2024-02-18T22:00:49Z"
file_count: 4
total_bytes: 342754665
sha256_aggregate: "ab5ef4e6221314753897ba2295b1dffc2d7287320cd084e1957815aa5e88bb84"
sample_load_passed: true
sample_load_notes: "Verified 2x parquet files via PAR1 magic bytes (head + tail). Sizes: train=292 MB (8.6K rows with embedded images), test=50 MB (1.4K rows). Schema: image, ner_tags, bboxes, tokens, id. 4 total files: 2 parquet + README.md + .gitattributes."
anomalies: []
source_stub: "../../../../docs/sources/datasets/fatura2-invoices.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/fatura2-invoices.md`](../../../../docs/sources/datasets/fatura2-invoices.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://huggingface.co/datasets/mathieu1256/FATURA2-invoices data/raw/english/fatura2-invoices
# For HF datasets with LFS: git lfs pull (before dropping .git/)
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/english/fatura2-invoices log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/english/fatura2-invoices/.git
# Regenerate this manifest:
make data-manifest SLUG=fatura2-invoices LANG=english
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=fatura2-invoices LANG=english
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
