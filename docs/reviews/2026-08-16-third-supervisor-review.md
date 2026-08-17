# Third-Pass Review — re-audit of the Chapters 1–3 review, and the fix pass that followed

**Role**: Third full pass. Unlike passes one and two, this one was a **re-audit of a prior review's own findings** as well as of the manuscript: the task was to check whether the previous pass was right, wrong, or hallucinating, and then to fix what survived.
**Manuscript state on entry**: working tree of 2026-08-16 on `docs/thesis-manuscript`, committed build 128 pages, zero unresolved references and citations.
**Manuscript state on exit**: 136 pages (body pp. 1–110, within the 80–120 Textseiten window), zero unresolved references and citations, zero LaTeX errors, zero biblatex warnings, 13 overfull boxes with worst 3.22 pt (pre-existing, unchanged).
**Verification depth**: all twelve chapters read end-to-end — the material difference from pass two, which had read only the first 251 lines of six of them; all nine result tables re-traced; the decision-record index and the endgame, reader-selection, held-out and grading records read in full; the live 58-issue tracker checked; German statutes verified against the official government text and the enacting bill; both professional chambers' AI guidance read; the European supervisory board's opinions read; the closest prior benchmark, the multilingual parsing benchmark, the synthetic-invoice dataset, the German invoice corpus and three model cards verified against their primary sources.

---

## 1. Verdict on the previous pass

Eleven of its fifteen findings hold. One was a non-issue, one had the wrong diagnosis, one number was misreported, and its headline verdict — *no blocking issue* — was wrong.

| Previous finding | Verdict |
|---|---|
| "No blocking issue" | **Wrong.** See §2. |
| Legal framing over-broad | **Correct**, and provable against the statutes. |
| Vendor-amendment claim unproven | **Correct**, and the absolute version is false for one provider. |
| Research question 1 too broad | **Correct.** |
| Research question 2 says "outperform", evidence is open | **Correct.** |
| Throughput named, never measured | **Correct**, though the cause differs: it was instrumented and then deliberately left unproven. |
| "Exact, free and incorruptible" ground truth | **Correct.** |
| "First systematic comparison" vulnerable | **Correct, and understated.** See §3.4. |
| "Fourth generation" lumps unlike models | **Correct.** |
| Graph retrieval "helps exactly" | **Correct** — ch.2 was more confident than ch.4. |
| Quantisation memory wording | **Correct.** |
| "Every model is a transformer" | **Not a defect.** Dropped. |
| "Archived sources are stubs" | **Wrong diagnosis.** The real defect was three *incorrect* bibliography entries plus five archived sources cited nowhere. |
| Prose too rhetorical | **Correct but already handled** by pass two's dedup. Low value; not acted on. |
| "Worst overfull 0.38 pt" | **Misreported.** The worst is 3.22 pt and was already accepted. Non-issue. |

**Why pass two missed the biggest defect**: it read the first 251 lines of chapters 4, 5, 6, 7, 10 and 11. Chapter 5 is 542 lines. The contradiction lives at line 535.

---

## 2. The blocking finding, and why two prior passes did not close it

Pass two's Addendum 3 found — on the author's challenge — that the abstract's "hosted entirely on a 16 GB Apple-silicon laptop" was false, and corrected four passages. That correction was incomplete twice over.

**Six sites still carried the absolutism**, all attached to the headline number: `07-results.tex:367`, `09-discussion.tex:12`, `09-discussion.tex:58`, `11-conclusion.tex:8`, the generated caption in `heldout-headline.tex:10` (real source `scripts/thesis_assets.py`), and `figures/architecture.tex:31`. The discussion site was **factually false about both tables it cited**, since one of them labels two of its four rows as full-precision cloud runs.

**And the venue split is broader than the held-out corpus.** `scripts/gpu/README.md` states in its own opening paragraph that the rented session ran the bake-off, **regenerated all 146 synthetic transcripts** with the winning reader, and transcribed the 39 real invoices, while "training and final eval stay on the M1". Therefore:

> Every transcript behind every reported figure was produced on rented cloud hardware at full precision and native page resolution. Only the structuring stage and the scoring ran on the laptop. The arm label `4-bit / Apple silicon` describes the **structurer**.

Chapter 5 enumerated three classes of rented pass and did not name the synthetic regeneration — the disclosure was itself incomplete.

**Why this is substantive, not cosmetic.** The local reader is capped at ≈ A4 at 150 DPI because the native-resolution vision tower demanded a 35 GiB Metal buffer. So the unmeasured quantity is *reading quality at half resolution* — and the thesis's headline finding is that capture quality dominates, worth over eleven points of mean per-invoice F1. Page resolution is a capture-quality variable. **The one configuration never measured sits on the axis the thesis argues matters most.**

