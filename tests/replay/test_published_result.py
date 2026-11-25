"""The published result, rebuilt from the published events: the text the claims of the run came from.

What they prove, and why: (a) the rebuild takes the answer the run verified, and not the final answer of the
investigation, because the escalation may add a notice to the answer after the verification and the claims of the
run were extracted from the text the verifier saw (ADR-077); (b) a bundle without a span of the verifier falls back
to the final answer, so a recording without a verification still rebuilds something the reader can read; (c) the
values of a result reach the verifier with their column and their currency, because a value without one is a number
nobody can put under a column (ADR-079); (d) a claim that cites a value of a result keeps its label when the bundle
is rebuilt, because the label the bundle publishes is the label the code gives for the published evidence.

Why it matters: the check of ADR-073 compares the label the bundle publishes with the label the code gives for
the published evidence. A rebuild that reads the wrong text finds claims the run never had, and the difference
looks like a broken recording when it is a broken rebuild.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.replay.verdict import differences, published_result
from ledgerlens.verify.claims import ledger_values

__all__ = [
    "test_a_claim_that_cites_a_value_of_a_result_keeps_its_label",
    "test_the_rebuild_falls_back_to_the_final_answer_when_there_is_no_verification",
    "test_the_rebuild_takes_the_answer_the_run_verified",
    "test_the_values_of_a_result_reach_the_verifier_with_their_column_and_their_currency",
]

# The columns of the statement the test publishes, and the rows it returns. The rows are more than the eight the
# trace used to keep, because that cut is the one this file is about.
_COLUMNS = ["settlement_id", "currency", "gross_major", "gross_minor"]
_ROWS = [["ST-0044", "BRL", "30919.54", 3091954] for _ in range(13)]

# The answer of the run and the value it states, the value the rows of the statement carry.
_ANSWER = "The gross of the settlement was BRL 30,919.54 [sql:1]."


def _event(seq: int, name: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One event of a bundle, with the shape the trace writes."""
    return {
        "schema_version": "1",
        "run_id": "run-1",
        "seq": seq,
        "at": f"2026-11-24T10:0{seq}:00.000+00:00",
        "event_type": event_type,
        "payload": {"name": name, **payload},
    }


def _bundle(tmp_path: Path, events: list[dict[str, Any]]) -> Path:
    """A folder with the events of a bundle, which is what the rebuild reads."""
    directory = tmp_path / "bundle"
    directory.mkdir()
    text = "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n"
    (directory / "events.jsonl").write_text(text, encoding="utf-8")
    return directory


def _statement() -> dict[str, Any]:
    """The output of the tool that read the ledger, with the rows it returned."""
    return {
        "ok": True,
        "evidence_ids": ["sql:1"],
        "data": {
            "sql": "SELECT * FROM settlements",
            "columns": list(_COLUMNS),
            "rows": [list(row) for row in _ROWS],
            "row_count": len(_ROWS),
            "truncated": False,
        },
    }


def test_the_rebuild_takes_the_answer_the_run_verified(tmp_path: Path):
    """The claims of the run came from the answer the verifier saw, and the rebuild uses that text.

    Why the two answers differ here: the escalation adds a notice to the answer when the reference source could
    not give a rate, and the notice comes after the verification. A rebuild that reads the final answer would
    find sentences the run never turned into claims (ADR-077).
    """
    verified = "The refund came to BRL 549.31 [sql:1]."
    final = verified + " The reference rate could not be obtained and the case went to a person."
    directory = _bundle(
        tmp_path,
        [
            _event(1, "investigate", "span.started", {"inputs": {"question": "why?"}}),
            _event(2, "verify", "span.started", {"inputs": {"answer": verified}}),
            _event(3, "investigate", "span.ended", {"outputs": {"answer": final}}),
        ],
    )

    result = published_result(directory)

    assert result.answer == verified


def test_the_rebuild_falls_back_to_the_final_answer_when_there_is_no_verification(tmp_path: Path):
    """A recording without a verification has no claims to rebuild, and the rebuild still reads the answer."""
    final = "The refund came to BRL 549.31 [sql:1]."
    directory = _bundle(
        tmp_path,
        [
            _event(1, "investigate", "span.started", {"inputs": {"question": "why?"}}),
            _event(2, "investigate", "span.ended", {"outputs": {"answer": final}}),
        ],
    )

    result = published_result(directory)

    assert result.answer == final


def test_the_values_of_a_result_reach_the_verifier_with_their_column_and_their_currency(tmp_path: Path):
    """The values of a result reach the verifier with their column and their currency.

    Why this and not only the rule of the cut: the verifier matches a value the answer states with a value of the
    ledger by its column and by its currency, and a value that reaches it without one is a number nobody can
    check. The published evidence of a result that the trace cut lost both, and the label the bundle published
    was not the label the code gave for it (ADR-079).
    """
    directory = _bundle(
        tmp_path,
        [
            _event(1, "query_ledger", "span.ended", {"run_type": "tool", "outputs": _statement()}),
        ],
    )

    result = published_result(directory)

    assert len(result.evidence) == 1
    values = ledger_values(result.evidence[0].content)
    gross = [value for value in values if value.column == "gross"]
    assert gross, "the published evidence holds no value of the column of the gross"
    assert {value.currency for value in gross} == {"BRL"}
    assert {value.value for value in gross} == {Decimal("30919.54")}


def test_a_claim_that_cites_a_value_of_a_result_keeps_its_label(tmp_path: Path):
    """A claim that cites a value of a result keeps its label when the bundle is rebuilt.

    Why this is the promise of ADR-073 in one test: the bundle publishes the label of the claim and the evidence
    of the claim, and the code of the repository has to give the same label for that evidence. A recording of a
    real run of the scenario S08 published thirteen rows of a statement and the verifier could not read the
    values of those rows, so four claims of the bundle published as supported were not reachable from the
    evidence the bundle published (ADR-079).
    """
    directory = _bundle(
        tmp_path,
        [
            _event(1, "investigate", "span.started", {"inputs": {"question": "how much?"}}),
            _event(2, "verify", "span.started", {"inputs": {"answer": _ANSWER}}),
            _event(3, "query_ledger", "span.ended", {"run_type": "tool", "outputs": _statement()}),
            _event(4, "CL1", "span.ended", {"outputs": {"label": "supported"}}),
            _event(5, "investigate", "span.ended", {"outputs": {"answer": _ANSWER}}),
        ],
    )

    assert differences(directory) == []
