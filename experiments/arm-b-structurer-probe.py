# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Phase-0 proof: can Gemma structure Granite's text (no image)?
#
# This probe answers the single open feasibility question behind the "read-then-
# structure" extraction method (image -> Granite -> text -> Gemma -> fields):
# **can the structuring model take a block of OCR text, with no image, and emit
# the canonical fields?** Every extractor in `horus.vlm_extractor` is image-in
# only, so this path was never exercised before.
#
# It is a throwaway proof, not production code. The real structurer lands in
# `src/horus/eval/` after this confirms the mechanism. Findings (does it work,
# rough latency, whether a new dependency is needed) feed the architecture
# decision record.
#
# Mechanism under test (no new dependency — both already installed):
#   - `mlx_vlm.apply_chat_template(..., num_images=0)` builds a text-only prompt
#     (the `gemma4` arch omits the image token when `num_images == 0`).
#   - `mlx_vlm.generate(model, processor, prompt, image=None, ...)` generates
#     from text alone (`image` defaults to `None`).
#
# Run (foreground + streaming, per `long-running-foreground`):
#   uv run python experiments/arm-b-structurer-probe.py

# %%
from __future__ import annotations

import json
import time
from pathlib import Path

from mlx_vlm import generate as mlx_generate
from mlx_vlm import load as mlx_load
from mlx_vlm.prompt_utils import apply_chat_template

from horus.eval.adapters_json import _try_parse_json
from horus.eval.ground_truth import FIELDS
from horus.eval.schema import PURPOSE_SUMMARY_KEY, validate_and_repair
from horus.eval.transcripts import parse_transcript, split_per_page_texts
from horus.vlm_extractor import COHORT_MANIFEST

# %% [markdown]
# ## 1. Load one cached Granite transcript as the structurer's text input
#
# `EN16931_Einfach` is the canonical smoke invoice; this Granite (MLX) transcript
# carries every field (number/dates/both parties+addresses/VAT IDs/the
# Belegsummen totals/tax rates), so a capable structurer should recover most of
# the 19 fields. Granite's DocTags markup is intentionally left in — that is what
# the real pipeline will hand to Gemma.

# %%
TRANSCRIPT = Path(
    "docs/sources/transcripts-multipage/"
    "ibm-granite__granite-docling-258m-mlx__EN16931_Einfach.txt"
)
model_id_read, invoice_stem, body = parse_transcript(TRANSCRIPT)
reader_text = "\n\n".join(split_per_page_texts(body))
print(f"Reader (Granite) transcript: {model_id_read} / {invoice_stem}", flush=True)
print(f"Transcript length: {len(reader_text)} chars", flush=True)

# %% [markdown]
# ## 2. Build the reasoning-then-strict-JSON structuring prompt
#
# The honesty guardrail for the tax domain is the explicit "extract only what is
# present, else null" instruction. All 19 scored keys are requested verbatim from
# the field registry (single source of truth), plus the non-scored
# `purpose_summary` for the later demo. This is a first-cut prompt; the build
# phase refines it on dev.

# %%
scored_keys = list(FIELDS.keys())
all_keys = [*scored_keys, PURPOSE_SUMMARY_KEY]
key_list = ", ".join(all_keys)
structuring_prompt = (
    "You are a meticulous accountant reading the OCR text of a German B2B "
    "invoice. The text may contain layout markup and tables. First reason "
    "briefly about where each value is, then output ONE JSON object on the "
    "final line.\n\n"
    "Rules:\n"
    "- Extract ONLY values that are actually present in the text. If a field is "
    "not present, use null. NEVER invent a value.\n"
    "- Money values as printed (digits, decimal separator). Dates as printed.\n"
    "- Return EXACTLY these keys: "
    f"{key_list}.\n"
    "- `purpose_summary`: one short sentence on what the invoice is for.\n\n"
    "Invoice OCR text:\n"
    "<<<\n"
    f"{reader_text}\n"
    ">>>\n"
)
print(f"Prompt length: {len(structuring_prompt)} chars", flush=True)

# %% [markdown]
# ## 3. Load Gemma (the structurer) and generate from TEXT ONLY
#
# Model id + MLX 4-bit port read from the cohort manifest (no hardcoding). The
# `num_images=0` + `image=None` pair is the whole point of the probe.

# %%
gemma_id = "google/gemma-4-E4B-it"
gemma_entry = COHORT_MANIFEST[gemma_id]
gemma_repo = gemma_entry["alt_model_id"] or gemma_id
print(f"Loading structurer: {gemma_id}  (weights: {gemma_repo})", flush=True)

load_start = time.perf_counter()
model, processor = mlx_load(gemma_repo)
load_seconds = time.perf_counter() - load_start
print(f"Loaded in {load_seconds:.1f}s", flush=True)

formatted = apply_chat_template(processor, model.config, structuring_prompt, num_images=0)

print("\n----- Gemma text-only generation (streaming) -----", flush=True)
gen_start = time.perf_counter()
output = mlx_generate(
    model,
    processor,
    formatted,
    image=None,
    max_tokens=1024,
    verbose=True,
)
gen_seconds = time.perf_counter() - gen_start
raw_text = output if isinstance(output, str) else getattr(output, "text", str(output))
print(f"\n----- Generated in {gen_seconds:.1f}s -----", flush=True)

# %% [markdown]
# ## 4. Run the output through the real recovery + validate/repair path
#
# Proves the end-to-end chain: model text -> JSON recovery ladder
# (`adapters_json`) -> `validate_and_repair` -> the canonical 19-key scored dict.

# %%
parsed = _try_parse_json(raw_text)
print(f"JSON recovered: {parsed is not None}", flush=True)

repaired = validate_and_repair(parsed)
non_null = {k: v for k, v in repaired.items() if v is not None}
print(f"\nNon-null scored fields: {len(non_null)}/{len(scored_keys)}", flush=True)
print(json.dumps(repaired, indent=2, ensure_ascii=False), flush=True)

# %% [markdown]
# ## 5. Verdict
#
# - WORKS if: generation returned text, JSON recovered, and a meaningful number
#   of the 19 fields are non-null (the transcript contains them all).
# - Records: load seconds, generation seconds, dependency used (mlx-vlm only —
#   no mlx_lm, no new dependency).

# %%
print("\n===== PHASE-0 VERDICT =====", flush=True)
print(f"text-only generation: {'OK' if raw_text.strip() else 'EMPTY'}", flush=True)
print(f"json recovered:       {parsed is not None}", flush=True)
print(f"non-null fields:      {len(non_null)}/{len(scored_keys)}", flush=True)
print(f"load_seconds:         {load_seconds:.1f}", flush=True)
print(f"gen_seconds:          {gen_seconds:.1f}", flush=True)
print("dependency:           mlx-vlm only (image=None, num_images=0)", flush=True)
