"""An intervention that breaks a money invariant is refused, and the state of the world is the one before it.

What they guarantee, and why: an intervention on the reference rate that drives the applied rate of an entry
to zero or below breaks the invariant fx_rate_positive_and_finite of `ledgerlens/sandbox/invariants.py`, and
the engine refuses it and names the invariant, because an intervention that breaks the world is not applied,
and the world after the refusal is the world before the intervention.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.causal.engine import run, run_and_write
from ledgerlens.causal.intervention import Intervention, InterventionRefused


def test_an_intervention_that_breaks_a_money_invariant_is_refused_and_the_invariant_is_named(world) -> None:
    """A reference rate under the spread drives the applied rate below zero, and the world refuses it."""
    breaking = Intervention("fx.reference_rate", Decimal("0.04"), day=date(2024, 1, 10))

    with pytest.raises(InterventionRefused, match="fx_rate_positive_and_finite"):
        run(world, breaking)


def test_the_state_of_the_world_after_the_refusal_is_the_one_before_the_intervention(world, tmp_path: Path) -> None:
    """The refusal comes before the write, and the world keeps the values it had."""
    breaking = Intervention("fx.reference_rate", Decimal("0.04"), day=date(2024, 1, 10))
    out_dir = tmp_path / "out"

    with pytest.raises(InterventionRefused):
        run_and_write(world, breaking, out_dir)

    assert not out_dir.exists()
    assert world.reference_rates[date(2024, 1, 10)] == Decimal("5.00")
