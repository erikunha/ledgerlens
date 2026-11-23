"""What the published artefacts of the held out set may not carry: the answer key of the generator.

Why it exists: ADR-067 promises that the expected label of a case (the answer key of the generator that wrote the
set) "is not published and will not be published, in any form, including a hash". The promise was false in two
published artefacts: the note of the two cases where the blind reading disagreed with the recipes named the label
the recipe expected, and the fact that differs between the recipe and the reading. The label of the reading is
published for every case of the set, and the generator agreed with the reading in 46 of the 48 cases, so those two
notes handed the reader the whole key of the set, and the set stopped being a set that a change of the future can
still be measured over.

Why the tests read the recipes: the expected label of a case is not published anywhere, so a test that looks for it
in a published file has no way of knowing what to look for. The recipes are in the local tree (they are the answer
key and they are not in git), so the test reads them and asks the published artefacts to keep quiet about what they
say.

Why the tests only ask about the diverging cases: in the 46 cases where the reading and the recipe agree, the label
of the reading is the expected label, and the label of the reading is published by design. The leak is only ever
about a case where the two differ, so that is the case the test asks about.

Why the tests skip when the recipes are not there: in a tree that has no recipes (a clone of the public repository)
the question cannot be asked, and a test that fails there would fail for a reason that is not a defect.

These tests were written before the redaction of the note and were seen failing without it.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "label_heldout.py"
LABELLED_PATH = ROOT / "data" / "eval" / "verification_heldout.jsonl"
REPORT_MARKDOWN_PATH = ROOT / "data" / "eval" / "report_heldout.md"
REPORT_JSON_PATH = ROOT / "data" / "eval" / "report_heldout.json"
RECIPES_PATH = ROOT / "data" / "eval" / "heldout" / "recipes.jsonl"

# The marker the note of a disagreement used to carry. It named the fact that differs between the recipe and the
# reading, and that fact is the reason the recipe expected the label it expected.
FACT_MARKER = "the fact that differs"

# The cases where the reading and the recipe disagree. The published report names them, so the test can.
DIVERGING_CASES = ("ho-002", "ho-013")

__all__ = [
    "test_no_published_artefact_carries_the_fact_that_differs",
    "test_the_note_of_a_disagreement_names_neither_the_expected_label_nor_the_fact_that_differs",
    "test_the_published_labelled_set_names_no_expected_label_of_a_diverging_case",
    "test_the_published_markdown_report_names_no_expected_label_of_a_diverging_case",
    "test_the_published_measurement_survives_the_redaction",
]


@pytest.fixture()
def tool():
    """The script of the blind reading, loaded as a module so the test can drive its functions."""
    spec = importlib.util.spec_from_file_location("label_heldout_publication", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---- the artefacts as they are published ----------------------------------------------------------------


def _published_records() -> list[dict]:
    """The records of the published labelled set, the dataset with the role `held_out`."""
    assert LABELLED_PATH.exists(), f"The published labelled set {LABELLED_PATH} does not exist."
    text = LABELLED_PATH.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _published_notes() -> dict[str, str]:
    """The note of every case of the published labelled set, by the id of the case."""
    return {record["id"]: record.get("note", "") for record in _published_records()}


def _reading_labels() -> dict[str, str]:
    """The label the reading gave to every case, read from the published labelled set."""
    return {record["id"]: record["label"] for record in _published_records()}


def _recipes(tool) -> dict[str, str]:
    """The label the generator expected of every case, read from the recipes of the generator.

    Why it skips when the file is not there: the recipes are the answer key, they are not in git, and a clone of
    the public repository has no way of asking the question this file asks.
    """
    if not RECIPES_PATH.exists():
        pytest.skip("the recipes of the generator are not in this tree: the answer key is not published")
    return {recipe.id: recipe.expected_label for recipe in tool.load_recipes(ROOT)}


def _diverging(tool) -> dict[str, str]:
    """The cases where the reading and the recipe disagree, with the label the recipe expected for each."""
    labels = _reading_labels()
    recipes = _recipes(tool)
    return {case_id: expected for case_id, expected in recipes.items() if labels.get(case_id) != expected}


def _cells(row: str) -> list[str]:
    """The cells of a row of a Markdown table, with the escaped bars kept inside their cell."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row.strip())][1:-1]


def _case_rows() -> dict[str, list[str]]:
    """The rows of the table of the cases of the published report, by the id of the case."""
    markdown = REPORT_MARKDOWN_PATH.read_text(encoding="utf-8")
    section = re.search(r"^## The cases\n(.*?)(?=^## |\Z)", markdown, re.MULTILINE | re.DOTALL)
    assert section is not None, "The published report has no section 'The cases'."
    rows: dict[str, list[str]] = {}
    for line in section.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|- "):
            continue
        cells = _cells(stripped)
        if cells[0] in ("id",) or set(cells[0]) <= {"-"}:
            continue
        rows[cells[0]] = cells
    return rows


