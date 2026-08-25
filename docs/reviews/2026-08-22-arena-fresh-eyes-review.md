# 2026-08-22 — Fresh-eyes arena review (three independent AI reviewers)

**Scope**: full-manuscript fresh-context review for residual content, terminology,
pattern and consistency defects after the 2026-08-18 examiner registry and the
2026-08-20 Feinschliff. Three independent reviewers were run in parallel on the
same 141-page build (`Fable 5 max`, `Opus 5 max`, `GPT 5.5 xhigh`); every finding
was then **verified against the `.tex` source, the generators, the ADR trail and
the rendered PDF (`pdftotext` + page images) before any fix was applied**. No
finding was accepted on a reviewer's claim alone; several were rejected as wrong.

**Verification session**: one session. Fix branch:
`docs/arena-fresh-eyes-fixes`.

## Confirmed and fixed — MAJOR (examiner-visible)

| # | Defect | Evidence | Fix |
|---|---|---|---|
| M1 | "an False Positive / an False Negative" rendered on p. 15 — article set for the short form, first use expands | `02-background.tex` FP/FN definitions after `\acresetall` | "a \ac{FP} / a \ac{FN}"; later short-form "an FP/FN" uses unchanged |
| M2 | Table 7.11 caption "Photographed documents…" + note "0.9148 vs 0.7889, gap 12.6 points" — contradicts the corpus's own channel definition (scans, not photographs) and mixes both languages' emails against German-only scans while body prose says "more than eleven points" | generated `tables/heldout-by-channel.tex`; body denials at `05:106`, `07:437` | Generator (`scripts/thesis_assets.py`): caption → "Phone-scanned documents…"; note → like-for-like "German email-native 0.9027 vs 0.7889 German phone scans, 11.4 points"; `11-future-work.tex` "ten photographed" → "ten phone-scanned" |
| M3 | Circular self-reference: §1.3 said "Section 1.3 states…" about itself (`\ref{sec:rq-map}` on a starred subsection resolves to the enclosing section) | `01-introduction.tex:137,162` | "the mapping at the end of this section states…"; dead label removed (zero other refs) |
| M4 | **Found by the verifying session, missed by all three reviewers**: nested first-use expansion "16-bit (brain floating-point, 16-bit (bfloat16))" on p. 10 | `02-background.tex:92` | "the \ac{bf16} representation" — expansion supplies the parenthetical once |

## Confirmed and fixed — MINOR (~22 word-level items)

- **Truth-precision on absolutes** (GPT): "no model provider processed anything at
  any point" scoped to "in these passes" (the answer-key channels are cloud and
  disclosed); "every number in this manuscript is generated / typed by no hand"
  (4 sites: ch. 7 conventions, ch. 8 operational interface, ch. 12, appendices E/F)
  scoped to "every measured table and chart… prose repeats only values those
  artefacts record" — 9 TikZ figures are hand-authored diagrams of designs.
- **H8 disposition mislabel** (Fable): ch. 1 said "registered-but-unevaluated /
  comparison was not run"; the register says formalised 2026-05-31, memory clause
  evaluated 7/8, decode clause not cleanly evaluable — a final position. Ch. 1 now
  matches the register.
