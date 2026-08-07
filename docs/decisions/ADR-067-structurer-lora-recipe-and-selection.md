# ADR-067: Structurer LoRA — recipe, 2×2 attribution design, and pre-registration

**Status**: Proposed (pre-registration — authored BEFORE any training run)
**Date**: 2026-08-07
**Refs**: #55 (fine-tune epic), ADR-054 (the conditional-LoRA gate this executes), ADR-057
(reader selection — the transcripts trained on), ADR-059 (the oracle instrument this reuses),
ADR-064 (a prompt-fixable gap is never a fine-tune target), ADR-066 (which proved zero prompt
repairs remain), ADR-068 (venue: where this runs), ADR-034/038 (matched-precision arms)

## Context (current-state survey)

ADR-054 pre-registered a **conditional** LoRA: *"fine-tune the structurer ONLY if the
re-baseline stays < 0.90."* That condition is met — the sealed-val zero-shot re-baseline
after the ADR-057 reader swap is **0.8257** (`data/finetune/eval-zeroshot-qwen-adr059-val.json`),
below the 0.90 gate. ADR-064's ordering rule (repair the prompt first) is also discharged:
ADR-066 escalated all three prompt candidates per-invoice and found **zero** are
prompt-fixable. So the fine-tune is warranted and unblocked.

### The finding that reshapes what this ADR may claim

Reading the committed val reports together (all five produced with
`structurer = google/gemma-4-E4B-it`, greedy decode, MLX 4-bit):

| arm | input text | overall_micro_f1 | flat micro_f1 |
|---|---|---|---|
| `oracle-adr059` | perfect GT-rendered | **0.9719** | 0.9743 |
| `zero-shot-olmocr-reader` | olmOCR-2-7B | 0.8335 | 0.8426 |
| `zero-shot-qwen-adr059` | Qwen3-VL-4B (canonical) | **0.8257** | 0.8649 |
| `qwen-tier1` | Qwen3-VL-4B (earlier ruler) | 0.8189 | 0.8616 |
| `zero-shot` | granite-docling-258M (superseded) | 0.6771 | 0.7697 |

**Gemma already clears the 0.90 gate on perfect text (0.9719).** The 0.0743 shortfall is
therefore *not* a raw-capability deficit — it is behaviour under **reader noise**. This was
surfaced by a direct user challenge ("why gemma, i thought we settled on oracle") that turned
out to rest on a terminology conflation — "oracle" is an *input condition*, not a model — but
the challenge exposed a real framing error in the plan this ADR replaces, which had described
the LoRA as closing a structurer capability gap.

Consequence for the design: a reader-arm gain, measured alone, is **uninterpretable**. It
could be the adapter learning the output schema (which the prompt already elicits at 0.9719 on
clean input) or learning to survive reader artifacts. Those are different scientific claims and
the thesis may only make the one it measured.

### What bounds the achievable number

Per ADR-057's corrected findability, Qwen3-VL-4B puts **0.970** of GT values somewhere in the
transcript, against a 0.995 text-layer ceiling. Values absent from the transcript cannot be
recovered by any structurer. So the reader-arm headroom is roughly the span between 0.8257 and
the neighbourhood of findability — real and substantial, but not 1.0, and not the 0.9719 oracle
figure either.

## Options considered

1. **Single reader-arm LoRA, report the delta** — the original plan. Cheapest (one training
   run). Rejected: produces exactly the uninterpretable number described above. The thesis
   would have to either overclaim ("the structurer was undertrained") or hedge with an
   untested explanation.
2. **Reader arm + oracle arm (2×2), chosen.** Train two adapters differing *only* in input
   distribution, then evaluate each on both input conditions:

   |  | evaluate on reader text | evaluate on oracle text |
   |---|---|---|
   | **reader-trained** | the deployable number | did noise-training cost clean accuracy? |
   | **oracle-trained** | does schema-learning transfer to noisy text? | headroom above the 0.9719 ceiling |

   Roughly doubles GPU time. Bought because it converts one ambiguous number into a
   decomposition, and because the marginal cost is small next to the run already authorised.
