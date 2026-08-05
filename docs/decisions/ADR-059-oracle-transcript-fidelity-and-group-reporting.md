# ADR-059: Oracle-transcript fidelity + group-level reporting

**Status**: Accepted
**Date**: 2026-08-04 (work shipped) / **authored retroactively 2026-08-06**
**Refs**: ADR-058 (the prompt-surface audit this shipped alongside), ADR-054 (the
attribution audit the oracle arm serves), ADR-049/053 (registry-driven glossary; the
flat-only decision), ADR-042 (repeating-group scoring), ADR-046 (document-type has a value
but no printed label), ADR-037 (the frozen regex baseline that compiles `german_label`),
ADR-064 (prompt-fixable vs fine-tune ordering, which this instrument makes decidable),
ADR-011 (supersession over deletion)

## Note on authoring

**This record was written after its implementation shipped.** Four modules
(`scripts/audit_field_prompts.py`, `scripts/compare_eval_reports.py`,
`src/horus/finetune/evaluate.py`, `tests/test_finetune_dataset.py`) plus
`eval/finetune-attribution-audit.md` cite "ADR-059" in 12 places, and the number had been
reserved in `docs/decisions/INDEX.md` with an explicit *"record not yet authored — authoring
it is outstanding debt"* row so no later session would claim it for unrelated work. The
reservation worked; the authoring was the gap. This record closes it and describes what
actually shipped, verified against the code rather than reconstructed from memory.

## Context (current-state survey)

The **oracle arm** feeds the structurer a transcript rendered from ground truth — the text a
*perfect* reader would have produced. Its purpose (ADR-054) is to split the observed error
into a reading share and a structuring share: if the structurer scores 0.96 on perfect text
and 0.68 on real reader text, the gap is reading, not comprehension.

That makes the oracle transcript a **measuring instrument**, and it had three defects.

### 1. The instrument printed labels that no invoice prints

`render_oracle_transcript` emitted one `<label>: <value>` line per present field, where the
label came from `FieldSpec.german_label` — the canonical EN16931 term. But EN16931 terms are
*schema* vocabulary, not page vocabulary. Where the two diverge, the oracle page asserted a
wording the corpus never uses.

The consequence is not "an optimistic ceiling". It is **a ceiling that is wrong in an
unpredictable direction**:

| Field | Oracle (perfect text) | Real reader text |
|---|---:|---:|
| `charge_total_amount` (BT-108) | **0.000** | 0.889 |

A field scoring *worse* on perfect input than on degraded input is a contradiction in terms.
The cause was the rendered label: the model could not map an invented wording to the key, so
it emitted `null` on the very input that was supposed to be maximally answerable. Any
attribution computed from that arm was unsound for those fields.

### 2. Group cells lost their label/value boundary

Repeating-group rows rendered as `"<label> <value>"` — space-separated, no colon. That reads
correctly only while every label is long and unambiguous. Once labels shortened, the
boundary became unrecoverable: a row like `Menge 2 Stück` gives the parser no way to know
where the label ends and the value begins.

Measured cost: **103 cells lost on PERFECT input**, concentrated in two cells that went from
perfect to zero. Two further latent breakages in the same renderer:

- A group row could span multiple lines if a cell value contained a newline (some CII
  descriptions do), silently corrupting every downstream row boundary.
- Line-item ordinals came from `enumerate(rows, start=1)` rather than the row's own GT
  position, so a page could assert a line number the ground truth does not have.

### 3. A pooled headline could move with no visible cause

`mean_overall_micro_f1` pools flat fields **and** group cells. `compare_eval_reports.py`
diffed only the flat surface. So a change confined to group cells moved the headline while
every per-field row in the report looked identical — the same defect class as the per-field
reporting bug written up in `eval/per-field-reporting-audit.md`: *a number was computed,
then discarded before it reached the report.*

## Options considered

- **Ground the oracle labels against the corpus (chosen).** Measure what pages actually
  print; render that.
- **Drop the oracle arm.** Rejected: it is the only instrument that separates reading from
  comprehension, and ADR-054's whole endgame rests on that split.
- **Keep `german_label` for rendering and accept the bias as a documented limitation.**
  Rejected: the `charge_total_amount` inversion shows the bias is not a bounded offset, so it
  cannot be reasoned around in prose.
- **Hand the group-rendering defect to the LoRA as "structurer weakness".** Rejected on
  ADR-064 grounds — it is an instrument defect, not a capability gap.
- **Gate only the flat registry, not group cells.** Rejected: group cells carry the most
  gradable cells and were never audited at all, which is exactly where 10 further ungrounded
  labels were hiding.

## Decision + integration thoughts

**(a) The rendered label becomes a corpus-grounded assertion, gated.**

`FieldSpec` gains `printed_label: str | None`, and a `rendered_label` property returning
`printed_label or german_label`. `printed_label` carries the corpus-measured page wording
(e.g. BT-106 → `Positionssumme`, BT-109 → `Rechnungssumme ohne USt.`, BT-119 → `Steuersatz`,
BT-31 → `USt.-Id.-Nr`).

`make audit-prompts` check B **gates** on rendered-label grounding, for the flat registry
*and* every repeating-group cell. `german_label` itself is deliberately **not** required to
be grounded: it is the canonical EN16931 term, it is not prompt text, and `adapters.py`
compiles the frozen regex baseline from it (ADR-037).

Fields with genuinely no printed label live in `_NO_PRINTED_LABEL_REASONS` with a written
reason each — currently **6**, four flat and two group cells:

