# Handoff — full-coverage extraction: the fields aren't populating (investigate + brainstorm)

## Why you're reading this

A previous Cascade session extended HORUS's scored schema from 19 to 34 flat fields plus
three repeating groups (ADR-041 / ADR-042) and declared it **"live-validated / working."**
The user looked at the dashboard and found that claim is false — the extracted fields are
not filled. **Treat the previous session's success claims as unreliable.** Verify
everything yourself, from scratch, with fresh eyes.

## The symptom (observed fact, not a theory)

- In the dashboard (Invoice Explorer → Method A), the extracted fields come up empty.
- `EN16931_Einfach` — a clean, simple invoice that plainly carries a document type and a
  payment due date — shows those as not filled.
- Looking at the raw model transcript for that same invoice, even **core** fields that
  scored fine under the old 19-field setup — `invoice_number`, `seller_name` — come back
  `null`. So this is a regression in *basic* extraction, not only the new fields.
- The headline number the previous session reported (flat micro-F1 ≈ 0.58) was presented
  as a win. ~40% of fields wrong or empty is not a win.

## Your task

Find out why the fields aren't populating, and brainstorm what's actually going on. Form
your own hypotheses and chase them. **Nothing below is a checklist or an instruction** —
it's only a map of where the relevant things live so you don't waste time locating them.

## The territory (where it lives — deliberately not a diagnosis)

- Branch `feat/schema-step1` — 8 commits, **not pushed**, stacked on `feat/heldout-belege-gt`.
  `git log --oneline -n 8` shows the range `ec4a861 … cbdcad1`.
- The work spans schema → CII parse → prediction coercion → scoring → hand-draft capture →
  structurer prompt → eval wiring → app. All in those 8 commits.
- The smoke that was run: `make pilot-13 CFG=configs/pilot-13.yaml,configs/arm-a.yaml INVOICES=EN16931_Einfach,EN16931_Rabatte,EN16931_Gutschrift`
  → MLflow experiment `arm-a-dev`, parent run `b76a1657`.
- Raw model outputs (what the model actually emitted, per page): `docs/sources/transcripts-arm-a-dev/`.
- Dashboard: `make app` → Invoice Explorer.
- Decisions + retro written by the previous session: ADR-041, ADR-042,
  `docs/retros/full-coverage-schema.md` — **read them critically**, they reflect the claim
  that turned out wrong.

## What I'm deliberately NOT telling you

The previous session has hunches about the cause. The user explicitly asked that the next
Cascade investigate and brainstorm **without being steered**, so those hunches are being
withheld on purpose. Don't go looking for them — look at the evidence yourself.

## State worth knowing

- 835 unit tests pass, ruff + lint + mypy all clean — which is precisely the trap: green
  tests, broken behavior. The gap between "the suite is green" and "the fields populate" is
  the thing to understand.
- Nothing is pushed and no PR is open; the user sequences any merge.
- The user's own in-flight changes (a `.devin` rename, held-out-branch tweaks) are
  untouched by this work.
