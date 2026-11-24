"""The engine: the descendants of the target are recomputed along the edges, and the history is not rewritten.

What they guarantee, and why: two runs over the same base carry the same digest of the exogenous stream,
because two runs over two streams are two worlds and not a comparison; the changed nodes are the descendants
of the target in the registry, because only a declared edge makes a descendant; every applied rate of the
ledger is unchanged after an intervention on the reference rate of a day with no entries, because the
reference rate of a later day does not reach into the past; and an intervention on a merchant policy names
the periods it covered and leaves every node outside them unchanged.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerlens.causal.engine import run
from ledgerlens.causal.intervention import Intervention
from ledgerlens.causal.registry import descendants_of
from ledgerlens.sim.twin.arrivals import digest_of, generate_stream
from ledgerlens.sim.twin.config import TwinConfig


def test_two_runs_over_the_same_base_carry_the_same_digest_of_the_exogenous_stream(world) -> None:
    """The digest of the exogenous stream is the proof that the two runs compare one world."""
    intervention = Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10))
    first = run(world, intervention)
    second = run(world, intervention)

    expected = digest_of(generate_stream(TwinConfig(seed=42)))
    assert first.exogenous_digest == second.exogenous_digest == expected


def test_the_changed_nodes_are_the_descendants_of_the_target_in_the_registry(world) -> None:
    """Only a declared edge makes a descendant, and every descendant that changed is explained."""
    result = run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10)))

    assert {change.node for change in result.changed} == set(descendants_of("fx.reference_rate"))
    assert result.unknown == ()
    assert result.after["fx.applied_rate"]["e1"] == Decimal("5.95")
    assert result.after["fx.markup"]["e1"] == Decimal("0.8333")


def test_an_intervention_on_the_reference_rate_leaves_every_applied_rate_of_the_ledger_unchanged(world) -> None:
    """The reference rate of a later day does not reach into the past, and the history is not rewritten."""
    result = run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 31)))

    assert result.changed == ()
    assert result.unknown == ()
    for entry_id, rate in result.before["fx.applied_rate"].items():
        assert result.after["fx.applied_rate"][entry_id] == rate


def test_an_intervention_on_a_merchant_policy_names_the_periods_and_leaves_the_rest_unchanged(world) -> None:
    """The policy covers the first fifteen days of the month, and the entries outside them do not move."""
    result = run(world, Intervention("policy.markup_ceiling", Decimal("0.9")))

    assert result.covered_periods == ((date(2024, 1, 1), date(2024, 1, 15)),)
    assert {change.node for change in result.changed} == {"fx.markup"}
    assert result.after["fx.markup"]["e0"] == Decimal("0.9000")
    assert result.after["fx.markup"]["e1"] == Decimal("0.9000")
    assert result.after["fx.markup"]["e2"] == result.before["fx.markup"]["e2"]
    assert result.after["fx.markup"]["e3"] == result.before["fx.markup"]["e3"]
    assert result.after["fx.applied_rate"] == result.before["fx.applied_rate"]
    assert result.after["settlement.net"] == result.before["settlement.net"]
