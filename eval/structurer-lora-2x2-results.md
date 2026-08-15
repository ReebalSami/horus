# Structurer LoRA — 2×2 attribution results (issue #55, ADR-067 + ADR-068)

**Outcome: negative. The LoRA makes the structurer worse on every cell of the grid.**

ADR-067 pre-registered that "a null result is publishable, and will be published." This is
that case, reported without a rescue attempt. No hyperparameter sweep was run, no
alternative recipe was tried, and the sealed 29 were scored exactly once per cell.

## The grid

All six numbers are one stack: `google/gemma-4-E4B-it`, **bf16**, CUDA (A10G 23 GB),
greedy decode, sealed val (29 ZUGFeRD invoices), 29/29 parsed on every cell.

| structurer | input text | overall micro-F1 | flat micro-F1 | spurious emission |
|---|---|---|---|---|
| zero-shot (baseline) | reader transcript | **0.8480** | 0.8843 | 0.1575 |
| zero-shot (baseline) | oracle (GT-rendered) | **0.9778** | 0.9832 | 0.0204 |
| LoRA, reader-trained | reader transcript | 0.8246 | 0.8798 | 0.2012 |
| LoRA, reader-trained | oracle (GT-rendered) | 0.9583 | 0.9700 | 0.0456 |
| LoRA, oracle-trained | reader transcript | 0.8354 | 0.8863 | 0.1692 |
| LoRA, oracle-trained | oracle (GT-rendered) | 0.9303 | 0.9425 | 0.0287 |

Deltas against the matched bf16 baseline:

| adapter | on reader input | on oracle input |
|---|---|---|
| reader-trained | **−0.0234** | −0.0196 |
| oracle-trained | **−0.0126** | −0.0476 |

Four cells, four regressions. The deployable cell — reader-trained adapter on reader
input — is the second-worst of the four.

## Why the matched baseline was not optional

This is the clearest empirical result of the run, and it is a methodological one.

The previously committed structurer baseline is **0.8257**, measured on MLX **4-bit** on
Apple Silicon. The fine-tuned adapter scores **0.8246** in bf16 on CUDA. Comparing those
two numbers — the obvious thing to do, and what a reader would expect from a
"before/after" — gives:

```
0.8246 − 0.8257 = −0.0011      "no meaningful change"
```

Against the matched bf16 baseline measured on the same box, the truth is:

```
0.8246 − 0.8480 = −0.0234      a real regression, ~21x larger
```

**The quantisation confound would have hidden the regression almost exactly.** The
adapter's damage (−0.0234) and the bf16-over-4-bit gain (+0.0223) very nearly cancel. A
run that skipped the re-baseline would have reported "the LoRA is neutral" and been
wrong — not by a rounding error, but by the entire finding.

ADR-068 predicted this class of error before any GPU was rented and made the re-baseline
mandatory in three places. It cost roughly 80 minutes of A10G time. Without it this
document would have said the opposite of the truth.

## Secondary finding: what 4-bit costs the structurer

bf16 **0.8480** vs MLX 4-bit **0.8257** on identical inputs and prompt: **+0.0223** for
full precision. Both figures are retained rather than one superseding the other — the
4-bit number describes what actually runs on the target hardware, which is a real claim
for a privacy-first local system, and the gap quantifies the price of that locality.

## Mechanism: the adapter learned to over-emit

Spurious emission rate on reader input rises **0.1575 → 0.2012** with the reader-trained
adapter. The model emits *more* values it should have left null. Flat micro-F1 barely
moves (0.8843 → 0.8798), so the loss is concentrated in fields where the correct answer
is "not present" — the same failure surface ADR-048 measured for prompt perturbation and
ADR-058 traced to null-handling. Training on 100 examples in which most fields *are*
populated appears to have taught the model that emitting a value is usually right.

This is consistent with the oracle-trained adapter regressing *less* on reader input
(−0.0126 vs −0.0234): its training text contained no reader noise to over-fit to, so it
acquired less of the over-emission habit.

## Selection behaved exactly as designed

Dev-slice loss by epoch (both arms; dev = 17 invoices carved from TRAIN, seed 4242,
`sha256_dev f5b9bb80…`, zero overlap with the sealed 29). *Correction 2026-08-15
(supervisor review): an earlier revision of this table printed the oracle arm's curve
labelled "reader arm"; both curves below are re-read from the two
`horus_training_provenance.json` files, which are authoritative.*

| epoch | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| dev loss (reader arm) | **0.1956** | 0.3918 | 0.4438 | 0.4183 | 0.3857 | 0.3801 |
| dev loss (oracle arm) | **0.0965** | 0.3095 | 0.3799 | 0.3644 | 0.3150 | 0.3078 |

Dev loss **at least doubles between epoch 1 and epoch 2 in both arms** and never
recovers. The pre-registered rule (minimum dev loss selects) picked the end-of-epoch-1
checkpoint in both arms — the least-adapted checkpoint available.

Two things follow. First, the 6-epoch budget was correctly framed as a *budget*: epochs
2–6 existed to make the overfitting turn visible, and they did. Second, and more
importantly — **the reported regression is the best checkpoint this recipe can produce.**
Selection did not fail; there was nothing better to select. Had the sealed 29 been used
as the validation set (as the code did before ADR-067), the selection would have been made
on the reported set, and this conclusion would have been unavailable.

## What this does and does not license

**Supported**: on 100 training examples, LoRA on `gemma-4-E4B-it` does not improve
structured extraction over the zero-shot prompted model, and mildly harms it. The
bottleneck is not schema knowledge — the same model reaches 0.9778 on perfect text
zero-shot.

**Not supported**: that fine-tuning cannot help. n=100 is small, one recipe was tried,
one rank (8), one LR (1e-4). ADR-067 forbids a sweep, so the honest statement is that
*this* pre-registered recipe regressed, not that the technique is exhausted.

**Reinforced (ADR-064)**: the earlier decision not to fine-tune over prompt-fixable gaps
looks better in hindsight. ADR-066 found zero prompt repairs remaining, so this LoRA was
attacking genuine reading-gap fields — and still lost. A LoRA aimed at gaps the prompt
could have closed would have been credited with even less.

## Provenance

- Adapters + selection provenance: `data/finetune/adapter/`, `data/finetune/adapter-oracle/`
  (`horus_training_provenance.json` in each: chosen checkpoint, full dev curve, dev stem
  list + hash, hyperparameters, 258 target modules)
- Reports: `data/finetune/eval-{zeroshot,oracle}-bf16-val.json`,
  `data/finetune/eval-ft-{reader,oracle}-on-{reader,oracle}-val.json`
- Runbook: `scripts/gpu/README.md` §5C
- Driver: `scripts/gpu/run_lora_2x2.sh`
- Hyperparameters: rank 8, alpha 16, dropout 0.05, LR 1e-4 cosine + 3% warmup,
  batch 1 × grad-accum 8, max_length 6144 (auto; longest example 6094 → no truncation),
  `completion_only_loss=True`, 258 LoRA targets (text tower only), seed 42
