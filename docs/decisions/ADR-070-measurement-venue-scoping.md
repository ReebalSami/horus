# ADR-070: Measurement-venue claims are scoped per stage; the hardware claim is two-tier; the floor's reading configuration is declared unmeasured

**Status**: Accepted
**Date**: 2026-08-16
**Refs**: ADR-054 (endgame: reader-first recovery + rented-GPU session), ADR-057 (reader selection), ADR-063 (held-out grading scope), ADR-068 (fine-tune venue — the first venue-scoping decision), `scripts/gpu/README.md` (the runbook this ADR reads as evidence), `docs/reviews/2026-08-16-second-supervisor-review.md` Addendum 3 (the partial fix this supersedes)

## Context (current-state survey)

### What the third review pass found

The 2026-08-16 second review found, on the author's own challenge, that the abstract's "hosted entirely on a 16 GB Apple-silicon laptop" was false, and corrected four passages (ch.5 hardware, ch.9 local-viability, ch.10 hardware envelope, abstract). A third pass on the same day found the correction incomplete in two distinct ways.

**First, six sites still carried the absolutism**, and they were the ones attached to the headline number:

| Site | Claim |
|---|---|
| `thesis/chapters/07-results.tex:367` | "39 real invoices, zero-shot, fully local" |
| `thesis/chapters/09-discussion.tex:12` | "zero-shot and entirely local" |
| `thesis/chapters/09-discussion.tex:58` | "obtained on a single laptop … using 4-bit quantised weights" |
| `thesis/chapters/11-conclusion.tex:8` | "running entirely on hardware a German tax firm already owns" |
| `thesis/tables/heldout-headline.tex:10` (generated) | caption "zero-shot and fully local" |
| `thesis/figures/architecture.tex:31` | "Runs entirely on local hardware" |

The discussion site is the worst of them: it was **factually false about both tables it cited**, since `tab:sealed-val-arms` explicitly labels two of its four rows `bf16 / CUDA`.

**Second, and not previously identified, the venue split is broader than the held-out corpus.** `scripts/gpu/README.md` states its own scope in its opening paragraph: the rented session ran the bake-off at full precision, **"regenerates the 146 structurer-training transcripts with the winning reader"**, and brought the artifacts home, while **"training and final eval stay on the M1"**. Combined with ADR-054 step 2 and ADR-057's unchanged transcript lineage, that means:

> **Every transcript behind every figure reported in the thesis was produced on a rented single-GPU instance (one NVIDIA A10G, 24 GB) at full precision and native page resolution. What ran on the laptop is the structuring stage and all scoring.**

Consequently the arm label `4-bit / Apple silicon` describes the **structurer**, not the reader — a reading a careful examiner would make and the manuscript did not state. Chapter 5's disclosure enumerated *three* classes of rented pass and did not name the synthetic-corpus regeneration, so the disclosure was itself incomplete.

### Why this is not a cosmetic wording problem

The local reader is capped at `max_pixels = 2_150_000` (≈ A4 at 150 DPI) on MPS, because the selected reader's native-resolution vision tower demanded a 35.10 GiB Metal buffer on a 300 DPI A4 page (`COHORT_MANIFEST` note; `src/horus/vlm_extractor.py`). The cap is a memory workaround, not a quality choice, and `scripts/transcribe_heldout.py` says in its own docstring that a local run is therefore "wiring verification only".

So the unmeasured quantity is *reading quality at half resolution* — and the thesis's headline empirical finding is that **capture quality is the dominant real-world cost**, worth more than eleven points of mean per-invoice F1 between email-native and phone-scanned documents. Page resolution is a capture-quality variable. The one configuration never measured sits on the axis the thesis argues matters most. That is a substantive gap, not a footnote.

## Options considered

1. **Leave the wording; treat "local" as meaning "open-weights, no network call".** Rejected: defensible as a private definition, indefensible in a thesis whose deployment premise is the reason it exists. A reader who reaches ch.5 and then ch.7 finds a contradiction, and the contradiction is on the central claim.
2. **Measure the local configuration before submitting, and report it.** Attractive and still recommended — but the experiment track was frozen by ADR-054 §5 in favour of the writeup, and an unplanned run reported without the pre-registration discipline every other measurement carries would itself be a methodology regression. Deferred rather than rejected.
3. **Delete the deployment claim entirely and present the work as a cloud-GPU study.** Rejected: false in the other direction. The delivered pipeline genuinely is open-weights, genuinely makes no network call, and both models genuinely fit in 16 GB. Those are the claims; only reading *quality* inside the envelope is unmeasured.
4. **Scope every venue claim per stage, complete the disclosure, and declare the gap with a bounded closing measurement.** **Chosen** — and then **amended the same day** (see the Amendment section) after the author correctly objected that the first application of this option stripped the local claim instead of scoping it.
5. **(Amendment) Re-anchor the deployment claim to a two-tier on-premises envelope and present the rented venue as the hardware-equivalence evidence it is.** **Chosen as the final form.** The rented instance was not a cloud *model* and not exotic hardware: one A10G 24 GB is the memory class of a single consumer graphics card, the models are open-weights under the author's control, the instance was single-tenant in an EU region and destroyed after use, and the data it handled was the synthetic corpus plus the author's own collected invoices — no client document. Renting the target class for measurement removed the author's-laptop confound from the science; it is a strength to disclose, not a taint to confess.

