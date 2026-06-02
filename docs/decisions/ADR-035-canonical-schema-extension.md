# ADR-035 — Canonical extraction schema extension: German-canonical Pydantic `InvoiceFields` + tax-rate + addresses + non-scored purpose-summary

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-02 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (held-out-evaluation strategy session; plan `~/.windsurf/plans/horus-heldout-eval-strategy-d8c53c.md`) |
| **Issue** | [`ReebalSami/horus#88`](https://github.com/ReebalSami/horus/issues/88) |
| **Relationship** | Sub-decision of **ADR-034**; **extends/supersedes the schema contract of ADR-012** (forward-compat clause). |

## Context

ADR-034 chose a structurer (Gemma-4) that emits a structured object directly, and a held-out, **language-agnostic** evaluation. Two schema needs follow:

1. **Type safety + locale robustness.** The current JSON arm parses with a bare `json.loads()` (ADR-029) — no typing, and it hallucinates on absent fields (spurious 0.458). The German money/date locale variance (`1.234,56` vs `1,234.56`; `DD.MM.YYYY` vs ISO) needs deterministic coercion, not model trust.
2. **Field coverage.** ADR-012 fixed a 16-field EN16931 schema and **explicitly deferred** "line items (BG-25), per-VAT-rate breakdown (BG-23), address fields, and charge/allowance totals … see §'What this ADR does NOT decide' for the deferral rationale + forward-compat clause" (`ground_truth.py:242-244`). Real Belege analysis needs at least the **VAT rate** and the **seller/buyer addresses** to be useful (and demo-worthy).

This ADR exercises ADR-012's forward-compat clause: it adds the most-valuable deferred fields and makes the schema a typed Pydantic model that doubles as the JSON-arm fine-tuning target (#88).

## Current-state survey (2026-06-02)

| Component | Where | State |
|---|---|---|
| Canonical 16-field schema | `src/horus/eval/ground_truth.py` `FIELDS` | English-keyed `FieldSpec` catalog (BT-1/2/5/72, seller/buyer names+IDs, 5 totals); `field_type` ∈ {STRING, MONEY, DATE, CODE}; per-type normalizers |
| Deferred fields | `ground_truth.py:242-244` | BG-5/BG-8 addresses, BG-23/BT-119 VAT-rate breakdown, BG-25 line items — out of scope, forward-compat reserved |
| JSON adapter | `src/horus/eval/adapters_json.py` | bare `json.loads()` → dict; no typing, no validation (ADR-029) |
| Pydantic | `pyproject.toml` (ADR-004) | already a dependency — no new-library ADR |
| Constrained decoding | — | **unavailable** on MLX (ADR-018) → validation must be **post-hoc**, not decode-time |
| Scorer | `src/horus/eval/scorer.py` (ADR-013/027) | per-`field_type` comparators + 4-metric surface; new scalar fields slot into the existing dispatch |

## Options considered

**A — Field granularity:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Header scalars only (tax-rate + addresses) | objective, ANLS\*/exact-scorable, low risk | **chosen** for the scored set — defensible headline metric |
| Full line-item recognition (BG-25, per-row desc/qty/price) | richest; matches DocILE-LIR | **deferred (stretch)** — row-alignment scoring is heavier; not needed for the headline |
| Generated free-text purpose summary | great for the demo / Streamlit | **included but NON-scored** — subjective; would need an LLM-judge; kept out of the F1 lineage |

**B — Validation strategy:**

| Option | Why considered | Why not / why chosen |
|---|---|---|
| Constrained / grammar-guided decoding | hard type guarantees | **unavailable on MLX** (ADR-018) — not an option locally |
| Trust the model's JSON | simplest | the 0.458 spurious rate (ADR-029) proves it is unsafe for tax data |
| **Post-hoc Pydantic validate + repair (chosen)** | deterministic coercion of locale money/date; honest null on missing | the only locally-feasible path; pairs with a strict "extract-only-what-is-present, else null" prompt |

**C — Canonical keys:** keep ADR-012's **English snake_case** canonical keys (stable, standards-anchored) with German labels retained for provenance; values are emitted **as printed** in any language (language-agnostic per ADR-034). Rejected: German keys (churns ADR-012's contract for no gain).

## Decision + integration thoughts

1. **Define `InvoiceFields` Pydantic model** (new, e.g. `src/horus/eval/schema.py`) covering ADR-012's 16 fields **plus**:
   - `tax_rate` — applied VAT rate(s) (EN16931 BG-23 / BT-119); `field_type` CODE-like exact-on-normalized (e.g. `19.0`).
   - `seller_address`, `buyer_address` — postal address (EN16931 BG-5 / BG-8); `field_type` STRING (ANLS\*).
   - `purpose_summary` — generated free-text "what is this invoice for"; **non-scored** (excluded from all F1 metrics; rendered in the Streamlit app only).
2. **Typing + coercion:** dates → ISO 8601; money → 2-dp `Decimal`; codes/rates → normalized `str`; missing → explicit `null` (never invented). Validators reuse the ADR-013 normalizers.
3. **Post-hoc validate/repair:** the structurer emits reasoning-then-strict-JSON; the JSON is parsed → `InvoiceFields.model_validate` → repair pass (locale coercion) → scored. Invalid/absent fields become honest nulls.
4. **GT parser extension:** `parse_cii_xml` gains xpaths for BG-5/BG-8 (`PostalTradeAddress`) and BG-23/BT-119 (`ApplicableTradeTax/RateApplicablePercent`) so the new scored fields have ground truth. Byte-identical v1/v2 handling per ADR-033.
5. **Schema = fine-tuning target** (#88): the typed model is the canonical target for the JSON-arm LoRA (#55).

**Integration:** additive to `FIELDS` + the scorer dispatch (ADR-027 metrics recompute over the larger field set); the regex baseline (ADR-013/028) is unaffected on its existing 16 fields and simply reports null on the 3 new ones (honest). No change to the harness contract.

## Source archival

Internal only: ADR-012 (16-field schema + forward-compat clause), ADR-004 (Pydantic), ADR-013/027 (scorer + metrics), ADR-018 (no constrained decoding on MLX), ADR-029 (JSON-arm spurious evidence), ADR-033 (v1/v2 CII), ADR-034 (parent strategy). EN16931 business terms (BT-119, BG-5, BG-8, BG-23, BG-25) are the standard already anchored by ADR-012; no new external stub.

## Supersession trigger

Superseded if **any** of:

1. Full line-item recognition (BG-25) is adopted → a new ADR defines the row-alignment scoring contract; this schema becomes its header subset.
2. The canonical field set changes again (add/remove scored fields) → amend here or supersede.
3. Constrained/grammar-guided decoding becomes available locally (e.g. a future MLX feature) → the post-hoc validation path becomes the floor, and a new ADR ratifies decode-time enforcement.
4. The `purpose_summary` is promoted to a scored field → requires an LLM-judge protocol ADR (it is non-scored here by design).

## Consequences

- The structurer has a typed, locale-robust, language-agnostic target that doubles as the fine-tuning target.
- The scored field set grows from 16 to 19 objective fields (+ 1 non-scored demo field); ADR-012's deferral is partially discharged with a clean supersession link.
- Hallucination is bounded by post-hoc validation + honest-null + the ADR-027 `spurious_emission` metric (the tax-domain guardrail from ADR-034).
- Implementation is handed to a coding session (plan §"Coding-session handoffs"); no code in this ADR.
