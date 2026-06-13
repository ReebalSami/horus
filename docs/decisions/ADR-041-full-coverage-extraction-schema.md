# ADR-041 — Full-coverage invoice extraction schema (Step 1: flat fields + VAT breakdown + Skonto)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-13 |
| **Milestone** | `feature-complete` (Phase 6 — implement) |
| **Authored by** | Cascade (schema-extension thinking session; plan `~/.windsurf/plans/horus-invoice-schema-full-coverage-68a4ac.md`) |
| **Issue** | Step 1 tracking issue (full-coverage schema) on the `horus roadmap` board; substrate for #78 (held-out GT drafting), #104 (eval-correctness audit). |

> **Sub-decision of ADR-034 (held-out strategy); extends ADR-035 (the 19-field schema).**
> The complete field universe + data shapes + touchpoint map live in the living reference
> `docs/architecture/invoice-field-model.md`; this record carries the *decision and its
> rationale*. Line-item scoring is deferred to ADR-042 (Step 2).

## Context

The scored schema is **19 fields** (ADR-012's 16 + ADR-035's tax-rate + two addresses).
A real German B2B invoice carries far more: document type, payment terms, bank details,
early-payment discount (*Skonto*), per-rate VAT breakdown, document-level
charges/allowances/prepaid, and the line-item table. Reporting an F1 over only 19 fields
is **not an honest claim about the tool** — it silently excludes everything the model was
never asked to read. The user's requirement is explicit and correct: to claim the tool
can do the work, the score must cover the work.

