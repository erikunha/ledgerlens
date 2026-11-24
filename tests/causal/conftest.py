"""The shared factory of the toy world of the causal tests.

Why a toy world: the engine of the causal interventions is tested over a world small enough to check by hand,
with four entries, one policy period and one settlement. The world is built by a factory so that every test
starts from the same consistent base, and the variants of the world (the ad valorem fee model of the unknown
link test) are one argument away. The digest of the exogenous stream comes from the twin of the repository,
because the engine compares two runs only when the exogenous stream is the same.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ledgerlens.causal.engine import Entry, WorldState
from ledgerlens.sim.twin.arrivals import digest_of, generate_stream
from ledgerlens.sim.twin.config import TwinConfig

DAY0 = date(2024, 1, 1)
HORIZON = (date(2024, 1, 1), date(2024, 1, 31))
PERIOD = (date(2024, 1, 1), date(2024, 1, 15))


def exogenous_digest() -> str:
    """The digest of the arrival stream of the seed of the repository, for the checks of the engine."""
    return digest_of(generate_stream(TwinConfig(seed=42)))


def make_world(
    *,
    fee_model: str = "fixed",
    fee_bps: Decimal = Decimal("0.002"),
    ceiling: Decimal = Decimal("1.5"),
) -> WorldState:
    """The toy world of the causal tests: four entries, one policy period and one settlement.

    The reference rate is 5.00 every day of January, the spread of the merchant is 0.05 over the reference,
    and the policy covers the first fifteen days of the month, so that the entry of the first day and the
    entry of the tenth day are covered and the entries of the twentieth and of the twenty fifth day are not.
    """
    days = [DAY0 + timedelta(days=offset) for offset in range(31)]
    entries = (
        Entry("e0", date(2024, 1, 1), Decimal("10")),
        Entry("e1", date(2024, 1, 10), Decimal("100")),
        Entry("e2", date(2024, 1, 20), Decimal("200")),
        Entry("e3", date(2024, 1, 25), Decimal("50")),
    )
    return WorldState(
        exogenous_digest=exogenous_digest(),
        horizon=HORIZON,
        reference_rates={day: Decimal("5.00") for day in days},
        entries=entries,
        merchant_spread=Decimal("0.05"),
        policy_rule="fx_markup_limit",
        policy_deadline_window=10,
        policy_markup_ceiling=ceiling,
        policy_periods=(PERIOD,),
        fee_model=fee_model,
        fee_bps=fee_bps,
        settlement_gross=Decimal("1732.50"),
        settlement_refunds=Decimal("0"),
        settlement_fees=Decimal("4.00"),
        settlement_period=(DAY0, date(2024, 1, 31)),
        settlement_currency="EUR",
        dispute_opened=date(2024, 1, 15),
        review_as_of=date(2024, 1, 22),
    )


@pytest.fixture
def world() -> WorldState:
    """The base world of the causal tests, with the fixed fee model."""
    return make_world()


@pytest.fixture
def world_factory():
    """The factory of the toy world, for the tests that need a variant of the base world."""
    return make_world


@pytest.fixture
def horizon() -> tuple[date, date]:
    """The horizon of the toy world, for the validation of the days of an intervention."""
    return HORIZON
