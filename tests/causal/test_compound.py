"""The compound intervention names both of its targets, and its result is not the sum of the two singles.

What they guarantee, and why: a compound intervention over the reference rate and over the ceiling of the
policy names the two targets one by one, because a compound result that named one target would be a silent
cause, and the result of the compound intervention is not the sum of the results of the two single
interventions, because the descendants of one target read the value of the other: the markup bounded by the
new ceiling is computed from the implied markup of the new reference rate.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerlens.causal.engine import run
from ledgerlens.causal.intervention import CompoundIntervention, Intervention

DAY = date(2024, 1, 10)


def test_the_compound_intervention_names_both_of_its_targets(world) -> None:
    """A compound result names the two targets, and no target is hidden."""
    compound = CompoundIntervention(
        Intervention("fx.reference_rate", Decimal("6.00"), day=DAY),
        Intervention("policy.markup_ceiling", Decimal("0.9")),
    )
    result = run(world, compound)

    assert result.targets == ("fx.reference_rate", "policy.markup_ceiling")


def test_the_result_of_the_compound_is_not_the_sum_of_the_results_of_the_two_singles(world) -> None:
    """The ceiling stops binding when the reference rate moves, and the sum of the singles misses it."""
    reference = Intervention("fx.reference_rate", Decimal("6.00"), day=DAY)
    ceiling = Intervention("policy.markup_ceiling", Decimal("0.9"))
    compound = CompoundIntervention(reference, ceiling)

    single_reference = run(world, reference)
    single_ceiling = run(world, ceiling)
    both = run(world, compound)

    before = Decimal("1.0000")
    delta_reference = single_reference.after["fx.markup"]["e1"] - before
    delta_ceiling = single_ceiling.after["fx.markup"]["e1"] - before
    delta_compound = both.after["fx.markup"]["e1"] - before

    assert delta_compound != delta_reference + delta_ceiling
    assert both.after["fx.markup"]["e1"] == single_reference.after["fx.markup"]["e1"]
    assert both.after["fx.applied_rate"]["e1"] == Decimal("5.95")
    assert both.unknown == ()
