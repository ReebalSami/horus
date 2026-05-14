# DeepSeek-OCR-2 smoke — Type B install-conflict diagnostic

**Companion file:** `deepseek-ocr-2.txt` (cohort-smoke runner transcript).
**Classification:** Type B (install-conflict-blocked) per ADR-009 §3.6 + plan §6 A2.
**Status as of this commit:** Excluded from PR(a) smoke evidence; remains in
the ADR-009 cohort table as a documented Type B failure (transcript +
diagnostic). Cat 2 still has PaddleOCR-VL (smoke evidence due in PR(b)).

## What the cohort-smoke runner captured

```text
Status:         error
Load wall-time: 0.00 s
Error: ValueError: Unrecognized processing class in <cache-path>
       Can't instantiate a processor, a tokenizer, an image processor,
       a video processor or a feature extractor for this model.
```

The trace surfaces a recursive descent through mlx_vlm's
`_patched_auto_processor_from_pretrained` (base.py:476), terminating in
`transformers/models/auto/processing_auto.py:453`. The outer error is
**generic** — it tells us AutoProcessor couldn't find a processor class
but does not say *why*.

## What direct testing revealed (the real root cause)

mlx_vlm's patched `AutoProcessor.from_pretrained` wraps the match-and-call
branch in `try/except Exception: pass` (`mlx_vlm/models/base.py:443-475`):

```python
try:
    ...
    if model_type in target_model_types:
        kwargs.setdefault("trust_remote_code", True)
        return processor_cls.from_pretrained(
            pretrained_model_name_or_path, **kwargs
        )
except Exception:
    # On any failure, fall back to previous behavior
    pass

return previous_from_pretrained.__func__(cls, ...)
```

The patch's `target_model_types={'deepseekocr_2'}` and the cached
`config.json` declares `model_type: 'deepseekocr_2'`. Match succeeds.
The patch then calls `DeepseekOCR2Processor.from_pretrained(path)` —
which **raises an exception that is silently swallowed**. Control falls
through to the unmodified `AutoProcessor.from_pretrained` which then
fails with the generic `ValueError: Unrecognized processing class`.

Calling `DeepseekOCR2Processor.from_pretrained()` directly (bypassing the
swallow) progressively reveals four stacked dependency / ABI issues:

| Step | Real error revealed |
|---|---|
| Initial call | `ImportError: This modeling file requires addict, matplotlib` |
| After `uv add addict matplotlib` | `ModuleNotFoundError: No module named 'einops'` |
| After `uv add einops` | `ImportError: cannot import name 'LlamaFlashAttention2' from 'transformers.models.llama.modeling_llama'` |
| After (hypothetical) transformers downgrade to <4.45 | (unknown — likely additional ABI issues) |

## The blocker (Type B)

The mlx-community port's bundled remote code
(`modeling_deepseekv2.py:37-40`) does:

```python
from transformers.models.llama.modeling_llama import (
    LlamaAttention,
    LlamaFlashAttention2
)
```

`LlamaFlashAttention2` was **removed in transformers ≥4.45** when HF
consolidated per-implementation attention classes into the unified
`attn_implementation` config-driven system (see transformers PR #32827,
"Refactor attention implementation"). The project's pinned transformers
version is **5.8.0** (15+ minor versions ahead of the model's last-working
transformers).

## Why we don't downgrade transformers

- ADR-007 mlx_vlm install + Granite-Docling smoke + cohort dispatcher all
  validate on transformers 5.8.0. Downgrading risks regressing Cat 1
  baseline + Cat 3 cohort entries.
- All five `mlx-community/DeepSeek-OCR-2-{4,5,6,8}bit` + `-bf16` ports
  ship the same remote code (created on the same day by the same
  uploader). Switching to a different MLX port does not resolve the ABI
  issue.
- DeepSeek-OCR v1 ships analogous remote code with the same upstream
  base. The chain repeats.
- Forcing PyTorch backend (Transformers + MPS via `TransformersMPSExtractor`)
  does not help: the `LlamaFlashAttention2` import happens at remote-code
  module-load time, before any backend dispatch.

## Why this is a textbook Type B (not Type A or C)

- **Type A (install-blocked)** would be e.g. `pip install` failing on a
  package version constraint. The package *did* install via `uv add`; the
  failure surfaces at runtime *load* time.
- **Type C (runtime-blocked)** would be e.g. OOM, dtype mismatch, or
  inference failure on a successfully-loaded model. DSO-2 doesn't reach
  loaded state.
- **Type B (compat-blocked)** is exactly: the model installs cleanly,
  but its remote code ABI is incompatible with our pinned dependency
  versions. DSO-2 fits Type B as the canonical example.

## Open path forward (deferred to PR(b) or follow-up sprint)

A clean DSO-2 enablement would need any of:

1. **Upstream patch** to the mlx-community ports (replace
   `LlamaFlashAttention2` import with the modern equivalent and bundle
   addict/matplotlib/einops in `requirements.txt`). Out of scope for HORUS.
2. **Maintain a transformers-version-pinned venv** scoped to DSO-2
   evaluations only. Adds operational complexity, breaks `uv-discipline`.
3. **Bypass remote code** by hand-rolling the processor pipeline using
   the model's tokenizer + image preprocessor directly. Significant
   scope; defeats the cohort's "use it as documented" methodology.

All three exceed the PR(a) scope. Per plan §6 A2, Type B failures are
documented and do not block ADR-009 ratification.

## References

- `~/.windsurf/plans/adr-009-pilot-vlm-cohort-fbbfa0.md` §6.4 (Type
  taxonomy + escalation lemma)
- `mlx_vlm/models/base.py` lines 443-475 (the silent-swallow patch logic)
- `~/.cache/huggingface/modules/transformers_modules/_<sha>/<sha>/modeling_deepseekv2.py:37-40`
  (the offending import; copied verbatim from upstream DeepSeek-OCR-2)
- transformers PR #32827 (attention implementation refactor that removed
  `LlamaFlashAttention2`)

## Provenance of this diagnostic

Captured during PR(a) Step 6 execution as a bisection of the mlx_vlm
silent-swallow. Three dependencies (addict, matplotlib, einops) were
added to `pyproject.toml` along the way; they stay in the project deps
because they are broadly useful for ML eval and likely required by
other cohort models (matplotlib for evaluation plots; einops for tensor
manipulation across many VLMs).
