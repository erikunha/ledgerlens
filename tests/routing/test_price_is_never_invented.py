"""The snapshot of a price: a price that was not verified is unknown and never zero, and a stale price says so.

What they guarantee, and why: (a) a model without a verified price has no dollar amount, because a price of zero
would say that the call was free; (b) a price whose day is older than the freshness the caller declares is
stale, and the snapshot says so; (c) a price that was never verified is never fresh.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ledgerlens.agents.price_snapshot import is_stale, staleness_of
from ledgerlens.economics.assumptions import PriceSnapshot

TODAY = date(2026, 11, 25)


def test_a_model_without_a_verified_price_has_no_dollar_amount() -> None:
    """A price that was not verified is unknown, and unknown is never zero."""
    snapshot = PriceSnapshot(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None)

    assert snapshot.is_verified is False
    assert snapshot.input_per_1m_usd is None
    assert snapshot.output_per_1m_usd is None
    assert is_stale(snapshot, freshness_days=30, today=TODAY) is True
    assert "never zero" in staleness_of(snapshot, freshness_days=30, today=TODAY)


def test_a_price_older_than_the_freshness_is_stale() -> None:
    """A price is a fact of a day, and a price of an old day decides as if the day were today."""
    snapshot = PriceSnapshot(
        source="manual",
        last_verified=date(2026, 10, 1),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    )

    assert is_stale(snapshot, freshness_days=30, today=TODAY) is True
    assert "older than the freshness" in staleness_of(snapshot, freshness_days=30, today=TODAY)
    assert is_stale(snapshot, freshness_days=90, today=TODAY) is False
    assert staleness_of(snapshot, freshness_days=90, today=TODAY) == "the price is fresh"
