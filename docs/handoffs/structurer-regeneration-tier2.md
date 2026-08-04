# Handoff — Tier-2 structurer re-generation + LoRA gate re-evaluation

**From**: the ADR-058 prompt-surface audit session (Cascade D)
**To**: a fresh coding session (Sonnet 4.6 1M recommended — mechanical run + measure work)
**Branch**: `feat/reader-bakeoff-run` (already checked out; ADR-058 work is uncommitted)
**Status of predecessor work**: complete and gate-green. Nothing here depends on further
reasoning about *why* the fields were broken — that is settled and documented.

---

## Your role

Run the Tier-2 re-generation, measure it, and decide the LoRA gate on the corrected baseline.
This is deliberately a **measurement** task: all code fixes are already landed and gated. Do
not re-litigate the diagnosis; if a measurement contradicts it, that is a finding to record
(and ADR-058 names it as a supersession trigger).

---

## Read in this order

1. `docs/decisions/ADR-058-structurer-prompt-surface-and-scoring-fairness.md` — what changed
   and why; §"Measured effect" gives the Tier-1 numbers you are extending
2. `eval/field-prompt-audit.md` — the evidence (leaks, ungrounded aliases, the oracle
   transcript proof for BT-107/108)
3. `eval/per-field-reporting-audit.md` — the predecessor audit; note the **inline corrections**
   marking its sign-mismatch hypothesis and its LoRA target list as superseded
4. `docs/decisions/ADR-054-thesis-endgame-reader-first-recovery-and-scope-freeze.md` — the
   LoRA gate you are re-evaluating (**fine-tune only if the re-baseline stays < 0.90**)
5. `docs/decisions/ADR-048-*` — why a prompt-fixable gap must never become a LoRA target
6. `docs/decisions/ADR-057-reader-selection-qwen3-vl.md` — canonical reader lineage

---

## Why Tier 2 is needed

Tier 1 re-scored **frozen** generations, so it could only measure the scorer/normalizer fixes:

| field | granite | qwen3-vl-4b | oracle |
|---|---|---|---|
| `tax_rate` | 0.182 → **0.778** | 0.182 → **0.900** | 0.000 → **0.952** |
| `prepaid_amount` | 0.000 → **0.750** | 0.333 → **0.750** | 0.750 → 0.750 |
| `allowance_total_amount` | 0.000 → 0.000 | 0.000 → 0.000 | 0.000 → 0.000 |
| `charge_total_amount` | 0.571 → 0.571 | 0.889 → 0.889 | 0.000 → 0.000 |
| **overall_micro_f1** | 0.6771 → **0.6856** | 0.8141 → **0.8189** | 0.9608 → **0.9676** |

BT-107/108 are flat because their cause is the **prompt**, and a prompt fix cannot change a
generation that already exists. The glossary now names `Gesamtbetrag der Abschläge` (88/146)
and `Gesamtbetrag der Zuschläge` (88/146) instead of the never-printed `Summe Nachlässe` /
`Summe Zuschläge`. Re-generation is the only way to measure that.

---

## Work to do

### Step 1 — sanity gates before spending any inference

```sh
make lint && make typecheck && make test && make audit-prompts
```

Expect: lint clean · mypy clean (148 files) · **982 passed** · `audit-prompts` **RESULT: PASS**
(`UNGROUNDED ALIASES: 0`, `LEAKED GT VALUES: 0`).

If `audit-prompts` fails, **stop** — the prompt is contaminated again and re-generating would
bake that in.

### Step 2 — record the exact prompt being measured

```sh
make glossary RAW=1 > /tmp/glossary-adr058.txt
wc -c /tmp/glossary-adr058.txt      # expect ~5.1 KB, 22 glossed fields
```

Attach the char count to the run notes; the glossary is now a versioned experimental variable.

### Step 3 — re-generate the two decisive arms

Runs the structurer (`google/gemma-4-E4B-it`, MLX, local) over the sealed val split, saving
raw generations so Tier-1-style offline re-scoring stays possible later. All flags below are
verified against `--help`.

