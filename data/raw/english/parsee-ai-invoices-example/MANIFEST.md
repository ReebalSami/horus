---
slug: parsee-ai-invoices-example
language: english
source_url: "https://huggingface.co/datasets/parsee-ai/invoices-example"
source_type: hf_git_clone
license_spdx: "MIT"
license_url: "https://huggingface.co/datasets/parsee-ai/invoices-example"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "85fd1e51ed6e2975dcf86b98b5d4256e72002e5e"
commit_date: "2024-03-20T08:56:13Z"
file_count: 3
total_bytes: 45995
sha256_aggregate: "300ac498ed79ebb52c66475eac9ae61b8702537e429c7187f8f07e5c7b856c47"
sample_load_passed: true
sample_load_notes: "Verified parquet via PAR1 magic bytes (head + tail). Single 42.7 KB parquet file with 45 rows. 3 total files: invoices_parsee.parquet + README.md + .gitattributes."
anomalies: []
source_stub: "../../../../docs/sources/datasets/parsee-ai-invoices-example.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/parsee-ai-invoices-example.md`](../../../../docs/sources/datasets/parsee-ai-invoices-example.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://huggingface.co/datasets/parsee-ai/invoices-example data/raw/english/parsee-ai-invoices-example
# For HF datasets with LFS: git lfs pull (before dropping .git/)
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/english/parsee-ai-invoices-example log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/english/parsee-ai-invoices-example/.git
# Regenerate this manifest:
make data-manifest SLUG=parsee-ai-invoices-example LANG=english
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=parsee-ai-invoices-example LANG=english
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
