# ADR-056: Answerability-ruler honesty fix + blank-page reader guard

**Status**: Accepted
**Date**: 2026-08-02
**Refs**: ADR-054 (endgame this executes), #114 (GPU bake-off), #55 (fine-tune epic), ADR-043/045/046/047/048/050/051/052 (the scoring-fairness precedent family this extends to the answerability probe), `eval/finetune-attribution-audit.md` (the audit whose reader-share this partially re-weights)

## Context (current-state survey)

The #114 GPU bake-off ran all four reader candidates at bf16 on the 29 sealed val
invoices (A10G, `--force-transformers`). The raw answerability table looked wrong in a
specific way: the best candidates plateaued at 0.77 while the corpus is born-digital
(pixel-perfect renders) — modern doc-VLMs should read nearly everything printed. A
per-invoice, per-field investigation (user-directed) found the plateau was the
**ruler's**, not the readers':

- **Text-layer probe (decisive instrument)**: scoring the PDFs' own embedded text
  layer — perfect reading by construction — under the same ruler yielded **0.794**.
  The winner (0.777) was therefore reading ≈ 98 % of what the ruler could ever find.
- **Phantom-miss classes** (verified case-by-case in the saved transcripts):
  1. **Composite addresses** (57 of the winner's 128 misses; 28/29 invoices): GT is a
     comma-joined string (`'Lieferantenstraße 20, 80333, München, DE'`) but the page
     prints a reordered multi-line block (`Lieferantenstraße 20 / DE 80333 München`) —
     full-string containment can never match, for ANY reader, including perfect text.
  2. **`document_type`** (21/29): GT stores the token `invoice`/UNTDID code `380`; the
     page prints the German word ("Rechnung", "Handelsrechnung") — same
     as-printed-vs-as-stored class as ADR-046.
  3. **`invoice_currency_code`** (7): GT `EUR`; the page prints only `€` (fail3: 8 ×
     `€`, zero literal "EUR").
  4. **IBAN spacing** (4): GT raw is 6-group spaced (`DE88 2008 0000 0970 3757 00`);
     the page prints it compact — the variant set derived groupings only from
     already-compact values.
  5. **Slash dates** (3): French corpus invoices print `16/11/2017`; only German dot
     + ISO shapes were tried.
- **Blank-page hallucination** (found the same session): Qwen3-VL-4B invented a
  complete fictional US invoice ("CloudServices Inc.", $540) on the visually blank
  page 3 of `zugferd_2p1_EN16931_Sachversicherung…`; the downstream structurer then
  preferred the fake "complete" invoice over the real one — overall_micro_f1
  **0.885 → 0.047** on that invoice. olmOCR answered "There is no text present in the
  image." on the same page; robustness must not depend on reader temperament.
- Residual class: values present in the CII XML but **never rendered on the page**
  (e.g. the `ZUGFeRD_2_fully_compliant_complete` test fixture's totals; tax IDs).
  No reader can extract those from an image; they remain honest misses of the
  fixed ruler (fixed-ruler perfect-text ceiling: **0.941**).

## Options considered

1. **Leave the ruler as-is** (comparative-use disclaimer already in the module
   docstring) — rejected: the bake-off's decision rule keys on the mean; with ~0.16
   of artifact mass the rule ranked readers on noise (it also inverted the top-2
   order, see ADR-057) and understated every candidate to the user.
2. **Switch the bake-off metric to endpoint F1 only** — rejected as the sole fix:
   F1 needs a structurer pass (~45 s/invoice on the M1) vs milliseconds for
   answerability; the probe stays the cheap comparative instrument, it just has to
   be honest. F1 is added as the tie-breaker instrument in ADR-057 instead.
3. **Representation-only variant expansion + component-wise composites + blank-page
   guard** — **chosen**, detailed below.
4. **LLM-as-judge findability** — rejected: nondeterministic, adds a model
   dependency to a pure-text probe, and violates the deterministic-ruler precedent
   (ADR-048's "isolated, deterministic ruler fix" rationale).

## Decision (+ integration thoughts)

1. `horus.finetune.answerability` (`value_variants` + new `_composite_findable`):
   - ISO dates additionally emit `dd/mm/yyyy`;
   - spaced-IBAN GT values emit compact + re-grouped variants;
   - `field_key`-aware variants (new optional arg, backward-compatible):
     `document_type` tokens map to printed German/French/English surface words;
     `invoice_currency_code` maps to the printed symbol (`EUR` → `€`);
   - `seller_address`/`buyer_address` switch to **component-wise containment**
     (every comma component ≥ 3 chars must be findable; 2-char country codes are
     skipped as substring noise). Findable = ANY of raw/normalized component sets.
   - All changes are **representation-only**: they recognize true renderings of the
     GT value; a wrong value still counts as missing (ADR-048 principle).
2. `horus.eval.harness._extract_and_concat` gains `skip_blank_pages: bool = False`;
   `_is_blank_page` detects blank pages by image statistics (dark-pixel fraction
   < 0.005 on a 256-px grayscale thumbnail; calibrated: the one blank val page
   measures 0.000, the darkest-blank content page 0.021). The **reader pass**
   (`run_reader_pass`) passes `True` — blank pages contribute their separator + an
   empty string with **no VLM call**. The pilot-13 cohort-harness path keeps the
   default `False` (byte-identical lineage). Image-statistic (not text-layer)
   detection works identically for scanned Belege — the privacy-first vision
   premise is untouched.
3. **All four bake-off tables re-scored offline** from the saved transcripts (the
   ADR-020 rescore-from-saved-evidence precedent; no re-inference):

   | candidate | old ruler | fixed ruler | subdir clause |
   |---|---|---|---|
   | olmOCR-2-7B-1025 | 0.774 | **0.913** | all ≥ baseline |
   | Qwen3-VL-4B-Instruct | 0.777 | **0.906** | all ≥ baseline |
   | MinerU2.5-Pro-2604 | 0.741 | 0.878 | all ≥ baseline |
   | granite-docling-258M (canonical) | 0.658 | 0.792 | — |
   | MinerU2.5-Pro-2605 | 0.630 | 0.735 | ZUGFeRDv1 collapse (−0.176) |

   Perfect-text ceiling under the fixed ruler: **0.941** (residual = not-rendered
   values). The top-2 order INVERTED vs the broken ruler — the reader selection is
   therefore decided with an added endpoint-F1 instrument in ADR-057.
4. Consequence for the attribution audit: its string-findability instrument (51 %
   "reader-attributed") carried the same artifacts and **overstated** the reader
   share; the audit's decisive oracle instrument (0.9608 structurer ceiling) is
   unaffected. The audit record stands; its findability percentage is to be read
   with this ADR's correction note.

## Source archival

Per `horus-source-archival`: no new external sources — all evidence is in-repo:
`data/finetune/bakeoff/**` (4 × 29 saved transcripts, synced from the GPU box),
`data/finetune/bakeoff-local-m1/**` (preserved local M1 4-bit wave),
`data/finetune/eval-zeroshot-qwen-val.json` (endpoint F1, ADR-057),
tests `tests/test_finetune_answerability.py` + `tests/test_harness.py`
(`test_extract_and_concat_skips_blank_pages`).

## Supersession trigger

- If a future field's printed surface form falls outside the variant classes here
  (new locale, new field family), extend `value_variants` with a sibling amendment —
  or supersede if the containment paradigm itself stops fitting (e.g. layout-aware
  findability).
- If the blank-page threshold misfires on a future corpus (very light scans),
  recalibrate `_BLANK_PAGE_DARK_FRACTION` with the same histogram method and note
  it here.
