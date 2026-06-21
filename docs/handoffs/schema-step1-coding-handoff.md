# Handoff — Build the full-coverage schema, Step 1 (flat fields + VAT breakdown + Skonto)

| Field | Value |
|---|---|
| **From** | Cascade (schema-extension thinking session) |
| **To** | A fresh coding session (recommend Sonnet 4.6 1M — code-heavy) |
| **Decision** | ADR-041 (`docs/decisions/ADR-041-full-coverage-extraction-schema.md`) |
| **Field model** | `docs/architecture/invoice-field-model.md` (the authoritative checklist + touchpoint map) |
| **Plan** | `~/.windsurf/plans/horus-invoice-schema-full-coverage-68a4ac.md` |
| **Status** | ready to build |

## Your role

Implement **Step 1** of the full-coverage invoice schema: every new **flat single-value
field**, plus the two **simple repeating groups** (per-rate VAT breakdown, Skonto tiers).
You do **not** build the line-item table — that is Step 2 (ADR-042). You do **not** draft
ground-truth answer keys — the user does that once, after both steps land.

## Read first (in order)

1. `docs/decisions/ADR-041-full-coverage-extraction-schema.md` — the decision + rationale.
2. `docs/architecture/invoice-field-model.md` — **the build spec**: §4 (flat fields), §4.3
   (VAT breakdown), §4.4 (Skonto), §6 (touchpoint map), §8 (frozen-16 rework), §9
   (build-time decisions to finalize).
3. `src/horus/eval/ground_truth.py` — the `FieldSpec` registry, normalizers, the parse
   loop, `LEGACY_EXPERIMENT_FIELDS`, the `GroundTruth` line-item forward-compat hook.
4. `src/horus/eval/schema.py` — the `InvoiceFields` Pydantic model + `_coerce_one`.
5. `src/horus/eval/scorer.py` — `FIELD_GROUPS` / `DOCUMENT_FIELDS` + the partition asserts.
6. `src/horus/eval/normalizers.py` — prediction-side normalizers.
7. `app/data/fields.py` + `app/views/heldout_review.py` — display layer + the answer-key UI.
8. `src/horus/eval/heldout.py` — the hand-draft GT route + `gt_document` JSON shape.

## The build — flat fields (the bulk of Step 1)

For **each** new flat field in `invoice-field-model.md` §4.2, change all of these
**together** (three have import-time asserts that crash on drift — that is the guard):

1. **`ground_truth.py` → `FIELDS`**: add a `FieldSpec` row — `english_key`, `bt_code`,
   `german_label`, `xpath`, `normalize`, `field_type`. Reuse the container-path prefixes
   (`_HEADER_AGREEMENT` / `_HEADER_DELIVERY` / `_HEADER_SETTLEMENT` / `_SETTLEMENT_TOTALS`).
   **Verify each exact CII leaf XPath against a real corpus fixture** (factur-x extraction)
   before trusting it — the field-model doc gives BT codes + element families, not pinned
   paths. `FIELDS_V1` auto-derives; fields absent in v1 invoices simply read
   `is_present=False` (honest).
2. **`schema.py` → `InvoiceFields`**: add the field (`str | None = None`). `_coerce_one`
   already dispatches the existing types; add a branch only for a new `field_type`.
3. **`scorer.py`**: add the key to `FIELD_GROUPS[<group>]` or `DOCUMENT_FIELDS`. Add the
   **new `payment` group** to `FIELD_GROUPS` (due date, means code/text, status, IBAN, BIC,
   account name, reference). Keep `prepaid/allowance/charge/rounding` in `totals`.
4. **`app/data/fields.py`**: add to `LABELS` + `FIELD_ORDER` (+ `GROUP_DISPLAY["payment"]`).
5. **`normalizers.py`**: add a prediction normalizer only for a new `field_type`.

Per the field-model doc §9, finalize these small choices (record any deviation in a one-line
ADR-041 amendment): **document-type** representation (canonical label recommended);
**quantity / Skonto-days** numeric type (add a unit-less `NUMBER` type — do not reuse the
2-dp money normalizer); **unit** representation; **payment_status** derivation (paid /
partially_paid / open from prepaid-vs-due on the XML route; dropdown on the hand route).

## The build — repeating-group machinery (VAT breakdown + Skonto)