# ---- the note that goes into the published set -----------------------------------------------------------


def test_the_note_of_a_disagreement_names_neither_the_expected_label_nor_the_fact_that_differs(tool) -> None:
    """The note of a case where the reading and the recipe disagree says that they disagree and nothing more.

    Why it matters: the note goes into the labelled set, and the labelled set is published. The expected label of a
    case is the answer key of the generator that wrote the set, and the fact that differs is the reason the recipe
    expected the label it expected. Naming either of them in a published note hands the reader the key of the case.
    """
    disagreement = tool.Disagreement(
        id="ho-002",
        reader_label="supported",
        expected_label="contradicted",
        template="two_source_shape",
        pair_id="hp-11",
        differing_fact="payout: withheld",
        note="the reader wrote this",
    )

    note = tool._compose_note("the reader wrote this", disagreement)

    assert "contradicted" not in note, f"the note names the label the recipe expected: {note}"
    assert "payout: withheld" not in note, f"the note names the fact that differs: {note}"
    assert FACT_MARKER not in note, f"the note names the fact that differs: {note}"
    assert "the reader wrote this" in note, "the note lost what the reader wrote"
    assert "the recipe expected a different label" in note, (
        f"the note does not say that the recipe expected another label: {note}"
    )


# ---- the published artefacts -----------------------------------------------------------------------------


def test_the_published_labelled_set_names_no_expected_label_of_a_diverging_case(tool) -> None:
    """The published labelled set says that the reading and the recipe disagreed, and names no expected label.

    Why it matters: the labelled set is the dataset with the role `held_out`, and it is the file a reader of the
    repository reads first. The label of the reading of a diverging case is published, and the label the recipe
    expected is not.
    """
    diverging = _diverging(tool)
    assert sorted(diverging) == list(DIVERGING_CASES), (
        f"the reading disagrees with the recipes in cases {sorted(diverging)}, and the test asks about another set"
    )

    notes = _published_notes()
    for case_id, expected in diverging.items():
        note = notes[case_id]
        assert expected not in note, (
            f"the published note of the case {case_id} names the label the recipe expected ({expected}): {note}"
        )


def test_the_published_markdown_report_names_no_expected_label_of_a_diverging_case(tool) -> None:
    """The published report carries the note of every case, and the note of a diverging case names no expected label.

    Why it matters: the report is what a person reads, and it carries the note of the reader for every case of the
    set. The note is the place where the answer key of the generator used to leak, one case at a time.
    """
    diverging = _diverging(tool)
    assert sorted(diverging) == list(DIVERGING_CASES), (
        f"the reading disagrees with the recipes in cases {sorted(diverging)}, and the test asks about another set"
    )

    rows = _case_rows()
    for case_id, expected in diverging.items():
        assert case_id in rows, f"the published report has no row for the case {case_id}"
        note = rows[case_id][5]
        assert expected not in note, (
            f"the published note of the case {case_id} names the label the recipe expected ({expected}): {note}"
        )


def test_no_published_artefact_carries_the_fact_that_differs() -> None:
    """No published artefact names the fact that differs between the recipe of a case and the reading of it.

    Why it matters: the fact that differs is the reason the recipe expected the label it expected. A reader who has
    the fact and the claim of the case can work the expected label out, so the fact is the key as much as the label
    is.
    """
    for path in (LABELLED_PATH, REPORT_MARKDOWN_PATH, REPORT_JSON_PATH):
        text = path.read_text(encoding="utf-8")
        assert FACT_MARKER not in text, f"the published file {path.name} names the fact that differs"


def test_the_published_measurement_survives_the_redaction() -> None:
    """The number, the matrix and the identifiers of the diverging cases are the ones the repository published.

    Why it matters: the redaction of the note is a change of the text of the report and nothing else. A change of
    the number, of the matrix or of the identifiers would mean that the measurement was redone and not redacted, and
    the number of a set that may not be tuned against may not move without a decision of its own.
    """
    markdown = REPORT_MARKDOWN_PATH.read_text(encoding="utf-8")
    published = json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))

    assert "- over the set: 24/48 (0.500)" in markdown
    assert "| supported | 10 | 0 | 9 | 19 |" in markdown
    assert "| contradicted | 2 | 10 | 11 | 23 |" in markdown
    assert "| not_enough_evidence | 2 | 0 | 4 | 6 |" in markdown
    assert "the reading disagrees with the recipe of 2 case(s) of 48: ho-002, ho-013" in markdown

    assert published["accuracy"] == {"correct": 24, "cases": 48, "value": "0.500"}
    assert published["reading_against_the_recipes"] == {"count": 2, "case_ids": ["ho-002", "ho-013"]}
