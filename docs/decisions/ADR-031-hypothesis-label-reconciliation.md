# ADR-031 — Hypothesis-label reconciliation to canonical §6 + pre-registration of H8 (efficiency)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-31 |
| **Milestone** | `experiments-validated` close-out (hypothesis-label audit) |
| **Authored by** | Cascade (experiment-phase close-out session) |
| **Issue** | No dedicated issue — surfaced during the milestone-close hypothesis-label audit while reconciling per-experiment ADR citations against the locked brainstorm v2 §6 |
| **Supersession trigger** | (a) the external locked §6 registry is restructured / renumbered → re-reconcile + supersede; OR (b) H8 is split (decode-throughput vs memory-fit promoted to separate numbered hypotheses) → supersession ADR ratifies the split; OR (c) an efficiency hypothesis is later found to have been pre-registered earlier than 2026-05-31 in a source not consulted here → correct the H8 dating + supersede. |

## Context

Per-experiment ADRs cite which brainstorm v2 §6 hypothesis (`H_i`) they test — this is HORUS's operative no-HARKing audit trail (`02-brainstorm.md` §12 amendment, line 274). During experiment-phase close-out, a label audit cross-checked every `H1`–`H7` citation across the ADRs, scripts, README, and the ADR INDEX against the **verbatim** §6 text in the locked brainstorm.

The audit found systematic mislabels — including one **fabricated citation**. Because the hypothesis labels are the no-HARKing spine of the thesis, the mislabels are not cosmetic: a reader (or the thesis writeup) trusting an ADR's "§6 H_n" citation would attribute the wrong prediction to the wrong layer, and in one case would cite a pre-registered hypothesis that never existed.

This ADR (1) records the verbatim §6 mapping as the single source of truth, (2) catalogs and corrects every mislabel, and (3) pre-registers the efficiency hypothesis as **H8** — the user's decision (option 2) over leaving efficiency as an un-numbered comparison.

## Canonical §6 (verbatim — locked brainstorm v2, 2026-05-08)

Source: `/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/research/THESIS_BRAINSTORM_STATE_v2.md` §6, lines 215–243 (read-only research file). Mirrored by reference (not by definition) in `docs/prompts/stages/02-brainstorm.md`.

| H | Layer | Claim (abbreviated; see §6 for full text + thresholds) |
|---|---|---|
| **H1** | Layer 1 | Local document VLMs (3B–7B) reach compliance-aware F1 within X pp of EU-hosted cloud SOTA on ZUGFeRD German invoices. |
| **H2** | Layer 1 architecture | Single-shot end-to-end VLMs beat orchestrated specialist pipelines on **clean** ZUGFeRD; orchestrated pipelines beat single-shot on **degraded** Belege where validator-retry corrects errors (directional flip). |
| **H3** | Layer 2 | Compliance-aware extraction F1 predicts KG compliance pass-rate monotonically; standard token F1 is a worse predictor. |
| **H4** | Layer 3 | **Graph** retrieval beats **vector** retrieval on multi-hop (class 3) + compliance-check (class 2) queries by ≥Y; vector matches/exceeds on simple-lookup (class 1). |
| **H5** | Layer 3 | A query-feature-only router reaches accuracy within Z of an oracle router. |
| **H6** | conditional | Validator-driven retry on single-shot VLMs closes the compliance-pass-rate gap to cloud by ≥N pp within latency budget L. |

**H7** is a *floated candidate* (transfer-learning / template-shift robustness), explicitly "possibly H7" in `02-brainstorm.md:49` and used in `experiments/02-fatura2.py:574`. It is **not** locked. **H8** was free before this ADR.

## Errors found + corrections

### Class A — architecture hypothesis mislabeled `H1` (canonical = `H2`)

The single-shot-vs-orchestrated comparison is **H2**. Several ADRs slipped to "H1" (which is local-vs-cloud). Proof the slip is a mistake, not a scheme: the same ADRs cite H2 *correctly* elsewhere (`ADR-008:15` quotes the canonical H2 verbatim; `ADR-009:213` says "H2 single-shot-vs-orchestrated").

| Location | Before | After |
|---|---|---|
| `ADR-008:10` | "H1 single-shot-vs-orchestrated comparison" | H2 |
| `ADR-009:96,:112` | "H1 (single-shot-vs-orchestrated)" | H2 |
| `ADR-009:636` | "single-shot vs orchestrated … (sibling; H1 hypothesis)" | H2 |
| `ADR-009:699` | "pilot #13's H1 comparison" (single-shot pairs orchestrated) | H2 |
| `ADR-009:21,:82` | "H1 / H2 single-shot-vs-orchestrated" (muddled) | clarified: cohort feeds **H1** (local-vs-cloud arm) **and** **H2** (single-shot arm); the single-shot-vs-orchestrated experiment itself is **H2** |

### Class B — efficiency mislabeled `H4` (canonical `H4` = graph-vs-vector); fabricated §6 citation

There is **no efficiency hypothesis in §6**. `ADR-017` labeled the latency/throughput/memory work "H4" throughout and, at `:324`, fabricated a verbatim quote:

> *"Pre-registered hypothesis: brainstorm v2 §6 H4 — 'MLX-routed VLMs achieve ≥3× tokens/sec compared to Transformers-MPS-routed VLMs at comparable F1 on the ZUGFeRD corpus.'"*

§6 H4 is the Layer-3 graph-vs-vector hypothesis; this efficiency claim is absent from §6 entirely. The "§6 H4" attribution at `ADR-017:93,:134,:156,:324` (+ README:131, INDEX:21) is corrected: efficiency is **H8**, pre-registered **2026-05-31** via this ADR — never part of the 2026-05-08 §6 lock.

