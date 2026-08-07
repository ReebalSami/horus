# ADR-068: Fine-tune venue — CUDA + TRL/PEFT, with a matched-stack baseline re-measurement

**Status**: Accepted — executed 2026-08-07. The mandated re-baseline **changed the conclusion**
of ADR-067 (see Measured outcome). Results: `eval/structurer-lora-2x2-results.md`.
**Date**: 2026-08-07
**Refs**: #55 (fine-tune epic), ADR-067 (the recipe this hosts), ADR-007 (dual-track local-VLM
decision this partially supersedes for *training*), ADR-057 (the reader bake-off that proved
this GPU workflow), ADR-034/038 (matched-precision arms), `know-your-hardware`

## Context (current-state survey)

`src/horus/finetune/train.py` trains through `mlx_vlm`, chosen under ADR-007's local-first
posture. Empirically it does not scale to this job on the available hardware.

**Observed, 2026-08-07**: a deliberately tiny path-validation smoke
(`--limit-train 4 --iters 4`, i.e. 4 training examples and 4 forward passes) ran long enough
that the user cancelled it, reporting the machine at its limit. The real budget is
`100 examples × 6 epochs ≈ 600` forward passes — two orders of magnitude more work. The
mechanism is understood and documented in the trainer itself: gemma-4-E4B is 7.99 B params, and
at 4-bit with gradient checkpointing and sequences ~3 k tokens the step already sits against
the ~12.7 GB Metal working-set ceiling on a 16 GB M1 Pro. `train.py` carries three separate
workarounds for this (`_free_unused_towers`, a manual `grad_checkpoint` patch because
mlx_vlm's own check silently no-ops on gemma-4's nested layers, and a held wired-limit raise) —
i.e. the local path was already at the edge before this run.

There is a second, non-technical constraint that the `know-your-hardware` rule explicitly
covers: the M1 Pro is the user's **only** working machine. A multi-hour local training run does
not merely risk OOM, it blocks all other work.

The repo already has a proven CUDA workflow: `scripts/gpu/setup.sh` + `scripts/gpu/README.md`
bootstrap a g5.xlarge (A10G 24 GB) and were used for the ADR-057 reader bake-off, including the
Qwen3-VL-8B run adjudicated earlier this session. `mlx-vlm` is already platform-gated out of
`uv sync` on Linux, and all mlx imports in `src/` are method-local, so the package installs and
imports cleanly there.

### The trap this decision has to avoid

`mlx_vlm` is Apple-only, so a CUDA move implies a different training stack — and therefore a
different *inference* stack for anything that consumes the adapter. That creates a
confound that would be easy to ship silently:

- the committed baseline `data/finetune/eval-zeroshot-qwen-adr059-val.json` (**0.8257**) was
  produced by **MLX 4-bit** inference on Apple Silicon;
- a CUDA-trained PEFT adapter is naturally evaluated in **bf16**;
- so `finetuned_bf16 − zeroshot_4bit` measures the adapter **plus** a quantisation change.

ADR-034/038 established "matched precision" as a property of the arms. Reporting that
cross-stack delta would violate it while looking like a clean before/after.

Additionally, `evaluate_structurer` hard-required an `MLXVLMExtractor` and fused adapters with
`mlx_vlm.trainer.utils.apply_lora_layers`. Left unchanged, the GPU box would produce adapters
that **cannot be scored anywhere** — training something unmeasurable.

## Options considered

1. **Keep training locally on MLX** — rejected on the evidence above: a 4-example smoke did not
   finish acceptably, and the full run blocks the user's only machine.
2. **CUDA + hand-rolled PyTorch training loop** — rejected: re-implements optimizer stepping,
   LR scheduling, gradient accumulation, per-epoch eval, and best-checkpoint tracking, all of
   which ADR-067's selection discipline depends on being *correct*. Hand-rolling the thing that
   guarantees methodological honesty is the wrong place to save a dependency.
3. **CUDA + TRL `SFTTrainer` + PEFT `LoraConfig`, chosen.** ADR-067's entire selection rule is
   native configuration (`eval_strategy="epoch"`, `load_best_model_at_end=True`,
   `metric_for_best_model="eval_loss"`), and completion-only loss masking is native for
   conversational prompt-completion data. The venue change therefore makes the discipline
   *simpler and better tested*, not harder.
4. **CUDA + 4-bit QLoRA to match the baseline's quantisation** — rejected. bitsandbytes 4-bit
   is not the same quantisation as MLX 4-bit, so it would not actually match; it would merely
   *look* matched, which is worse than an honest mismatch. Re-measuring the baseline (§Decision
   3) is both simpler and actually sound.
