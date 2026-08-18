---
source_url: "https://www.fh-wedel.de/"
source_title: "FH Wedel — Richtlinie / Leitfaden für Abschlussarbeiten (inkl. KI-Kennzeichnungspflicht)"
source_author: "Fachhochschule Wedel"
source_date: "2024-04-25"
retrieved_date: "2026-06-28"
verified_date: "2026-08-18"
extracted_concepts: ["Eidesstattliche Erklärung", "AI-disclosure / KI-Kennzeichnung", "thesis formal requirements", "document order", "Textumfang", "page geometry"]
tags: ["legal", "regulation", "thesis", "fh-wedel", "ai-disclosure"]
archived_pdf: "~/Projects/FH-Wedel/SS26/Master-Thesis/anmeldung-und-richtlinien/Richtlinie 3.0 (Stand 25.04.2024).pdf"
status: verified
verified: [declaration-wording, ai-clause-text, kurzfassung-obligation, textseiten-window, page-margins, font-size, line-spacing, part-order]
---

# FH Wedel — Thesis Richtlinie / Leitfaden

FH Wedel's formal requirements for theses: the document structure/order
(Deckblatt → … → Literaturverzeichnis → Eidesstattliche Erklärung) and the
current requirement to **disclose and document the use of AI tools**.

## Why cited in HORUS

Drives two `thesis/` requirements (ADR-054): (1) the statutory declaration must
include the AI-disclosure clause; (2) an appendix documents AI-tool usage. Local
copies of the Anmeldung + Richtlinie live under
`/Users/reebal/Projects/FH-Wedel/SS26/Master-Thesis/anmeldung-und-richtlinien/`.

## Verified 2026-08-18 (ADR-073)

Extracted from the locally held `Richtlinie 3.0 (Stand 25.04.2024).pdf` via
`pdftotext -layout`. The `verified:` frontmatter list names the facets actually
checked; anything not listed there is unchecked.

### §3.9 + Abb. 2 (p. 14) — declaration wording: **one defect found and fixed**

Prescribed text, verbatim:

> Ich erkläre hiermit an Eides Statt, dass ich die vorliegende Arbeit
> selbstständig und ohne Benutzung anderer als der angegebenen Hilfsmittel
> angefertigt habe; die aus fremden Quellen direkt oder indirekt übernommenen
> Gedanken sowie durch eine künstliche Intelligenz wie ChatGPT erstellte oder
> bearbeitete Inhalte sind als solche kenntlich gemacht.
>
> Die Arbeit wurde bisher in gleicher oder ähnlicher Form keiner anderen
> Prüfungskommission vorgelegt und auch nicht veröffentlicht.

Sentence 1 and the inline AI clause matched the manuscript exactly, including
`an Eides Statt` (capital *S*). Sentence 2 did **not**: the manuscript read
"in ähnlicher Form", omitting `in gleicher oder`, which narrowed the assurance
by declining to declare the work had not been submitted in *identical* form.
Fixed in `thesis/preamble/declaration.tex`.

Introduced permissively ("Folgender Text **kann** verwendet werden"), but the
Richtlinie warns on the same page that the declaration "ist keine reine
Formsache, sondern eine rechtliche Zusicherung" whose material breach "kann zur
Nichtanerkennung der Prüfungsleistung führen".

### §3.1 Tab. 1 (p. 5) — part order + Kurzfassung obligation

Order: Deckblatt → Sperrvermerk/Vorwort/Executive Summary (`Fallweise`) →
Inhalts-/Abbildungs-/Tabellen-/Abkürzungsverzeichnis → **Text der Arbeit** →
Anhang → Glossar → **Literaturverzeichnis** → Stichwortverzeichnis →
**Eidesstattliche Erklärung** → Anlagen. The manuscript matches.

*Excecutive Summary* [sic] is **`Fallweise`**, so no German Kurzfassung is
obligatory; the English Abstract discharges the optional slot.

Front matter roman (Deckblatt = I, unprinted); arabic from the first page of the
text, continuing to the end. §3.7 (p. 13): "Der Anhang folgt unmittelbar dem
Text der Arbeit; die arabische Seitenzählung wird fortgesetzt" — appendix before
bibliography is correct.

### §3.5 items 3–7 (pp. 12–13) — Textumfang and page setup

- **Textumfang**: "für die Masterarbeit ein Umfang von 80 bis 120 Textseiten".
  Manuscript: body ch. 1–11 = arabic pp. 1–113 → **113 Textseiten**, inside the
  window (appendices open at 114; 140 pp. total).
- **Margins (prose)**: left 3,5 cm / right 4 cm / top 3 cm / bottom 3 cm;
  **Schriftgröße 11**; Zeilenabstand 1½.
- These prose figures describe the **Word** template. FH Wedel's own **LaTeX**
  template (`thesis-template-master/Thesis/`) sets `inner=2.5cm, outer=2.0cm,
  top=1.5cm, bottom=1.5cm` at `12pt` with `onehalfspace` — which is what the
  manuscript uses, identically. §3 opens by permitting deviation in agreement
  with the supervisor.
- **Do not "correct" the LaTeX geometry to the prose numbers.** That would
  diverge from the institution's own template. Recorded here so a later pass
  does not repeat the reasoning and get it wrong.

### Still outstanding

- `source_url` remains the FH Wedel root: the Richtlinie is Moodle-internal and
  has no stable public URL. The authoritative copy is the local PDF named in
  `archived_pdf`.
- The printed copies must be **signed by hand** ("eigenhändig … zu
  unterschreiben", §3.9) — not dischargeable by any repository change.
