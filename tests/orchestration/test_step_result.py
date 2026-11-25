"""The typed plan and the typed result of a step of the studio.

What they guarantee, and why: (a) the result of a step carries its status, its evidence, its spend and its error,
because a step that failed silently is a step that the reader cannot account for; (b) the money of a step is a
`Decimal` and a float is refused, because a float is already a rounded number; (c) the plan and the result forbid
the fields that nobody wrote, because a plan with an extra field is a plan that two readers read differently.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ledgerlens.schemas import OrchestrationPlan, OrchestrationStep, StepResult


def test_the_result_of_a_step_carries_its_status_its_evidence_its_spend_and_its_error() -> None:
    """The four fields of a result are present and they are typed."""
    result = StepResult(
        step_id="read",
        status="ok",
        evidence_refs=["sql:1"],
        spend_usd=Decimal("0.25"),
        error=None,
    )

    assert result.step_id == "read"
    assert result.status == "ok"
    assert result.evidence_refs == ["sql:1"]
    assert result.spend_usd == Decimal("0.25")
    assert result.error is None


def test_the_money_of_a_step_is_a_decimal_and_a_float_is_refused() -> None:
    """A float is refused and not converted, because a float is already a rounded number."""
    with pytest.raises(ValidationError):
        StepResult(step_id="read", status="ok", spend_usd=0.25)

    with pytest.raises(ValidationError):
        StepResult(step_id="read", status="ok", amount=1.5)


def test_an_unknown_spend_is_none_and_never_zero() -> None:
    """A price that was never verified leaves the money unmeasured, and a zero would say that it was free."""
    result = StepResult(step_id="read", status="ok", spend_usd=None)

    assert result.spend_usd is None


def test_the_status_of_a_step_is_one_of_the_four() -> None:
    """A status that nobody wrote is a status that no reader can interpret."""
    with pytest.raises(ValidationError):
        StepResult(step_id="read", status="maybe")


def test_the_plan_forbids_the_fields_that_nobody_wrote() -> None:
    """A plan with an extra field is a plan that two readers read differently."""
    with pytest.raises(ValidationError):
        OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger", budget="a lot")


def test_the_plan_carries_the_steps_and_the_snapshot() -> None:
    """The plan carries the snapshot, because two steps of two snapshots are two steps of two questions."""
    plan = OrchestrationPlan(
        steps=[OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger")],
        snapshot="b" * 64,
    )

    assert plan.steps[0].id == "read"
    assert plan.snapshot == "b" * 64
