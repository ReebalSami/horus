# Supervisor review 2026-08-18 — comment registry

Canonical, actionable register of every annotation made by the **first examiner** on the interim manuscript, with an exact `.tex` target for each.

| Field | Value |
|---|---|
| Review artefact | the annotated interim-manuscript PDF in `thesis/proff-kommentare/` — local-only, untracked (see § Placement and privacy) |
| Covering email | `thesis/proff-kommentare/email.md` — local-only, untracked |
| Reviewed commit | `485d1a9` — `pdftotext` of the review PDF is **byte-identical** to `thesis/_build/main.pdf`, so every anchor below is valid against current `main` |
| Annotations | **38** authored (20 `/Highlight`, 18 `/Text`). The other 1214 annotations in the file are LaTeX-generated `/Link`s and `/Popup` companions |
| Page numbering | **PDF page − 8 = printed page.** Verified on 8 independent pages. Front matter is Roman. Every row gives `PDF/printed` |
| Status | Registry complete; **no `.tex` edits applied yet** |

## Placement and privacy

**Placement.** This record lives in `docs/reviews/` per **ADR-069**, which makes that directory the canonical home for manuscript review records under the `YYYY-MM-DD-<slug>.md` convention, and which explicitly rejected `thesis/<subdir>/` for review prose. It is the seventh entry in that series and the first to register an *external* reviewer's own annotations rather than a self-audit.

**Privacy.** The review PDF and the covering email carry the examiner's name and signature. Both stay at `thesis/proff-kommentare/` on the local filesystem and are **gitignored in full**; only this anonymised registry is tracked. The examiner is referred to throughout as "the first examiner". This follows the precedent set by the `chore/redact-supervisor-and-reframe-meeting` branch.

## Status legend

- `[ ]` open — not yet addressed
- `[~]` in progress
- `[x]` done — record the commit SHA next to it
- `[-]` deliberately declined — record why

---

## 0. Scope — read this before anything else

**This is a fine-polish pass, not a rewrite.** The examiner asked for *Feinschliff*, and his own qualifiers set the dose:

| His words | What it licenses |
|---|---|
| *"Der Inhalt und die Darstellung sind bereits sehr gut gelungen"* | The content is finished. Do not re-argue it |
| *"manchmal grenzwertig und **selten** auch nicht angemessen"* | Register problems are **rare**, not pervasive |
| *"**in Teilen** … zu umständlich"* | Convoluted sentences are **in parts**, not throughout |
| *"**vielleicht etwas weniger** mit diesen Gedankenstrichen"* (R10) | Fewer em-dashes. Not zero, and no target count |
| *"ich möchte ihnen **keinen anderen Stil aufdrängen**"* | The voice stays. Remove the tells, not the author |
| *"den Text einmal kritisch … **nachjustieren**"* | Readjust. Not rewrite |

**Operating rule: the current manuscript is the reference.** A sentence changes only if a registry row points at it, or if it is a clear instance of one of the named classes. If a sentence is merely long, or merely contains an em-dash, and it reads fine — it stays. When uncertain, leave it.

Every chapter has some slack to take out. **No chapter needs reworking.**

---

## 1. Themes

### From the covering email

The examiner's own summary is that the content is already strong (*"inhaltlich sehr gut"*, *"Inhalt und die Darstellung sind bereits sehr gut gelungen"*) and that his criticism is **formal**. Four headline complaints:

1. **Colloquial register** — *"ihre Formulierungen für eine wissenschaftliche Arbeit manchmal grenzwertig und selten auch nicht angemessen bzw. zu umgangssprachlich"*. He asks explicitly for one critical pass over the text with respect to *Umgangssprache*. → rows R11, R15, R16, R18, R22.
2. **Argue-by-negation** — *"Sie arbeiten bei ihrem Stil auch gerne damit zunächst eine Verneinung zu formulieren und dann ihr Vorgehen gegen diese Verneinung darzustellen. Dies ist für wissenschaftliche Arbeiten etwas zu 'ausgeschmückt' und könnte kürzer und neutraler geschrieben werden."* → rows R27, R29.
3. **Convoluted sentences / length** — *"in Teilen formulieren sie ihre Sätze auch zu umständlich und nicht 'auf den Punkt'"*, and length is named as a possible criticism. → row R09, plus the em-dash batch B1.
4. **Thread of argument** — *"Der rote Faden ist manchmal etwas schwer nachzuvollziehen aber vorhanden, da sie dann immer mal wieder in unterschiedliche Aspekte eintauchen."* → structural rows R23, R33, R37, R38.

