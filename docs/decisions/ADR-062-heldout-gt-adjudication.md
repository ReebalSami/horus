# ADR-062: Held-out GT adjudication model and provenance schema

**Status**: Proposed

**Context**

Three channels have now read all 39 held-out Belege: the superseded text-layer draft, the
ADR-060 cloud vision judge, and the ADR-061 Azure `prebuilt-invoice` channel. Between them
they assert values in 711 of the 1,326 flat cells (34 registered fields × 39 documents).

Reviewing 711 cells by hand is not a plan. Reviewing none of them is what produced the
retracted 0.5692. Something has to decide which cells carry a warrant strong enough to stand
without the author looking, and rank the rest so attention goes to the dangerous ones first.

Two constraints make this harder than a majority vote:

1. **The printed-evidence gate proves presence, never assignment.** A seller VAT id and a
   buyer VAT id are both printed, so filing one as the other passes the gate. Deterministic
   proof therefore cannot be the top warrant on its own.
2. **Tier B has no text layer at all.** 221 asserted cells across 12 documents can never
   receive deterministic proof, no matter how the gate is tuned (ADR-061).

**Decision**

Adjudicate every cell into one of **five provenance classes**, and rank every unresolved cell
on **how much damage an unnoticed error would do**.

### Provenance classes

| Class | Warrant | Auto-accepted |
|---|---|---|
| `text-layer-proven` | The value is in the document's own embedded characters **and** ≥2 channels assign it to this field | yes |
| `two-channel-agreed` | ≥2 independent channels produced the same value, with no deterministic backing (the Tier B case) | yes |
| `author-adjudicated` | Nothing settles it; the author decides | no |
| `exempt-by-policy` | Controlled vocabulary the page never prints as stored (`document_type`, BT-81, BT-118) asserted by one channel | no |
| `null-claim` | Every channel that *could* express the field reported absence | yes |

`two-channel-agreed` is accepted deliberately. Excluding it would escalate every Tier B cell
and make the second channel pointless. It stays a visibly weaker class in every report rather
than being absorbed into one headline number, because two cloud systems can fail together.

### The gate runs per reading, and settles what it can

The gate is applied **once per asserted channel value**, not once per cell against one
channel's GT. This is what makes a disagreement answerable: the question that resolves it is
*which of the competing values is printed*.

