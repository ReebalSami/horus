# ADR-073: Statutory declaration corrected against the prescribed source

**Status**: Accepted
**Date**: 2026-08-18

## Context

The fifth-pass pre-submission audit named exactly one item it called a true gate — the only finding that could affect the *act* of submission rather than the grade:

> **U1 — the statutory declaration's wording has never been verified against the prescribed source, by the project's own record.** `docs/sources/legal/fh-wedel-thesis-richtlinie.md` is still a stub carrying an open TODO: *"Verify the EXACT declaration wording + AI-clause text against the official Richtlinie 3.0."* … Until that five-minute check happens, "submit" rests on an unverified formal assumption — the only finding in this audit the author cannot delegate.

The audit judged the source unreachable ("the Richtlinie is Moodle-internal and not checkable from the public web"). It is, however, held locally at `~/Projects/FH-Wedel/SS26/Master-Thesis/anmeldung-und-richtlinien/Richtlinie 3.0 (Stand 25.04.2024).pdf`, and `pdftotext` is installed. The check was therefore performed rather than deferred.

Two further items were bundled with the gate: whether a German *Kurzfassung* is required — ADR-055 chose an English thesis and left "a German `Kurzfassung` alongside the English abstract … as an open option" — and whether the manuscript sits inside the prescribed page window.

(The audit attributed the open Kurzfassung flag to `README.md`. It is not there; a grep of the repository finds it only in ADR-055. Recorded because this ADR closes the question and the reader should be able to find where it was open.)

## Decision

### 1. The declaration was defective; it is corrected verbatim

Richtlinie 3.0 §3.9, p. 14, "Abb. 2: Eidesstattliche Erklärung" prescribes two sentences. Sentence 1 and the inline AI-disclosure clause matched the manuscript **exactly**, including `an Eides Statt` with a capital *S* — the spelling the audit flagged as a risk. Sentence 2 did not:

| | Text |
|---|---|
| **Prescribed** | "Die Arbeit wurde bisher **in gleicher oder ähnlicher Form** keiner anderen Prüfungskommission vorgelegt und auch nicht veröffentlicht." |
| **Manuscript (before)** | "Die Arbeit wurde bisher **in ähnlicher Form** keiner anderen Prüfungskommission vorgelegt und auch nicht veröffentlicht." |

`in gleicher oder` was absent. The omission is not stylistic. It narrows a legal assurance: as written, the declaration asserted only that the work had not been submitted in *similar* form, and therefore declined to assert the stronger and more obvious proposition that it had not been submitted in *identical* form. The Richtlinie states on the same page that the declaration

> "ist keine reine Formsache, sondern eine rechtliche Zusicherung. Ein erheblicher Verstoß gegen ihren Inhalt kann zur Nichtanerkennung der Prüfungsleistung führen."

`thesis/preamble/declaration.tex` now carries the prescribed sentence verbatim. Its header comment records the exact source (§3.9, Abb. 2, p. 14), the verification date, and *why* `gleicher` is load-bearing, so a future editor cannot re-narrow it by tidying.

The Richtlinie introduces the block with "Folgender Text **kann** verwendet werden" — permissive, not mandatory. That lowers the severity but does not change the decision: there is no reason to submit a self-weakened variant of the institution's own formulation, and a *narrower* declaration is the one direction where deviation is actually adverse.

### 2. A German Kurzfassung is not required — question closed

Tab. 1 (§3.1, p. 5) enumerates the written parts and marks each `obligatorisch` or `Fallweise`. *Excecutive Summary* [sic] is **`Fallweise`**. No German Kurzfassung is obligatory, and the English Abstract discharges the optional slot. ADR-055's open option is hereby closed as *not required*; adding one remains permissible but is no longer an outstanding question.

### 3. The page window is met — question closed

§3.5 item 4: *"für die Masterarbeit ein Umfang von 80 bis 120 Textseiten."* Measured from `thesis/_build/main.toc` on the final build of this pass: body chapters 1–11 occupy arabic pages 1–115; Appendix A opens at 116, the bibliography at 128, the declaration at 134, with 142 pages total. **115 Textseiten**, inside the window. Tab. 1 distinguishes *Text der Arbeit* from *Anhang*, so appendices are not Textseiten.

