# Handoff — thesis writeup phase

**From**: LoRA-study / writeup-readiness closeout session (Cascade D, 2026-08-09)
**To**: a fresh Cascade dedicated to authoring the manuscript
**Recommended model**: a thinking-optimal one. This is decision-heavy prose, not code.

---

## 0. Your role

Write the thesis. **The experimental phase is closed.** Every number you need is committed;
none of it needs re-running. Your job is to turn a chapter skeleton with **57 `TODO`
markers** into a defensible manuscript, and to do it without inventing a single figure.

Do **not** start new experiments. Do **not** rent a GPU. Do **not** call a paid API. If you
find yourself wanting a number that does not exist in §3 below, that is a signal to
re-scope the sentence, not to go measure something — see §6.

---

## 1. Read these, in this order

1. `AGENTS.md` — project orientation, toolchain, project-local rules.
2. `docs/decisions/ADR-054-thesis-endgame-reader-first-recovery-and-scope-freeze.md` —
   **the governing document.** §5 is the scope freeze, §6 is the numbers lineage and the
   writeup gate. Everything below derives from it.
3. `docs/decisions/ADR-055-thesis-authoring-setup.md` + `thesis/README.md` — LaTeX setup,
   FH Wedel template adapted to English, biblatex `alphabetic` + biber, `make thesis`.
4. `docs/decisions/ADR-031` — the no-HARKing convention. Governs how unevaluated
   hypotheses must be reported.
5. `eval/structurer-lora-2x2-results.md` — the final experimental result, written up.
6. `docs/decisions/INDEX.md` — 68 ADRs. Skim titles; read the ones §3 cites.

---

## 2. Where the manuscript stands

`thesis/chapters/`, built with `make thesis` → `thesis/_build/main.pdf`.

| Chapter | State |
|---|---|
| `01-introduction.tex` | **substantially written** (125 prose lines, 1 TODO) |
| `00-abstract.tex` | stub — write last |
| `02-background.tex`, `03-related-work.tex` | 4 TODOs each; scaffolding |
| `04-system-design.tex` | 7 TODOs |
| `05-methodology.tex` | 11 TODOs — heaviest after limitations |
| `06-results.tex` | 8 TODOs — all numbers available, see §3 |
| `07-implementation.tex` | 3 TODOs |
| `08-discussion.tex` | 4 TODOs — see §5, there is a real finding to make here |
| `09-limitations-future-work.tex` | 13 TODOs — heaviest; see §4 and §6 |
| `10-conclusion.tex` | 1 TODO — write last |

Per-chapter status is also tracked in `docs/prompts/stages/05-writeup.md`.

---

## 3. The numbers you may cite — and their stacks

**Every figure must name its stack.** Two inference stacks coexist and they do not agree.
Conflating them is the single most likely way to publish something false.

### Structurer, sealed val (29 synthetic ZUGFeRD invoices)

| Reading | Stack | Figure | Source |
|---|---|--:|---|
| zero-shot, reader transcript | **bf16 / CUDA** | **0.8480** | `data/finetune/eval-zeroshot-bf16-val.json` |
| zero-shot, oracle (GT-rendered) text | **bf16 / CUDA** | **0.9778** | `data/finetune/eval-oracle-bf16-val.json` |
| zero-shot, reader transcript | **4-bit / MLX** | 0.8257 | ADR-059 |
| zero-shot, oracle text | **4-bit / MLX** | 0.9719 | ADR-059 |

Cost of running locally in 4-bit: **+0.0223** for bf16 (ADR-068). Both figures are retained
on purpose — the 4-bit number is what actually runs on the target hardware, which is a real
claim for a privacy-first system, and the gap is the price of that locality.

> **Latent error to fix on contact**: `09-limitations-future-work.tex` currently cites
> **0.9719** without naming its stack. Its bf16 twin is 0.9778. Fix it wherever it appears.

### LoRA 2×2 (ADR-067, bf16 / CUDA throughout)

| structurer | reader input | oracle input |
|---|--:|--:|
| zero-shot (matched baseline) | 0.8480 | 0.9778 |
| LoRA, reader-trained | 0.8246 (**−0.0234**) | 0.9583 (−0.0196) |
| LoRA, oracle-trained | 0.8354 (−0.0126) | 0.9303 (−0.0476) |

All four cells regress. Selection picked `checkpoint-13` (end of epoch 1) by minimum dev
loss; the dev curve ran 0.0965 → 0.3095 → 0.3799 → 0.3644 → 0.3150 → 0.3078, so **the
reported regression is the best this recipe produces.** Mechanism: `spurious_emission` rose
0.1575 → 0.2012 while flat micro-F1 barely moved (0.8843 → 0.8798).