That verdict is then used. When exactly one competing value is printed and ≥2 channels assign
it to the field, the losing readings are refuted by the document itself and the cell is
accepted as `text-layer-proven` — the same warrant a unanimous cell carries, plus a refuted
competitor. Where two competing values are *both* printed (an invoice prints the seller's
address and the buyer's), the gate discriminates nothing and the cell escalates regardless of
majority.

### Three distinctions that are not conflicts

- **Coverage is not conflict.** A cell one channel filled and another left null is a coverage
  gain; the silent channel made no competing claim. Conflating them is how "109
  disagreements" turned out to be mostly the judge filling fields the draft never attempted.
- **Inability is not silence.** A channel that *cannot express* a field (ADR-061
  `not-covered`) is excluded from the vote entirely. Counting it as a vote for absence would
  hand a Tier B null a confirmation it never earned.
- **Specificity is not conflict.** A logo mark and the registered entity behind it are one
  seller at two levels of detail; a marketplace trader and the marketplace operator are a
  genuine question about which party BT-27 names. Word-set containment separates them — and
  deliberately not substring containment, because a truncated *reference* drops characters
  that change what is referred to.

### Escalation ranking

Ordered by the damage an unnoticed error would do, which is not the same as how hard the cell
is to decide.

| Rank | Meaning |
|---|---|
| 1 `asserted-unevidenced` | One channel, nothing printed, nothing contradicting — the most dangerous cell there is, because it looks exactly like a good one |
| 2 `conflict-none-evidenced` | Competing values, and the gate discriminates nothing (none printed, or all printed) |
| 3 `conflict-one-evidenced` | Competing values, exactly one printed — nearly resolves itself |
| 4 `null-disputed` | One channel asserts something no text layer backs; another looked and found nothing |
| 5 `weak-match` | Match too short to be evidence (a 2–3 character string occurs incidentally) |
| 6 `unparseable` | The value will not parse as its declared type |
| 7 `exempt-vocabulary` | Controlled vocabulary from a single channel; no amount of searching will help |
| 8 `single-channel-proven` | Printed, but only one channel assigns it to this field |
| 9 `nested-readings` | Readings of the same value at different levels of detail |

Two placements deviate from the parent plan on purpose. `conflict-none-evidenced` outranks
`conflict-one-evidenced` because a disagreement with a printed side has a tiebreaker and one
without has none. `null-disputed` sits at 4 rather than last because it is only ever *reached*
when the asserted value is not printed — an evidenced value against a silent channel exits
earlier as proven — which makes it the handoff's headline danger, not a footnote.

### Reporting

The collapse ratio is reported over **asserted cells**, excluding cells no channel claimed a
value for. Counting 615 undisputed absences as collapsed work would turn 65.1 % into 81.3 %
without a single additional cell being settled. Both figures are printed, asserted-first, so
no reader can pick the flattering denominator. Tier A and Tier B are reported separately
throughout, because a blended percentage hides the thing that matters.

**Integration**

- `src/horus/eval/adjudication.py` — the combiner: `adjudicate_cell`, `adjudicate_document`,
  `collapse_summary`, `escalated`, `group_row_counts`. Pure; no I/O, no credentials.
- `scripts/review_heldout_gt.py` — runs it over all 39 documents and writes
  `_review/manifest.json` (machine-readable, for the sign-off page) plus `_review/sheet.md`
  (ranked worst-first, with page-text context per cell).
- Repeating groups are **not** adjudicated cell-by-cell. Rows do not align across channels —
  one reader splits a line another merges — so a positional comparison would manufacture
  conflicts out of segmentation differences. Row-count disagreement is reported instead.
- Both artefacts are written inside the git-ignored corpus tree; stdout carries counts and
  field NAMES only (ADR-040).

- `src/horus/eval/promotion.py` — the writer. Turns manifest cells plus author answers into a
  `schema_version: 2` document whose `provenance` block sits **beside** `fields`, so a warrant
  cannot desync from the value it warrants. `build_groundtruth_from_json` reads only `fields`
  and the three groups, so the block is invisible to the scorer and published ZUGFeRD figures
  cannot move.
- `app/views/heldout_review.py` — the sign-off surface, now driven by the manifest rather than
  by the whole schema. It shows only escalations, ranked, each with every channel's reading,
  the printed marker, and the page text; accepted cells are inspectable but read-only.

Three rules the writer enforces, each of which is a way the retraction could recur:

1. **An unreviewed escalation is written as `null`, never as the proposed value.** Keeping the
   proposal because it is conveniently attached would produce an unchecked answer key that
   looks reviewed.
2. **No radio is pre-selected.** Defaulting to the proposed value makes "I have not looked at
   this" indistinguishable from "I agree".
3. **`verified` is gated on completeness, not on the checkbox.** Ticking sign-off with cells
   outstanding saves the progress and refuses the flag, saying so.

**Promotion writes to `_promoted/`, not over `gt/`.** `gt/` is still one of the three channels
the combiner reads. Overwriting it would let the answer key reappear at the next adjudication
run as an "independent" reading of itself, manufacturing agreement — and it would erase the
record of what produced the retracted 0.5692 (ADR-011: supersede, never delete). Repointing
the held-out evaluation at the promoted tree is a path change; un-fabricating agreement is not.

**Still outstanding**: repointing `finetune_evaluate.py`'s held-out path at `_promoted/` once
enough documents are signed off, and the author's actual pass over the 248 cells.

**Measured result**

39 documents, 3 channels, 1,326 cells:

| | Asserted | Auto-accepted | Escalated |
|---|---:|---:|---:|
| All | 711 | 463 (65.1 %) | 248 |
| Tier A (27 docs) | 490 | 332 (67.8 %) | 158 |
| Tier B (12 docs) | 221 | 131 (59.3 %) | 90 |

Provenance: `text-layer-proven` 341 (285 accepted), `two-channel-agreed` 178 (all accepted),
`author-adjudicated` 148, `exempt-by-policy` 44, `null-claim` 615.

Escalations: 43 `conflict-none-evidenced`, 4 `conflict-one-evidenced`, 52 `null-disputed`,
20 `unparseable`, 44 `exempt-vocabulary`, 56 `single-channel-proven`, 29 `nested-readings`.
Zero `asserted-unevidenced` and zero `weak-match`.

The escalation set concentrates in a handful of *recurring questions* rather than 248
independent mysteries: `document_type` (39 documents — judge-only controlled vocabulary the
draft schema never had and Azure cannot express), `due_payable_amount` (27 — the draft copies
one printed total into BT-106/BT-109/BT-112/BT-115 alike, so BT-115 is printed but assigned
by one channel), `seller_name` (27), `payment_means_text` (18).

**Four defects this pass found in its own machinery**

Recorded because each one inflated the escalation count with artefacts, and because ADR-058
established that a measurement's own instrument must be audited before its output is trusted.

1. **Azure's single merged `VendorTaxId` was written into both BT-31 and BT-32** — guaranteeing
   one of the two was wrong on every document that had one. 29 escalations were artefacts of
   the mapping. Fixed by routing on format (a VAT id carries an ISO country prefix, a
   Steuernummer never does) and *abstaining* when the format does not decide, rather than
   asserting into both.
2. **A weak text-layer match ranked above channel agreement**, making the gate non-monotonic:
   three channels agreeing on a 3-letter currency code escalated on 32 documents, while the
   same three agreeing on a Tier B page with no text layer at all were auto-accepted. A weak
   match means "found, but too short to count" — neutral, not negative.
3. **Conflict rank was computed from evidenced *channels* rather than evidenced *value
   groups***, so three channels proving one value against a lone dissenter was labelled
   identically to three channels proving three different values.
4. **The per-reading gate never actually settled a conflict.** Per-reading gating existed
   precisely so the "which value is printed" question could be asked, and then nothing asked
   it.

**Alternatives considered**

- **Escalate every Tier B cell** (require deterministic proof for auto-accept) — rejected:
  221 cells where no warrant can ever exist, which makes ADR-061's second channel pointless.
- **Majority vote across channels** — rejected: it would accept two channels agreeing on a
  value the page contradicts, and it treats a silent channel as a vote.
- **One blended collapse percentage** — rejected: it hides the Tier A/Tier B distinction,
  which is the distinction that justified the retraction in the first place.
- **Fold specificity differences into agreement silently** — rejected. EN16931 keeps BT-27
  (legal name) and BT-28 (trading name) apart, so the choice is a real one; it gets its own
  lowest rank and a proposed default, not an auto-accept.
- **Confidence-weighted acceptance** using Azure's per-field scores — rejected per ADR-061:
  a confidently-wrong OCR read is the failure this design exists to catch. Confidence orders
  a review list and nothing more.
- **Provenance in a sidecar file** — rejected: a warrant that lives apart from its value will
  desync from it.
- **Promoting over `gt/`** (one answer-key location, no new tree) — rejected: `gt/` is an
  adjudication channel, so the promoted key would be re-read as an independent confirmation of
  itself on the next run. Dropping `draft` from the channel list instead would discard
  information (its agreement with an independent reader still counts) and erase the record of
  the retraction.

**Consequences**

- 463 cells are promotable without author eyes, with the warrant recorded per cell rather
  than asserted in prose.
- 248 cells need a decision, ranked, and clustered into a few recurring questions — which is
  what makes the sign-off page tractable.
- Every accepted cell records *which* warrant it rests on, so the final held-out figure can
  be reported alongside the share of its answer key that rests on agreement rather than
  proof. That share is a limitation to state, not a number to bury.
- The 20 `unparseable` cells (mostly two-digit-year `issue_date` renderings) are surfaced but
  deferred by author decision (#118).
- Adjudication reads channel files and never writes them, so re-running is free and any
  channel can be re-derived and re-adjudicated independently.

**Source archival**

No new external source. Rests on ADR-040 (private held-out set), ADR-058 (symmetric
normalization; audit-the-instrument discipline), ADR-060 (channel 1) and ADR-061 (channel 2,
three-valued coverage). The printed-evidence gate's own contract is in
`src/horus/eval/printed_evidence.py`.

**Supersession trigger**

Revisit if: author adjudication of the 248 cells shows the ranking mis-orders danger in
practice; or a third independent channel changes what "agreement" is worth; or the promotion
writer reveals that provenance cannot be stored in-document without breaking a consumer; or
the held-out corpus grows enough that 248 escalations stop being reviewable in one pass.
