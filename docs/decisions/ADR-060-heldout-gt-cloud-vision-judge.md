# ADR-060: Held-out ground-truth authority — cloud vision judge over page images

**Status**: Proposed (sample-validation gate below decides scope before any full re-author)
**Date**: 2026-08-04
**Refs**: ADR-040 (the held-out Belege set + its GT convention this supersedes), ADR-054 (scope freeze; what the thesis may claim), ADR-057 (reader selection — the reader whose output is being judged), ADR-011 (supersession over deletion), ADR-023 (corpus-absent auto-skip), #114 (held-out evaluation ticket), `docs/architecture/belege-heldout-datasheet.md` (the `verified: 0/39` record)

## Context

The 39-invoice held-out Belege set has carried ground truth since ADR-040, and it was
used for the first time this session. Scoring it produced
`overall_micro_f1 = 0.5692`, which was **retracted within the same session** after an
audit found the number measures the answer key rather than the pipeline. Two
independent defects, both verified against the actual page rasters rather than
inferred:

**1. Coverage.** The drafted GT carries exactly 19 flat fields and **no repeating
groups**. The scorer scores ~37 flat fields plus `line_items` / `vat_breakdown` /
`skonto`. Every prediction outside those 19 keys was therefore scored against nothing
and counted as a false positive, producing exactly-0.000 pooled F1 on `line_items`
(n=388), `vat_breakdown` (n=101) and `document_type` (n=36). Because
`overall_micro_f1` pools groups with flat fields, the headline was dominated by absent
GT.

**2. Correctness, concentrated in the image-only channel.** The GT was authored by a
previous Cascade session from each PDF's **embedded text layer**
(`heldout_manifest.py text`, described in-file as a "drafting aid"), recorded as
`drafted_by: "cascade"`, `verified: false` for all 39. The 10 `iphone-pdf-scan`
invoices are photographs with effectively no text layer, so for those the drafter had
almost nothing to read. Adjudicating `belege-de-scan-010` (a photographed MEDIA MARKT
till receipt) against its page image:

| field | drafted GT | page shows | verdict |
|---|---|---|---|
| `issue_date` | `28.01.2022` | `28.09.2022` | wrong month |
| `grand_total_amount` | `53,97` | `63,97` (`Total EUR`, `GIROCARD`) | wrong |
| `due_payable_amount` | `53,97` | `63,97` | wrong |
| `tax_total_amount` | `null` | `10,21` (`incl. 19,00% MwSt`) | false null |
| `tax_basis_total_amount` | `null` | `53,76` (`Netto-Warenwert`) | false null |
| `seller_address` | `Billstedter Platz 3` | `Billstedter Platz 37` | wrong digit |

`53,97` appears nowhere on the receipt — it is neither the net (`53,76`) nor the total
(`63,97`), i.e. a blend of the two. The pipeline's own output for the same invoice was
independently wrong in a *different* direction (`59,87` total, `Hilgertstr. 37`,
`buyer_name: "HAMA"` — a product brand), so the 0.158 score for that invoice compared
two hallucinations. By contrast `belege-en-email-001` (a digital OpenAI invoice with a
real text layer) was adjudicated **correct on all 14 non-null fields**, which localises
the defect to the channel that lacks a text layer rather than to the drafting session
as a whole.

A held-out set whose answer key is unverified and provably wrong on a subset cannot
support the generalisation claim ADR-054 reserves for it. The GT authority has to
change before any held-out number is reportable.

## Current-state survey

Surveyed 2026-08-04 via the `context7` MCP against `/anthropics/anthropic-sdk-python`
(`mcp2_resolve-library-id` → `mcp2_query-docs`, two queries), because
`context7-and-docs-first` forbids implementing against an external SDK from
training-data memory and this project has never had a cloud-LLM dependency (verified:
no `anthropic`/`openai` entry in `pyproject.toml`, no `Anthropic`/`claude-`/
`api.openai` reference anywhere under `src/`, `scripts/`, `app/`).