**Per the `long-running-foreground` rule: run each FOREGROUND, streaming. Do not background
and poll.** 29 invoices per arm.

```sh
# (a) canonical reader lineage — THE arm the LoRA gate is decided on
uv run python scripts/finetune_evaluate.py --split val \
  --config configs/finetune-structurer.yaml \
  --label zero-shot-qwen-adr058 \
  --save-outputs data/finetune/zeroshot-qwen-adr058-outputs \
  --out data/finetune/eval-zeroshot-qwen-adr058-val.json

# (b) oracle ceiling — the DECISIVE test for BT-107/108
uv run python scripts/finetune_evaluate.py --split val \
  --config configs/finetune-structurer.yaml --oracle \
  --label oracle-adr058 \
  --save-outputs data/finetune/oracle-adr058-outputs \
  --out data/finetune/eval-oracle-adr058-val.json
```

Confirm each arm reports `29 ok / 0 failed / 29 total`.

**The granite arm is deliberately NOT re-generated.** ADR-057 superseded that lineage, no
config selects it (only the stale bare `FinetuneConfig()` default does), and its pre-fix
number (0.6771) is not the gate. Spending inference on a superseded reader would buy nothing.

#### Trap: there are TWO Qwen configs pointing at DIFFERENT transcript trees

| config | `transcript_dir` | its pre-fix baseline |
|---|---|---|
| `configs/finetune-structurer.yaml` | `docs/sources/transcripts-multipage` | `eval-zeroshot-qwen-lineage-val.json` = **0.8141** ← use this |
| `configs/finetune-structurer-qwen-val.yaml` | `data/finetune/bakeoff/qwen__qwen3-vl-4b-instruct` | `eval-zeroshot-qwen-val.json` = 0.7829 |

Both set `reader_model: Qwen/Qwen3-VL-4B-Instruct`, so the reader name does **not** tell them
apart — only `transcript_dir` does. The correct pairing was established by mtime provenance:
`data/finetune/zeroshot-qwen-outputs/` (2026-08-02 18:31) matches
`eval-zeroshot-qwen-lineage-val.json` (2026-08-02 18:31) to the minute, while the other
candidate is 9 h earlier. **Use `configs/finetune-structurer.yaml`** so the Tier-2 numbers are
comparable to the Tier-1 table above.

### Step 4 — measure the delta

The Tier-1 side lived in `/tmp` and is probably gone. Regenerate it from the still-on-disk
pre-regeneration generations (no inference — `--score-only` loads no model), then diff:

```sh
# Tier-1 reference points (post-fix scorer, PRE-fix prompt)
uv run python scripts/finetune_evaluate.py --split val \
  --score-only data/finetune/oracle-outputs \
  --label oracle-tier1 --out data/finetune/eval-oracle-tier1-val.json
uv run python scripts/finetune_evaluate.py --split val \
  --score-only data/finetune/zeroshot-qwen-outputs \
  --label qwen-tier1 --out data/finetune/eval-zeroshot-qwen-tier1-val.json

# Tier-1 -> Tier-2: isolates the PROMPT fix, since the scorer is identical on both sides
uv run python scripts/compare_eval_reports.py \
  data/finetune/eval-oracle-tier1-val.json \
  data/finetune/eval-oracle-adr058-val.json
uv run python scripts/compare_eval_reports.py \
  data/finetune/eval-zeroshot-qwen-tier1-val.json \
  data/finetune/eval-zeroshot-qwen-adr058-val.json
```

Diffing Tier-1 against Tier-2 (rather than against the original baselines) is what makes the
delta attributable to the **prompt** alone — both sides run the same scorer.

**The decisive question**: did `allowance_total_amount` and `charge_total_amount` move off
0.000 on the **oracle** arm?

- **Yes** → the prompt-gap diagnosis is confirmed. Record the numbers, flip ADR-058 to
  `Accepted`.
