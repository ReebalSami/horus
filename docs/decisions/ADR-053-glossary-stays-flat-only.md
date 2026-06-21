# ADR-053: Structurer field glossary stays flat-only — repeating-group cell extension measured net-negative and rejected

**Status**: Accepted
**Date**: 2026-06-21
**Refs**: ADR-049 (the flat field glossary this declines to extend), ADR-042 (the repeating-group scoring whose cells were the candidate), ADR-048 (precedent: an ADR documenting a measured rejection), ADR-038 (the Arm-B structurer this measures)

## Context (current-state survey)

ADR-049 added a registry-driven field glossary to the structuring prompt: each confusable **flat** `FieldSpec` carries a `description` + `prompt_aliases`, and `structurer.render_field_glossary()` renders one guide line per such field. The renderer is deliberately open/closed — adding a `description` to *any* `FieldSpec` auto-extends the guide — which invites the obvious next step: gloss the confusable **line-item** cells too.

The motivation was concrete. After ADR-049 + the ruler fixes (ADR-050/051/052), all six dev-cohort invoices reach **flat** `micro_f1` ≥ 0.905 (the headline metric the harness reports per invoice and the dashboard shows). But the Innergem invoice's **overall** micro_f1 (flat + repeating groups, ADR-042) sits at 0.861 — below 0.90 — driven by line-item misses: the model merges the article number into the product `name`, drops `seller_assigned_id`, and (a genuine reader slip) reads the IBAN `DE12…` as `DF12…`. The three confusable line-item cells — `name` vs `seller_assigned_id` vs `net_price` — look exactly like the flat fields ADR-049 fixed, so extending the glossary to them is the natural hypothesis.

## Decision

**The glossary anchors flat scalar fields only. Repeating-group (line-item) cells are deliberately NOT glossed.** The hypothesis was implemented and measured on the 6-invoice dev cohort, and **rejected on the evidence**: it is net-negative.

Because the Arm-B structurer decodes greedily (mlx-vlm `generate` with no temperature → deterministic argmax), a with/without comparison is a clean A/B — any metric change is causal, not sampling noise. Adding `description` + `prompt_aliases` to the three line-item cells (`name`/`seller_assigned_id`/`net_price`) and rendering them as `group[].cell` guide lines produced:

| Invoice | flat micro_f1 (both) | overall — flat-only glossary | overall — + group cells | Δ overall |
|---|---|---|---|---|
| EN16931_Einfach | 0.9474 | 0.9524 | 0.9524 | 0 |
| EN16931_Gutschrift | 0.9444 | 0.9750 | 0.9750 | 0 |
| EN16931_Innergemeinschaftliche | 0.9048 | 0.8611 | 0.8767 | **+0.0156** |
| EN16931_Miete | 0.9231 | 0.9748 | 0.9748 | 0 |
| EN16931_Rabatte | 0.9545 | 0.9204 | 0.9009 | **−0.0195** |
| XRECHNUNG_Einfach | 0.9787 | 0.9895 | 0.9677 | **−0.0218** |

Three findings, all decisive:

1. **Flat `micro_f1` is unmoved on all six.** Line-item cells are not in the flat headline (ADR-042 scores groups separately), so the group glossary cannot help the user-facing per-invoice metric by construction.
2. **It fails its own goal.** Innergem overall gains only +0.0156 (0.861 → 0.877) and stays **below 0.90**. The residual misses are a name/article-number *merge* and a reader IBAN slip — neither is fixable by a generic semantic anchor without invoice-specific instructions (which would breach the no-leakage guardrail).
3. **It regresses two other invoices.** Rabatte (−0.0195) and XRECHNUNG (−0.0218) overall *drop* — net −0.026 across the cohort. This is greedy-decode prompt-brittleness: a longer prompt shifts the deterministic token trajectory on invoices that were near a decision boundary. The same brittleness was observed in the same session when an ad-hoc `net_price` "not the line total" refinement flipped a Gutschrift flat field (0.944 → 0.919) — also reverted.

The shipped code therefore keeps `render_field_glossary` flat-only; `ground_truth.py` carries **no** `description`/`prompt_aliases` on any repeating-group cell; `structurer.render_field_glossary` iterates `FIELDS` only, with a docstring note recording this rejection.

## Alternatives considered

- **Ship the group glossary anyway** ("it helps Innergem"). Rejected: it helps Innergem overall by less than it hurts Rabatte + XRECHNUNG, leaves Innergem < 0.90 regardless, and does nothing for the flat headline. Net-negative is net-negative.
- **Keep the group-rendering machinery but populate no cells** (inert open/closed generalization). Rejected: unused machinery violates "no shortcuts / no dead code"; the rejection is better recorded in an ADR + a one-line docstring than in a latent code path a future reader must reverse-engineer.
- **Pursue the Innergem line-item misses with targeted guidance.** Rejected: the misses are a model/reader ceiling (name/number merge; OCR `DE`→`DF`), fixable only with invoice-specific nudging — out of bounds for a generic, no-leakage glossary.

## Consequences (integration)

- **The glossary's scope is now explicit and bounded.** Flat confusable scalars only (ADR-049). A future Cascade tempted by the open/closed renderer will find this ADR + the `render_field_glossary` docstring and not re-run the same experiment blind.
- **The acceptance bar is met without it.** All six dev invoices are ≥ 0.905 on the flat headline via ADR-049 + ADR-050/051/052; the dropped extension was never load-bearing for that result.
- **Honesty guardrail intact.** No model output is masked; no ground-truth value enters the prompt.
- **Tests.** `tests/test_structurer.py::test_render_field_glossary_is_registry_sourced` pins the renderer to the flat described fields (rendered keys == described `FIELDS`); the no-GT-leakage guard is unchanged. Full gate green: 927 passed, ruff clean, mypy clean.

## Source archival

Measurement command: `make arm-b CFG=configs/pilot-13.yaml,configs/arm-b.yaml` (deterministic, greedy) + `scripts/inspect_arms.py --arm b` for the per-invoice flat/overall split, run with and without the three group-cell descriptions on 2026-06-21. The greedy-decode determinism is a property of the mlx-vlm `generate` default (no temperature), verified in `src/horus/vlm_extractor.py::MLXVLMExtractor.extract_text`.

## Supersession trigger

If a future structurer is materially less prompt-brittle (e.g. a larger model, or sampling with self-consistency) **and** a re-measured A/B shows the group glossary nets positive on overall `micro_f1` without regressing other invoices, populate the group cells under a new ADR (the renderer change is a trivial re-extension). If the held-out Belege set's line-item errors prove to be comprehension (not reader-ceiling) errors that a generic anchor could fix, revisit. Until such evidence exists, the glossary stays flat-only.