## Decision (+ integration thoughts)

**A manuscript invariant.** Any sentence about where a number came from distinguishes three separable properties, and never lets one stand in for another:

- **Model provenance** — open-weights vs proprietary API. True of everything reported.
- **Network posture** — whether an inference path makes a network call. No path does.
- **Execution venue and resolution** — which machine, which precision, which pixel budget. Varies by *stage*, and must be stated per stage.

**The two-tier envelope (amendment; final form).** The hardware claim is made at two tiers, both on-premises-class, and every venue sentence in the manuscript names the tier it speaks about:

- **Target class** — a workstation with one modern 24 GB graphics processor. *Measured there*: every reading pass (bake-off, 146-transcript regeneration, all 39 held-out invoices — 58 pages in ~16 min including the 9 GB checkpoint fetch, zero errors), adapter training, and the precision-matched bf16 evaluations. Under 6 GPU-hours total.
- **Floor** — the author's 16 GB M1 Pro laptop. *Measured there*: the structuring stage in its deployed 4-bit precision (sealed val + held-out), all scoring and re-scoring. The reader loads and runs but is capped to ≈150 DPI by an MPS-specific memory workaround (`max_pixels` is MPS-only per the runbook §4) — the cap is a property of this laptop, not of local deployment.
- **The residual gap** — the floor's *reading quality* is unmeasured on either corpus. Carried as the `§ lim-hardware` limitation and closed by the `§ fw-envelope` measurement (#129).

**Concretely applied:**

1. **`§ method-repro` defines both tiers**, enumerates the four target-class pass classes (adapter training; precision-matched adaptation evaluations; reader comparison; every reported transcript), names the instance (A10G 24 GB, EU region, single-tenant, destroyed at termination, author-controlled open weights, author-owned data only), and states the consequence unbolded: the reading figures are target-class figures and `4-bit / Apple silicon` labels the structurer.
2. **The headline result carries its venue before the number is read** — a `Venue.` paragraph in `§ results-heldout` and a matching clause in the generated table's protocol note (`scripts/thesis_assets.py`), both stating the tier per stage and the 58-pages/~16-min throughput fact.
3. **`§ lim-hardware` reframes the limitation as evidence distribution across tiers, not as a hole in "local"**: a target-class firm can run, adapt and reproduce everything on premises; a floor-only firm can run but not adapt; the floor's reading figure is missing, plausibly sits below the reported one via the same mechanism as the measured channel penalty, and the thesis refuses to call the gap small.
4. **`§ fw-envelope` ("Measure the Floor of the Envelope") specifies the closing measurement**: read the 39 held-out invoices on the laptop under the pixel cap, then structure and score with the unchanged pipeline. Two protocol requirements are pre-committed — archive the local transcripts like any other generation, and pre-register the two-cell comparison before the run — so a disappointing floor figure cannot be reframed afterwards.
5. **The conclusion's non-claims section names the two-tier boundary** alongside the unbuilt layers and the corpus size — including the positive half (nothing needed more than a single 24 GB card).
6. **The architecture figure** states open-weights, no network call, single-24-GB-card sufficiency, and the floor-capable structurer.
7. **`§ disc-local` corrects the adaptation story**: training fits the target class (both adapters trained, evaluated and re-baselined within one 24 GB card), so a target-class firm adapts on premises; only the floor-only firm faces the rent-or-forgo trade.

Integration: no scoring code, no evaluation code and no model was touched, so **no committed number moves**. The only executable change is the caption and protocol-note text in `scripts/thesis_assets.py`; `make thesis-assets` regenerates all tables from unchanged data.

## Source archival

Per `horus-source-archival`, the evidence for this ADR is in-repo rather than external: `scripts/gpu/README.md` §"Purpose" + §4 + §5B, `scripts/transcribe_heldout.py` module docstring, `src/horus/vlm_extractor.py` `max_pixels` documentation and the `COHORT_MANIFEST` note for the selected reader, `eval/structurer-lora-2x2-results.md`, and `thesis/tables/sealed-val-arms.tex` arm labels.

## Supersession trigger

- **When the `§ fw-envelope` measurement is taken**, this ADR's limitation clause is superseded by a record reporting the measured deployment penalty, and `§ lim-hardware` shrinks to a pointer at that result. Tracked as a GitHub issue filed with this ADR.
- If a future reader is selected whose native resolution fits the 16 GB envelope, the pixel cap disappears and the whole gap closes structurally — supersede with the new reader-selection record.
- If the deployment envelope claim is ever widened (e.g. to an on-premises workstation with a discrete accelerator, which `§ lim-hardware` already notes the privacy premise would permit), re-derive: the cap is a property of the machine, not of the method.

## Consequence recorded for the learning pipe

The venue split was documented in the repository the whole time — in a runbook, in a script docstring, in eval reports, and even in a table's own arm labels — yet prose absolutism survived **three** review passes, because each pass traced *numbers* rather than *venue metadata*. Two passes then fixed it partially, because each fixed the sites it happened to read. The generalisable lesson: when a claim class is found defective, grep for the claim class across the whole manuscript **and the generators** before declaring it fixed. Captured to the meta-repo review queue.
