"""The intervention is a typed record, and an invalid one is refused before anything is written.

What they guarantee, and why: an intervention on an unknown node, on a node with an invalid value and on a
date outside the horizon are each refused with a readable reason that names the field that is wrong, and the
output directory holds no result after a refusal, because a refusal that left a result behind would be a
result without a cause.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.causal.engine import run_and_write
from ledgerlens.causal.intervention import Intervention, InterventionRefused, validate


def test_an_intervention_on_an_unknown_node_is_refused_and_the_reason_names_the_target(horizon) -> None:
    """A node outside the registry is never a target, and the refusal says so."""
    reasons = validate(Intervention("fx.spread", Decimal("0.10")), horizon)

    assert reasons
    assert any("target" in reason and "fx.spread" in reason for reason in reasons)


def test_an_intervention_with_an_invalid_value_is_refused_and_the_reason_names_the_value(horizon) -> None:
    """A rate that is not a positive Decimal is not a rate, and the refusal names the do value."""
    negative = validate(Intervention("fx.reference_rate", Decimal("-1"), day=date(2024, 1, 10)), horizon)
    text = validate(Intervention("fx.reference_rate", "six", day=date(2024, 1, 10)), horizon)

    assert any("do_value" in reason for reason in negative)
    assert any("do_value" in reason for reason in text)


def test_an_intervention_on_a_date_outside_the_horizon_is_refused_and_the_reason_names_the_day(horizon) -> None:
    """The horizon of the world bounds the days of an intervention, and the refusal names the day."""
    reasons = validate(Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 2, 1)), horizon)

    assert any("day" in reason and "2024-02-01" in reason for reason in reasons)


def test_the_output_directory_holds_no_result_after_a_refusal(tmp_path: Path, world) -> None:
    """The refusal comes before the write, and the directory of the result stays empty."""
    out_dir = tmp_path / "out"
    refused = Intervention("fx.reference_rate", Decimal("-1"), day=date(2024, 1, 10))

    with pytest.raises(InterventionRefused):
        run_and_write(world, refused, out_dir)

    assert not out_dir.exists()