Findings that shaped the design, all from current SDK sources rather than recall:

- **Vision input** is a content block `{"type": "image", "source": {"type": "base64",
  "media_type": "image/png", "data": …}}`; `Base64ImageSourceParam` accepts `str` or
  `Base64FileInput`, so a `Path` can be handed to the SDK directly and multiple image
  blocks can share one request — the whole-document view a multi-page invoice needs.
- **`output_config.effort`** accepts `"low" | "medium" | "high" | "xhigh" | "max"`, and
  is an independent field from `thinking.budget_tokens` (separate TypedDicts, no
  cross-validation). This is the "xhigh effort" lever requested by the user, and it is
  real rather than assumed.
- **`output_config.format`** takes a JSON schema (structured outputs), so the judge's
  reply can be schema-locked to the GT shape. This matters more than it appears: the
  existing pipeline needs `validate_and_repair` (ADR-035) precisely because free-form
  JSON from a local model is unreliable, and an answer key produced through a repair
  path would be a second-order guess.
- **`thinking`** is a union of `enabled` (explicit `budget_tokens`, min 1024, counted
  against `max_tokens`), `adaptive` (auto-budget), and `disabled`.
- **`client.models.list()`** returns available models **newest first**, so the strongest
  model can be resolved from the caller's own account at runtime instead of pinning a
  model ID that this session cannot verify still exists. SDK examples currently show
  `claude-sonnet-5`; `claude-opus-4-6` appears in the thinking-capable warn list.

## Options considered

| Option | Reference | Why considered | Why not chosen |
|---|---|---|---|
| **Cloud frontier vision judge (Anthropic Messages API), Opus-class, `effort="xhigh"`, schema-locked output, reading the 300 DPI page rasters** | `docs/sources/tools/anthropic-messages-api.md` | Only option that puts frontier vision on the photographed receipts — the exact subset the text-layer draft got wrong. Schema-locked output removes the repair path. Effort lever is explicit and verified. Pages are already rasterized (58 PNGs, this session), so no new preprocessing. | **CHOSEN** |
| Local frontier VLM on a rented GPU | ADR-057, `scripts/gpu/README.md` | Keeps the privacy-first posture absolute — no invoice ever leaves owned hardware, which is HORUS's whole thesis. Infrastructure already proven this session (A10G, ~$0.45/run). | The candidates that fit a 24 GB A10G are the same class as the *system under test* (Qwen3-VL-4B is the selected reader). An answer key authored by a sibling of the model being measured is circular; the audit above shows exactly how that fails. A genuinely stronger open model (200B+) exceeds the rented-box budget and still would not clearly beat a frontier judge. |
| Human-only annotation by the author | — | The actual gold standard; the only thing that can set `verified: true` honestly. | 39 invoices × ~40 fields including line items ≈ 1,500+ cells authored from scratch. Not rejected — **retained as the verification layer** on top of the judge, which is what makes it tractable (review disagreements, not every cell). |
| Status quo: keep the text-layer Cascade draft | ADR-040, `heldout_manifest.py` | Zero cost; already on disk. | Disproven this session: wrong values and false nulls on the sampled scan invoice, 19/37 field coverage, zero group coverage, `verified: 0/39`. Cannot support a generalisation claim. |

Vendor comparison within the cloud-judge option (OpenAI, Google) was **not** surveyed.
Stated plainly as a limitation rather than papered over: the binding constraints were
vision-on-scans, schema-locked output, an explicit effort control, and the user's stated
preference for Opus/Sonnet-class judging. Cross-vendor agreement is the documented
escalation path below, not a silent omission.

## Decision + integration thoughts

**Author held-out GT with an Opus-class Anthropic vision judge reading the 300 DPI page
images, schema-locked to the full field registry, at `effort="xhigh"`, and gate the
scope on a sample first.**

