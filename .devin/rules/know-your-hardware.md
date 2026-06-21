---
trigger: model_decision
description: Local hardware is M1 Pro / 16 GB / Metal 4 / 14 GPU cores / no CUDA. Tool / library / model choices respect ARM availability + RAM ceiling + Metal-vs-CUDA. When task plausibly exceeds local capacity (training >3B model, processing >50 GB data, requiring CUDA-only library, or other resource-heavy compute), STOP and surface: what is needed / why local fails / AWS-or-API recommendation / budget estimate / ask user approval. Never spin up AWS resources or make paid API calls without explicit budget-acknowledged approval.
sources_consulted:
  - cascade-system/docs/decisions/ADR-018-release-discipline-cluster.md (own) — co-authored with this rule
  - cascade-system/docs/architecture/parked-items-brainstorm.md (own) — §3 design walking + drift correction (workspace-only deploy, not global)
  - SETUP_ROADMAP.md §1 L0 system tools — actual hardware spec
  - User operating constraints — AWS escalation policy explicitly requested in original plan §2
adapted_for:
  - L2 workspace-deployed rule (NOT in `global_rules.md` per ADR-018 drift correction; deployed via `/start-project` step 6a to every project's `.windsurf/rules/`)
  - `model_decision` trigger — only fires when resource-heavy intent is detected (saves context budget; per Windsurf docs only workspace rules support `model_decision`)
  - AWS / OpenAI / Anthropic / Bedrock as escalation paths (original plan was AWS-only)
  - Cost guardrails: spot instances, S3 lifecycle, immediate teardown
---

# know-your-hardware

> **CONSTRAINT**: Cascade runs on the user's machine. Heavy compute (training, large datasets, CUDA-only libraries) does not fit. Surface the constraint, propose an alternative path with budget, get explicit approval before spending money.

## Hardware spec

```
Machine:    Apple Silicon — M1 Pro
RAM:        16 GB unified memory
GPU:        Apple GPU, 14 cores, Metal 4
CUDA:       NOT AVAILABLE (Apple Silicon)
Storage:    ~500 GB SSD (varies — check headroom before large downloads)
Python:     3.13 via pyenv
Node:       v25
```

These constraints are global. They apply to every project Cascade touches.

## Implications for tool selection

| Concern | Local fits | Local fails — surface |
|---|---|---|
| **Architecture** | ARM-native packages (`pip`, `npm`, Homebrew arm64) | x86-only libraries, packages with no Apple Silicon wheels |
| **GPU** | Metal-backed frameworks (`mlx`, PyTorch MPS, `tensorflow-metal`) | CUDA-only libraries (e.g., FlashAttention v2, `bitsandbytes` quantization, Triton kernels) |
| **RAM** | Models + activations under ~10 GB | Fine-tuning >3 B params, batched inference at scale, in-memory datasets >8 GB |
| **CPU parallelism** | 8-core M1 Pro is fine for data prep, embedding, sklearn | Distributed training, multi-node anything |
| **Storage** | Datasets up to ~50 GB after compression | >50 GB working set; large model checkpoints (Llama-70B is ~140 GB FP16) |

When any constraint binds, fire this rule.

## Escalation procedure (5 steps)

When local plausibly fails:

1. **What** — Describe the task plainly (e.g., "fine-tune Llama-3-7B on 50k examples").
2. **Why local fails** — Cite the binding constraint (RAM / CUDA-only lib / dataset size / etc.).
3. **Recommendation** — One of:
   - **AWS GPU rental**: e.g., `g5.2xlarge` ($0.36/hr spot, ~$1.20/hr on-demand). Best for: training, fine-tuning, multi-hour jobs.
   - **AWS Bedrock**: managed inference for foundation models. Best for: production inference of Anthropic / Mistral / Cohere / Llama.
   - **OpenAI / Anthropic API**: per-token pricing. Best for: classification, extraction, one-off inference; often cheaper than GPU rental for small volumes.
   - **Cloud notebook**: Colab / Kaggle / Lightning Studios. Best for: exploration, when iteration speed matters more than throughput.
4. **Budget estimate**:
   - GPU rental: hourly rate × estimated hours + S3/EBS storage
   - API: per-token rate × estimated tokens (input + output)
   - State assumptions explicitly (training epochs, batch size, dataset size)
5. **Ask user approval**:

```
⚠ Task plausibly exceeds local capacity:
  Need:           <task description>
  Why local fails: <constraint>
  Recommendation: <option> (~$<estimate>)
  Alternatives:   <option B>, <option C>
  Approve / defer / pick alternative?
```

**Never** spin up AWS resources or hit paid APIs without explicit user approval.

## Cost guardrails (when AWS path is approved)

- **Spot instances by default** — ~70% cheaper; tolerate interruptions for training (checkpointing required)
- **S3 lifecycle policies** — move outputs to Infrequent Access after 30 days; Glacier after 90; auto-delete after 365 (project-dependent)
- **Immediate teardown** — when job completes, stop instance + remove EBS volume; don't leave instances "for later"
- **Budget alarms** — set CloudWatch billing alarm at 50% / 80% / 100% of the approved budget
- **Region** — `us-east-1` (cheapest for most resources); `eu-central-1` only when data residency requires

## Examples

**Example 1: "Fine-tune Llama-3-7B on 50k examples"**

```
⚠ Task plausibly exceeds local capacity:
  Need:           Fine-tune Llama-3-7B (LoRA) on 50k examples, 3 epochs
  Why local fails: 7B model + LoRA training peaks ~20 GB; 16 GB local insufficient.
                  No CUDA → can't use Unsloth / FlashAttention.
  Recommendation: AWS g5.2xlarge spot (~$0.36/hr); estimated 6h training → ~$2.20
                  + S3 for dataset + checkpoint (~$0.50)
                  Total: ~$3
  Alternatives:   - Cloud notebook (Lightning AI, ~$0.50/hr GPU)
                  - Smaller model locally (Phi-3-mini fits in MPS)
  Approve / defer / pick alternative?
```

**Example 2: "Process 80 GB of CSV files for entity extraction"**

```
⚠ Task plausibly exceeds local capacity:
  Need:           Stream-process 80 GB CSVs through entity extractor
  Why local fails: 80 GB > local SSD headroom; CPU-only extraction is slow at this scale
  Recommendation: API path (Anthropic Claude Haiku for extraction)
                  ~80 GB / 4KB chunk = 20M API calls
                  At Haiku pricing (~$0.25 / 1M input tokens, avg 1k tokens/call):
                  ~$5,000 — likely too expensive
  Alternatives:   - AWS EMR with Spark on spot fleet (~$50-100 for the job)
                  - Local stream processing with smaller extractor (DistilBERT NER on MPS)
                    — 10× slower, but fits — estimated 8-12 hours
  Approve / defer / pick alternative?
```

**Example 3: "Inference quantized 7B model"**

```
Local fits — fire this rule but recommend local:

  Need: Run quantized Mistral-7B for chat
  Local works: Ollama with 4-bit quant fits in ~5 GB; runs on MPS
  Tool: Ollama (Apple Silicon native)

No escalation needed.
```

**Example 4: "Build a Next.js app"**

```
Local fits trivially. Rule does not fire (no resource-heavy intent in description).
```

## Activation triggers (`model_decision` keywords)

The rule activates when the description signals resource-heavy work. Keywords / patterns that trigger:

- "fine-tune" / "train" / "training run" / "RLHF" / "DPO"
- "GPU" / "CUDA" / "Metal" (any compute hardware mention)
- "AWS" / "EC2" / "S3" / "Bedrock" / "spot instance"
- "dataset" + size unit (>50 GB)
- "Llama-70B" / "Mixtral" / "GPT-4" + run-locally context
- "embedding" + ">1M documents"
- "Spark" / "EMR" / "distributed"
- "OCR" / "Donut" / "LayoutLMv3" + ">10k pages"

When the description is ambiguous (e.g., "process some data"), do not fire prematurely; ask the user to clarify volume + compute path first.

## Source

Workspace-deployed rule per ADR-018 brainstorm drift correction. Long-form archive at `~/Projects/cascade-system/docs/rules/know-your-hardware.md`. Deployed to every project's `.windsurf/rules/` by `/start-project` step 6a (the per-project rule copy mechanism from ADR-014).
