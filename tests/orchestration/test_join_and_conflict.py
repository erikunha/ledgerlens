"""The join of the results of the steps: the evidence that resolves and the arithmetic that decides.

What they guarantee, and why: (a) an evidence identifier that resolves to no record of the run is refused, because a
join that accepted it would publish a number about a row that does not exist; (b) two results that disagree over an
amount end with the value of the calculator or with a named abstention and never with a value that came from a vote;
(c) a result of another snapshot is refused, because two results of two snapshots are two results of two questions.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.orchestration.join import JoinRefused, join_results
from ledgerlens.schemas import StepResult


def _result(step_id: str, *, row: str | None = None, amount: Decimal | None = None, evidence: list[str] | None = None):
    """A result of a step, with the fields the join reads."""
    return StepResult(
        step_id=step_id,
        status="ok",
        evidence_refs=evidence if evidence is not None else ["sql:1"],
        row=row,
        amount=amount,
    )


def test_an_invented_evidence_identifier_is_refused() -> None:
    """An identifier that a result invented is a claim about a row that nobody read."""
    results = [_result("read", evidence=["sql:invented"])]

    with pytest.raises(JoinRefused, match="resolves to no record"):
        join_results(
            results,
            snapshot="a" * 64,
            records=["sql:1"],
            recompute=lambda row: Decimal("1"),
        )


def test_two_results_that_agree_keep_the_amount() -> None:
    """The join of two readings that agree is the amount they both read."""
    results = [
        _result("one", row="TX-1", amount=Decimal("10.00")),
        _result("two", row="TX-1", amount=Decimal("10.00")),
    ]

    outcome = join_results(results, snapshot="a" * 64, records=["sql:1"], recompute=lambda row: Decimal("99"))

    assert outcome.amounts == {"TX-1": Decimal("10.00")}
    assert outcome.contested == ()
    assert outcome.abstained is False


def test_two_results_that_disagree_end_with_the_value_of_the_calculator() -> None:
    """The arithmetic decides and never the vote (FR-006)."""
    results = [
        _result("one", row="TX-1", amount=Decimal("10.00")),
        _result("two", row="TX-1", amount=Decimal("12.00")),
    ]

    outcome = join_results(
        results,
        snapshot="a" * 64,
        records=["sql:1"],
        recompute=lambda row: Decimal("11.00"),
    )

    assert outcome.amounts == {"TX-1": Decimal("11.00")}
    assert outcome.contested == ()
    assert outcome.abstained is False


def test_a_disagreement_that_the_calculator_cannot_settle_is_a_named_abstention() -> None:
    """A row that nobody can settle is a row the run does not know, and it is named."""
    results = [
        _result("one", row="TX-1", amount=Decimal("10.00")),
        _result("two", row="TX-1", amount=Decimal("12.00")),
    ]

    outcome = join_results(results, snapshot="a" * 64, records=["sql:1"], recompute=lambda row: None)

    assert outcome.contested == ("TX-1",)
    assert outcome.abstained is True
    assert outcome.amounts == {"TX-1": Decimal("10.00")}


def test_a_result_of_another_snapshot_is_refused() -> None:
    """Two results of two snapshots are two results of two questions."""
    results = [_result("read", row="TX-1", amount=Decimal("10.00"))]

    with pytest.raises(JoinRefused, match="snapshot"):
        join_results(
            results,
            snapshot="a" * 64,
            records=["sql:1"],
            recompute=lambda row: Decimal("1"),
            result_snapshots={"read": "b" * 64},
        )


def test_a_result_of_the_snapshot_of_the_run_is_joined() -> None:
    """The snapshot that matches is the one the join accepts."""
    results = [_result("read", row="TX-1", amount=Decimal("10.00"))]

    outcome = join_results(
        results,
        snapshot="a" * 64,
        records=["sql:1"],
        recompute=lambda row: Decimal("1"),
        result_snapshots={"read": "a" * 64},
    )

    assert outcome.amounts == {"TX-1": Decimal("10.00")}
