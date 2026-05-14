# Cohort smoke transcripts (ADR-009)

This directory holds per-model transcript outputs from `make cohort-smoke`,
the runner that populates ADR-009 §Decision per-model evidence blocks.

## Why a separate directory

ADR-009 §Decision references these transcripts as primary evidence (per the
ADR-007 + ADR-008 transcript-block precedent). With 10 cohort models +
~3-5 KB of output per model, inlining all transcripts in the ADR file would
push it past 2000 lines. The plan's open-choice §8 O1 codified this dir as
the externalisation target: ADR-009 embeds *snippets* (first ~500-1000 chars)
and links here for the full transcripts.

## File naming

`<model-slug>.txt` — kebab-case, mirrors the `docs/sources/tools/<slug>.md`
naming. Example:

- `granite-docling-258m.txt` ← `ibm-granite/granite-docling-258M-mlx`
- `deepseek-ocr-2.txt` ← `deepseek-ai/DeepSeek-OCR-2`
- `gemma-4-e4b-it.txt` ← `google/gemma-4-E4B-it`

## How transcripts are generated

```sh
make cohort-smoke MODEL=<hf-model-id> OUT=docs/sources/transcripts/<slug>.txt
```

The runner (`scripts/cohort_smoke.py`) emits the ADR-007-style transcript
block: border lines, key-value rows (load wall-time, extract wall-time,
output length, status), then the first ~4000 chars of model output as a
snippet. See `scripts/inference_smoke.py::_format_block` for the precedent.

## Refs

- Plan §8 O1 (open low-stakes choice; default approved)
- ADR-009 §Decision (per-model evidence narrative)
- ADR-007 (smoke-transcript-block format precedent)
