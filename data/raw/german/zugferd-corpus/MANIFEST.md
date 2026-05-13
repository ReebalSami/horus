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
file_count: 279
total_bytes: 178846554
sha256_aggregate: "bc031e43296032fa9a307153c0da8e638488b72724f0ffdcfeacaa80bbd67dfe"
sample_load_passed: true
sample_load_notes: "Opened 3 random PDFs (%PDF- magic verified) and parsed 3 random XMLs via xml.etree; all passed. Corpus contains ZUGFeRDv1/, ZUGFeRDv2/, XML-Rechnung/{FX,CII,UBL}/, fatturaPA/, incoming/, PEPPOL/, unstructured/ subdirs."
anomalies: []
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