The held-out Belege set (#78, ADR-040) exists with ground truth **drafted but not yet
verified** (39/39 drafted, 0/39 verified) and **never scored**. So extending the schema
now changes no reported number — and lets the author verify the answer keys **once**
against the full schema (the no-double-pass goal). The schema redesign is therefore on the
critical path *before* held-out grading.

## Current-state survey (2026-06-13)

| Fact | Evidence | Implication |
|---|---|---|
| Schema = 19 flat fields; open/closed registry | `ground_truth.py` `FIELDS` (16) + ADR-035's 3 | Flat scalar adds are a registered-row change |
| Adding a scored field touches **4 files with 3 import-time asserts** | `scorer.py` partition assert; `app/data/fields.py` order assert; `ground_truth.py` `len==16` assert | A field add is a coordinated multi-file change, not a one-liner (corrects the handoff's understatement) |
| Frozen-16 set is **subtractive** (`FIELDS` minus 3) | `ground_truth.py` `LEGACY_EXPERIMENT_FIELDS`, `assert len==16` | **Breaks the moment `FIELDS` grows** → must be reworked to a positive list (ADR-037 supersession trigger 2 anticipated this) |
| Prediction model mirrors `FIELDS`, **drops nested objects** | `schema.py` `InvoiceFields` (`extra="ignore"`, flat fields only); `to_scored_dict` iterates `FIELDS` | Repeating groups need new submodels + the before-validator must stop dropping lists |
| GT has two routes, one shape | `parse_cii_xml` (XML) + `heldout.build_groundtruth_from_mapping` (hand-draft) | Both routes + the review UI must carry any new field |
| Real-invoice presence is uneven | datasheet: `seller_gln` 0/39, `buyer_vat_id` 0/39, totals ~100 % | Field set must be grounded in what invoices actually carry; honest-null absorbs the rest |
| Line items need row-alignment scoring | DocILE LIR (arXiv 2510.15727, already cited) + maximum-weight bipartite (arXiv 2405.20245) | The one genuinely hard piece → isolated to Step 2 |
| §14-UStG field weights are a supervisor sign-off item | thesis brainstorm v2 §5.2 + §4.1 + open-question #1; issue #17 | Carry weights as metadata; do **not** lock a weighted metric |

## Options considered

**A — Scope of coverage:**

| Option | Why considered | Verdict |
|---|---|---|
| Keep 19 fields | least work | rejected — the score is dishonest about real invoices (user's core point) |
| Add only the highest-value scalars | quick | rejected — partial coverage still can't claim "does the work" |
| **Full EN16931 / §14-UStG coverage incl. line items (chosen)** | the only honest basis for an F1 claim | chosen — locked with the user |

**B — Document family:** invoice family only (invoice / credit note / correction) — one
shared field set, matches the standard + the 39 documents. Receipts (*Kassenbon* /
*Bewirtungsbeleg*) are a distinct field set + would need their own samples → **separate
future schema**, not this one.

**C — Delivery shape:** **two steps** (chosen). Step 1 = all flat fields + the two simple
repeating groups (VAT breakdown, Skonto); Step 2 = the line-item table + its smart-matching
scorer (ADR-042). Same end coverage; isolates the one hard, research-weighted piece;
keeps each change reviewable. Rejected: one monolithic change (the hard line-item scorer
would gate the easy 80 % and bloat review). GT drafting waits for **both** steps, so the
author still verifies once.

**D — Line-item row alignment (deferred to ADR-042, recorded here for coherence):** smart
content matching (chosen direction) over position-only matching — position-only unfairly
penalizes harmless reordering; content matching is the accepted, citable standard.

**E — Compliance weighting:** carry an optional legal-importance level per field
(traceable to the thesis draft tiers) but keep the reported F1 **unweighted** until the
supervisor signs off. Rejected: baking an unsigned weighted metric now (would pre-empt a
§4.1 a-priori lock the supervisor owns — a HARKing-adjacent risk).

## Decision + integration thoughts

1. **Extend to full invoice-family coverage.** The complete field list is in
   `docs/architecture/invoice-field-model.md` §4–5: new flat fields (document type BT-3;
   payment block — due date BT-9, means BT-81/82, derived status, bank BT-84/85/86,
   reference BT-83; prepaid/allowance/charge/rounding BT-113/107/108/114; order reference
   BT-13; billing period BT-73/74), plus two simple repeating groups (per-rate VAT
   breakdown BG-23; Skonto tiers). The line-item table (BG-25) is **Step 2**.
2. **A new scorer/display group `payment`** joins seller / buyer / totals / document.
3. **Repeating-group machinery** (built in Step 1 with the simple VAT breakdown + Skonto,
   reused by line items in Step 2): a `…GT` dataclass + an optional `list[…]` on
   `GroundTruth` (the forward-compat hook already documented there); a `list[…]` submodel
   on `InvoiceFields` (the before-validator must stop ignoring nested lists); a new scoring
   path; the `gt_document` JSON shape + the review UI's variable-length grid.
4. **Rework the frozen-16 set to an explicit positive list** (`_LEGACY_16_KEYS`) so
   closed-milestone published numbers stay frozen at 16 as `FIELDS` grows. No new "19-field
   snapshot" is needed — nothing has been scored at ≥19 fields yet.
5. **Honesty preserved end-to-end:** on-document-only capture, honest null on absence,
   canonical keys / as-printed values. The structurer prompt (`configs/arm-{a,b}.yaml`) is
   extended to request the new fields; Pydantic post-hoc repair + the spurious-emission
   metric (ADR-027) remain the tax-domain guardrails.
6. **Compliance weights carried, not locked** (option E).

**Integration:** reuses the ADR-014 harness, the ADR-013/027 scorer dispatch + four-metric
surface, the ADR-035 validate/repair path, and the ADR-040 held-out routes. Flat fields
reuse the existing `field_type` comparators; new types (a unit-less `NUMBER` for quantity /
Skonto-days) are added at build time per the field-model doc §9. No production code is
written in this record — the build is handed to coding sessions (Step 1 handoff).

## Source archival

- **External:** EN16931 / ZUGFeRD-Factur-X business-term model — already archived at
  `docs/sources/legal/zugferd-en16931.md` (BT/BG codes + CII element families cited
  throughout the field-model doc). No new external stub required for Step 1; the
  line-item-scoring literature (DocILE arXiv 2510.15727 — already cited in
  `ground_truth.py`; RASG arXiv 2405.20245) gets its source stub when ADR-042 is authored.
- **Internal:** ADR-012 (16-field contract + forward-compat hook), ADR-035 (16→19 +
  Pydantic schema), ADR-037 (frozen-baseline scope), ADR-034 (held-out strategy +
  pre-registration), ADR-040 (held-out routes + honesty contract), ADR-013/027 (scorer).

## Supersession trigger

Superseded / amended if **any** of:

1. ADR-042 lands → line-item scoring is defined; this record's Step-2 framing is extended.
2. The frozen held-out results land → a results record cites this schema as its
   pre-registration provenance.
3. The supervisor signs off on §14-UStG field weights → a metric record adds the
   compliance-weighted F1; the unweighted score remains the baseline.
4. The field set changes again (new business terms, or receipt schemas) → the field-model
   doc + this record are revisited.

## Consequences

- The reported F1 can finally describe the **whole** extraction job — the honest basis for
  any "the local tool can do the work" claim.
- The held-out answer keys are drafted + verified **once**, against the full schema.
- Closed-milestone numbers stay frozen (positive-list rework); no published number shifts.
- The repeating-group machinery built in Step 1 is the substrate line items reuse in Step 2.
- Two records follow this design: ADR-042 (line-item scoring) and, later, the held-out
  results record.
