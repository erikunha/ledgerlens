"""The result carries its assumptions, and the sensitivity is a measurement of the assumption.

What they guarantee, and why: the result of a run carries the assumptions that produced it, and the two runs
of one intervention under two assumptions carry each the assumption that produced it, so a reader of a result
knows what the result assumed. The sensitivity of a node to an assumption is the movement of the node between
the two runs, because the two runs differ only in the assumption, and the sensitivity is a measurement of the
assumption and not an interval of confidence.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.causal.engine import (
    ASSUMPTION_FIRST_DAY_COVERED,
    ASSUMPTION_FIRST_DAY_NOT_COVERED,
    run,
    sensitivity,
)
from ledgerlens.causal.intervention import Intervention, InterventionRefused

INTERVENTION = Intervention("policy.markup_ceiling", Decimal("0.9"))


def test_the_result_carries_the_assumptions_that_produced_it(world) -> None:
    """A result without its assumptions would be a result a reader cannot check."""
    intervention = Intervention(
        "policy.markup_ceiling", Decimal("0.9"), assumptions=(ASSUMPTION_FIRST_DAY_COVERED,)
    )
    result = run(world, intervention)

    assert result.assumptions == (ASSUMPTION_FIRST_DAY_COVERED,)


def test_the_two_results_under_two_assumptions_carry_each_its_assumption(world) -> None:
    """The sensitivity compares two runs, and each run says what it assumed."""
    measured = sensitivity(
        world,
        INTERVENTION,
        (ASSUMPTION_FIRST_DAY_COVERED,),
        (ASSUMPTION_FIRST_DAY_NOT_COVERED,),
    )

    assert measured.first.assumptions == (ASSUMPTION_FIRST_DAY_COVERED,)
    assert measured.second.assumptions == (ASSUMPTION_FIRST_DAY_NOT_COVERED,)


def test_the_sensitivity_is_the_movement_of_the_nodes_between_the_two_runs(world) -> None:
    """The entry of the first day of the period moves with the assumption, and the movement is measured."""
    measured = sensitivity(
        world,
        INTERVENTION,
        (ASSUMPTION_FIRST_DAY_COVERED,),
        (ASSUMPTION_FIRST_DAY_NOT_COVERED,),
    )

    movement = {change.node: change for change in measured.movement}
    assert set(movement) == {"fx.markup"}
    assert movement["fx.markup"].before["e0"] == Decimal("0.9000")
    assert movement["fx.markup"].after["e0"] == Decimal("1.0000")


def test_an_assumption_that_is_not_registered_is_refused_and_the_reason_names_it(world) -> None:
    """The vocabulary of the assumptions is closed, and a stranger assumption names the field."""
    stranger = Intervention(
        "policy.markup_ceiling", Decimal("0.9"), assumptions=("an assumption nobody registered",)
    )
    with pytest.raises(InterventionRefused, match="assumption"):
        run(world, stranger)
