"""Datasheet-for-Datasets renderer (Gebru et al. 2018; ADR-025 Phase A skeleton).

This module ratifies the per-dataset documentation template adopted by
ADR-025 across all 7 EDA chapters. Each chapter ends with a Datasheet
appendix entry covering the seven canonical sections proposed in
Gebru et al. 2018, *Datasheets for Datasets* (arXiv:1803.09010):

  1. Motivation       — for what purpose was the dataset created?
  2. Composition      — what do instances represent? schemas / labels / annotations?
  3. Collection       — how was the data acquired? sampling / consent / who?
  4. Preprocessing    — was raw data cleaned / normalized / labeled?
  5. Uses             — what tasks has it been used for? what NOT?
  6. Distribution     — license? maintainer? hosting?
  7. Maintenance      — versioning? errata channel? lifetime?

The :class:`Datasheet` Pydantic model is the schema; :func:`render_to_qmd`
produces the markdown chunk that gets concatenated into
`experiments/A1-datasheets.qmd` (the consolidated appendix).

Phase A ships the model + renderer + tests; per-chapter Datasheet
instances are populated in Phases B–C as their chapters land.

Refs: ADR-025 §"Decision" + §"Source archival",
docs/sources/papers/gebru-2018-datasheets-for-datasets.md.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasheetSection(BaseModel):
    """One Q&A pair within a Datasheet section.

    The `question` field mirrors the canonical Gebru et al. 2018 question
    text verbatim (so the Datasheet output is greppable against the
    original paper); the `answer` is the per-dataset response.
    """

    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class Datasheet(BaseModel):
    """One dataset's Datasheet entry (Gebru et al. 2018 §3 schema).

    Each of the seven `motivation` / `composition` / `collection` /
    `preprocessing` / `uses` / `distribution` / `maintenance` lists holds
    Q&A pairs for that section. Sections may be empty (skipped) when
    inapplicable to the dataset — but per ADR-025 the canonical questions
    should be answered with explicit "N/A — see <reason>" rather than
    omitted, so reviewers can distinguish "answered: not applicable" from
    "skipped: oversight".
    """

    slug: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(..., min_length=1)
    motivation: list[DatasheetSection] = Field(default_factory=list)
    composition: list[DatasheetSection] = Field(default_factory=list)
    collection: list[DatasheetSection] = Field(default_factory=list)
    preprocessing: list[DatasheetSection] = Field(default_factory=list)
    uses: list[DatasheetSection] = Field(default_factory=list)
    distribution: list[DatasheetSection] = Field(default_factory=list)
    maintenance: list[DatasheetSection] = Field(default_factory=list)


_SECTION_HEADERS: tuple[tuple[str, str], ...] = (
    ("motivation", "Motivation"),
    ("composition", "Composition"),
    ("collection", "Collection process"),
    ("preprocessing", "Preprocessing / cleaning / labeling"),
    ("uses", "Uses"),
    ("distribution", "Distribution"),
    ("maintenance", "Maintenance"),
)


def render_to_qmd(datasheet: Datasheet) -> str:
    """Render a :class:`Datasheet` into a Quarto-markdown string.

    The output is the markdown chunk for one dataset's entry in
    `experiments/A1-datasheets.qmd`. Wraps each section in a level-2
    heading; each Q&A pair becomes a bolded question + paragraph answer.

    Empty sections render as a placeholder line so reviewers can spot
    missing-by-design sections at a glance.
    """
    lines: list[str] = []
    lines.append(f"## Datasheet — {datasheet.title} {{#sec-datasheet-{datasheet.slug}}}")
    lines.append("")
    lines.append(
        "Per Gebru et al. 2018, *Datasheets for Datasets* "
        "(arXiv:1803.09010). See "
        "[`docs/sources/papers/gebru-2018-datasheets-for-datasets.md`]"
        "(../docs/sources/papers/gebru-2018-datasheets-for-datasets.md) "
        "for the methodology source archival."
    )
    lines.append("")
    for attr, header in _SECTION_HEADERS:
        section: list[DatasheetSection] = getattr(datasheet, attr)
        lines.append(f"### {header}")
        lines.append("")
        if not section:
            lines.append("*(No entries — section deferred or not applicable.)*")
            lines.append("")
            continue
        for entry in section:
            lines.append(f"**{entry.question}**")
            lines.append("")
            lines.append(entry.answer)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
