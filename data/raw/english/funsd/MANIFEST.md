---
slug: funsd
language: english
source_url: "https://guillaumejaume.github.io/FUNSD/dataset.zip"
source_type: direct_zip
license_spdx: "LicenseRef-FUNSD-noncommercial-research"
license_url: "https://guillaumejaume.github.io/FUNSD/work/"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: ""
commit_date: ""
file_count: 401
total_bytes: 27789495
sha256_aggregate: "3079ebf1bd1d9dedc7ba512ed2f19b61dae2c8b1bee583ef491292cf7a571787"
sample_load_passed: true
sample_load_notes: "Opened 3 random PNGs (\\x89PNG magic verified) and parsed 3 random JSONs via json.load; all passed. Structure: dataset/{training_data,testing_data}/{annotations,images}/."
anomalies: []
source_stub: "../../../../docs/sources/datasets/funsd.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/funsd.md`](../../../../docs/sources/datasets/funsd.md) for bibliographic details.

## Download recipe (reproducible)

```sh
# Download from: https://guillaumejaume.github.io/FUNSD/dataset.zip
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/english/funsd log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/english/funsd/.git
# Regenerate this manifest:
make data-manifest SLUG=funsd LANG=english
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=funsd LANG=english
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
