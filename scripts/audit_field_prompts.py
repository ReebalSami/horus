#!/usr/bin/env python3
"""Audit the FIELDS registry's prompt surface against the ACTUAL corpus.

Every ``description`` and ``prompt_alias`` in the registry is an assertion about
what invoices really print. Written from memory, those assertions rot: an alias
nobody prints is dead weight in the prompt (and ADR-048 measured over-glossing as
net-NEGATIVE), while a label the corpus *does* print but the registry omits is a
findability gap the model pays for. This script replaces belief with measurement.

Checks performed, per field:

**A. alias grounding** — does each ``prompt_alias`` literally occur in the corpus
reader transcripts? An alias with 0 hits is UNFOUNDED: either invented, or a
different corpus's wording. Reported so it can be justified or dropped.

**B. rendered-label grounding** — the label `render_oracle_transcript` prints
(``FieldSpec.rendered_label``: ``printed_label`` if set, else ``german_label``)
must occur in the corpus. This one GATES (ADR-059), because an ungrounded oracle
label does not merely make the ceiling optimistic — it makes it WRONG in an
unpredictable direction: `charge_total_amount` scored 0.000 on the perfect page
while scoring 0.889 on real reader text, purely because the spec wording
"Summe Zuschläge" occurs 0/146 while "Gesamtbetrag der Zuschläge" occurs 88/146.

Five fields have no printed label anywhere in the corpus (composite addresses,
document type, rounding, Skonto basis); they are listed in
``_NO_PRINTED_LABEL_REASONS`` with a written reason each and reported as
documented exceptions. A field NOT on that list whose rendered label is
ungrounded fails the gate; a field ON the list whose label turns out to BE
grounded also fails, so the exception list cannot silently go stale.

Checked for the flat ``FIELDS`` registry **and** for every repeating-group cell
(``vat_breakdown`` / ``skonto`` / ``line_items``) — the group cells are rendered
into the same oracle page but were previously never audited at all, which hid 10
further ungrounded labels on the surface carrying the most gradable cells.

Note ``german_label`` itself is deliberately NOT required to be grounded: it is
the canonical EN16931 term, it is not prompt text, and `adapters.py` compiles the
FROZEN regex baseline from it (ADR-037).

**C. missing aliases** — for each invoice where the field's GT value is present,
find the transcript line carrying that value and report its leading label. A
frequent label that is NOT in ``prompt_aliases`` is a concrete, evidence-backed
addition.

**D. glossary hygiene** — flags fields that are glossed but have no aliases, and
descriptions that contain a stale ADR reference or exceed a length that crowds the
prompt.

**E. no-leakage guardrail** — no ground-truth value of any invoice may appear in ANY
string the field contributes to the prompt. Covers ``prompt_aliases`` as well as
``description``, and runs whether or not the field is glossed: aliases render as
"printed as: <alias>", so an answer sitting in one reaches the model just as a
leaked description would.

Run:

    uv run python scripts/audit_field_prompts.py
    uv run python scripts/audit_field_prompts.py --field allowance_total_amount

Exit code is 1 when any UNFOUNDED alias/label or leaked value is found, so this is
usable as a gate; 0 otherwise. Advisory findings (missing aliases) never fail.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horus.eval.ground_truth import FIELDS, REPEATING_GROUPS, FieldSpec  # noqa: E402

# Fields for which NO printed label exists anywhere in the corpus, so
# `render_oracle_transcript` necessarily falls back to the synthetic EN16931 term.
# Each entry needs a written reason; the gate fails on an ungrounded label that is
# NOT here, and equally on an entry here whose label IS grounded (a stale
# exception). Keys are qualified with the group name for repeating-group cells,
# since sub-field names are only unique within their group.
_NO_PRINTED_LABEL_REASONS: dict[str, str] = {
    "seller_address": (
        "composite address, printed UNLABELLED in the letterhead block; 'Anschrift' "
        "(27/146) occurs only inside Rechnungs-/Lieferanschrift, a different thing"
    ),
    "buyer_address": (
        "composite address, printed UNLABELLED in the customer block (as seller_address)"
    ),
    "document_type": (
        "pages print the type WORD itself as a heading ('Rechnung' 121/146), never a "
        "'Belegart:' label in front of it — there is a value but no label (ADR-046)"
    ),
    "rounding_amount": (
        "'Rundungsbetrag' / 'Rundung' / 'Rundungsdifferenz' all 0/146; BT-114 occurs on "
        "1/146 invoices and that page prints no rounding label"
    ),
    "skonto.basis_amount": (
        "all Skonto-basis spellings 0/146; the generic 'Basisbetrag' (90/146) is the VAT "
        "table's taxable-base column, so borrowing it would render a WRONG label"
    ),
    "vat_breakdown.category_code": (
        "'Steuerkategorie' 0/146; 'Umsatzsteuer' (97/146) labels the VAT SECTION, not the "
        "EN16931 category LETTER, so borrowing it renders 'Umsatzsteuer: S' — measured 11 "
        "oracle FNs (1.000 -> 0.831) vs 0 for 'Steuerkategorie: S'. The letter itself is "
        "never printed either, which is why predicted_normalize exists for this cell"
    ),
}

# `_canon` is private but deliberately reused: it is the transcript canonicalizer the
# #114 findability audit validated (lowercase + markdown-strip + German umlaut fold +
# whitespace collapse). Re-implementing a second folding rule here would let the two
# drift, and a drifted fold silently turns real matches into UNFOUNDED verdicts.
from horus.finetune.answerability import _canon, value_variants  # noqa: E402
from horus.finetune.config import FinetuneConfig  # noqa: E402
from horus.finetune.dataset import build_records, reader_text_from_transcript  # noqa: E402

# A label printed on an invoice may differ from the registry spelling by case,
# umlaut composition (NFC vs NFD), or run-together whitespace. Fold all three
# before comparing, so a real match is never reported as UNFOUNDED.
_WS_RE = re.compile(r"\s+")


def _fold(text: str) -> str:
    """Canonicalize for comparison, insensitive to case/umlaut-form/whitespace.

    NFC first so a decomposed "a + combining diaeresis" reaches `_canon`'s literal
    "ä" -> "ae" fold; otherwise NFD-encoded transcripts miss every umlaut alias.
    """
    return _canon(unicodedata.normalize("NFC", text))


# The reader emits docling DocTags, so a "line" is markup: table cells are
# `<fcel>`-delimited and text blocks carry `<loc_N>` bounding boxes. Turning every
# tag into a separator makes the cell BEFORE a value the label, which is what a
# human reads off the page. Without this the audit reports '<fcel>' as the label.
_DOCTAG_RE = re.compile(r"<[^>]*>")
_LABEL_SPLIT_RE = re.compile(r"[:|]")

# A label candidate must contain at least three consecutive letters. Amount cells
# ("0,23"), bare dates and code fragments are neighbouring VALUES, not labels, and
# reporting them as "labels seen" buries the real findings in noise.
_LABELLIKE_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def _leading_label(clean: str, value: str) -> str:
    """Best-effort extraction of the label introducing ``value``.

    ``clean`` must already have DocTags replaced by ``|`` separators (the caller does
    this once per line). Takes the last delimited segment left of the value: table
    rows carry several cells per line, and the nearest one is the label.
    """
    idx = clean.find(value)
    head = clean[:idx] if idx > 0 else clean
    segments = [s for s in _LABEL_SPLIT_RE.split(head) if s.strip()]
    candidate = segments[-1] if segments else head
    return _WS_RE.sub(" ", candidate).strip(" .-\t|*#") or "(no label)"


#: A ground-truth value shorter than this is vocabulary, not an answer — requiring 4+
#: characters stops the guardrail flagging "EUR" or a one-digit VAT rate.
MIN_LEAKED_VARIANT_CHARS = 4


class Leak(NamedTuple):
    """One ground-truth value found inside a string the prompt shows the model."""

    surface_kind: str  # "description" | "alias"
    surface_text: str
    variant: str  # the GT value, in the printed form that matched
    invoice: str  # which invoice's answer it is


def find_leaked_value(
    surfaces: Sequence[tuple[str, str]],
    variants_by_invoice: Sequence[tuple[str, Collection[str]]],
    *,
    min_variant_chars: int = MIN_LEAKED_VARIANT_CHARS,
) -> Leak | None:
    """First ground-truth value appearing in any prompt-visible ``surfaces`` string.

    ``surfaces`` is ``(kind, text)`` pairs — every string this field contributes to the
    prompt, i.e. its ``description`` **and** each of its ``prompt_aliases``.
    ``variants_by_invoice`` is ``(invoice_stem, printed_variants)``; matching the printed
    variants rather than only the canonical value is what catches a description saying
    ``01.06.2018`` for a GT stored as ``2018-06-01``.

    Returns the first `Leak` found, or ``None``. Pure, so the guardrail is testable
    without a corpus — it previously lived inline in `main` and could only be exercised
    by running the whole audit.
    """
    for surface_kind, surface_text in surfaces:
        folded_surface = _fold(surface_text)
        for invoice, variants in variants_by_invoice:
            # Sorted because `value_variants` returns a set: without this, WHICH leak is
            # reported first would follow hash order, so a gate failure would not
            # reproduce identically run-to-run.
            for variant in sorted(variants):
                # Length is judged on the value as written; a 1-3 char value is the
                # field's vocabulary ("EUR", "19", "S"), not an answer.
                if len(variant) < min_variant_chars:
                    continue
                # BOTH sides folded. `value_variants` returns values as written, while
                # `_fold` lowercases and transliterates umlauts (ä -> ae), so comparing
                # a raw needle against a folded haystack could only ever match values
                # that were already lowercase ASCII. That silently exempted most German
                # text values from the guardrail, since German nouns, company names and
                # VAT ids are all capitalized — dates and amounts matched, "Überweisung
                # auf unser Konto" did not. Regression-tested in
                # tests/test_audit_field_prompts.py.
                if _fold(variant) in folded_surface:
                    return Leak(surface_kind, surface_text, variant, invoice)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", default=None, help="audit only this field")
    # A bare FinetuneConfig() would select the SUPERSEDED granite-258M reader (the
    # dataclass default); ADR-057 made Qwen3-VL-4B canonical and only the YAML says
    # so. Auditing against a weak reader's transcripts would report labels that ARE
    # printed as UNFOUNDED, purely because that reader failed to read them.
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/finetune-structurer.yaml"),
        help="finetune config selecting the reader lineage to audit against",
    )
    parser.add_argument(
        "--max-description-chars",
        type=int,
        default=240,
        help="flag descriptions longer than this (prompt-budget hygiene)",
    )
    args = parser.parse_args()

    cfg = FinetuneConfig.from_yaml(args.config)
    records = build_records(
        Path(cfg.corpus_root),
        transcript_dir=Path(cfg.transcript_dir),
        reader_model=cfg.reader_model,
    )
    usable = [r for r in records if r.ready and r.gt is not None]
    if not usable:
        raise SystemExit("no records with both GT and a cached transcript")

    texts: dict[str, str] = {}
    for rec in usable:
        assert rec.transcript_path is not None
        texts[rec.stem] = reader_text_from_transcript(rec.transcript_path)
    folded = {stem: _fold(text) for stem, text in texts.items()}

    keys = [args.field] if args.field else list(FIELDS)
    if args.field and args.field not in FIELDS:
        raise SystemExit(f"unknown field {args.field!r}")

    # Gating vs advisory is a real distinction, not a severity dial:
    #   * an ungrounded ALIAS is text sent to the model claiming "invoices print this",
    #     which is false and costs prompt budget (ADR-048: over-glossing is
    #     net-NEGATIVE) -> gates.
    #   * an ungrounded RENDERED label is the text the oracle page shows the model, so
    #     it silently corrupts the ceiling measurement (ADR-059) -> gates, unless the
    #     field is a documented no-printed-label exception.
    #   * `german_label` on its own is neither: not prompt text, and the frozen regex
    #     baseline compiles from it (ADR-037) -> not checked here at all.
    unfounded_aliases: list[str] = []
    unfounded_labels: list[str] = []
    stale_exceptions: list[str] = []
    documented_exceptions: list[str] = []
    leaks: list[str] = []
    missing: list[str] = []
    glossed_no_alias: list[str] = []
    too_long: list[str] = []

    def check_rendered_label(qualified: str, spec: FieldSpec) -> list[str]:
        """Gate one spec's oracle-rendered label; returns findings to print."""
        found: list[str] = []
        label = spec.rendered_label
        hits = sum(1 for f in folded.values() if _fold(label) in f)
        reason = _NO_PRINTED_LABEL_REASONS.get(qualified)
        if hits == 0 and reason is None:
            found.append(
                f"  UNGROUNDED ORACLE LABEL   {label!r} — 0/{len(folded)} transcripts; "
                "the oracle page would show a wording no invoice prints"
            )
            unfounded_labels.append(f"{qualified}: {label!r}")
        elif hits == 0:
            found.append(f"  documented exception — no printed label exists ({reason})")
            documented_exceptions.append(qualified)
        elif reason is not None:
            found.append(
                f"  STALE EXCEPTION   {label!r} is grounded ({hits}/{len(folded)}) but "
                "still listed in _NO_PRINTED_LABEL_REASONS — remove the entry"
            )
            stale_exceptions.append(f"{qualified}: {label!r} ({hits}/{len(folded)})")
        return found

    print(f"corpus: {len(usable)} invoices with GT + cached transcript")
    print(f"reader: {cfg.reader_model}")
    print()

    for key in keys:
        spec = FIELDS[key]
        aliases = spec.prompt_aliases or ()
        findings: list[str] = []

        # --- B. rendered-label grounding (GATES; ADR-059) -----------------------
        findings.extend(check_rendered_label(key, spec))

        # --- A. alias grounding -------------------------------------------------
        for alias in aliases:
            hits = sum(1 for f in folded.values() if _fold(alias) in f)
            if hits == 0:
                findings.append(f"  UNFOUNDED ALIAS   {alias!r} — 0/{len(folded)} transcripts")
                unfounded_aliases.append(f"{key}: {alias!r}")

        # --- D. glossary hygiene ------------------------------------------------
        if spec.description is not None:
            if not aliases:
                findings.append(
                    "  GLOSSED, NO ALIASES — model gets semantics but no label to look for"
                )
                glossed_no_alias.append(key)
            if len(spec.description) > args.max_description_chars:
                findings.append(f"  LONG description  {len(spec.description)} chars")
                too_long.append(f"{key} ({len(spec.description)})")

        # --- E. no-leakage guardrail -------------------------------------------
        # No GT value of ANY invoice may appear in ANY string this field contributes to
        # the prompt. Checked against the PRINTED variants too, not just the canonical
        # form: a description saying "01.06.2018" leaks a GT stored as "2018-06-01",
        # and an ISO-only comparison would wave it through.
        #
        # Covers `prompt_aliases` as well as `description`, and runs whether or not the
        # field is glossed. Previously it was nested under `description is not None` and
        # folded only the description, which left two holes: an alias could carry an
        # answer unchecked, and a field with aliases but NO description got no leak
        # check at all. Aliases render into the prompt as "printed as: <alias>", so a
        # value there reaches the model exactly as a description would. This is not
        # hypothetical — `payment_means_text`'s ground truth IS a payment-method
        # phrase, so a plausible-looking alias for it is indistinguishable from an
        # answer, and ADR-058 records an earlier description that leaked two corpus
        # values before the guardrail existed.
        surfaces: list[tuple[str, str]] = []
        if spec.description is not None:
            surfaces.append(("description", spec.description))
        surfaces.extend(("alias", alias) for alias in aliases)

        variants_by_invoice: list[tuple[str, Collection[str]]] = []
        for rec in usable:
            assert rec.gt is not None
            gt_rec = rec.gt.header[key]
            if not gt_rec.is_present:
                continue
            variants_by_invoice.append(
                (rec.stem, value_variants(gt_rec.raw_value, gt_rec.normalized_value, key))
            )

        leak = find_leaked_value(surfaces, variants_by_invoice)
        if leak is not None:
            findings.append(
                f"  LEAKED GT VALUE   {leak.variant!r} in {leak.surface_kind} "
                f"{leak.surface_text!r} (from {leak.invoice})"
            )
            leaks.append(f"{key} [{leak.surface_kind}]: {leak.variant!r}")

        # --- C. missing aliases -------------------------------------------------
        observed: Counter[str] = Counter()
        for rec in usable:
            assert rec.gt is not None
            gt_rec = rec.gt.header[key]
            if not gt_rec.is_present or not gt_rec.raw_value:
                continue
            # The printed form is what a page shows, so search the printed variants
            # (German-grouped amounts, dd.mm.yyyy dates) not just the CII raw value.
            needles = [
                v
                for v in value_variants(gt_rec.raw_value, gt_rec.normalized_value, key)
                if len(v) >= 3
            ]
            # Scan EVERY line, not just the first hit: a money value like "0,23"
            # also occurs in unrelated line-item cells, and first-match would report
            # that neighbouring number as the label. Numeric-only candidates are
            # dropped below, which leaves the real text label standing.
            for line in texts[rec.stem].splitlines():
                clean = _DOCTAG_RE.sub("|", line)
                folded_line = _fold(clean)
                matched = next((n for n in needles if n in folded_line), None)
                if matched is None:
                    continue
                anchor = next((n for n in needles if n in clean), None)
                label = _leading_label(clean, anchor if anchor else "")
                if _LABELLIKE_RE.search(label):
                    observed[label] += 1
        known = {_fold(a) for a in (*aliases, spec.german_label, spec.rendered_label)}
        novel = [
            (lbl, n) for lbl, n in observed.most_common() if _fold(lbl) not in known and n >= 2
        ]
        if novel:
            shown = ", ".join(f"{lbl!r}×{n}" for lbl, n in novel[:5])
            findings.append(f"  LABELS SEEN, NOT LISTED: {shown}")
            missing.append(f"{key}: {shown}")

        if findings:
            print(f"{key}  ({spec.bt_code})")
            for finding in findings:
                print(finding)
            print()

    # Repeating-group cells are rendered into the same oracle page as the flat
    # fields, so their labels need the same gate. Only the label check applies:
    # group cells carry no description/aliases (deliberately — ADR-053 measured
    # glossing them as net-negative), so checks A/C/D have nothing to inspect.
    if not args.field:
        for group, (_row_xpath, sub_fields) in REPEATING_GROUPS.items():
            for sub_key, sub_spec in sub_fields.items():
                qualified = f"{group}.{sub_key}"
                group_findings = check_rendered_label(qualified, sub_spec)
                if group_findings:
                    print(f"{qualified}  ({sub_spec.bt_code})")
                    for finding in group_findings:
                        print(finding)
                    print()

    print("=" * 78)
    print("GATING (text the model actually reads — prompt surface + oracle page)")
    print(f"  UNGROUNDED ALIASES        : {len(unfounded_aliases)}")
    print(f"  LEAKED GT VALUES          : {len(leaks)}")
    print(f"  UNGROUNDED ORACLE LABELS  : {len(unfounded_labels)}  {unfounded_labels}")
    print(f"  STALE LABEL EXCEPTIONS    : {len(stale_exceptions)}  {stale_exceptions}")
    print("ADVISORY")
    print(
        f"  documented no-label fields: {len(documented_exceptions)}  {documented_exceptions}"
        "  (oracle stays synthetic for these, by design)"
    )
    print(f"  glossed w/o aliases       : {len(glossed_no_alias)}  {glossed_no_alias}")
    print(f"  long descriptions         : {len(too_long)}  {too_long}")
    print(f"  labels not listed         : {len(missing)}")

    failed = bool(unfounded_aliases or leaks or unfounded_labels or stale_exceptions)
    print()
    print(
        "RESULT: FAIL — ungrounded/leaking content reaches the model" if failed else "RESULT: PASS"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