5. **Train on CUDA, convert the adapter to MLX format, evaluate locally** — rejected: a bespoke
   format conversion is an untested correctness risk sitting directly under the headline number,
   and evaluating a bf16-trained adapter in 4-bit reintroduces the same confound from the other
   side.

## Decision

### 1. Structurer LoRA training runs on CUDA via TRL + PEFT

New `src/horus/finetune/train_cuda.py`. It refuses to start without a visible CUDA device — no
silent fallback to a path this ADR records as non-viable. `train.py` (MLX) is **retained**, not
deleted: it still runs, it documents the Metal-specific workarounds, and ADR-011
supersession-over-deletion applies.

Data is byte-identical to the MLX path: same sealed split, same `carve_dev`, same prompt, same
`build_dataset` targets, same self-consistency gate. **Only the executor changes** — which is
what makes ADR-067's numbers attributable to the adapter rather than to the move.

### 2. A CUDA text-only structurer for evaluation

New `src/horus/finetune/structurer_cuda.py` (`CudaStructurerExtractor`): bf16, greedy decode,
optional PEFT adapter, conforming structurally to `horus.eval.live.TextExtractor`. It is a
separate narrow class rather than an `extract_text` bolted onto `TransformersMPSExtractor`,
because that class is an image-first *cohort reader* extractor (max_pixels, repetition_penalty,
image-token plumbing) whose `COHORT_MANIFEST` contract is about readers.

`evaluate_structurer` gains an injectable `extractor` parameter. When nothing is injected the
original MLX path is byte-for-byte unchanged, so **no committed report can move**.
`scripts/finetune_evaluate.py` gains `--backend {mlx,cuda}` (default `mlx`) and
`--base-model-id`.

### 3. The zero-shot baseline is re-measured on the same backend — MANDATORY

Before any adapter number is compared to anything, `--backend cuda` with no `--adapter` is run
over the sealed 29 to produce a **bf16 zero-shot baseline**. Every ADR-067 comparison is then
within one stack.

This is enforced in three places rather than left to memory: the CLI `--backend` help text, a
runtime banner printed whenever `--backend cuda` is used, and the module docstring of
`structurer_cuda.py`.

The MLX 4-bit figure (0.8257) is **retained** as the local-deployability reading — it is the
number that describes what runs on the target hardware, which is a genuine thesis claim (HORUS
is privacy-first and local). It is simply not a valid comparator for a bf16 adapter. Expect the
two baselines to differ; the size of that difference is itself worth reporting, since it
quantifies what 4-bit quantisation costs the structurer.

### 4. Instance class

g5.xlarge (A10G 24 GB), matching the reader bake-off. gemma-4-E4B in bf16 is ~16 GB of weights;
with LoRA-only optimizer state, gradient checkpointing, and effective batch 8 at ~3 k tokens
this is expected to fit with headroom. If it does not, the documented fallback is a larger
instance (L40S/A100 48 GB) — **not** dropping to 4-bit, which would reintroduce §Options 4's
confound.

### 5. Dependencies

`peft`, `trl`, `accelerate`, `datasets` declared in `[project] dependencies`. Deliberately
**not** platform-gated, unlike `mlx-vlm`: all four are pure Python, and gating them would make
the CUDA trainer untestable on the only platform that runs the test suite. The CUDA guard lives
in the code, not the dependency table.

Two defects were caught by the newly-available type information rather than by review:
`trl` types `lora_alpha` as `int` while `LoraParams.alpha` is `float` (rounding would change
the alpha/rank scaling that defines adapter strength — now refused rather than truncated), and
`completion_only_loss` defaults to `None`/"auto" (now asserted, since that one flag decides
whether loss covers the ~3 k-token prompt).

## Measured outcome (added after the run)

**The predicted confound was real, and it would have inverted the reported conclusion.**

| comparison | delta | reading |
|---|---|---|
| bf16 adapter 0.8246 vs committed **MLX 4-bit** 0.8257 | −0.0011 | "the LoRA is neutral" |
| bf16 adapter 0.8246 vs **matched bf16** 0.8480 | **−0.0234** | a real regression |

The adapter's damage (−0.0234) and the bf16-over-4-bit gain (**+0.0223**) nearly cancel. A run
that had skipped the mandatory re-baseline would have concluded "no effect" — not off by a
rounding error, but off by the entire finding. The re-baseline cost ~80 min of A10G time.
This is the strongest justification the record could have asked for.

