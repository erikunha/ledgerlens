"""The rule of the cut in the trace: what a published bundle may leave out and what it may never leave out.

What they prove, and why: (a) the values of one record and the names of the columns of a result are never cut,
because they are what the answer cites, and a cut there takes the evidence of the claim away and leaves values
that no reader can put under a column; (b) the records of a result are never cut, because the tool that read them
bounded them and said how many it read, and a cut of a record takes the values a claim cites away (ADR-079);
(c) the identifiers the tool returned are never cut, because they are the list that links a piece of evidence to
its content; (d) a list of records is never cut, whatever the name of the field it has; (e) any other list is cut
in its number of items, with the marker that says what was left out; (f) the answer of the run is published whole,
because the claims of the run are extracted from it (ADR-076).

Why the rule matters at all: the published bundle is the proof a reader checks the verdict of the run against,
and the verdict of a claim is computed from the evidence the bundle publishes. A cut that takes a cited value
away makes the published verdict unreachable from the published evidence.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from typing import Any

from ledgerlens.observability.trace import compact

__all__ = [
    "test_a_list_of_records_is_published_whole_whatever_the_name_of_the_field",
    "test_a_list_of_values_is_cut_with_the_marker_of_items",
    "test_any_other_text_is_still_cut",
    "test_the_answer_of_the_run_is_published_whole",
    "test_the_identifiers_the_tool_returned_are_published_whole",
    "test_the_names_of_the_columns_are_never_cut",
    "test_the_records_of_a_result_are_published_whole",
    "test_the_values_of_a_record_are_never_cut",
]


def _columns(count: int) -> list[str]:
    """The names of the columns of a result, in order."""
    return [f"column_{index}" for index in range(count)]


def _row(count: int) -> list[Any]:
    """The values of one record, in the order of the columns."""
    return [f"value_{index}" for index in range(count)]


def test_the_values_of_a_record_are_never_cut():
    """The values of one record are never cut, because they are what the answer cites.

    Why the values of a record and not only the records: a record that is left out takes no value of the
    evidence away, while a value that is left out is a value the answer cites and nobody can check.
    """
    columns = _columns(12)
    row = _row(12)

    compacted = compact({"data": {"columns": columns, "rows": [row], "row_count": 1}})

    assert compacted["data"]["rows"] == [row]
    assert len(compacted["data"]["rows"][0]) == 12


def test_the_names_of_the_columns_are_never_cut():
    """The names of the columns are never cut, because they are what says what a value is.

    Why the names and not only the values: a value without its column is a number nobody can put under a
    column, and the reader of the bundle cannot tell a rate from an amount.
    """
    columns = _columns(12)

    compacted = compact({"data": {"columns": columns, "rows": [], "row_count": 0}})

    assert compacted["data"]["columns"] == columns


def test_the_records_of_a_result_are_published_whole():
    """The records of a result are published whole, because the tool bounded them and said what it read.

    Why the whole and not a cut with a marker: the marker of the cut went into the list of the rows, and a list
    that holds a text is not a list of rows any more. The values of the rows then reach the verifier without a
    column and without a currency, and the label the bundle publishes is not the label the code gives for them
    (ADR-079). The tool that read the rows bounded them already (`max_rows`, `row_count`, `truncated`), so the
    trace does not cut a second time what the tool has already bounded.
    """
    rows = [[index] for index in range(12)]

    compacted = compact({"data": {"columns": ["value"], "rows": rows, "row_count": 12}})

    assert compacted["data"]["rows"] == rows


def test_the_identifiers_the_tool_returned_are_published_whole():
    """The identifiers the tool returned are published whole, because they link the evidence to its content.

    Why this list and not only the records: a cut list of identifiers takes away the evidence of the claims
    that cite the identifiers that are gone, and the reader of the bundle cannot tell which evidence is missing
    (ADR-079).
    """
    identifiers = [f"sql:{index}" for index in range(12)]

    compacted = compact({"outputs": {"evidence_ids": identifiers}})

    assert compacted["outputs"]["evidence_ids"] == identifiers


def test_a_list_of_records_is_published_whole_whatever_the_name_of_the_field():
    """A list of records is published whole, whatever the name of the field that holds it.

    Why the shape and not the name of the field: the collections of a record (the refunds of a payment, the
    chargebacks, the rates applied to it) are records, and a cut of them takes the values of a claim away in the
    same way the cut of the rows of a statement did (ADR-079).
    """
    refunds = [{"id": f"R-{index:04d}", "amount_minor": 1000} for index in range(12)]

    compacted = compact({"data": {"transaction": {"id": "TX-2048"}, "refunds": refunds}})

    assert compacted["data"]["refunds"] == refunds


def test_a_list_of_values_is_cut_with_the_marker_of_items():
    """Any other list is cut in its number of items, and the marker says that they were values."""
    compacted = compact({"metadata": {"tags": [f"tag-{index}" for index in range(12)]}})

    assert compacted["metadata"]["tags"] == [f"tag-{index}" for index in range(8)] + ["…+4 items"]


def test_the_answer_of_the_run_is_published_whole():
    """The answer of the run is published whole, because the claims of the run are extracted from it.

    Why the answer and not the conversation: the verifier reads the answer, splits it in sentences and links every
    sentence that carries a citation to the evidence it cites. A cut answer takes the claims away, and the bundle
    would publish the label of a claim that the code cannot rebuild from the published evidence (ADR-076).
    """
    answer = "The payment came to BRL 566.79 and the refund to BRL 549.31. " * 20

    compacted = compact({"outputs": {"answer": answer}})

    assert compacted["outputs"]["answer"] == answer
    assert "…" not in compacted["outputs"]["answer"]


def test_any_other_text_is_still_cut():
    """A text that is not the answer of the run keeps the cut of six hundred characters.

    Why the other texts keep the cut: they are reference material, the payload of the site stays inside the budget
    of the specification, and a cut there takes no claim away (ADR-076).
    """
    excerpt = "policy text " * 200
    compacted = compact({"outputs": {"excerpt": excerpt}})

    assert compacted["outputs"]["excerpt"].endswith(f"…+{len(excerpt) - 600} chars")