### Real-world held-out (the out-of-sample claim)

| Reading | Figure | Source |
|---|--:|---|
| mean per-invoice F1 | **0.8825** | ADR-065 (supersedes ADR-063's 0.8767) |
| pooled cell F1 | **0.8987** | ADR-065 |
| english / email (n=11) | 0.9318 | ADR-063 |
| german / email (n=18) | 0.8997 | ADR-063 |

Corpus: 39 private invoices, **39/39 author-verified** ground truth signed off through the
ADR-062 adjudication queue. Public sanitized record with the id↔sha256 freeze table and a
per-field presence table over all 34 fields:
`docs/architecture/belege-heldout-datasheet.md`.

### Arms comparison (ADR-038, in-sample dev)

regex 0.675 / Arm A 0.809 / Arm B 0.935 micro-F1; `spurious_emission` **0.000 across all
three**. Honest counter-finding: regex beats both VLM arms on `seller_tax_id` (1.000 vs
0.000), so no approach is strictly dominant.

### Reader

Qwen3-VL-4B selected by competitive bake-off (ADR-057, #117); the pre-registered 8B sibling
test was adjudicated and the 4B choice confirmed (#124).

> **Provenance rule**: `docs/prompts/stages/04-experiments.md` opens with a caveat that every
> F1 in it is **in-sample / diagnostic** on clean synthetic PDFs and that *no number there
> may be cited as HORUS's real-world accuracy*. Honour that. The out-of-sample surface is the
> held-out Belege set above, and only it.

---

## 4. Hard constraints on what the thesis may claim

1. **Layer 1 only** (ADR-054). The knowledge-graph and query layers are *design and future
   work*. No evaluated claim about them exists, so none may be made.
2. **No-HARKing (ADR-031).** Pre-registered-but-unevaluated hypotheses must be listed and
   reported as "not evaluated within thesis scope". `sec:unevaluated` is already stubbed for
   this. The list is in §6 below and mirrors the open `future-work`-labelled issues.
3. **The structurer was never competitively selected**, unlike the reader. It was held
   constant so the prompt-repair work stayed interpretable. This is a genuine limitation and
   the LoRA result makes it *sharper*, not softer — a different structurer might close the
   reader-noise gap with no fine-tuning at all. Already drafted at
   `09-limitations-future-work.tex` §`sec:lim-structurer`; keep it honest.
4. **Field coverage is 19→34 scored fields, not the whole invoice** (#111, deferred). A real
   German B2B invoice carries more: line items, and the full EN16931 surface. State which
   fields are scored, that the reported F1 describes the extraction job *as scoped*, and
   point at the datasheet's presence table so the gap is inspectable rather than rhetorical.
   `LEGACY_EXPERIMENT_FIELDS` pins published closed-milestone numbers at 16 behind an
   import-time assert, so historical figures are stable.
5. **Measurement-construct honesty.** The reading-quality proxy (is a GT value findable as a
   substring in the transcript) correlates with the end metric but *is* a proxy — a value can
   be present as a string yet unusable because the surrounding table is mangled. Say so.
6. **Every cited source gets archived** under `docs/sources/<type>/<slug>.md` before
   citation, per `horus-source-archival`. Four stubs were added for you in §5.

---

## 5. Ch. 8 has a real finding — do not undersell it

The negative LoRA result is **not** an anomaly. It is a documented, mechanistically-explained
phenomenon, and four sources were archived for you during closeout:

- `docs/sources/papers/2024-unfamiliar-finetuning-examples-hallucinate.md` (arXiv 2403.05612)
  — **the exact mechanism.** SFT models default to a *hedged prediction* matching their
  training data's answer distribution. 100 mostly-populated invoices ⇒ the hedge became
  "emit a value" ⇒ the measured `spurious_emission` rise. Also explains why the
  oracle-trained adapter regressed *less* on reader input.
- `docs/sources/papers/2024-limitations-of-instruction-tuning.md` (arXiv 2402.05119) — LoRA
  "is limited to learning response initiation and style tokens", so it could not add reading
  capability. Explains the *absence* of gain.
- `docs/sources/papers/2026-why-finetuning-encourages-hallucinations.md` (arXiv 2604.15574) —
  stability–plasticity; freezing plasticity when no new knowledge is needed is the principled
  argument for not fine-tuning here at all.
- `docs/sources/papers/2026-epistemological-humility-sft-hallucination.md` (arXiv 2603.17504)
  — SFT "implicitly rewards always responding"; 800 controlled LoRA SFT runs including
  **Gemma3-4B**, the same family.

**The contribution angle**: HORUS's `spurious_emission` metric (ADR-027) *quantified* what
2403.05612 predicts, on a **structured-extraction** task where "absent" is a first-class
legitimate answer that the scorer grades. The cited work studies factual QA, where abstention
is a behaviour to be taught and measured indirectly. That difference is yours to claim.

**The second finding is methodological and belongs in Ch. 5 as well as Ch. 8**: ADR-068's
mandatory matched-stack re-baseline *changed the conclusion*. Comparing the bf16 adapter
(0.8246) against the committed 4-bit baseline (0.8257) yields −0.0011, "neutral". The matched
comparison yields **−0.0234**, ~21× larger. The adapter's damage and the bf16-over-4-bit gain
(+0.0223) very nearly cancel, so skipping the re-baseline would have reported the opposite of
the truth. That is a clean, concrete argument for precision-matched evaluation.

Author/venue fields in all four stubs are `(TBD)` — confirm them at deep-read before citing,
per the existing convention in `docs/sources/papers/`.

---

## 6. Pre-registered but NOT evaluated — report as such

These are open GitHub issues labelled `future-work`, milestone cleared, deliberately left
open so the record stays visible (ADR-031). Each has a comment explaining the deferral.

| # | Item | Basis |
|---|---|---|
| #80 | Cloud H1 comparison on the held-out set | **Named verbatim in ADR-054 §5.** Note its anchor citation ("Berghaus-2025") is *unverified* — do not cite it unchecked |
| #49 | KG / GraphRAG (Layer 2 + 3) | H3–H6 frozen; manuscript capped at Layer 1 |
| #50 | Multi-agent / orchestration router | H3–H6 frozen |
| #91 | Parser-agent vs deterministic adapter | New experiment; ADR-054 forbids. Half-answered by ADR-038 |
| #111 | Full-coverage EN16931 schema | Would invalidate ADR-054 §6's frozen numbers lineage |
| #81 | Layer-1 production hardening | Consumers shipped (#82/#109) or frozen (#49) |

Also frozen by ADR-054 §5 and needing a sentence each: **degraded/photographed-Belege
robustness** (MDPBench axis) and **template-shift (H7)**.

Open writeup issues: **#48** (OCR-free framing in Ch. 1 motivation + README) and **#56**
(README + architecture diagrams refresh). `#96` (soften §203 Ch. 1 framing) is
supervisor-gated and low-priority. `#48`/`#56` are the `submission-ready` milestone.

---

## 7. Operating constraints

- **`@release-manager` for every landing.** No direct push to `main` (cascade-system ADR-018).
- **`/commit` for any commit with a body** — embedded newlines in `run_command` quoted args
  crash the Windsurf macOS terminal. Non-negotiable.
- **`make thesis`** builds the PDF (needs TeX Live/MacTeX; self-contained, *not* uv).
  `make thesis-clean` removes artifacts.
- **`make lint` / `make typecheck` / `make test`** must stay green (1265 tests). Prose work
  should not touch them, but verify before landing anything that does.
- **CI runs on ubuntu**, where `mlx` is absent (Apple-Silicon-gated). If you add code, keep
  mlx imports lazy and guard mlx-dependent tests — this bit us once already.
- ADRs for significant decisions, at the moment of decision (`document-as-you-go`,
  `horus-decision-discipline`). Reserve the number in `docs/decisions/INDEX.md` **first**.

---

## 8. Suggested order

1. **Ch. 5 methodology** — the apparatus is fully documented in ADRs; writing it first fixes
   your vocabulary and forces the stack-naming discipline early.
2. **Ch. 6 results** — transcribe §3 above; no new analysis needed.
3. **Ch. 4 system design** + **Ch. 7 implementation** — descriptive, low-risk.
4. **Ch. 8 discussion** — §5 above; the strongest chapter available to you.
5. **Ch. 9 limitations + future work** — §4 and §6; also fix the 0.9719 stack ambiguity.
6. **Ch. 2 background** + **Ch. 3 related work** — informed by the Ch. 8 literature.
7. **Ch. 1** — already substantial; reconcile with #48.
8. **Abstract + conclusion last.**

## 9. Done means

- `make thesis` produces a PDF with no `TODO` markers surviving in the chapter bodies.
- Every reported figure names its inference stack.
- No claim beyond Layer 1; every frozen hypothesis listed as not-evaluated.
- Every cited source archived under `docs/sources/`.
- `#48` and `#56` closed; `submission-ready` milestone closable.
