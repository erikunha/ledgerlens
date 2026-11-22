"""The reader of the held out file: the shape it reads, the case without evidence and the counts of the set.

Why it exists: the held out set is the last set of the milestone, and its file has a shape the readers of the
tuning sets do not understand: the evidence of a case may come from two tools at once, a premise may hold many
rows and one case of the set cites no evidence at all. The reader of the sweep drops a case whose premise is
empty, so that case would have disappeared from the set and every number over the set would have been a number
over fewer cases than the file holds.

These tests build their own file under a temporary folder, with the same shape the file of the set has. They do
not depend on the file of the set nor on the module that writes it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.eval import heldout_reader
from ledgerlens.eval.heldout_reader import (
    HeldoutError,
    heldout_counts,
    heldout_nli_cases,
    heldout_result,
    read_heldout_cases,
)
from ledgerlens.verify.checks import load_thresholds, verify_result
from ledgerlens.verify.claims import focus_premise, render_premise
from ledgerlens.verify.nli import HuggingFaceNli, StubNli

TX_COLUMNS = [
    "id",
    "merchant_id",
    "customer_id",
    "amount_major",
    "currency",
    "status",
    "created_at",
    "source_ref",
]


def _tx_row(index: int) -> list[str]:
    """One row of the ledger, with the id and the day the fixtures use."""
    return [
        f"TX-70{index:02d}",
        "M-11",
        "C-0412",
        "120.00",
        "EUR",
        "captured",
        "2026-10-15T09:12:00Z",
        "scenario:S01",
    ]


def _sql_content(rows: list[list[str]], columns: list[str], table: str) -> str:
    """The envelope of a query result, the shape the tool stores and the verifier renders."""
    selected = ", ".join(columns)
    return json.dumps(
        {
            "sql": f"SELECT * FROM (SELECT {selected} FROM {table} WHERE id = '{rows[0][0]}') LIMIT 50",
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": False,
        }
    )


def _policy_content(chunk_id: str, text: str) -> str:
    """The envelope of a policy chunk, the shape the tool stores and the verifier renders."""
    return json.dumps(
        {
            "chunk_id": chunk_id,
            "document": "refund-policy",
            "section": "Refunds",
            "topic": "refund",
            "version": "2026-10-01",
            "text": text,
        }
    )


def _rows() -> list[dict[str, Any]]:
    """The cases of the fixture: the ordinary one, the one with two tools, the long one, the one without evidence
    and the one whose evidence contradicts itself."""
    return [
        {
            "id": "ho-001",
            "claim": "The transaction TX-7001 was captured on 2026-10-15.",
            "evidence_ids": ["sql:1"],
            "evidence": [
                {"id": "sql:1", "content": _sql_content([_tx_row(1)], TX_COLUMNS, "transactions")},
            ],
            "label": "supported",
            "note": "the ledger row holds the status and the day",
        },
        {
            "id": "ho-002",
            "claim": (
                "The transaction TX-7002 was captured and the policy asks for the refund to be requested "
                "within 30 days."
            ),
            "evidence_ids": ["sql:1", "policy:refund-policy#deadline"],
            "evidence": [
                {"id": "sql:1", "content": _sql_content([_tx_row(2)], TX_COLUMNS, "transactions")},
                {
                    "id": "policy:refund-policy#deadline",
                    "content": _policy_content(
                        "refund-policy#deadline",
                        "Refunds\nA refund must be requested within 30 days of the charge.",
                    ),
                },
            ],
            "label": "supported",
            "note": "the row and the chunk of the policy back the sentence",
        },
        {
            "id": "ho-003",
            "claim": "The transactions TX-7003 and TX-7004 were both captured.",
            "evidence_ids": ["sql:1"],
            "evidence": [
                {
                    "id": "sql:1",
                    "content": _sql_content([_tx_row(i) for i in range(1, 13)], TX_COLUMNS, "transactions"),
                },
            ],
            "label": "supported",
        },
        {
            "id": "ho-004",
            "claim": "The customer C-0412 was charged twice for the same order.",
            "evidence_ids": [],
            "evidence": [],
            "label": "not_enough_evidence",
            "note": "the negative control of the set: the sentence cites no evidence at all",
        },
        {
            "id": "ho-005",
            "claim": "The settlement ST-9001 was paid in full on 2026-10-20.",
            "evidence_ids": ["sql:1"],
            "evidence": [
                {
                    "id": "sql:1",
                    "content": _sql_content(
                        [
                            ["ST-9001", "paid", "100.00", "EUR"],
                            ["ST-9001", "unpaid", "0.00", "EUR"],
                        ],
                        ["id", "status", "net_major", "currency"],
                        "settlements",
                    ),
                },
            ],
            "label": "contradicted",
            "note": "the two rows of the evidence say opposite things",
        },
    ]


def _write(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    """The fixture file: one JSON object per line, as the file of the set is."""
    path = tmp_path / "heldout_cases.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _fixture(tmp_path: Path) -> Path:
    """The fixture file with the five cases."""
    return _write(tmp_path, _rows())


def _by_id(cases: tuple[Any, ...]) -> dict[str, Any]:
    """The cases by their id."""
    return {case.case_id: case for case in cases}


def test_reads_an_ordinary_case(tmp_path: Path) -> None:
    """One claim, one evidence, and the label of the file comes out."""
    path = _fixture(tmp_path)
    cases = read_heldout_cases(path)
    assert len(cases) == 5
    case = _by_id(cases)["ho-001"]
    assert case.claim == "The transaction TX-7001 was captured on 2026-10-15."
    assert case.label == "supported"
    assert case.evidence_ids == ("sql:1",)
    assert [item.id for item in case.evidence] == ["sql:1"]
    assert "TX-7001" in case.evidence[0].content
    assert case.note == "the ledger row holds the status and the day"
    assert case.has_evidence is True


def test_reads_a_case_with_two_tools(tmp_path: Path) -> None:
    """Two evidence items, and the premise of the model holds both rendered envelopes."""
    path = _fixture(tmp_path)
    case = _by_id(read_heldout_cases(path))["ho-002"]
    assert case.evidence_ids == ("sql:1", "policy:refund-policy#deadline")
    built = _by_id(heldout_nli_cases([case]))
    premise = built["ho-002"].case.premise
    assert "TX-7002" in premise
    assert "A refund must be requested within 30 days" in premise
    assert built["ho-002"].needs_model is True


def test_reads_a_long_case(tmp_path: Path) -> None:
    """Many rows of evidence, and the premise of the model is not shortened to one row."""
    path = _fixture(tmp_path)
    case = _by_id(read_heldout_cases(path))["ho-003"]
    assert len(case.evidence) == 1
    rows = json.loads(case.evidence[0].content)["rows"]
    assert len(rows) == 12

    premise = _by_id(heldout_nli_cases([case]))["ho-003"].case.premise
    # the premise is the one the verifier builds: the rendered evidence, focused on the ids of the claim
    joined = "\n".join(render_premise(item.content) for item in case.cited_evidence)
    limit = int(load_thresholds()["max_premise_chars"])
    assert premise == focus_premise(joined, case.claim)[:limit]
    # the rows of the focus rule are kept, and the premise is not one row
    assert len(premise.splitlines()) == 2
    assert "TX-7003" in premise
    assert "TX-7004" in premise
    assert "TX-7001" not in premise


def test_the_case_without_evidence_is_not_dropped(tmp_path: Path) -> None:
    """The negative control comes out of the reader and the verifier judges it by itself."""
    path = _fixture(tmp_path)
    cases = read_heldout_cases(path)
    without = [case for case in cases if not case.has_evidence]
    assert len(without) == 1
    assert without[0].case_id == "ho-004"
    assert without[0].label == "not_enough_evidence"

    built = _by_id(heldout_nli_cases(cases))
    assert "ho-004" in built
    assert built["ho-004"].needs_model is False
    assert built["ho-004"].case.premise == ""

    # the real verifier path, not a copy of it
    result = verify_result(heldout_result(without[0]), nli=StubNli())
    assert len(result.verdicts) == 1
    verdict = result.verdicts[0]
    assert verdict.label == "not_enough_evidence"
    assert verdict.method == "none"


def test_counts_the_denominator(tmp_path: Path) -> None:
    """The counts say how many cases the file holds and how many of them the model reads."""
    path = _fixture(tmp_path)
    counts = heldout_counts(path)
    assert counts.total == 5
    assert counts.nli == 4
    assert counts.decided_by_code == 1
    assert counts.nli + counts.decided_by_code == counts.total


def test_a_line_that_is_not_json_is_a_sentence(tmp_path: Path) -> None:
    """A broken line is a sentence that names the file and the line, and never a traceback."""
    path = _write(tmp_path, [_rows()[0]])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("this is not json\n")
    with pytest.raises(HeldoutError) as error:
        read_heldout_cases(path)
    message = str(error.value)
    assert "heldout_cases.jsonl" in message
    assert "line 2" in message
    assert "Traceback" not in message


def test_a_line_that_is_not_an_object_is_a_sentence(tmp_path: Path) -> None:
    """A line that parses as JSON but is not an object is refused the same way."""
    path = _write(tmp_path, [_rows()[0]])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("[1, 2]\n")
    with pytest.raises(HeldoutError) as error:
        read_heldout_cases(path)
    message = str(error.value)
    assert "heldout_cases.jsonl" in message
    assert "line 2" in message
    assert "Traceback" not in message


def test_a_case_that_misses_a_field_is_a_sentence(tmp_path: Path) -> None:
    """A case without a label is refused with a sentence that names the file and the line."""
    row = _rows()[0]
    del row["label"]
    path = _write(tmp_path, [row])
    with pytest.raises(HeldoutError) as error:
        read_heldout_cases(path)
    message = str(error.value)
    assert "heldout_cases.jsonl" in message
    assert "line 1" in message
    assert "label" in message


def test_a_file_that_cannot_be_read_is_a_sentence(tmp_path: Path) -> None:
    """A file that is not there is refused with a sentence and not a traceback."""
    with pytest.raises(HeldoutError) as error:
        read_heldout_cases(tmp_path / "missing.jsonl")
    assert "missing.jsonl" in str(error.value)


def test_the_reader_needs_no_nli_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cases and the premises are built without the model, even when the model refuses to load."""

    def refuse(self: HuggingFaceNli) -> None:
        raise AssertionError("the reader must not load the NLI model")

    monkeypatch.setattr(HuggingFaceNli, "_load", refuse)
    path = _fixture(tmp_path)
    cases = read_heldout_cases(path)
    built = heldout_nli_cases(cases)
    assert len(built) == 5
    assert all(item.case.premise for item in built if item.needs_model)


def test_the_reader_does_not_depend_on_the_generator() -> None:
    """The reader reads the file and does not import the module that writes it."""
    source = Path(heldout_reader.__file__).read_text(encoding="utf-8")
    assert re.search(r"ledgerlens\.eval\.heldout\b", source) is None


def test_the_reader_names_the_same_tools_as_the_sweep() -> None:
    """The prefix of an evidence id names the same tool in the reader and in the sweep."""
    from ledgerlens.verify import sweep

    assert heldout_reader._SOURCE_TOOL == sweep._SOURCE_TOOL