3. **Swap the structurer instead** — the structurer was never competitively selected the way
   the reader was (ADR-057 ran 5 candidates; Gemma was simply fixed as "the controlled
   variable" in `configs/arm-b.yaml`). Rejected: ADR-054's scope freeze, and a swap would
   invalidate every committed baseline. **Recorded as a thesis limitation instead** — see
   §Consequences.
4. **Train on reader + oracle text pooled into one adapter** — rejected: pooling destroys the
   very contrast the second arm exists to create, while costing the same as running both.

## Decision

### 1. Two arms, one variable

Both arms hold constant: sealed split (`split.json`, fingerprints verified), dev carve (seed
+ fraction), structuring prompt (from `configs/arm-b.yaml`, so all arms share one instruction
string per ADR-034/038), target construction, self-consistency gate, and every
hyperparameter. A test asserts this (`test_shipped_configs_declare_distinct_arms_and_adapter_dirs`).
The **invoice set is also identical** — readiness still gates membership, so the oracle arm
trains on the same invoices with different input text, not on a different corpus.

The oracle arm reuses `render_oracle_transcript` — the *same* renderer as the oracle eval arm
(ADR-059) — via a new `reader_text_fn` seam on `build_example`/`build_dataset` that mirrors the
one `evaluate_structurer` already exposed. A parallel implementation would be free to drift, and
ADR-059 established that a drifted oracle instrument makes the ceiling wrong *in an
unpredictable direction*, not merely optimistic.

### 2. The oracle-trained adapter is an instrument, never a product

It is trained on text no real document produces. It may **never** be reported as HORUS's
deliverable, and `configs/finetune-structurer-oracle.yaml` says so in its header. Only the
reader-trained adapter is deployable.

### 3. Checkpoint selection on a dev slice carved from TRAIN

Before this ADR, the trainer passed the **sealed 29** as `val_dataset` with `val_batches=-1`,
so every run computed loss over the exact set the headline is reported on. Nothing was
*selected* on it, so no published number is retroactively invalid — but it is a look at the
answer sheet, and it makes per-epoch selection impossible to do honestly.

`split.carve_dev` carves a dev slice out of the sealed TRAIN side: stratified by
`subdir × profile` like the outer seal, seeded independently (4242 vs 42) so it is not a replay
of the same permutation, and never emptying a stratum's training side. Verified on the real
split: **100 fit / 17 dev, zero overlap with the sealed 29**, deterministic across calls.

It is a **derivation, not a re-seal** — `split.json` is never rewritten, so its
`sha256_train`/`sha256_val` fingerprints keep verifying and the original sealing guarantee is
undisturbed.

The sealed validation set is touched **exactly once per arm**, after the epoch is already
chosen.

### 4. Selection delegated to the library, not hand-rolled

On CUDA: `eval_strategy="epoch"` + `save_strategy="epoch"` + `load_best_model_at_end=True` +
`metric_for_best_model="eval_loss"` + `greater_is_better=False`. That combination *is* the
pre-registered rule below, implemented by a well-tested library rather than by this repo.
`save_total_limit=None` keeps every epoch so the curve stays auditable.

The selected epoch, the full dev-loss curve, the dev stem list and its SHA-256 are written to
`<adapter_dir>/horus_training_provenance.json`. Without that, the choice is unreproducible
after the fact.

### 5. Hyperparameters

| knob | value | why |
|---|---|---|
| LoRA rank / alpha / dropout | 8 / 16 / 0.05 | conventional small-data starting point; unchanged from the MLX config so the venue change is the only difference |
| target modules | language-model linears only, fully qualified | PEFT matches `target_modules` as name *suffixes*, so bare names like `q_proj` would also adapt the vision/audio towers. The MLX path scoped LoRA to `model.language_model`; matching that keeps the runs comparable |
| learning rate | 1e-4, **cosine with 3 % warmup**, floor 0.1× | replaces a constant rate. LoRA's B matrix starts at zero, so the first optimizer steps carry the least trustworthy gradients of the run, and at ~10² steps a bad first step is a meaningful fraction of it |
| batch / grad-accum | 1 / 8 | memory-bound; effective batch 8 |
| epochs | **6, as a BUDGET not a target** | published guidance puts the sweet spot at 1–3 epochs under ~500 examples. The later epochs exist to make the overfitting turn *visible*, not to be used. Training past the best checkpoint costs wall-clock, not correctness |
| loss masking | `completion_only_loss=True`, **asserted** | its default is `None` ("auto"), and that single flag decides whether loss is taken over the ~3k-token prompt as well as the answer |
| decode (eval) | greedy | every committed report was produced greedily; ADR-053's A/B relied on it |

## Pre-registration (binding; written before any run)

1. **Selection rule**: the reported adapter for each arm is the epoch with **minimum dev
   `eval_loss`**. Not best sealed-val score, not last epoch. If two epochs tie, the earlier wins.
2. **The sealed val set is scored once per arm**, with the already-selected adapter. No
   "let me try epoch 4 instead" after seeing a sealed-val number. If that ever happens it must
   be disclosed in the record as a second look.
3. **Matched stack**: the fine-tuned number is compared **only** against a zero-shot baseline
   measured on the *same* inference backend and dtype (ADR-068). The committed 0.8257 is MLX
   4-bit and is **not** a valid comparator for a bf16 CUDA adapter.
4. **Success is not required.** A LoRA that fails to lift the reader arm is a publishable
   result and will be reported as one. ADR-054's attribution already predicts a modest ceiling
   here, and the 2×2 exists precisely to explain a null result rather than hide it.
5. **What gets claimed**: if the reader arm improves, the claim is "improved robustness to
   reader artifacts", **not** "the structurer was undertrained" — unless the oracle arm's
   evaluation on oracle input also lifts above 0.9719, which would be the evidence for a
   genuine capability gain.
6. **No hyperparameter sweep.** One configuration, pre-registered above. Sweeping and then
   reporting the best on sealed val is the failure mode this whole apparatus exists to prevent.
   A sweep, if ever run, must be selected on dev and disclosed as a sweep.

## Source archival

Per `horus-source-archival`. In-repo evidence (all committed):
`data/finetune/eval-oracle-adr059-val.json` (0.9719 ceiling),
`data/finetune/eval-zeroshot-qwen-adr059-val.json` (0.8257 gate reading),
`data/finetune/split.json` (the seal), `eval/reader-findability-audit.md` (the 0.970/0.995
bound), `eval/finetune-attribution-audit.md` (ADR-054's decomposition),
`data/finetune/field-gap-classification-val.json` (ADR-066's zero-repairs verdict).

External APIs verified against the **installed** versions this session rather than from
training-data memory (`context7-and-docs-first`): TRL 1.9.2 (`SFTConfig` /
`SFTTrainer(processing_class=…, peft_config=…)` / `completion_only_loss` semantics for
conversational prompt-completion data) and PEFT 0.20.0 (`LoraConfig`, `PeftModel`). TRL docs
consulted via `context7` (`/huggingface/trl`); the installed dataclass fields were then
introspected directly, which is what caught that `completion_only_loss` defaults to `None`
and that `lora_alpha` is typed `int` against our `float` config.

## Consequences

- **Enables** an attribution claim the single-arm design could not support.
- **Costs** roughly double the GPU time of a single arm.
- **Constrains** the thesis: the reader arm is the only deployable result; the oracle arm is an
  instrument and must be labelled as such wherever it appears.
- **Records a limitation**: the structurer was never competitively selected (contrast ADR-057's
  5-candidate reader bake-off). Gemma was fixed as the controlled variable and frozen by
  ADR-054. This belongs in the thesis's *Limitations and Future Work* chapter, and is the
  honest answer to "why Gemma?" — it was not chosen over rivals on evidence; it was held
  constant so the *other* variables could be studied.
- **No committed number moves.** `evaluate_structurer`'s MLX path is unchanged when no
  extractor is injected; `split.json` is not rewritten.

## Supersession trigger

- If the reader arm lifts sealed val to ≥ 0.90 on a matched-stack comparison, ADR-054's gate is
  satisfied and this ADR closes as Accepted with the measured 2×2 table appended.
- If it does not, ADR-054's own supersession trigger governs (revised recovery plan), and the
  2×2 table is the evidence for *why* — specifically whether the loss is unreadable text
  (reader-side, ADR-057 territory) or unlearnable mapping (structurer-side).
- If the oracle arm evaluated on oracle input fails to exceed 0.9719, that is evidence the
  remaining flat-field loss is not learnable from 100 examples at all, and the fine-tune
  approach itself should be reconsidered rather than re-tuned.
- If a future structurer bake-off is ever run (the limitation above), it supersedes the
  "Gemma as controlled variable" premise and every number in this ADR must be re-measured.