All remaining bare "H4" tokens in `ADR-017` + `scripts/inspect_pilot_13.py:198` (which all denote the efficiency hypothesis — ADR-017 never discusses Layer-3 retrieval) → **H8**.

### Class C — #76 approach-gate mislabeled `H2`

`ADR-030` reframes #76 (free-form+adapter vs native-JSON extraction) and labels it "H2 (exploratory→confirmatory, arXiv 2503.08124)". But #76 compares two **output-formatting modes of single-shot VLMs** — neither arm is an orchestrated specialist pipeline, so #76 is **not** §6 H2. ADR-030 itself frames it as "diagnostic, NOT a verdict." Per the §12 convention (`02-brainstorm.md:294`: cite an `H_i` *or* "explicitly mark 'exploratory under §4.2 branches-on-results'"), #76 is **exploratory**. The arXiv 2503.08124 exploratory→confirmatory *continuum* is the **methodology stance** (kept), not a hypothesis label (dropped).

| Location | Before | After |
|---|---|---|
| `ADR-030:13,:115` + `:18/:55/:62` | "H2 (exploratory→confirmatory …)" / "violates H2" | exploratory under §4.2; methodology = exploratory→confirmatory (arXiv 2503.08124) |
| `scripts/reading_ceiling.py:525` → generated `eval/reading-ceiling-and-approach-comparison.md:5` | "hypothesis H2" | exploratory (arXiv 2503.08124) — regenerated |

## Decision

1. **Correct every mislabel in-place** (Class A/B/C above), with a short erratum note in each affected ADR pointing here.
2. **Pre-register H8 (efficiency)** — the user's option (2). Statement adopted **verbatim from ADR-017's own existing wording** (not newly invented), correctly numbered + honestly dated:

   > **H8 (Layer 1, efficiency — formalized 2026-05-31):** *MLX-routed VLMs achieve ≥3× decode tokens/sec compared to Transformers-MPS-routed VLMs at comparable F1 on the ZUGFeRD corpus, and the cohort's local document VLMs run within the M1 Pro / 16 GB unified-memory envelope.*
   > - **Falsifiable:** yes — perf sweep across the 7-working-model cohort using the ADR-017 instrumentation (`decode_tps` / `inference_tps` / `peak_memory_gb` / `%_max`).
   > - **Threshold provenance:** the ≥3× figure is **literature-grounded** (brainstorm v2 §7.2 directional ranking: MLX ~230 tok/s vs PyTorch MPS ~7–9 tok/s), to be confirmed/refined by the HORUS sweep — not fitted to any HORUS result.
   > - **Evidence status:** the efficiency **test has not been run** (`ADR-017:156` shipped instrumentation only; pilot-13 logged no perf metrics per `ADR-017:131`). No confirmatory data exists → H8 is a **genuine pre-registration**, dated later than the H1–H6 lock and never claimed otherwise.

3. **No-HARKing honesty note for the thesis writeup:** Chapter 3 reports H1–H6 pre-registered 2026-05-08; **H8 added 2026-05-31** after the instrumentation (ADR-017) but **before** the efficiency test ran. This is transparent late-formalization, not retro-fitted confirmation, consistent with `02-brainstorm.md:304`'s exploratory→confirmatory framing.
4. **H7 unchanged** — remains a floated transfer-learning candidate; not locked by this ADR.
5. **Pre-registration ≠ test commitment.** Recording a falsifiable prediction does not commit the thesis to running every test (H6 is already explicitly conditional; Layer-2/3 hypotheses H3/H4/H5 may not be reached within scope). Untested hypotheses are reported honestly as "not evaluated within thesis scope."
6. **Going-forward rule (restates `02-brainstorm.md:294`):** every experiment ADR cites a §6 hypothesis (now **H1–H8**) by its verbatim definition, **or** marks the work "exploratory under §4.2 branches-on-results." No §6 number may be attached to work that is not that hypothesis.

## Consequences

- **Corrected surfaces:** `ADR-008`, `ADR-009` (Class A); `ADR-017`, `README.md`, `scripts/inspect_pilot_13.py`, `INDEX.md` (Class B); `ADR-030`, `scripts/reading_ceiling.py`, regenerated `eval/reading-ceiling-and-approach-comparison.md`, `INDEX.md` (Class C). `docs/prompts/stages/02-brainstorm.md` gets a §13 pointer recording H8 in the registry's in-repo home.
- **External §6 file is read-only to Cascade.** H8 must be synced into `THESIS_BRAINSTORM_STATE_v2.md` §6 by the user. **Flagged as a user action.** Until synced, ADR-031 + `02-brainstorm.md` §13 are the authoritative in-repo record of H8.
- **GitHub issues** citing the old labels (e.g. #77 "H4 latency-efficiency") are not rewritten by this ADR; they are reconciled during board triage with a reference here.
- **Scientific-record integrity restored:** the fabricated "§6 H4" citation is the most serious finding; correcting it removes a false pre-registration claim from the canonical ADR trail.

## Related

- `docs/prompts/stages/02-brainstorm.md` §6 (registry) + §12 (cite-`H_i`-or-mark-exploratory convention) + §13 (H8 pointer)
- `ADR-017` (efficiency instrumentation — Class B source)
- `ADR-030` (#76 reframe — Class C source)
- arXiv 2503.08124 (exploratory→confirmatory continuum — methodology, archived per `horus-source-archival`)
- Kerr 1998 (`docs/sources/papers/kerr-1998-harking.md`) — the no-HARKing anchor this reconciliation defends