Fixed under **ADR-070**: venue claims scoped per stage across all six sites plus the generator; ch.5 now enumerates four classes and states the consequence in one bolded sentence; ch.10 declares the delivered reading quality unmeasured and explicitly refuses to characterise the gap as small; a new future-work section specifies the bounded closing measurement with two pre-committed protocol requirements; the conclusion's non-claims section names the boundary. **No committed number moved** — no scoring, evaluation or model code was touched.

---

## 3. The other findings acted on

### 3.1 The legal paragraph (ADR-071, closes #96)

Three defects: the service-provider requirements were sourced to the tax-advisor statute alone although all three named professions have their own (`§ 43e BRAO`, `§ 50a WPO`, all three from BT-Drs. 18/11936); the data-protection sentence implied a processor contract plus EU hosting settles the matter, where the supervisory board's published position is that an EEA processor can still be reached by third-country law and that contract language does not cure it; and the provider claim was absolute where Google's NDA-only addendum falsifies it.

Two arguments added because they are the strongest available and were missing: professional secrecy protects **legal persons** where data-protection law largely protects natural ones — decisive for a business-invoice thesis — and a data-protection processing agreement is **not** the confidentiality instrument, which both chambers state directly. Apparatus in footnotes, per the author's decision, to keep the chapter's scope promise.

### 3.2 Research questions realigned to what was measured

Question 1 → reading stages behind a fixed structurer. Question 2 → what evidence supports the split and what stays unproven. Question 3 → throughput dropped, memory envelope kept. A new **question-to-evidence map** states per question whether the answer is a sealed measurement, a diagnostic, a preliminary study, or not evaluated. The discussion chapter's four answer headings were realigned to match. Precedent for revising them: they had already been rewritten once, when the scope freeze removed the two upper layers.

### 3.3 Chapter 2 corrections

The embedded-reference passage no longer claims ground truth is "exact, free and incorruptible" — it now carries the two warnings chapter 6 later proves. The evaluation section now introduces **all five** scoring outcomes, including the true negative that the spurious-emission rate arithmetically requires and the neutral *excluded* class that carries the whole validity argument; the previous text defined three counts and then invoked a metric it lacked the vocabulary for. The hybrid-invoice profile list is completed to six (the public-sector reference profile was missing, though the corpus contains a document in it) and legally qualified (two of the six are booking aids, not invoices under VAT law). The phased e-invoicing obligation is now sourced to the transitional provision where the dates actually live, with the small-amount and small-business exemptions added — which strengthens the mixed-document argument. Quantisation corrected to weight storage. Graph retrieval hedged to match chapter 4.

### 3.4 Chapter 3: two arguments rebuilt

**The German-invoice literature was under-engaged.** The 977-invoice corpus was cited only as inaccessible. The same authors **published an extraction result on it** — macro-F1 0.8753 with a graph network over OCR output — and a **follow-up studying precisely the layout-shift question this thesis registers and leaves untested**. An examiner from the auditing side knows this work. A new subsection makes the comparison explicit and states the three reasons the numbers are not comparable, none of which flatters this thesis.

**The prior-work reconciliation rested on a rebuttal that fails.** Chapter 3 argued the closest benchmark only tested a layout converter, not a vision transcriber. They tested **two** converters, and the second is a compact document vision-model emitting the same structural markup — the direct predecessor of this thesis's own first reader. The rebuttal is given up in print and replaced with a stronger, evidence-backed one: parse-first with a compact structural converter loses in their data *and* in this thesis's, and recovery came only from a reader an order of magnitude larger. The novelty claim is restated as a searched-and-found-nothing formulation with the search scope in a footnote. Two smaller errors fixed: "a text-only model extracts the fields" (they used the same multimodal models on text) and two categories named for three families.

### 3.5 Bibliography

Three entries were **incorrect**, all built from a convenient handle rather than the work: a dataset credited to a Hugging Face account name rather than its three real authors; the German corpus given an invented descriptive title and "and others" for a fully resolvable four-author paper with a DOI; and a statute given an invented heading. A fourth entry was doing duty for two different articles from a private commentary site. Five archived sources were cited nowhere and are now wired into the passages they were archived for. The bibliography's own blanket claim that everything "was verified against the primary source" is corrected in place rather than quietly relaxed — a claim of verification is itself a claim to be checked, which is the lesson chapter 6 already makes about field specifications.

---

## 4. Not acted on, deliberately