- **Figure/prose contradictions** (Fable): GT-adjudication figure routed
  "claimed absent" into the 463-warrant box (prose: 463 = printed proof +
  two-channel; 1,326 − 463 − 248 = 615) → own "accepted as absences — 615 cells"
  sink; pipeline figure's bare "1./2." instrument labels → ch. 5's stable names
  ("Instrument two, per-miss findability" / "Instrument three, the perfect-text
  ceiling"), completing R20's intent.
- **Statute spacing** (Fable/Opus): 15 unspaced `\S14`-style refs across 6 files
  harmonized to `\S~14` (spaced form already used in ch. 2 + bibliography).
- **Reader-selection narrative** (Opus): the third aggregate ordering flip
  (Table 7.2: 0.970 vs 0.965) now named in prose; the two MinerU rows acknowledged
  (same corrected ruler; the later checkpoint's repetition-loop collapse per
  ADR-057 explains its miss count).
- **Ch. 2 duplication** (Opus/Fable): the 8-line "A note on names…" paragraph
  re-argued ch. 1 §1.5's R07-praised terminology note → condensed to 3 lines
  pointing back, keeping the three model names; also removed its verbless opener.
- **Abbreviations list** (Opus): bfloat16 sorted before BRAO; CUDA (printed
  verbatim in generated arm labels) added via one `\ac{CUDA}` in a generated
  protocol note + `\acused` + `\phantomsection\label{acro:CUDA}` anchor in the
  ch. 5 venue paragraph (the list links to first use).
- **Consistency sweep**: ch. 12 starred headings → Title Case; "tax company" →
  "tax-consulting company"; "premises-class hardware" → "hardware a company
  plausibly owns"; "open-weight" → "open-weights"; "percent sign" → "per cent
  sign"; "commodity, on-premises" comma dropped; "false- negative" line-wrap
  rejoined; "Section 6.3–Section 6.6" → "Sections 6.3 to 6.6"; caption comma
  splice → semicolon (Fig. 7.3); apposition repaired (ch. 9 "rather than
  *through* a third-party model service —"); "463 of the decided cells" → "463
  cells" (ch. 9); appendix header gains H7's disposition; pronoun and Oxford-comma
  nits (appendix); Fig. 2.2 caption notes scale labels follow published names;
  pipeline figure "300 dpi" → "300 DPI".

## Rejected findings (verified wrong or deliberately not applied)

- **"Comma splice" at 01:38** (Opus) — a valid clausal series with a final
  coordinator, not a splice. Contrastive splices at 02:285/04:75 are consistent
  deliberate rhetoric.
- **Abstract's repeated "hardware …already owns"** (Opus) — deliberate bookend
  (opening premise → closing deployment note); both articles contextually correct.
- **Missing chapter lead-ins for ch. 6/7/9** (Opus/Fable) — orientation exists as
  §6.1/§7.1/§9.1; new prose two days before hand-in is unwarranted risk.
- **"MinerU rows unexplained"** (Opus) — partially wrong: the 8B sibling *is*
  discussed at length (§7.3.3); only the MinerU sentence was missing (added).
- **Registry "141 pages" claim** (Opus) — a dated verification record, accurate at
  its close; historical records are not amended.
- **F$_1$/`\ac{F1}` source split, `1,129` unbraced comma, quotchap deprecation
  warnings, `sec:results-reading` stale label (zero refs)** — print-identical or
  zero-render-impact; not worth churn.

## Repo-hygiene fixes (no PDF impact)

- `AGENTS.md` still described the citation style as `authoryear` → `numeric-comp`
  per ADR-074 (examiner's written instruction, R02).
- `docs/prompts/stages/05-writeup.md`: chapter map updated for the R37 split,
  waves 4c–4e recorded, stale citation-style open item resolved.
- `thesis/README.md`: status paragraph records this pass; chapter count corrected
  (twelve numbered chapters; "thirteen" had double-counted the abstract);
  141 pp build state.

## Verification at close

`make thesis-assets` deterministic (only the two intended strings changed in
`heldout-by-channel.tex`); `make thesis-clean && make thesis` → **141 pages, zero
overfull boxes, zero unresolved references/citations/hyperlinks**; render greps
confirm every defect pattern gone ("an False", "false- negative", "Photographed",
"Section 1.3 states", nested bfloat16, unspaced statute §); page images inspected
for every changed figure/table/heading (Fig. 4.2, Fig. 5.2 — re-laid out twice to
eliminate sink-box overlap — Table 7.2, Table 7.11, ch. 12 headings, abbreviations
page, ch. 2 ending — still orphan-free on p. 16); `make test` → 1,265 passed.
Body ends printed p. 114, within the 120-page Richtlinie wall.