(The figure was 113 before this pass's layout repairs — the disclosure prose added for ADR-072 and findings D1/D2, plus the top-aligned float pages, cost two body pages. Re-measure after any further body addition: the remaining headroom is 5 pages.)

### 4. Formal apparatus verified against the template, not the prose — no change made

The Richtlinie's prose (§3.5 items 3–7) gives margins of left 3,5 cm / right 4 cm / top 3 cm / bottom 3 cm and `Schriftgröße 11`. The manuscript sets `inner=2.5cm, outer=2.0cm, top=1.5cm, bottom=1.5cm` at `12pt`, under a comment claiming it matches the FH Wedel template.

That comment is **correct**, and this was checked before changing anything: FH Wedel's own LaTeX template, `anmeldung-und-richtlinien/thesis-template-master/Thesis/`, sets

- `stuff/header.tex:42-45` — `inner=2.5cm, outer=2.0cm, top=1.5cm, bottom=1.5cm` (identical)
- `thesis_main.tex:2` — `12pt` (identical)
- `thesis_main.tex:21` — `\newgeometry{left=3cm,right=2cm,top=2.0cm,bottom=2.0cm}` for the title page (identical)
- `thesis_main.tex:40` — `onehalfspace` (identical; also satisfies §3.5 item 7's *1½ Zeilen*)

The prose figures describe the Word template (`Richtlinie 3.0 Word-Vorlage (Stand 25.04.2024).docx`); the LaTeX template is the operative artifact for a LaTeX submission, and §3 opens by permitting deviation in agreement with the supervisor. **Recorded explicitly because "correcting" the geometry to the prose numbers would have been a regression** away from the institution's own template — a trap this audit trail should not lay for a future pass.

Part order also matches Tab. 1 exactly: Deckblatt → Verzeichnisse (roman, Deckblatt = I unprinted) → Text der Arbeit → Anhang → Literaturverzeichnis → Eidesstattliche Erklärung. Appendix-before-bibliography is correct per §3.7 (*"Der Anhang folgt unmittelbar dem Text der Arbeit; die arabische Seitenzählung wird fortgesetzt"*).

## Alternatives considered

- **Defer the check to the Prüfungsamt.** Rejected: the artifact and the tooling were both present, and the audit correctly identified this as the one item that cannot be delegated.
- **Leave the wording and note the deviation.** Rejected: the deviation *weakens* a legal assurance. There is no upside to preserving it.
- **Align margins to the Richtlinie prose.** Rejected on evidence — it would diverge from FH Wedel's own LaTeX template.
- **Add a German Kurzfassung defensively.** Rejected: Tab. 1 marks it `Fallweise`, and adding unrequired front matter would push the page count without improving compliance.

## Source archival

`docs/sources/legal/fh-wedel-thesis-richtlinie.md` is promoted from `status: stub` to `status: verified`, with the `verified:` facet list naming what was actually checked — declaration wording, Kurzfassung obligation, page window, margins, font size, line spacing, part order — per the queue lesson that `status: verified` without named facets invites exactly the partial-check trust failure the fourth pass documented.

Primary source: `Richtlinie 3.0 (Stand 25.04.2024).pdf`, held locally; §3.1 Tab. 1 (p. 5), §3.5 (pp. 12–13), §3.7 (p. 13), §3.9 + Abb. 2 (p. 14). Not publicly linkable — Moodle-internal, so `source_url` remains the FH Wedel root with the local path recorded in the body.

## Consequences

- The audit's only true submission gate is closed on evidence rather than assumption.
- The declaration now matches the institution's prescribed text character-for-character; the printed copies still require a handwritten signature, which no edit can discharge.
- Two bundled open questions (Kurzfassung, page window) are closed; ADR-055's open Kurzfassung option is resolved as *not required*.
- The formal apparatus is documented as verified-and-correct, with the prose-versus-template discrepancy recorded so it is not "fixed" later.
- Page count is now a tracked constraint: at 115 of 120 Textseiten, additions to the body have 5 pages of headroom.

## Supersession trigger

Supersede if FH Wedel issues a Richtlinie later than 3.0 (Stand 25.04.2024), if the Prüfungsamt prescribes a different declaration text or requires a German Kurzfassung for an English-language thesis, or if the body grows past 120 Textseiten.
