"""A change without a declared edge is unknown: the missing edge is named, and the claim is unsupported.

What they guarantee, and why: when the fee model of the world is ad valorem, the fee of the settlement reads
the applied rate, and the registry declares no edge from the applied rate to the fee. An intervention on the
reference rate then moves the fee, and the engine reports the fee and the net as `unknown`, names the missing
edge, and lists the claims as unsupported causal claims, because a tool that says "because" when it cannot is
worse than a tool that says nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerlens.causal.engine import run
from ledgerlens.causal.intervention import Intervention


def test_a_node_that_changes_without_a_declared_edge_is_reported_as_unknown(world_factory) -> None:
    """The fee reads the applied rate in the ad valorem world, and the registry declares no such edge."""
    world = world_factory(fee_model="ad_valorem")
    result = run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10)))

    unknown_nodes = {change.node for change in result.unknown}
    assert unknown_nodes == {"settlement.fee", "settlement.net"}
    for change in result.unknown:
        assert change.status == "unknown"

    fee = next(change for change in result.unknown if change.node == "settlement.fee")
    assert ("fx.applied_rate", "settlement.fee") in fee.missing_edges
    assert "fx.applied_rate -> settlement.fee" in fee.reason

    assert any("settlement.fee" in claim for claim in result.unsupported_claims)
    assert any("settlement.net" in claim for claim in result.unsupported_claims)

    assert result.after["settlement.fee"] == Decimal("3.7640")
    assert result.after["settlement.net"] == Decimal("1728.7360")


def test_the_explained_changes_are_still_the_descendants_when_an_unknown_is_present(world_factory) -> None:
    """The unknown does not pollute the explained: the descendants of the target stay the explained ones."""
    world = world_factory(fee_model="ad_valorem")
    result = run(world, Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10)))

    assert {change.node for change in result.changed} == {"fx.applied_rate", "fx.markup"}