- **No** → the diagnosis is refuted; ADR-058's supersession trigger fires. Re-open the
  GT/field-definition hypothesis. Next probe: is the GT `AllowanceTotalAmount` xpath actually
  the value a human reads off the totals block, or is it an aggregate the page never shows as
  one number?

### Step 5 — re-evaluate the ADR-054 LoRA gate

Gate: **fine-tune only if the re-baselined zero-shot arm stays < 0.90** overall micro F1.

Use arm (a) — the canonical reader lineage. Tier 1 already moved it 0.8141 → 0.8189 on scorer
fixes alone; the glossary fix will move it further. If it crosses 0.90, **the LoRA is off** per
ADR-054 and the scope freeze applies.

### Step 6 — re-derive the LoRA target list (only if the gate still opens)

`eval/per-field-reporting-audit.md` §"LoRA target list" is marked **PROVISIONAL**: every field
on it had ungrounded or missing aliases when it was written, so its gap was partly
prompt-fixable. Re-derive from the post-regeneration per-field table. A field belongs on the
list only if the **oracle** arm is high (structurer *can* do it given the text) **and** the
reader arm is still low **after** the corrected prompt.

### Step 7 — land it

Via `@release-manager` (never `git push origin main`). The ADR-058 work is **already
committed** on `feat/reader-bakeoff-run` as 5 commits:

1. `fix(eval): gate per-field aggregation on signal-bearing outcomes`
2. `feat(eval): shared accumulator + --score-only offline re-scoring`
3. `fix(eval): correct three oracle-zero fields + corpus-ground the prompt surface`
4. `feat(eval): prompt-surface audit gate + eval diagnostics`
5. `docs(ADR-058): prompt-surface + scoring-fairness correction`

Yours is the 6th: `feat(eval): Tier-2 re-baseline on the corrected prompt (ADR-058)`. The PR is
squash-merged, so intermediate commits collapse — the split exists for review readability.

---

## Operating constraints

- **Never hardcode.** The user was explicit and this session already found real violations
  (four GT values leaked into the prompt; 34 invented aliases). Any new alias must come with a
  corpus hit count from `make audit-prompts`.
- **No literal values in glossary descriptions** — describe the shape. Two gates enforce this
  (`test_glossary_descriptions_embed_no_concrete_identifiers` + `make audit-prompts`).
- **Never construct a bare `FinetuneConfig()`** — it silently selects the superseded
  granite-258M reader. Always `FinetuneConfig.from_yaml(...)`.
- **Foreground + streaming** for all inference (`long-running-foreground` rule).
- **No heredocs / no embedded newlines in `run_command`** (`no-terminal-oneline-scripts`);
  commits with a body go through `/commit`.
- **Repair, never invent**: the `tax_rate` backfill copies the *model's own* rate. Nothing may
  read the GT at inference or scoring time.

---

## Termination criteria

Done when **all** hold:

1. Both decisive arms re-generated; each reports `29 ok / 0 failed`
2. The BT-107/108 question in Step 4 is answered with numbers
3. The ADR-054 LoRA gate is re-evaluated against the new baseline and the verdict recorded
4. ADR-058 flipped to `Accepted` (or its supersession trigger fired and documented)
5. `eval/field-prompt-audit.md` §"Open / deferred" item 4 updated with the Tier-2 result
6. Gates green: `make lint`, `make typecheck`, `make test`, `make audit-prompts`
7. Landed via `@release-manager`; working tree clean

---

## Known-open, explicitly out of scope here

- **22 `german_label` values never occur in the corpus.** They feed
  `dataset.render_oracle_transcript`, so the oracle arm shows labels real pages never print.
  Deferred on purpose: changing them re-baselines the oracle arm and would confound *this*
  measurement. Separate ADR + separate re-baseline.
- **`FinetuneConfig.reader_model` default is stale** (granite vs ADR-057's Qwen3-VL-4B).
  Changing it shifts every bare-config caller; needs its own decision.
- **`rounding_amount`** — present on 1/146 invoices, no grounded label. Stays reported as
  untested; do not manufacture a number for it.