He also notes that the writing style and heading choices *help* readability (*"führt ihre Art zu schreiben und auch die Überschriften zu wählen zu einem guten Lesefluß"*) and that he does not wish to impose a different style. The fixes should therefore preserve voice while removing the specific tells he names.

### Not named in the email, revealed by the anchors

5. **Em-dash density** — flagged once (R10) but global: **469** instances of `---`. An independent reason to act is that heavy em-dash parentheticals are a recognisable LLM writing tell.
6. **Meta-headings** — headings that talk about the document rather than the subject matter (R24, R30/R31).

---

## 2. Method — how each target was pinned

**Highlights** carry `/QuadPoints`, so their target is exact by construction: each quad was matched against `pdftotext -bbox` word boxes on the same page.

**Sticky notes** carry only a 24×24 pt icon rect, which does not by itself say what the note refers to. The convention was therefore derived empirically: for all 18 stickies, the gap was measured from the icon's top edge to the nearest text line above and below (`y_top = 841.89 − rect[3]`).

**The convention is perfectly consistent — the target is the nearest text element, and the non-target is always ≥ 29 pt away.**

| Row | Nearest element | Gap (pt) | Next-nearest (pt) |
|---|---|---|---|
| R35 | "…the adapter learned exactly what it was shown." (above) | 1.05 | 31.32 |
| R33 | `7.7.4` heading (above) | 2.05 | 39.65 |
| R02 | citation cluster (above) | 2.55 | 29.83 |
| R38 | `10.3.2` heading (above) | 2.56 | 39.14 |
| R32 | failure-mode bullet (above) | 3.66 | 31.71 |
| R09 | dense-paragraph last line (below) | 5.26 | 12.68 |
| R04 | research-question list, last line (above) | 5.46 | 29.91 |
| R07 | terminology paragraph, last line (above) | 6.60 | 47.86 |
| R37 | `10.3` heading (below) | 8.19 | 46.50 |
| R34 | "…would have been the opposite." (above) | 8.30 | 308.42 |
| R31 | `7.1` heading (below) | 8.35 | 67.06 |
| R21 | `5.11` heading (above) | 13.95 | 33.86 |
| R36 | "…intervention on the models." (above) | 20.81 | 37.24 |
| **R26** | **"discarded to obtain it." (below)** | **0.61** | **33.30** |

Four stickies (R08, R14, R25, R28) sit beside figures rather than body text and are resolved by icon `x` instead: R08 at x 57.90 is in the **left margin**, outside the 70 pt text column, level with the `page image` node; R25 at x 478.86 and R28 at x 484.12 sit to the right of their figures at the height of the feature being questioned.

### Consequence for R26

R26 was the only genuinely contested target. Its nearest element is the **final line of the preceding paragraph at 0.61 pt**, against 33.30 pt to `A second class of exclusion was never declared.` — a 55× margin, the tightest binding of any sticky in the document. Three independent corroborations:

- `:108-125` is **the only passage in that area carrying no concrete values**. It states "Eight cells … carry values that *no* reading channel could locate" and "The exclusion was applied to exactly one field" without ever naming the field or showing a value.
- The following passage `:127-134` already supplies concrete figures (22 cells, 8 cells, all twenty-two are dates). It does not want for samples.
- §6.4 opens immediately afterwards with a concrete sample ("An invoice prints *Invoice no. 471102*"), plausibly the contrast that made their absence conspicuous.

**Therefore: add samples to `:108-125` only; leave `:127-134` untouched.** Adding samples there would duplicate figures the passage already states.

---

## 3. The register

IDs are assigned in **document order**. `K` = kind: `HL` highlight, `ST` sticky.