These do **not** fit `FIELDS`. Build the reusable machinery now (line items reuse it in
Step 2):

- **Ground-truth side**: a `VatBreakdownGT` + `SkontoGT` dataclass; add optional
  `vat_breakdown: list[VatBreakdownGT] | None` + `skonto: list[SkontoGT] | None` to
  `GroundTruth` (mirror the documented `line_items` hook). Parse the repeating CII elements
  (`ApplicableTradeTax` for VAT; `SpecifiedTradePaymentTerms` /
  `ApplicableTradePaymentDiscountTerms` **and** the FeRD structured-text Skonto convention
  for Skonto — handle both, see field-model §4.4).
- **Prediction side**: `list[...]` submodels on `InvoiceFields`; the `mode="before"`
  validator currently **drops** nested lists — extend it to coerce them.
- **Scorer**: a new scoring path that aligns rows by **natural key** (VAT: `rate_percent`;
  Skonto: `due_date`/order), then scores each cell; missing rows hurt recall, invented rows
  hurt precision. Keep this separable from the flat-field scoring.
- **Hand-draft route**: extend `gt_document` (`heldout.py`) JSON shape to carry the lists;
  add a small variable-length entry grid to `app/views/heldout_review.py` (today it is a
  fixed list of single boxes). `build_groundtruth_from_mapping` must accept the lists.

> The flat `tax_rate` / `tax_basis_total_amount` / `tax_total_amount` summaries **stay**
> (frozen single-rate view); the VAT breakdown is additive detail.

## Frozen-baseline rework (must-do)

`ground_truth.py` `LEGACY_EXPERIMENT_FIELDS` is subtractive (`FIELDS` minus 3 keys,
`assert len == 16`) — it **breaks** when `FIELDS` grows. Replace with an explicit positive
list (field-model §8):

```python
_LEGACY_16_KEYS = frozenset({ ...the 16 original keys... })
LEGACY_EXPERIMENT_FIELDS = {k: FIELDS[k] for k in _LEGACY_16_KEYS}
assert len(LEGACY_EXPERIMENT_FIELDS) == 16
```

Confirm the 3 closed-milestone reproduction tests still pin to it and pass unchanged. No new
freeze snapshot is needed (nothing scored at ≥19 fields yet).

## Prompt update

Extend the structurer prompts in `configs/arm-a.yaml` + `configs/arm-b.yaml` to request the
new fields (canonical English keys, "extract only what is present, else null"). Keep the
honesty instruction intact — the spurious-emission metric must stay near-zero.

## Tests required

- Per new flat field: a GT-parse test (present + absent), a prediction-normalization test,
  a scorer-dispatch test.
- Repeating groups: parse tests (single + multi-rate; one + two Skonto tiers), alignment +
  scoring tests, the before-validator nested-list coercion test, `gt_document` round-trip.
- The 3 closed-milestone reproduction tests: unchanged + passing (frozen-16).
- Synthetic-fixture coverage following the existing `tests/` patterns.

## Operating constraints

- **uv only** — `uv run python …`, `uv add …`; never bare `python`/`pip`.
- **No terminal one-liners with embedded newlines** — body content via files; commits via
  the `/commit` workflow.
- **Land via `@release-manager`** — branch → PR → CI green → squash-merge. Never push `main`.
- **Hardware** — M1 Pro / 16 GB; no change to model footprint in Step 1 (schema-only).
- **Evidence over claims** — see "Definition of done".

## Definition of done (Step 1)

1. `make install && make test` green; `make lint` + `make typecheck` clean.
2. `make zugferd-smoke` still passes; the new fields parse from a real ZUGFeRD fixture
   (show the extracted values for one invoice as evidence).
3. The three import-time asserts (scorer partition, display order, frozen-16) pass with the
   grown `FIELDS`.
4. The held-out review page renders the new flat fields + the VAT-breakdown / Skonto grids.
5. The structurer arms emit the new fields on a dev invoice with honest nulls (spurious
   near-zero).
6. PR merged via `@release-manager`; ADR-041 referenced.

## NOT in Step 1

- The **line-item table** (BG-25) and its smart content-matching scorer → **Step 2**, under
  ADR-042 (reserved). The repeating-group machinery you build here is what it reuses.
- **Ground-truth drafting / verification** of the 39 invoices → the user, once, after Step 2.
- **Held-out scoring** → later, once per approach.
