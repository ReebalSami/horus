---
slug: zugferd-corpus
language: german
source_url: "https://github.com/ZUGFeRD/corpus"
source_type: git_clone
license_spdx: "Apache-2.0"
license_url: "https://github.com/ZUGFeRD/corpus/blob/master/LICENSE"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "8a8d7330f67c5d77bd6f1095d629f3e6e25ce1ae"
commit_date: "2025-09-03T09:08:35+02:00"
file_count: 250
total_bytes: 151876604
sha256_aggregate: "9003a115aa2247ef15bcf50c8dd8628f4970fba3211436639109f3526ff83119"
sample_load_passed: true
sample_load_notes: "Opened 3 random PDFs (%PDF- magic verified) and parsed 3 random XMLs via xml.etree; all passed. Re-verified 2026-05-13 via /tmp/horus-verify-all.py: zero magic-byte failures across all 250 files (151 PDFs + 88 XMLs + 11 README/LICENSE/metadata). Corpus contains ZUGFeRDv1/, ZUGFeRDv2/, XML-Rechnung/{FX,CII,UBL}/, fatturaPA/, incoming/, PEPPOL/, unstructured/ subdirs."
anomalies:
  - "MANIFEST regenerated 2026-05-13 to fix .git/-inflation bug: original (commit 6c71da5, PR #27) reported file_count=279 / total_bytes=178,846,554 / sha256_aggregate=bc031e43... because data_manifest.py at that time counted .git/ contents in the scan. After PR #29 fix to skip .git/, the correct count is 250 files / 151,876,604 bytes / sha256=9003a115... — same disk content, accurate stats. No data was lost; .git/ was always meant to be dropped post-clone."
source_stub: "../../../../docs/sources/datasets/zugferd-corpus.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/zugferd-corpus.md`](../../../../docs/sources/datasets/zugferd-corpus.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://github.com/ZUGFeRD/corpus data/raw/german/zugferd-corpus
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/german/zugferd-corpus log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/german/zugferd-corpus/.git
# Regenerate this manifest:
make data-manifest SLUG=zugferd-corpus LANG=german
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=zugferd-corpus LANG=german
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