Overfull boxes (worst 3.22 pt, accepted in pass two, unchanged). "Every model is a transformer" (verified accurate). Prose register (pass two's dedup already took it from 89 to 42 occurrences of the worst tic). The thinness of archive records that are otherwise correct — the ones that mattered were wrong, not thin.

---

## 5. Grade read

With the venue contradiction live on the headline result this was not the 1.7 pass two would have implied: an examiner reading chapter 5 and then chapter 7 watches the thesis contradict itself about its central claim. After this pass, chapters 1–3 and the claims depending on them are defensible at **1.3**, and the measurement-validity chapter remains 1.0-class work.

The one thing still standing between the manuscript and the top mark is not a text defect. It is that **the delivered configuration has never been measured on real documents** — now honestly declared, with a bounded, local, zero-cost measurement specified and filed as #129.

---

## 6. Artefacts of this pass

- **ADR-070** — measurement-venue scoping; delivered reading configuration declared unmeasured
- **ADR-071** — legal-claim precision; closes the drafting gate of #96
- **#129** — the deferred local measurement, pre-registered in the issue body, on the roadmap board
- **#96** — closed as done on drafting scope; the supervisor-wording checkbox travels with the manuscript
- New source records: `brao-43e`, `wpo-50a`, `brak-2024-ki-leitfaden`, `edpb-processors-and-transfers`, `microsoft-professional-secrecy-amendment`, `ustg-27-uebergang-und-profile`, `krieger-2021-invoice-gnn`, `krieger-2023-longtail`, `limam-2023-fatura`
- Corrected records: `stberg-62a` (invented heading + provider overclaim); `gi-2021-german-invoices` superseded

## 7. Lesson for the learning pipe

Two prior passes fixed the venue absolutism partially, each correcting the sites it happened to read. The generalisable rule: **when a claim class is found defective, grep the class across the whole manuscript *and its generators* before declaring it fixed.** A defect that lives in a code-generated caption is invisible to a reader of `.tex` files. Same shape as the recurring lesson of chapter 6 — replace vigilance with a gate.

---

## 8. Addendum — author correction, same session: venue reframe v2 (two-tier envelope)

The author reviewed §2's fix and objected on substance: the correction had **stripped the local point instead of scoping it**, treating a rented GPU as if it were a cloud model. The objection is right, and the fix pass over-rotated in tone. Checked against `scripts/gpu/README.md`, the rented venue was:

- **one NVIDIA A10G, 24 GB** (g5.xlarge) — the memory class of a single consumer graphics card, not a data-centre part;
- **EU Frankfurt, single-tenant, storage destroyed at termination**, running the same open-weights checkpoints under the author's control — no model provider processed anything;
- fed **only the synthetic corpus and the author's own collected invoices** — no client document (runbook §2b states the justification in situ);
- fast and cheap in a way that *supports* the deployment claim: **39 invoices / 58 pages in ~16 min including the 9 GB checkpoint fetch, zero errors**, under 6 GPU-hours for the entire research programme — versus 49 min/page bf16 on the author's laptop. The bottleneck was the author's 2021 machine, never the method. The `max_pixels` cap is MPS-only (runbook §4).

**One claim of the author's was pushed back on**: "an average modern computer would have done the job completely locally" is not supportable — an average office PC carries no 24 GB GPU. The supportable (and stronger) form: *nothing reported needed more than one modern 24 GB graphics card*, and the LoRA training ran on that same single card.

**Resolution — the two-tier envelope** (author-selected): a **target class** (workstation with one 24 GB GPU; every reading figure and the whole adaptation study measured there) and a **floor** (the 16 GB laptop; structuring measured there; delivered demonstrator runs there). The disclosure stays complete — the AWS use is presented as the confound-removing methodological move it was — and the one honest gap narrows to its true size: the *floor's reading quality* is unmeasured (#129). One coherence guard kept: the manuscript does not recommend rented US-cloud GPUs as a *firm* venue, since chapter 1's own §203 argument (external-provider machinery + third-country jurisdiction) applies to infrastructure providers too; the research use was clean because the data was the author's own.

Applied across: abstract, ch.1 evidence map, ch.2 §bg-local, ch.5 §method-repro, ch.6 §validity-confound, ch.7 venue paragraph + generated table note, ch.8 deployment, ch.9 answers (1)/(3) + §disc-local, ch.10 §lim-hardware + §fw-envelope (retitled "Measure the Floor of the Envelope"), ch.11 non-claims, architecture figure. Formatting: the full-sentence mid-paragraph bolds introduced by the fix pass were reverted to the manuscript's house style (short bold lead-ins only); ch.1's two regime-name bolds became `\emph`. ADR-070 amended in place (uncommitted) with the final two-tier form; #129 re-scoped to the floor measurement.

§5's grade read stands, with the interpretation improved: the two-tier framing is *more* defensible than both the original absolutism and the first correction, because every sentence now names the machine class its evidence came from.
