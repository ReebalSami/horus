# ADR-071: Legal-claim precision in the manuscript's motivation

**Status**: Accepted
**Date**: 2026-08-16
**Refs**: #96 (the supervisor-gated softening ticket this closes), ADR-002 (source-archival convention), ADR-055 (thesis authoring setup), ADR-070 (sibling correction from the same review pass), `docs/reviews/2026-08-15-first-supervisor-review.md` (which added the statute citations), `docs/reviews/2026-08-16-second-supervisor-review.md`

## Context (current-state survey)

Issue #96 was filed to soften an earlier, overstated Chapter 1 claim that cloud processing is simply forbidden. The softening landed, and the first review added inline statute citations. A third review pass checked the softened paragraph against the statutes themselves, the two professional chambers' AI guidance and the European supervisory board's published opinions, and found three defects plus two significant omissions.

### Defect 1 — the service-provider requirements were sourced to one profession's statute

The paragraph named all three protected professions and then supported the text-form-contract and comparable-secrecy requirements with **§ 62a StBerG** alone. That statute's own text covers *"Steuerberater und Steuerbevollmächtigte"* only. Verified against the official texts and the enacting bill (BT-Drs. 18/11936), the requirements exist in three near-identically worded provisions, all introduced by the same 2017 act that added § 203 Abs. 3–4 StGB:

| Profession | Confidentiality duty | Service-provider provision |
|---|---|---|
| Steuerberater / Steuerbevollmächtigte | § 57 Abs. 1 StBerG | **§ 62a StBerG** |
| Rechtsanwälte | § 43a Abs. 2 Satz 1 BRAO | **§ 43e BRAO** |
| Wirtschaftsprüfer | § 43 WPO | **§ 50a WPO** |

Each has the same shape: careful selection and a termination duty (Abs. 2); a **Textform** contract obliging secrecy **with instruction about the criminal consequences**, limiting the provider to need-to-know knowledge, and settling sub-processor use (Abs. 3); a **comparable-protection test** for services performed abroad (Abs. 4); **client consent** where the service serves one individual mandate (Abs. 5); and data-protection law expressly unaffected.

### Defect 2 — the data-protection sentence was too simple, and weaker than the thesis's own argument

The paragraph asserted that data protection "can be satisfied for cloud processing through a data-processing agreement and EU data residency", citing a single Art. 32 entry — an entry that was also standing in for Art. 28 and pointing at a private commentary site rather than the law.

The supervisory authority's own published position is narrower. **EDPB Opinion 22/2024** holds that a processor established inside the EEA may still be faced with third-country law, and that adding contract wording such as *"unless required to do so by law or binding order of a governmental body"* does **not** release it from its GDPR obligations. **EDPB Recommendations 01/2020 v2.0** hold that remote access from a third country and non-EEA cloud storage are themselves transfers, that where the importer falls under FISA § 702 only **supplementary technical** measures suffice, and that *"contractual and organisational measures alone will generally not overcome access"*.

That is the thesis's own argument, stated by the regulator. The manuscript was citing the weaker version of it.

### Defect 3 — the provider claim was absolute where the evidence supports a narrower one

"The providers of the strongest general-purpose language models do not currently offer an equivalent amendment" is not supportable as stated. Reviewed 2026-08-16:

- **Microsoft** publishes one — *Zusatzvereinbarung für Berufsgeheimnisträger* / German Data Secrecy Amendment (Nov 2021), naming § 203 StGB expressly, with obligations that map onto the Abs. 3 requirements. It runs 36 months from acceptance with **no renewal clause** against an open-ended framework agreement, and published university IT-law assessments record gaps **specifically for AI services**.
- **Google** has a § 203 addendum, but **not publicly** — requested under NDA, handled best-effort. This alone falsifies the absolute claim.
- **Amazon** has no publicly linked § 203 standard agreement; the route is an individual agreement.
- **Direct model-API providers** (OpenAI, Anthropic) publish data-processing addenda and are silent on professional secrecy.

The repository already held archived records for the provider terms (`openaidpa`, `anthropicdpa`, `azureopenaieu`) and the chamber's data-protection guidance (`bstbkdsgvo`) — **and none of them was cited anywhere in the manuscript.** The evidence for the most attackable sentence in the thesis was sitting unused.

### Omission 1 — the argument that actually wins the point was missing

Professional secrecy protects everything entrusted in the exercise of the profession, **including the affairs of legal persons**, where data-protection law is concerned with natural ones (BStBK FAQ, explicit). A thesis about **business-to-business invoices** therefore sits almost entirely inside the stricter regime and only partly inside the better-known one. This is the single most on-point available support for the thesis's premise and it was absent.

