---
slug: omnidocbench
language: multilingual
source_url: "https://huggingface.co/datasets/opendatalab/OmniDocBench"
source_type: hf_git_clone
license_spdx: "LicenseRef-OmniDocBench-research-only"
license_url: "https://huggingface.co/datasets/opendatalab/OmniDocBench/blob/main/README.md"
license_verified_date: "2026-05-13"
retrieved_date: "2026-05-13"
commit_sha: "d386947f7fc3bafdcd756c8485845a2f43a19875"
commit_date: "2026-04-10T03:23:58Z"
file_count: 1659
total_bytes: 1545930107
sha256_aggregate: "af67dac2688b8f2a7b51dcd572fac3c5c7d763f44efef53cbaa66b0c217f2d9c"
sample_load_passed: true
sample_load_notes: "Verified 3x JPG (FFD8FF magic), 2x PNG (1 mislabeled — see anomalies), 2x JSON (json.load OK incl. 42MB OmniDocBench.json). Total 1659 files: 981 .jpg + 670 .png (636 real + 34 mislabeled) + 2 .json + 3 .md + 1 .txt + 2 LFS metadata."
anomalies:
  - "34 of 670 .png files are actually JPEG content (header ffd8ffe0). Files are valid images but mislabeled extension. Source-side dataset issue, not download corruption. List: page-573c437e..., page-14cd673f..., page-1853e666..., page-bb98165a..., page-99c0fd2f..., (29 more)."
  - "License unverified — HF page lacks SPDX tag; README.md Copyright Statement says 'for research purposes only and not for commercial use'. Custom non-commercial-research terms (LicenseRef pending). See sub-issue/follow-up."
source_stub: "../../../../docs/sources/datasets/omnidocbench.md"
acquisition_status: completed
---

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`docs/sources/datasets/omnidocbench.md`](../../../../docs/sources/datasets/omnidocbench.md) for bibliographic details.

## Download recipe (reproducible)

```sh
git clone https://huggingface.co/datasets/opendatalab/OmniDocBench data/raw/multilingual/omnidocbench
# For HF datasets with LFS: git lfs pull (before dropping .git/)
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/multilingual/omnidocbench log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/multilingual/omnidocbench/.git
# Regenerate this manifest:
make data-manifest SLUG=omnidocbench LANG=multilingual
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG=omnidocbench LANG=multilingual
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
