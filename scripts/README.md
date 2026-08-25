# scripts/

Operational scripts for HORUS — the runners behind the Make targets plus the
audit/diagnostic tooling. Reusable *logic* lives in `src/horus/`; scripts here
are thin, single-purpose entry points. Most are wired to a Make target
(`make help` names them); every script also documents itself via `--help` or
its module docstring.

## Tracking status

Tracked. Ordinary Python files (no jupytext pairing). Scripts that grow into
reusable library components graduate to `src/horus/` via refactor + ADR.

## Inventory by purpose

### Smokes & pipeline validation

| Script | Purpose |
|---|---|
| `generate_zugferd_smoke.py` / `validate_zugferd.py` | `make zugferd-smoke`: factur-x generation + independent Mustang (Java) cross-validation (ADR-005) |
| `inference_smoke.py` | Real-model load smoke via mlx-vlm + Transformers/MPS (ADR-007) |
| `orchestrated_smoke.py` | Docling `StandardPdfPipeline` smoke (ADR-008) |
| `cohort_smoke.py` | Per-model VLM smoke against the cohort manifest (ADR-009; optional MLflow via ADR-011) |

### Corpus & data management

| Script | Purpose |
|---|---|
| `data_manifest.py` | Generate `MANIFEST.md` + `sha256.txt` for a downloaded dataset (`make data-manifest`) |
| `extract_zugferd_xml.py` | Canonical ZUGFeRD XML extraction — the XML-grounded ground-truth source (ADR-010) |
| `generate_datasheets.py` | Datasheets-for-Datasets content for the EDA book (ADR-025) |

### Evidence sweeps & scoring

| Script | Purpose |
|---|---|
| `run_pilot_13.py` / `inspect_pilot_13.py` | The full (cohort × corpus) sweep + its headless post-mortem (ADR-014/017) |
| `rescore.py` | Offline adapter+scorer re-run on frozen transcripts — no VLM invoked (ADR-016) |
| `run_arm_b.py` / `inspect_arms.py` | The orchestrated arm (reader → structurer) runner + per-arm error inspection (ADR-038) |
| `reading_ceiling.py` | Read-quality ceiling + parser-loss diagnostic (`make reading-ceiling`; ADR-030) |
| `error_analysis.py` | Per-field FN/FP breakdown over the canonical multipage transcripts |
| `compute_probe_verdict.py` | Structured-output probe verdict matrix (ADR-019) |
| `compare_eval_reports.py` | Field-by-field diff of two structurer eval reports |
| `finalist_significance.py` | Paired significance test for the two reader finalists (thesis ch. 7) |

### Instrument audits (measurement validity)

| Script | Purpose |
|---|---|
| `audit_field_prompts.py` | Corpus-backed audit of every prompt alias/description (`make audit-prompts`; ADR-058) |
| `dump_field_glossary.py` | Print the rendered structurer glossary with per-alias corpus grounding (`make glossary`) |
| `classify_field_gaps.py` | Classify per-field F1 loss by cause: prompt gap vs reading gap (ADR-064 ordering rule) |
| `findability_corrected.py` | Post-audit corrected findability table (#114) |
| `check_oracle_transcript_labels.py` | Verify a field's label+value actually appear in the oracle transcript |

### Fine-tune / adaptation study (#55)

| Script | Purpose |
|---|---|
| `finetune_seal_split.py` | Build + seal the deterministic stratified split (hash-recorded) |
| `finetune_corpus_report.py` | Whole-corpus answerability report (offline, deterministic) |
| `finetune_reader_pass.py` / `finetune_reader_bakeoff.py` | Reader transcription passes + candidate-reader bake-off |
| `finetune_train.py` / `finetune_train_cuda.py` | LoRA training entry points (local MLX / rented CUDA) |
| `finetune_evaluate.py` / `finetune_attribution.py` | Sealed-split evaluation + reader-vs-structurer loss attribution |

### Held-out Belege set (private; ADR-040/060/062)

| Script | Purpose |
|---|---|
| `heldout_manifest.py` | `index` / `datasheet` / `text` modes — local index, sanitized datasheet, drafting aid (`make heldout-index` / `heldout-datasheet`) |
| `frozen_testset_bundle.py` | Author-side: build the encrypted examiner bundle (`make frozen-testset-bundle`; ADR-075) |
| `get_frozen_testset.py` | Examiner-side: download + decrypt + verify + restore the frozen set (`make get-frozen-testset`; ADR-075) |
| `transcribe_heldout.py` | Local reader transcription over the held-out corpus |
| `judge_heldout_gt.py` / `azure_heldout_gt.py` | The two independent GT adjudication channels (cloud judge + Azure prebuilt-invoice; GT-authoring only, never on the inference path) |
| `audit_azure_vocabulary.py` | Verify the `AZURE_FIELD_MAP` hypothesis against the service's actual return vocabulary |
| `review_heldout_gt.py` / `promotion_status.py` | Sign-off review tooling + corpus promotion progress |
| `heldout_attribution.py` / `heldout_breakdown.py` | Held-out loss attribution + per-channel breakdown (aggregates only leave the machine) |
| `audit_heldout_evidence.py` / `audit_heldout_exclusions.py` | Reproducible evidence audit + ADR-072 EXCLUDED-cause audit (`make audit-heldout-exclusions`) |

### Thesis & app assets

| Script | Purpose |
|---|---|
| `thesis_assets.py` | Generate every measured figure/table in the manuscript from committed artifacts (`make thesis-assets`; ADR-055) |
| `prepare_brand_assets.py` | Background-removed PNG brand assets for the dashboard (ADR-036) |

### Subdirectories

| Dir | Purpose |
|---|---|
| `gpu/` | Rented-GPU (A10G) session scripts: `setup.sh`, `run_lora_2x2.sh`, `regen_transcripts.py` — see `gpu/README.md` |
| `azure/` | Azure Document Intelligence setup runbook for the second GT channel — see `azure/README.md` |

## Provenance

- Directory scaffolded at issue #8 (M2D.5 step 1); grew with each ADR named above
- Per-script provenance lives in each script's module docstring
