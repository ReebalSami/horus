# ADR-044: JSON-recovery structural-repair rung — supply omitted delimiters without inventing values

**Status**: Accepted
**Date**: 2026-06-14
**Refs**: ADR-018 (`adapters_json` recovery ladder), ADR-038 (structurer reuses the ladder), ADR-034 (honesty guardrail), ADR-042 (repeating-group scoring), ADR-043 (sibling ruler fix)

## Context

During the Arm-A-vs-Arm-B comparison at the full-coverage schema (34 flat fields + repeating groups), the Arm-B Gemma structured output for `EN16931_Rabatte` scored `micro_f1=0.000` — while the same model on `EN16931_Einfach` and `EN16931_Gutschrift` scored 0.727. Inspection of the saved transcript (`docs/sources/transcripts-arms-dev/google__gemma-4-e4b-it__EN16931_Rabatte.txt`) showed the output was in fact **fully populated** — every header field, all totals, the VAT breakdown, and four line items were emitted — but the **4th `line_items` object was missing its closing `}`** before the array's `]`:

```json
    {"line_id": "4", ... "line_amount": "55,40"
  ],
```

The `adapters_json` recovery ladder (ADR-018, reused by the structurer per ADR-038) has four rungs: direct `json.loads`, balanced-brace scan, greedy substring, trailing-comma sanitization. None repairs a missing closer mid-document — the balanced-brace scan (which tracks only `{`/`}`) never returns to depth 0 once a brace is dropped, so the whole object is unrecoverable and the invoice collapses to an all-null prediction. A single syntactic slip thus **zeroed an otherwise-complete invoice**, distorting per-invoice and pooled micro-F1 and corrupting the A/B comparison (Arm B's Rabatte 0.000 is a measurement artifact, not a content failure; the same fragility hits Arm A, whose Rabatte output carried an unquoted German-comma decimal). This is the same class of problem as ADR-043: a broken ruler, not a model weakness.

## Decision

Add a fifth, last-resort rung to `_try_parse_json` — `_repair_unbalanced_json(text)` — reached only when every existing rung fails. It does a single string-aware pass from the first `{`, maintaining a delimiter stack, and:

1. **Mismatched-closer repair** — on encountering a closer that does not match the top of the stack but whose matching opener exists deeper in the stack (e.g. `]` while the innermost open delimiter is `{`, with a `[` below), it supplies the missing closer(s) for the intervening unclosed delimiter(s) before emitting the closer. This inserts the dropped `}` so the row, the array, and the enclosing object all balance.
2. **Spurious-closer drop** — a closer with **no** matching opener anywhere on the stack (e.g. a `}`→`]` substitution that leaves an extra `]` after the array has already closed: `... "55,40" ] ], ...`) is dropped, leaving the stack untouched. Critically, the repair must **not** pop an enclosing delimiter to satisfy a stray closer — doing so would close the root object prematurely and orphan the trailing fields (`"purpose_summary"`), defeating the recovery.
3. **Truncation repair** — at end-of-input it appends closers for any still-open `{`/`[` in LIFO order.
4. It **stops as soon as the top-level object closes**, so trailing markdown fences / prose are ignored.

Two distinct real Arm-B `EN16931_Rabatte` runs exhibited (1) and (2) respectively — Gemma is not deterministic across runs, so both the pure-missing-`}` and the `}`→`]`-substitution variants must be handled.

The scan is **string-safe** (braces/brackets inside JSON string literals do not affect depth; backslash escapes honored) and **value-preserving**: it supplies only delimiters the model omitted — never a key or a value — so the ADR-034 honesty guardrail (a structurer must never invent a value) holds. Dangling trailing commas left by an inserted closer are sanitized before the parse attempt. The recovered dict flows through the normal `InvoiceFields.validate_and_repair` path, so locale coercion (German `215,07` → `215.07`) applies as usual.

## Alternatives considered

- **Adopt a JSON-repair library (`json-repair` or similar).** Robust and battle-tested for LLM output, but (a) ADR-018 deliberately established a stdlib-only ladder, (b) a new runtime dependency requires its own ADR + decision-discipline review, and (c) the observed failure class is bounded and deterministically fixable in-house. Deferred as an evidence-driven future option: if scale-up (Phase 4, 10→15+ invoices) surfaces malformation modes the in-house rung cannot handle, that empirical evidence justifies revisiting with a library. Not added speculatively (YAGNI).
- **Exclude Rabatte from the comparison.** Rejected: it reduces coverage (the user's explicit objective is 100% coverage) and hides a real robustness gap rather than fixing it.
- **Aggressively close dangling strings too (recover mid-string truncation).** Rejected: guessing where a truncated string ended risks emitting a partial/wrong value and breaks the ratified "unparseable → honest all-null" contract (ADR-018/038). The rung deliberately declines mid-string truncation (`in_string` open at end → returns `None`).

## Consequences

- The Arm-B `EN16931_Rabatte` micro_f1=0.000 artifact is eliminated; all four line items and every flat field are recovered. Per-invoice and pooled micro-F1 become valid measurements again, restoring a fair A/B comparison.
- Behaviour is **unchanged for every input that already parses** — the rung is strictly additive (reached only after all prior rungs fail), so no historical run's numbers shift.
- The "unparseable → all-null" contract is preserved for genuinely broken output (mid-string truncation, no `}` present at all): regression-tested.
- Benefits **both arms** and all downstream phases (few-shot tuning, scale-up) by ensuring a single brace can no longer dominate aggregate metrics.

## Tests

`tests/test_adapters_json.py` §3b and `tests/test_structurer.py`:

- `test_repair_recovers_missing_brace_before_array_close` — the exact Rabatte pattern recovers all 4 line items + trailing `purpose_summary`.
- `test_repair_recovers_flat_fields_through_adapter` — flat-adapter surfacing (was all-null pre-ADR-044).
- `test_repair_recovers_bracket_truncation` — LIFO closer append.
- `test_repair_declines_when_truncated_midstring` — honest all-null contract preserved.
- `test_repair_does_not_invent_values` — value-preservation (delimiters only).
- `test_to_predicted_dict_recovers_missing_brace_via_arm_b_path` / `test_to_predicted_groups_recovers_missing_brace` — the typed Arm-B path recovers + locale-coerces.

## Supersession trigger

If scale-up surfaces malformation classes the in-house rung cannot deterministically repair (e.g. unquoted German-comma numerics, single-quoted keys, unescaped inner quotes), revisit and adopt a maintained JSON-repair dependency under its own ADR — replacing this rung rather than stacking heuristics.
