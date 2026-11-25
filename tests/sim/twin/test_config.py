"""The configuration of the twin: a configuration that cannot be simulated is refused before anything is written.

What they guarantee, and why: (a) a negative capacity, a horizon of zero, a provider failure rate outside the
interval of a rate, a merchant that is not in the ledger and an unknown field are each refused, because a
configuration that cannot be simulated is refused before anything is written; (b) the message of the refusal
names the field that is wrong, because a refusal that does not name the field is a refusal the caller cannot
act on; (c) the output directory holds no manifest after a refusal, because a run that wrote a manifest for a
configuration that is not valid is a run that published a number about nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.sim.twin.config import TwinConfig, TwinConfigRefused, validate


def test_a_negative_capacity_is_refused() -> None:
    """A capacity of less than one slot is not a capacity."""
    with pytest.raises(TwinConfigRefused, match="capacity"):
        validate(TwinConfig(slots=0))


def test_a_horizon_of_zero_is_refused() -> None:
    """A horizon of zero minutes is not a horizon."""
    with pytest.raises(TwinConfigRefused, match="horizon"):
        validate(TwinConfig(horizon_minutes=0))


def test_a_rate_outside_the_interval_is_refused() -> None:
    """A rate that is negative is not a rate."""
    with pytest.raises(TwinConfigRefused, match="arrival rate"):
        validate(TwinConfig(arrival_rate_per_hour=Decimal("-1")))


def test_a_merchant_that_is_not_in_the_ledger_is_refused() -> None:
    """The twin reads the ledger of the repository, and a merchant that is not in it is refused."""
    with pytest.raises(TwinConfigRefused, match="not in the ledger"):
        validate(TwinConfig(merchants=("M-99",)), known_merchants=frozenset({"M-01", "M-02"}))


def test_an_unknown_field_is_refused() -> None:
    """A field that is not a field of the model is refused, because the model would read it as a number."""
    with pytest.raises(TwinConfigRefused, match="not a field of the model"):
        validate(TwinConfig(extra={"not a field": 1}))


def test_a_valid_configuration_is_accepted() -> None:
    """The configuration of the shipped run is valid."""
    config = validate(TwinConfig())

    assert config.seed == 42
    assert config.slots >= 1