### Front matter

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R01 | 8/**VIII** | HL | *sehr intuitive Abkürzung ;)* | `ZUGFeRD` — quad x 70.87–133.80 matches the word exactly (`YAML` ends at 110.89, overlaps 1.5 pt only) · `preamble/acronyms.tex:62` | **None.** Ironic praise; the acronym is the standard's own name and cannot be changed | local |

### Chapter 1 — Introduction

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R02 | 11/**3** | ST | *Ich persönlich bevorzuge bei der Literaturangabe den IEEE oder ACM bibstyle - dort werden die Cites durch Nummern in Eckigen Klammern angegeben, was dann die Lesbarkeit verbessert.* | `\parencite{bstbk2026,brak2024ki,bstbkdsgvo}` → renders "(Bundessteuerberaterkammer, 2026b; Bundesrechtsanwaltskammer, 2024; Bundessteuerberaterkammer, 2026c)" · anchor `01-introduction.tex:67` · **fix `preamble/header.tex:205-221`** | Switch to numeric brackets. See batch **B3** and ADR-074 | **global** |
| `[ ]` R03 | 11/**3** | HL | *ist "company" nicht vielleicht der etabliertere Begriff* | `firm` — xMin 70.87 = quad xMin, first word of its rendered line · `01-introduction.tex:89` | Replace `firm` with `company`; sweep other uses for consistency | local |
| `[ ]` R04 | 13/**5** | ST | *sehr gut formuliert und strukturiert!* | the research-question list, last line "measurement?" (RQ4) · `01-introduction.tex:122-160` | **None.** Praise — preserve this structure through any rewrite | local |
| `[ ]` R05 | 13/**5** | HL | *§ ist nicht die gängige Bezeichnung für ein Kapitel. In englischen Arbeiten verwenden sie gerne "section" oder lassen sie das Symbol komplett weg (ggf. dann Schriftart auf bold setzen)* | `(§7.3)` = `(\S\ref{sec:results-reader})` · `01-introduction.tex:172` | See batch **B2** | **global** |
| `[ ]` R06 | 14/**6** | HL | *hier verwenden sie eine abweichende Bezeichnung* | `(Chapter` in "(Chapter~\ref{ch:measurement-validity});" · `01-introduction.tex:214` | Pairs with R05 — the document mixes `§7.3` and `Chapter 6`. See batch **B2** | **global** |
| `[ ]` R07 | 15/**7** | ST | *gute Einschränkung!* | `\paragraph{A note on terminology.}` — the OCR-free-is-architectural qualification · `01-introduction.tex:254-261` | **None.** Praise — keep the qualification | local |

### Chapter 2 — Background

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R08 | 18/**10** | ST | *wie sieht so ein page image bei text aus?* | **Figure 2.1, the `page image` node.** Icon at x 57.90, left margin · `figures/vlm-anatomy.tex:31` (`\node[endpoint…] (page) {page\\image};`), figure included at `02-background.tex:30-37` | Show what an actual input page image looks like — either a real sample page beside the schematic, or a sentence making the input concrete | local |
| `[ ]` R09 | 21/**13** | ST | *Wow, diesen Abschnitt musste ich mehrmals lesen ;)* | §2.2.1 "The semantic model and its carriers" — a **single 24-line paragraph** with 4 em-dash pairs, nested parentheticals and 5 citations · `02-background.tex:132-155` | Rewrite for readability: split into several paragraphs, remove the em-dash nesting, straighten the clause order. **Preserve precision and every claim** | local |
| `[ ]` R10 | 22/**14** | HL | *vielleicht etwas weniger mit diesen Gedankenstrichen arbeiten und dann lieber getrennte Sätze formulieren.* | the **first** `---` of the pair: "practice `---` reference data that was wrong or ill-posed". At x 115–127, immediately after "practice" (70→110) · `02-background.tex:210` | See batch **B1** | **global** |

### Chapter 3 — Related Work

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R11 | 29/**21** | HL | *Fast schon ein wenig zu umgangsprachlich - aber noch OK* | `\subsection{German invoices have been extracted before, and by whom}` · `03-related-work.tex:135` | Tighten the register. He concedes it is still acceptable, so this is optional — but it is a named instance of theme 1 | local |
| `[ ]` R12 | 32/**24** | HL | *eine sehr gute Idee dies immer mal wieder explizit anzugeben!* | `\textbf{What this thesis adds}:` — **the `:227` instance**. Disambiguated because `:220-221` is the first body line of that page; the other two instances are `:177` and `:258` · `03-related-work.tex:227` | **None.** Praise — keep the device and consider using it more | local |
| `[ ]` R13 | 33/**25** | HL | *besser: is located* | `sits` — quad x 200.16–217.54 brackets the word exactly · `03-related-work.tex:285` | Replace `sits` with `is located` | local |

### Chapter 4 — System Design

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R14 | 38/**30** | ST | *gute Übersicht!* | the pipeline figure — `pipeline.tex` is the only file containing the "instruments attach" labels visible on that page · `figures/pipeline.tex`, included at `04-system-design.tex:97-99` | **None.** Praise | local |
| `[ ]` R15 | 38/**30** | HL | *schon eher ein Füllsatz ohne zusätzliche Infos - derartige Sätze versuchen zu vermeiden* | "The design here does not do that." · `04-system-design.tex:112` | Delete. Also an instance of theme 2 (argue-by-negation) | local |
| `[ ]` R16 | 39/**31** | HL | *auch eher umgangssprachlich* | "won in both;" · `04-system-design.tex:131` | Replace with neutral phrasing | local |
| `[ ]` R17 | 45/**37** | HL | *Liefert keine neuen Informationen - ist lediglich eine Doppelung* | the bold block "**Layer 1 was built and measured. Layers 2 and 3 were designed and were neither implemented nor evaluated.** Everything reported in Chapters 7 and 9 concerns Layer 1." · `04-system-design.tex:353-355` | **Duplicates `:348`** ("Both commitments describe an intended design. Neither was implemented, and neither is claimed."), five lines above. Merge into one statement or delete the bold block | local |
| `[ ]` R18 | 45/**37** | HL | *definitiv zu umgangssprachlich - Fokus auf das was gemacht wurde und in der Diskussion dann relevante Aussagen zu Dingen die nicht gemacht bzw. berücksichtigt wurden. Das "not glossed" hier ist eigentlich nicht relevant und kann weggelassen werden.* | "not glossed." in "Two consequences are recorded, not glossed." · `04-system-design.tex:374` | Delete "not glossed" — he says so explicitly. Move any not-done material to the discussion | local |

### Chapter 5 — Methodology

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[-]` R19 | 46/**38** | HL | *sollte da dann nicht ein Fragezeichen folgen - ist in dieser Formulierung eigentlich ungeeignet als Überschrift. Das ist aber im gesamten Dokument ihr Styl und von daher zumindest konsequent durchgezogen und somit OK (aber für wiss. Arbeiten grenzwertig)* | `\section{What Is Measured}` · `05-methodology.tex:12` | **Declined** under the meta-headings-only scope (batch **B4**): this heading describes subject matter, not the document, and he concedes it is *"konsequent durchgezogen und somit OK"*. Revisit if the scope is widened | local |
| `[ ]` R20 | 58/**50** | HL | *Fall es später weiter verwendet wird, könnte man hier einen eindeutigen Bezeichner festlegen.* | `\textbf{Instrument one:` · `05-methodology.tex:442` | Give the instrument a stable identifier and use it at every later reference | local |
| `[ ]` R21 | 60/**52** | ST | *keine Einleitung?* | `\section{Reproducibility and Hardware}` · `05-methodology.tex:502`. Confirmed: `:505` opens directly on `\textbf{Configuration as data.}` with **no lead-in sentence** | Add an introductory paragraph before the first bold run-in | local |
| `[ ]` R22 | 60/**52** | HL | *auch wieder sehr umgangssprachlich* | "at the floor, not at the target," · `05-methodology.tex:526` | Rephrase neutrally. Also an instance of theme 2 | local |
| `[ ]` R23 | 61/**53** | HL | *hier könnten sie einfach eine Aufzählung mit Nummerierung verwenden* | `\textbf{One: adapter training}` — siblings confirmed at `Two:` `:543`, `Three:` `:550`, `Four:` `:555` · `05-methodology.tex:538-560` | Convert all four bold run-ins into a single numbered `enumerate` | local |

### Chapter 6 — Measurement Validity

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R24 | 63/**55** | HL | *definitiv nicht wissenschaftlich - hier kann man implizit von einer Relevanz aller Inhalte ausgehen und muss dies nicht im Section Header motivieren* | `\section{Why This Chapter Exists}` · `06-measurement-validity.tex:4` | Meta-heading — rename to a subject-matter title or drop the section header. See batch **B4** | local |
| `[ ]` R25 | 64/**56** | ST | *Hier ist eine Übelappung - gewollt?* | **Figure 6.1.** The dashed footnote node is hard-positioned `at (0,-11.3)` with no dependency on `c6`'s height; `c6` ("The near-miss --- precision confound") sits `anchor=west at (0.45,-9.9)` and is tall enough to collide · `figures/defect-chronology.tex:82-88` (footnote node), `:74-80` (`c6`) | Move the footnote node below `c6.south` — either increase the y-offset past `-11.3` or anchor it relative to `c6` instead of hard-coding. Exact offset is empirical; **verify by rebuilding** | local |
| `[ ]` R26 | 67/**59** | ST | *Konkrete Samples wäre hier sicher hilfreich* | **the preceding passage**, ending "…Not one correct answer was discarded to obtain it." Gap **0.61 pt** vs 33.30 pt — the tightest binding in the document · `06-measurement-validity.tex:108-125` | Name the field and show 1–2 example values (redacted as needed). **Do not add samples to `:127-134`** — it already states its figures, and duplicating them is exactly the redundancy to avoid. Derivation in § 2 | local |
| `[ ]` R27 | 68/**60** | HL | *Darstellung wieder durch Verneinung. Drücken sie das doch eher positiv und neutraler aus.* | "None of these is exotic." · `06-measurement-validity.tex:162` | Restate positively. Named instance of theme 2 — see batch **B5** | local |
| `[ ]` R28 | 72/**64** | ST | *eher Balken als Verlaufslinien bei nur zwei Messpunkten? (die zudem ja auch eigentlich unabhängig voneinander sind)* | the two-point line chart. **Generated asset**: `axes.plot(..., marker=…)` over 2 x-positions per arm · **`scripts/thesis_assets.py:1579-1580`** (function `figure_ruler_correction`, `_save` at `:1608`) → `figures/ruler-correction.pdf`, included at `06-measurement-validity.tex:312-314` | Switch to grouped bars. **This is a Python change plus asset regeneration, not a LaTeX edit.** The `annotate` offsets at `:1585` (−14) and `:1595` (+8) need retuning for bars | local |
| `[ ]` R29 | 73/**65** | HL | *wieder Argumentation über Verneinung - gibt hier keinen Mehrwert und macht den Text nur unnötig lang!* | "not a defect in" · `06-measurement-validity.tex:341` | Restate positively or delete. Named instance of theme 2 — see batch **B5** | local |

### Chapter 7 — Results

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R30 | 76/**68** | HL | *auch nicht geeignet für wiss. Arbeiten* | `\section{How to Read This Chapter}` · `07-results.tex:4` | Meta-heading — rename. See R31 for his proposed wording and batch **B4** | local |
| `[ ]` R31 | 76/**68** | ST | *eher etwas wie "General Remarks" oder einfach nur "Conventions"* | **the same heading** · `07-results.tex:4` | Pairs with R30 — **use his own wording**: "Conventions" or "General Remarks" | local |
| `[ ]` R32 | 80/**72** | ST | *gute Analyse* | the failure-mode bullet "…character-level slips *inside* values: a transposed letter, a duplicated digit." · `07-results.tex:142` | **None.** Praise | local |
| `[ ]` R33 | 92/**84** | ST | *das ist eigentlich schon eine Diskussion der Ergebnisse* | `\subsection{What this result does not cover}` — 6 lines, defers to ch.10 · `07-results.tex:480` | Move the interpretive content to ch.9, or reframe as a plain factual scope statement. Relates to theme 4 | local |
| `[ ]` R34 | 94/**86** | ST | *sehr gute Summary* | §7.8 Summary of Findings, at "…without which it would have been the opposite." · `07-results.tex:509` (section at `:489`) | **None.** Praise — preserve the summary format | local |

### Chapter 9 — Discussion

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R35 | 105/**97** | ST | *was kann man da in Zukunft anders / besser machen?* | "…every training target was a filled record. On that reading, the adapter learned exactly what it was shown." · `09-discussion.tex:144` | **The answer already exists in the thesis** at `10-limitations-future-work.tex:277` (`\subsection{Teach Abstention Rather Than Always Answering}`) but is not referenced here. Add the forward reference plus a sentence naming the remedy | local |

### Chapter 10 — Limitations & Future Work

| ID | PDF/pr | K | Comment (verbatim) | Target | Action | Scope |
|---|---|---|---|---|---|---|
| `[ ]` R36 | 117/**109** | ST | *sehr gut!* | `\textbf{Pre-process before reading.}`, ending "…an intervention on the image may be worth more than any intervention on the models." · `10-limitations-future-work.tex:263-266` | **None.** Praise | local |
| `[ ]` R37 | 117/**109** | ST | *Eventuell eigenes Kapitel, da hier doch eine Reihe sehr kurzer Unterkapitel mit eigener Kapitelnummer entstehen?* | `\section{Future Work}` · `10-limitations-future-work.tex:239`. Cause confirmed: subsections at `:245`, `:268`, `:277`, … each numbered 10.3.x | Promote Future Work to its own chapter. **Knock-on**: chapter renumbering in `main.tex`, every `\ref` to ch.10/11, and the abstract | local, high blast radius |
| `[ ]` R38 | 118/**110** | ST | *eigentlich zu kurz für eine eigene Subsection* | `\subsection{Measure Real Line Items}` — confirmed short: one paragraph, `:271-275` · `10-limitations-future-work.tex:268` | Merge into a neighbouring subsection or expand. Consider alongside R37 | local |

**Coverage**: no annotations in the abstract, ch.8 Implementation, ch.11 Conclusion, or the appendix.

**Tally: 38/38 targets exact.** 20 highlights by `/QuadPoints` word-box match, 18 stickies by the nearest-element rule of § 2. Nothing in this register is inferred.

---

## 4. Cross-cutting batches

Do these as single sweeps rather than per-row, or they will be done inconsistently.

### B1 — Em-dash thinning (from R10)

**469** instances of `---` (chapters 355, preamble 36, appendix 33, figures 29, tables 16). **18** sit inside `%` comments and are out of scope, leaving **451** live.

His words: *"vielleicht etwas weniger mit diesen Gedankenstrichen arbeiten und dann lieber getrennte Sätze formulieren"* — **somewhat fewer**. There is **no target count**. An earlier draft of this batch set one ("well under 50 survivors") and that was an over-reading of the source; it is withdrawn.

Policy — **thin, don't purge**. Change an em-dash where it is doing real damage:

1. **Two or more pairs in one sentence** — the construction that produced R09. Split into separate sentences.
2. **A pair wrapping a clause long enough that the main sentence is lost** — recast the aside as its own sentence.
3. **An em-dash in a sentence already carrying parentheses or a citation cluster** — demote to a comma or a full stop.

Leave a single em-dash marking a clean break in an otherwise short sentence. That is correct English punctuation, and he did not ask for its removal.

**Do not touch `---` inside `%` LaTeX comments.**

Secondary rationale, worth acting on but not worth over-correcting for: dense em-dash parentheticals are a recognisable LLM writing tell.

Chapter counts, for orientation only: 05 (53), 07 (39), 02 (38), 04 (36), 10 (34), 09 (33), 01 (32), 03 (28), 06 (23), 08 (20), 11 (15), 00 (4).

### B2 — Cross-reference convention (from R05 + R06)

**223** `\S\ref` and **93** `Chapter~\ref` across `thesis/`. The document currently mixes both forms, which is what R06 flags. Pick one convention and apply it everywhere. His suggestion for the `§` form is to spell out "section" or drop the symbol.

Per-chapter `\S\ref`: 10 (33), 09 (22), 02 (21), 04 (19), 03 (18), 06 (17), 07 (14), 11 (11), 01 (10), 05 (9), 08 (9).

### B3 — Bibliography style (from R02)

Switch `preamble/header.tex:205-221` from `style=authoryear` to a numeric bracketed style. Two dependencies:

- **The existing rationale comment is falsified.** `header.tex:206-211` claims `authoryear` was chosen *"per the first examiner's established preference"* — an **inference** from two prior graded works under the same supervisor. His written comment asks for the opposite. The comment must be rewritten, not just the option.
- **17 `\textcite` call sites** (03: 10, 09: 4, 05: 2, 02: 1) read badly under numeric styles when used as a sentence subject. Each needs rephrasing to `\parencite`, or an explicit author mention with the numeric cite appended.

Ratified in **ADR-074**.

### B4 — Meta-headings (from R24 + R30/R31)

Scope: **headings that talk about the document rather than the subject matter.** The examiner's own §6.1 reasoning supports this boundary — *"hier kann man implizit von einer Relevanz aller Inhalte ausgehen"*.

- **Change**: `Why This Chapter Exists` (R24) and `How to Read This Chapter` (R30/R31 → "Conventions" or "General Remarks", his wording).
- **Handled separately**: `What this result does not cover` (R33 — flagged as misplaced discussion, not as a heading-style problem).
- **No change**: the other 12 question-form headings (`Why the Adaptation Failed`, `Where the Shortfall Sits`, `What Generalises`, `Why the first attempt failed`, …). They describe subject matter, and he called the style *"konsequent durchgezogen und somit OK"*.
- **Declined**: R19 `What Is Measured` — subject-matter, and conceded OK. This is the one place the chosen scope declines a comment he actually wrote; recorded deliberately.

### B5 — Argue-by-negation (from R27 + R29, and email theme 2)

Three known instances: R27 and R29 (both ch.6), plus R15 (`04-system-design.tex:112`) found by the anchors.

The email calls it a habit — *"Sie arbeiten bei ihrem Stil auch gerne damit zunächst eine Verneinung zu formulieren"* — so look beyond the three. But the target is the **rhetorical construction** he described: opening with a negation, then defining the work against it. A sentence that merely contains "not" is **not** an instance. His own remedy is *"kürzer und neutraler"*, so prefer deletion or a short positive restatement over an elaborate rewrite.

### B6 — Colloquial register (from R11, R15, R16, R18, R22, and email theme 1)

Five explicit instances. He asks for one critical pass for *Umgangssprache*, so treat the five as samples of a class rather than the complete list — but calibrate to his own dose: *"manchmal grenzwertig und **selten** auch nicht angemessen"*. Rare, not pervasive.

**R11 is the ceiling, not the floor.** He marked `German invoices have been extracted before, and by whom` as *"Fast schon ein wenig zu umgangsprachlich - **aber noch OK**"*. Anything at or above that register is acceptable and stays. Fix only what is clearly below it.

---

## 5. Suggested sequencing

Mechanical and low-risk first, so the prose work happens against a stable document:

1. **B3** bibliography (single file + 17 call sites) — changes every citation's rendering, so do it before proofreading prose.
2. **R25** figure overlap, **R28** chart type — isolated, verifiable by rebuild.
3. **R03**, **R13**, **R15**, **R16**, **R18** — single-word and single-sentence fixes.
4. **B2** cross-references, **B4** meta-headings — mechanical, wide.
5. **B1** em-dashes — wide, judgement-heavy.
6. **R09** dense-paragraph rewrite, **B5**, **B6** — prose work.
7. **R08**, **R21**, **R26**, **R35** — new content.
8. **R23**, **R33**, **R37**, **R38** — structural, highest blast radius. **R37** last.

After every batch: `make thesis` and confirm the PDF builds with no new overfull boxes.

---

## 6. Provenance

- Anchors extracted with `pypdf` (annotation `/Rect`, `/QuadPoints`, `/Contents`, `/T`) and `pdftotext -bbox` (word boxes), both against the review PDF.
- Coordinate transform `y_top = 841.89 − rect[3]`, validated to 2 dp.
- Byte-identity of the review PDF's text layer with `thesis/_build/main.pdf` at `485d1a9` is what makes these line numbers safe to act on. **If the manuscript is edited before a row is addressed, re-verify that row's line number** — the anchors are line-numbered against that commit.
