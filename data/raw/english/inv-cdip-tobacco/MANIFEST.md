---
slug: inv-cdip-tobacco
language: english
source_url: "https://github.com/salesforce/inv-cdip"
source_type: git_clone
license_spdx: "CC-BY-NC-4.0"
license_url: "https://github.com/salesforce/inv-cdip/blob/main/LICENSE.txt"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "f19e620340ff67cf18edba06a642a47e7506b7d1"
commit_date: "2024-10-29T10:25:11-07:00"
file_count: 362
total_bytes: 2119461
sha256_aggregate: "7bea144a5a07c74ad32e8c5416b58e43af3d8cd6ae8e0f7f1794c2fd66435891"
sample_load_passed: true
sample_load_notes: "Annotations-only acquisition by intent (decision 2026-05-13 closing sub-issue #28 not-planned): 350 JSON annotation files verified (json.load, keys: image_dims + Fields). Underlying invoice PDFs intentionally not downloaded — UCSF Industry Documents service download_data.py is not pursued for the HORUS pilot scope. Annotation structure (field labels + bboxes) alone enables Berghaus-style baseline cross-comparison without raw scans. 362 total files = 350 annotations + 12 metadata/scripts."
anomalies: []
source_stub: "../../../../docs/sources/datasets/inv-cdip-tobacco.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/inv-cdip-tobacco.md`](../../../../docs/sources/datasets/inv-cdip-tobacco.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://github.com/salesforce/inv-cdip data/raw/english/inv-cdip-tobacco
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/english/inv-cdip-tobacco log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/english/inv-cdip-tobacco/.git
# Regenerate this manifest:
make data-manifest SLUG=inv-cdip-tobacco LANG=english
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=inv-cdip-tobacco LANG=english
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
