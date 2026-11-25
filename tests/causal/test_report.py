"""The report separates what is known, what is unknown and what nobody can check.

What they guarantee, and why: every amount of the report is a `Decimal` and every difference recomputes
exactly, because a difference without its two values is not a result; the amounts that did not change are
named, because a reader has to see what the intervention did not touch; no sentence of the report says what a
merchant outside the simulation received, because the engine knows nothing about a merchant outside the
simulation; and every sentence of cause names the simulation, because a sentence of cause that did not name
the simulation would read as a statement about the world outside it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ledgerlens.causal.engine import (
    ASSUMPTION_FIRST_DAY_COVERED,
    ASSUMPTION_FIRST_DAY_NOT_COVERED,
    run,
    sensitivity,
)
from ledgerlens.causal.intervention import Intervention
from ledgerlens.causal.report import render, render_sensitivity

AMOUNT_LINE = re.compile(r"before (\S+), after (\S+), difference ([^;\s]+)")
FORBIDDEN = re.compile(r"\bwould\b|\breal merchant\b|\bwould have\b|\bactually (received|paid)\b", re.IGNORECASE)


def _explained_report(world) -> str:
    return render(run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10))))


def test_every_amount_of_the_report_is_a_decimal_and_every_difference_recomputes(world_factory) -> None:
    """A difference without its two values is not a result, and a difference that does not recompute is worse."""
    world = world_factory(fee_model="ad_valorem")
    report = render(run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10))))

    amounts = AMOUNT_LINE.findall(report)
    assert len(amounts) >= 4
    for before, after, difference in amounts:
        try:
            before_value = Decimal(before)
            after_value = Decimal(after)
            difference_value = Decimal(difference)
        except InvalidOperation:
            raise AssertionError(f"an amount of the report is not a Decimal: {before}, {after}, {difference}") from None
        assert after_value - before_value == difference_value


def test_the_amounts_that_did_not_change_are_named(world) -> None:
    """A reader of the report sees what the intervention did not touch."""
    report = _explained_report(world)

    assert "Unchanged nodes:" in report
    unchanged_line = next(line for line in report.splitlines() if line.startswith("Unchanged nodes:"))
    assert "settlement.net" in unchanged_line
    assert "the amounts of fx.applied_rate that did not change: e0, e2, e3" in report


def test_no_sentence_of_the_report_says_what_a_merchant_outside_the_simulation_received(world_factory) -> None:
    """The engine knows nothing about a merchant outside the simulation, and the report says nothing either."""
    world = world_factory(fee_model="ad_valorem")
    report = render(run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10))))

    assert not FORBIDDEN.search(report)


def test_every_sentence_of_cause_names_the_simulation(world_factory) -> None:
    """A sentence of cause that did not name the simulation would read as a statement about the world."""
    world = world_factory(fee_model="ad_valorem")
    report = render(run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10))))

    cause_lines = [line for line in report.splitlines() if "cause" in line.lower()]
    assert cause_lines
    for line in cause_lines:
        assert "simulation" in line.lower()


def test_the_sensitivity_report_names_the_two_assumptions_and_the_movement(world) -> None:
    """The movement of the nodes between the two runs is a measurement of the assumption."""
    measured = sensitivity(
        world,
        Intervention("policy.markup_ceiling", Decimal("0.9")),
        (ASSUMPTION_FIRST_DAY_COVERED,),
        (ASSUMPTION_FIRST_DAY_NOT_COVERED,),
    )
    report = render_sensitivity(measured)

    assert ASSUMPTION_FIRST_DAY_COVERED in report
    assert ASSUMPTION_FIRST_DAY_NOT_COVERED in report
    amounts = AMOUNT_LINE.findall(report)
    assert amounts
    for before, after, difference in amounts:
        assert Decimal(after) - Decimal(before) == Decimal(difference)
    assert not FORBIDDEN.search(report)
