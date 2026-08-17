---
source_url: "https://www.gesetze-im-internet.de/stberg/__62a.html"
source_title: "§ 62a StBerG — Inanspruchnahme von Dienstleistungen"
source_author: "Bundesrepublik Deutschland (Steuerberatungsgesetz)"
source_date: ""
retrieved_date: "2026-08-16"
extracted_concepts: []
tags: ["stberg", "berufsgeheimnis", "external-providers", "foreign-providers", "cloud-act", "primary-legal", "german"]
archived_pdf: ""
status: verified
---

**Title corrected 2026-08-16 (third-pass thesis review).** This record previously carried the heading *"Mitwirkung externer Personen"*, which is not the statute's heading. The official heading, verified against gesetze-im-internet.de, is **"Inanspruchnahme von Dienstleistungen"**. The same invented heading had propagated into `thesis/references.bib` and is corrected there too.

§ 62a StBerG — *Inanspruchnahme von Dienstleistungen* (Steuerberatungsgesetz). Defines when external service providers may participate in Steuerberater work and what contractual + organizational requirements apply. **Scope note:** it covers *Steuerberater und Steuerbevollmächtigte* only. The parallel provisions are **§ 43e BRAO** for lawyers and **§ 50a WPO** for auditors, all three introduced by the same 2017 act (BT-Drs. 18/11936) that added § 203 Abs. 3–4 StGB. Two requirements the earlier version of this record omitted: **Abs. 3 Satz 2 Nr. 1** requires the confidentiality undertaking to be accompanied by an **instruction about the criminal consequences** of breach, and **Abs. 5** requires the **client's consent** where the service serves one individual mandate rather than the firm's general infrastructure. Cited in HORUS as the **primary statutory mechanism** for legalising external-provider participation: a Berufsgeheimnis-Verpflichtung in Textform is required for any external party that will encounter Mandantendaten. Critically, **§ 62a Abs. 4 StBerG** requires foreign service providers to offer comparable secrecy protection to German providers — US-based AI providers fail this clause even with EU-located servers, due to extraterritorial reach of the US Cloud Act and FISA 702 (per brainstorm v2 §7.6). This is the legal fault-line distinguishing "DSGVO-compliant" from "§ 203 + § 62a + § 57 compliant".

**Overclaim corrected 2026-08-16.** This record previously ended: *"currently NOT solvable for any major cloud AI provider as of early 2026"*. That is too strong and was carried into the thesis. Microsoft publishes a § 203-specific amendment (see `docs/sources/legal/microsoft-professional-secrecy-amendment.md`), Google has one available only under NDA, Amazon offers an individual-agreement route, and the direct model-API providers have none. The defensible statement is that **no provider of a frontier general-purpose model offered as a direct API publishes such an amendment**, and that the residual US-jurisdiction exposure the Abs. 4 comparable-protection test targets persists regardless of contract — which is exactly why the EDPB position archived in `docs/sources/legal/edpb-processors-and-transfers.md` matters. Note also that the DSGVO half is not as "solvable" as this record assumed: EU residency does not by itself remove third-country access exposure.