Scope is deliberately **not** settled by this ADR. The immediate step is a ~6-invoice
sample (3 `iphone-pdf-scan`, 3 `email`) producing a three-way side-by-side of
current-GT vs judge-GT vs page image, so the true error rate across the set is measured
rather than extrapolated from the two invoices audited above. A full 39-invoice
re-author is justified only if the sample shows the email-channel drafts are also
defective; if the defect stays confined to the scan channel, the cheaper targeted path
applies. Deciding scope from a 2-invoice sample would repeat the original sin of this
whole episode — acting on an unvalidated answer key.

How it fits the rest of the system:

- **The instrument stays fixed.** GT authority changes; the scorer, the field registry,
  the normalizers (ADR-043/045/046/048/050/051/052), and `evaluate_structurer` do not.
  `build_heldout_records` already routes held-out GT through
  `build_groundtruth_from_json` → the same `GroundTruth` type the factur-x path
  produces, so a re-authored GT file drops in with no scoring-code change.
- **Coverage becomes schema-complete.** The judge emits the full flat registry plus
  `line_items` / `vat_breakdown` / `skonto`, which removes the all-FP artifact that
  zeroed the groups. This is the half of the problem that affects all 39 invoices,
  including the ones whose flat GT is already correct.
- **`verified` keeps its meaning.** Judge output is written as `drafted_by:
  "<model-id>"`, `verified: false`. A frontier model is a better drafter, **not** a
  human. `verified: true` is set only by author review, per invoice, and the datasheet
  keeps reporting drafted-vs-verified separately. This ADR does not let a model close
  that gap, and the thesis must not claim it does.
- **Privacy cost is explicit and bounded.** This is the first time invoice *content*
  leaves owned hardware, which cuts against HORUS's central privacy claim. It is
  acceptable only because the judge is a measurement instrument, never part of the
  delivered system: the pipeline under test remains fully local, and no cloud call
  exists on the inference path. That distinction belongs in the thesis's threat model,
  not just here. Inputs stay inside the git-ignored tree (ADR-040); the API key is read
  from the environment / git-ignored `.env` (verified via `git check-ignore`) and never
  committed.
- **Forward compatibility.** The same harness serves the Phase-3 adjudication role
  (judging pipeline output against GT with the page image in context) and the post-LoRA
  comparison, so this is one dependency serving three needs rather than a one-off.

Known limitations, recorded as risks rather than resolved: a single judge has no
independent check on its own errors; the judge sees the same rasters as the reader, so a
rasterization defect would be invisible to both; and `iphone-pdf-scan` photographs are
genuinely hard, so some cells may be unreadable by *anything*, in which case the honest
GT value is an explicit "illegible" rather than a guess.

## Source archival

- `docs/sources/tools/anthropic-messages-api.md` — Anthropic Messages API / Python SDK
  vision + `output_config.effort` + structured-outputs + `models.list` capabilities, as
  retrieved via `context7` on 2026-08-04.

Internal evidence cited above needs no external stub: ADR-040 and
`docs/architecture/belege-heldout-datasheet.md` (GT provenance and `verified: 0/39`),
ADR-057 and `scripts/gpu/README.md` (the local-VLM alternative), and this session's
adjudication of `belege-de-scan-010` / `belege-en-email-001` against their page rasters.

## Supersession trigger

This ADR is superseded if **any** of the following is observed:

1. **The sample gate fails in the judge's direction** — the ~6-invoice sample shows the
   judge disagreeing with the page image (author-adjudicated) on more cells than the
   existing text-layer draft does. Then the cloud judge is not the better drafter and
   the decision reverts to targeted human annotation.
2. **Author review contradicts the judge on > 10% of non-null cells** during
   verification of the re-authored GT. That rate makes single-judge GT unfit as a
   thesis answer key, and the escalation is multi-judge agreement (two frontier vendors
   must agree; disagreements go to the author) — which is also where the un-surveyed
   OpenAI/Gemini options re-enter.
3. **A local model demonstrably matches frontier judging on this set** — e.g. a
   quantized 200B-class VLM runs within the rented-GPU budget and reproduces the
   verified GT. Then the privacy cost above is no longer justified and GT authoring
   returns to owned hardware.
