"""The unknown status of a call of the provider: the answer never arrived, and the run says so.

Why the unknown status exists: a call of the provider whose answer never arrived is not a call that succeeded
and it is not a call that failed for a reason the repository knows. A run that reported it as done would claim
a success it cannot prove, and a run that reported a cost for it would charge the visitor for an answer that
never arrived.

Why the cost of an unknown call is unknown and never zero: a number of zero would say the call was free, and
the call may have spent the money of the visitor without the repository knowing (FR-011). The cost is None,
and the run names it.

Why the run neither repeats the call nor claims a success: a repeated call may spend the money twice for the
same answer, and a claimed success is a lie. The run marks the call unknown, names it in the result, and the
case goes to a person.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

__all__ = ["ProviderCall", "call_provider"]


@dataclass(frozen=True)
class ProviderCall:
    """The record of a call of the provider: its status and its cost, known or unknown.

    Why the status is a word and not a flag: the states of a call are "ok" and "unknown", and a flag of done
    would collapse the two into one, and the two are not the same.
    """

    call_id: str
    model: str
    status: str  # "ok" or "unknown"
    cost_usd: Decimal | None

    @property
    def answered(self) -> bool:
        """Whether the answer of the provider arrived."""
        return self.status == "ok"


def call_provider(
    call_id: str,
    model: str,
    provider: Callable[[], Decimal],
) -> ProviderCall:
    """The record of a call of the provider: the cost when the answer arrived, the unknown status when it did not.

    Why the call is not repeated: the provider is called once, and a call whose answer never arrived is marked
    unknown instead of repeated, because a repeated call may spend the money of the visitor twice for the same
    answer. The `provider` is the call itself, and it is invoked exactly once.
    """
    try:
        cost = provider()
    except Exception:
        # The answer never arrived: the status is unknown and the cost is unknown, never zero.
        return ProviderCall(call_id=call_id, model=model, status="unknown", cost_usd=None)
    return ProviderCall(call_id=call_id, model=model, status="ok", cost_usd=cost)
