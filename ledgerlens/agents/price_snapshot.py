"""The snapshot of a price: the source, the day it was verified, and the staleness.

Why a price that was not verified is unknown and never zero: a price of zero would say that the call was free,
and a call is never free. The snapshot of a price carries the source and the day it was last verified, and a
price that was never verified has no amounts, because a guess is worse than an absence.

Why the snapshot says that it is stale: a price is a fact of a day, and a price of an old day decides as if the
day were today. The snapshot says that it is stale when it is older than the freshness the caller declares, so
a decision that reads a stale price says so instead of deciding as if the price were fresh.
"""

from __future__ import annotations

from datetime import date

from ledgerlens.economics.assumptions import PriceSnapshot

__all__ = ["PriceSnapshot", "is_stale", "staleness_of"]


def is_stale(snapshot: PriceSnapshot, *, freshness_days: int, today: date) -> bool:
    """Whether the snapshot of the price is stale, against the freshness the caller declares.

    A price that was never verified is never fresh: it has no day, and a price with no day is a price of no
    day. A price whose day is older than the freshness is stale.
    """
    if snapshot.last_verified is None:
        return True
    return (today - snapshot.last_verified).days > freshness_days


def staleness_of(snapshot: PriceSnapshot, *, freshness_days: int, today: date) -> str:
    """The label of the staleness of the snapshot, in words a reader can act on."""
    if snapshot.last_verified is None:
        return "the price was never verified, and an unverified price is unknown and never zero"
    if is_stale(snapshot, freshness_days=freshness_days, today=today):
        return (
            f"the price was last verified on {snapshot.last_verified.isoformat()}, and it is older than the "
            f"freshness of {freshness_days} days"
        )
    return "the price is fresh"