### Omission 2 — a processing agreement is not the confidentiality instrument

Both chambers state it directly: a GDPR processing agreement does **not** satisfy the professional-secrecy requirement; a separate undertaking referring to the criminal provision is needed. The manuscript treated the two regimes as sequential hurdles without saying that clearing one does not clear the other.

## Options considered

1. **Accuracy-only repair, same paragraph length.** Rejected as leaving the two strongest supports unused when they cost two sentences.
2. **Full legal grounding in the body**, including the bar association's stronger argument that transmitting client secrets to a general chat model is not *"erforderlich"* at the current state of the art, so the permission's own precondition fails. Rejected for the body: it is the strongest argument available, but writing it out pushes Chapter 1 toward legal scholarship, which `§ scope` expressly disclaims. Recorded in `docs/sources/legal/brak-2024-ki-leitfaden.md` instead, available if a defence question calls for it.
3. **Accuracy plus the two decisive supports, with the apparatus in footnotes.** **Chosen** (author decision, 2026-08-16).

## Decision (+ integration thoughts)

Chapter 1's motivation is restructured into three short paragraphs — data protection, professional secrecy, provider reality — plus the unchanged closing move to local inference. In the **body**: each regime described in words; the per-profession sourcing corrected; the EDPB position stated; the legal-persons point made; the processing-agreement-is-not-the-instrument point made; the provider claim narrowed to what is provable and cited. In **footnotes**: the statute-by-profession table in prose form, and the provider-by-provider evidence including the amendment's expiry wrinkle. The German profession names stay attached to the statute that enumerates them, preserving the second review's decision about decorative German.

Bibliography consequences, all repaired in the same pass: `stberg62a`'s invented heading corrected to the official *"Inanspruchnahme von Dienstleistungen"*; `dsgvo32` re-pointed to EUR-Lex and split so `dsgvo28` carries Art. 28; new entries for `brao43e`, `wpo50a`, `brak2024ki`, `edpb2024processors`, `edpb2021supplementary`, `msprofsecrecy`; and the previously uncited `openaidpa` / `anthropicdpa` / `azureopenaieu` / `bstbkdsgvo` wired into the text they were archived for. Three abbreviations added.

**Two further bibliography fabrications were found in the same pass and are recorded here** because they share a cause with the invented statute heading — an entry built from a convenient handle rather than from the work: `fatura2` credited *"Brandt, Mathieu"*, which is a mis-reading of the Hugging Face account hosting the redistribution (real: Limam, Dhiaf & Kessentini 2023, arXiv 2311.11856); and `krieger2021german` carried an invented descriptive title with *"and others"* for a fully resolvable four-author paper (real: Krieger, Drews, Funk & Wobbe 2021, WI 2021, LNISO, Springer, pp. 5–20, DOI 10.1007/978-3-030-86797-3_1). The bibliography header's blanket claim that every author list, title and venue "were verified against the primary source" is corrected in place rather than quietly relaxed.

## Source archival

Per `horus-source-archival`, added or corrected in this pass: `docs/sources/legal/brao-43e.md`, `wpo-50a.md`, `brak-2024-ki-leitfaden.md`, `edpb-processors-and-transfers.md`, `microsoft-professional-secrecy-amendment.md`, `ustg-27-uebergang-und-profile.md`; corrected `stberg-62a.md` (invented heading + a provider overclaim that had propagated into the manuscript); superseded `papers/gi-2021-german-invoices.md` by `papers/krieger-2021-invoice-gnn.md`; added `papers/krieger-2023-longtail.md` and `papers/limam-2023-fatura.md`.

## Supersession trigger

- **Vendor-contract facts decay.** The provider survey is dated in the footnote and in the archive record. If a direct model-API provider begins offering a professional-secrecy amendment, the narrowed claim becomes false and must be re-stated — supersede rather than silently edit.
- **The 36-month expiry** means the one public amendment can lapse. If a later review finds it withdrawn or renewed, update the archive record.
- If the supervisor or a legal reviewer disagrees with any characterisation here, their reading governs: this remains a technical thesis making a legal premise, not a legal opinion. #96's sign-off gate is discharged by this record, not removed.

## Consequence recorded for the learning pipe

Three of the four bibliography defects in this pass share one mechanism: an entry was created from whatever identifier was nearest to hand — an account name, a descriptive summary, a remembered heading — and a comment then asserted that verification had happened. This is precisely the defect class Chapter 6 documents for field specifications: *a claim about data is itself data to be measured*. The forcing function that worked there was a gate, not vigilance. Captured to the meta-repo review queue as a candidate for the same treatment on bibliographies.