**Secondary, independently useful**: bf16 0.8480 vs MLX 4-bit 0.8257 quantifies what local
4-bit quantisation costs the structurer (**+0.0223** for full precision) on identical inputs
and prompt. Both figures are retained — the 4-bit number describes what actually runs on the
target hardware, which is a genuine claim for a privacy-first local system.

### Two implementation findings from the run

1. **Liger does not patch `Gemma4ForConditionalGeneration`.** Gemma's 262,144-token vocabulary
   makes the logits tensor the dominant training memory cost (~3.2 GB bf16 at 6k tokens, ~6.4 GB
   upcast for cross-entropy, plus its gradient) — that, not activations, OOM'd the 24 GB A10G.
   Liger's fused linear cross-entropy is the textbook fix and liger 0.8.1's registry *does* list
   `gemma4`, but passing `use_liger_kernel=True` to `SFTConfig` silently no-opped (zero log
   output, memory profile unchanged, same OOM) because the model is instantiated before the
   trainer sees it; calling `_apply_liger_kernel_to_instance` directly installed **zero** Liger
   modules. The trainer now applies Liger explicitly and **raises** if nothing was patched,
   rather than continuing unfused and OOMing 40 minutes later.
2. **`activation_offloading=True` was the working lever** (TRL-native, bf16 preserved). The
   deficit was under 1 GB, and offloading saved activations to CPU cleared it. Precision was
   never traded, so no confound was introduced to fix a memory problem — which was the whole
   point of rejecting 4-bit QLoRA above.

Also corrected during the run: the CUDA path ignored the config's documented
`max_seq_length: 0 = auto` semantics and always used the **cap** (8192). The real longest
example is 6094 tokens, so auto now picks 6144 — and, more importantly, a cap of 4096 would
have silently truncated **26 of 100** training examples, training the model to produce a full
answer from partial input. Measuring the length distribution before touching `max_length` is
what kept that from happening.

## Source archival

Per `horus-source-archival`. External APIs verified against the **installed** versions
(`context7-and-docs-first`), not from memory: TRL **1.9.2** and PEFT **0.20.0**, both resolved
via `uv sync` this session. TRL documentation consulted through `context7`
(`/huggingface/trl`) for `SFTTrainer` + PEFT integration, `assistant_only_loss`, and
prompt-completion masking semantics; the installed `SFTConfig` dataclass fields and
`SFTTrainer.__init__` signature were then introspected directly to confirm the API surface,
which is what surfaced the two defects above.

In-repo evidence: `scripts/gpu/README.md` + `scripts/gpu/setup.sh` (the proven workflow),
`data/finetune/bakeoff/**` (prior A10G runs), `src/horus/finetune/train.py` (the three
Metal-ceiling workarounds documenting why local is at its limit),
`data/finetune/eval-zeroshot-qwen-adr059-val.json` (the MLX 4-bit baseline this ADR declines to
compare against cross-stack).

Hardware constraint per `know-your-hardware`: M1 Pro / 16 GB / Metal, no CUDA. GPU spend
authorised by the user in-session; the A10G budget originally earmarked for the ADR-057 8B
sibling test went unspent (that test was adjudicated from already-committed artifacts) and is
reallocated here.

## Consequences

- **Unblocks** the fine-tune at full scale and returns the user's machine.
- **Requires** one extra evaluation run (the bf16 baseline) before any comparison is legitimate.
- **Adds** four dependencies and a second training entry point; `train.py` and
  `train_cuda.py` must be kept in step on data handling. Mitigated by both calling the *same*
  `build_split_records` / `carve_dev` / `build_dataset`, so the shared logic has one home.
- **Partially supersedes ADR-007** for *training* only. HORUS's delivered **inference** path
  stays fully local — no cloud call exists in it. This is a training-venue decision, exactly as
  ADR-060/061 are measurement-only decisions.
- **Reportable finding**: the gap between the MLX-4bit and bf16 zero-shot baselines quantifies
  the cost of local quantisation for the structurer, which the thesis's privacy-first framing
  makes directly relevant.

## Supersession trigger

- If Apple Silicon tooling improves enough for a 7.99 B LoRA at ~3 k sequences to train locally
  in acceptable time, revisit — local training removes the cross-stack baseline problem entirely.
- If the bf16 and 4-bit baselines turn out to differ materially, the thesis must report BOTH and
  state which hardware each describes; a single headline number would be misleading.
- If A10G 24 GB proves insufficient, this ADR is amended with the actual instance class used
  (not silently changed).
- If a future decision moves inference off local hardware, ADR-007's supersession governs and
  this ADR's careful training-vs-inference separation can be simplified.
