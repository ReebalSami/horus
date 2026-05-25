"""Tests for `horus.eda.datasheet` (ADR-025 Phase A skeleton).

Verifies the Datasheet Pydantic model + qmd renderer produce well-formed
markdown that:
  - Carries a level-2 heading with a stable {#sec-datasheet-<slug>} anchor
    so cross-references in other chapters resolve.
  - Cites the Gebru et al. 2018 source archival (ADR-025 hard requirement).
  - Renders all seven canonical sections (motivation / composition /
    collection / preprocessing / uses / distribution / maintenance) in
    the Gebru-paper order.
  - Surfaces empty sections with a placeholder rather than silently
    omitting them, so reviewers can spot deferred-vs-omitted entries.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from horus.eda.datasheet import Datasheet, DatasheetSection, render_to_qmd


def test_datasheet_section_requires_non_empty_strings() -> None:
    with pytest.raises(ValidationError):
        DatasheetSection(question="", answer="some answer")
    with pytest.raises(ValidationError):
        DatasheetSection(question="a question", answer="")


def test_datasheet_slug_must_be_kebab_case() -> None:
    with pytest.raises(ValidationError):
        Datasheet(slug="ZUGFeRD", title="ZUGFeRD")  # uppercase rejected
    with pytest.raises(ValidationError):
        Datasheet(slug="zugferd corpus", title="ZUGFeRD")  # space rejected
    # Valid kebab-case.
    Datasheet(slug="zugferd-corpus", title="ZUGFeRD German corpus")


def test_render_emits_section_anchor_for_cross_references() -> None:
    sheet = Datasheet(slug="zugferd", title="ZUGFeRD German corpus")
    output = render_to_qmd(sheet)
    assert "{#sec-datasheet-zugferd}" in output
    assert "## Datasheet — ZUGFeRD German corpus" in output


def test_render_cites_gebru_source_archival() -> None:
    """ADR-025 hard requirement: Datasheet output must cite the source stub."""
    sheet = Datasheet(slug="zugferd", title="ZUGFeRD")
    output = render_to_qmd(sheet)
    assert "gebru-2018-datasheets-for-datasets.md" in output
    assert "1803.09010" in output


def test_render_includes_all_seven_canonical_sections_in_order() -> None:
    sheet = Datasheet(slug="zugferd", title="ZUGFeRD")
    output = render_to_qmd(sheet)
    expected_in_order = [
        "### Motivation",
        "### Composition",
        "### Collection process",
        "### Preprocessing / cleaning / labeling",
        "### Uses",
        "### Distribution",
        "### Maintenance",
    ]
    last_index = -1
    for header in expected_in_order:
        idx = output.find(header)
        assert idx != -1, f"missing section: {header}"
        assert idx > last_index, f"section {header} out of order"
        last_index = idx


def test_render_marks_empty_sections_explicitly() -> None:
    sheet = Datasheet(slug="zugferd", title="ZUGFeRD")
    output = render_to_qmd(sheet)
    # Every section is empty → placeholder appears 7 times.
    assert output.count("*(No entries — section deferred or not applicable.)*") == 7


def test_render_emits_question_and_answer_for_populated_section() -> None:
    sheet = Datasheet(
        slug="zugferd",
        title="ZUGFeRD",
        motivation=[
            DatasheetSection(
                question="For what purpose was the dataset created?",
                answer=(
                    "Sample collection by Mustang/Jochen Stärk for testing "
                    "ZUGFeRD readers + validators."
                ),
            ),
        ],
    )
    output = render_to_qmd(sheet)
    assert "**For what purpose was the dataset created?**" in output
    assert "Sample collection by Mustang/Jochen Stärk" in output
    # And the placeholder appears 6 times (one fewer; motivation is populated).
    assert output.count("*(No entries — section deferred or not applicable.)*") == 6


def test_render_output_ends_with_single_newline() -> None:
    sheet = Datasheet(slug="zugferd", title="ZUGFeRD")
    output = render_to_qmd(sheet)
    assert output.endswith("\n")
    assert not output.endswith("\n\n")