| exception | reason |
|---|---|
| `seller_address` | composite block printed **unlabelled** in the letterhead; `Anschrift` occurs 27/146 but only inside `Rechnungs-`/`Lieferanschrift`, a different thing |
| `buyer_address` | same, in the customer block |
| `document_type` | pages print the type *word* as a heading (`Rechnung` 121/146), never a `Belegart:` label in front of it (ADR-046) |
| `rounding_amount` | no corpus-attested label |
| `vat_breakdown.category_code` | `Steuerkategorie` 0/146. Borrowing `Umsatzsteuer` (97/146) would be **wrong** — it labels the VAT *section*, not the EN16931 category *letter*. Measured: rendering `Umsatzsteuer: S` costs **11 oracle FNs (1.000 → 0.831)** vs 0 for `Steuerkategorie: S`. The letter is never printed either, which is why ADR-048's `predicted_normalize` exists for this cell. |
| `skonto.basis_amount` | every Skonto-basis spelling 0/146; the generic `Basisbetrag` (90/146) is the VAT table's taxable-base column, so borrowing it would render a **wrong** label |

The `category_code` entry is the sharpest illustration of the whole record: borrowing a
plausible-but-wrong nearby label was *measured* to cost accuracy, so "no label" is a
deliberate, evidenced choice rather than an omission.

**The exception list is bidirectionally gated**: a field *not* on the list whose rendered
label is ungrounded fails, **and** a field *on* the list whose label turns out to be grounded
also fails. So the list cannot silently go stale as the corpus grows.

**(b) Group cells render as `<label>: <value>`, one line per row.**

Colon-delimited, so the boundary is explicit and short labels are safe. The row is forced
onto exactly one line whatever the value contains. Line-item ordinals read the GT position
(`_ROW_ORDINAL_CELL = {"line_items": "line_id"}`) rather than a loop counter, so the page
cannot assert a line number the ground truth does not carry.

**(c) Reporting covers the group surfaces.**

`compare_eval_reports.py` diffs `per_group_f1` / `per_group_outcomes` alongside
`per_field_f1` / `per_field_outcomes`; `finetune/evaluate.py` reports per-cell outcomes. A
pooled-headline move now always has a visible cause in the report that produced it.

**Tests are hermetic, deliberately.** Six guards in `tests/test_finetune_dataset.py`
(value-shaped `printed_label` rejection, corpus-wording rendering, label/value separation,
one-line-per-row under a multiline cell value, GT-position ordinals). The ZUGFeRD corpus is
gitignored, so a corpus-gated test would never run in CI — and CI is precisely where these
invariants broke unnoticed. `make audit-prompts` remains the exhaustive corpus-backed gate;
the hermetic tests are the always-runs floor.

## Measured effect

- `charge_total_amount` (BT-108) oracle 0.000 → 1.000; `allowance_total_amount` (BT-107)
  oracle 0.000 → 0.909. Both with **no model change** — the instrument was wrong, not the
  structurer. (Recorded in ADR-058 §"Measured effect"; the two records shipped together and
  their effects are entangled by construction: ADR-058 fixed what the *prompt* names,
  ADR-059 fixed what the *oracle page* prints. Both were required for those fields to become
  measurable at all.)
- 103 previously-lost group cells on perfect input recovered. Directly measurable: the
  deliberately-kept `oracle-adr059-nocolon` arm isolates fix (b) alone —
  **pooled `overall_micro_f1` 0.9719 → 0.9218** while flat `micro_f1` barely moves
  (0.9743 → 0.9735). A −0.050 headline swing that the entire flat surface is blind to is
  precisely the reporting blindness fix (c) removes.
- 10 ungrounded labels found on repeating-group cells — a surface that had never been
  audited.

**Two ceilings came down, and that is the point.** Grounding the labels made the oracle arm
*less* flattering for two fields, on perfect text only:

| field | perfect text | why |
|---|---|---|
| `line_total_amount` (BT-106) | 0.906 → **0.863** | page wording `Positionssumme` replaced schema term `Summe Nettobeträge` |
| `delivery_date` (BT-72) | 1.000 → **0.974** | page wording `Leistungsdatum` replaced `Liefer-/Leistungsdatum` |

The model scored marginally better against EN16931 jargon than against the wording real
invoices actually print. So the pre-fix ceiling was **optimistic** for these two fields and
the new figure is the truthful one. Reporting only the gains would reproduce the exact defect
this record exists to fix — a measuring instrument flattering the thing it measures. Reader-text
scores for both fields held or improved, so nothing about the system got worse.

## Source archival

No external sources. Internal: `src/horus/finetune/dataset.py`
(`render_oracle_transcript`, `_ROW_ORDINAL_CELL`), `src/horus/eval/ground_truth.py`
(`FieldSpec.printed_label` / `rendered_label`), `scripts/audit_field_prompts.py`
(`_NO_PRINTED_LABEL_REASONS`, `check_rendered_label`), `scripts/compare_eval_reports.py`,
`src/horus/finetune/evaluate.py`, `tests/test_finetune_dataset.py`,
`eval/per-field-reporting-audit.md`, `eval/finetune-attribution-audit.md`.
Reproduce with `make audit-prompts` and `make test`.

## Supersession trigger

Superseded or amended if **any** of:

1. The corpus changes (new invoices, or a new reader lineage per ADR-057) — every
   `printed_label` is a measurement against 146 transcripts and must be re-measured, and the
   `_NO_PRINTED_LABEL_REASONS` list re-verified in both directions.
2. The oracle arm stops being the attribution instrument (e.g. a real high-fidelity reader
   makes a rendered page unnecessary) — the grounding gate then protects nothing.
3. Repeating groups gain a rendering format other than one-line-per-row (e.g. a table
   serialization), which would invalidate the one-line invariant and its tests.
4. The corpus stops being gitignored, at which point the hermetic-vs-corpus-gated test split
   can be revisited.
