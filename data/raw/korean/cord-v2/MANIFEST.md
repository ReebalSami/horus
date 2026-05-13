---
slug: cord-v2
language: korean
source_url: "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
source_type: hf_git_clone
license_spdx: "CC-BY-4.0"
license_url: "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "7f0115a4b758a71d6473b8d085751692da2fef98"
commit_date: "2022-07-19T23:43:33Z"
file_count: 9
total_bytes: 2307287084
sha256_aggregate: "9a0a75059feba6fc83832d90506ab64925b30e1659f1b60881de314303212bf2"
sample_load_passed: true
sample_load_notes: "Verified 3x parquet files via PAR1 magic bytes (head + tail). Sizes: test=234 MB, train-00003=455 MB, train-00001=441 MB. 9 total files: 6 parquet (test=1, train=4, validation=1) + dataset_infos.json + README.md + .gitattributes."
anomalies: []
source_stub: "../../../../docs/sources/datasets/cord-v2.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/cord-v2.md`](../../../../docs/sources/datasets/cord-v2.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://huggingface.co/datasets/naver-clova-ix/cord-v2 data/raw/korean/cord-v2
# For HF datasets with LFS: git lfs pull (before dropping .git/)
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/korean/cord-v2 log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/korean/cord-v2/.git
# Regenerate this manifest:
make data-manifest SLUG=cord-v2 LANG=korean
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=cord-v2 LANG=korean
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
