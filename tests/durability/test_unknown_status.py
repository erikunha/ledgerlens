"""The unknown status of a call of the provider: the answer never arrived, and the run says so.

What they guarantee, and why: (a) a provider call whose answer never arrived carries the unknown status,
because a run that reported it as done would claim a success it cannot prove; (b) the cost of the call is
unknown and never zero, because a number of zero would say the call was free; (c) the call is not repeated,
because a repeated call may spend the money of the visitor twice for the same answer.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.durability.unknown import call_provider


def test_a_call_whose_answer_arrived_has_a_status_and_a_cost() -> None:
    """The call that answered has the status of ok and the cost of the answer."""
    call = call_provider("call-1", "openai:gpt-4.1-mini", lambda: Decimal("0.002"))

    assert call.status == "ok"
    assert call.cost_usd == Decimal("0.002")
    assert call.answered is True


def test_a_call_whose_answer_never_arrived_is_unknown_and_never_zero() -> None:
    """The status is unknown, the cost is unknown and never zero, and the call is not repeated."""
    calls = 0

    def provider_that_never_answers() -> Decimal:
        nonlocal calls
        calls += 1
        raise TimeoutError("the answer never arrived")

    call = call_provider("call-1", "openai:gpt-4.1-mini", provider_that_never_answers)

    assert call.status == "unknown"
    assert call.cost_usd is None
    assert call.answered is False
    assert calls == 1, "the call was repeated, and a repeated call may spend the money twice"
