"""The business rules of the sandbox: the invariants that every projection of a branch has to hold.

Why they exist: a visitor may change a rate, a deadline or an amount, and some of those changes are not possible
in the world the sandbox simulates. A rule that does not hold is not a strange value, it is a state that never
happens, so the mutation that produces it is refused and the branch keeps the revision and the hash it had
(FR-018).

The rules are the ones of the specification of the feature:

* the FX rate is positive and finite;
* a refund is not above the captured amount of its transaction;
* the deadline of a chargeback is not before the day it was opened;
* the state of a record is a state the ledger knows;
* a merchant is not settled twice for the same period.

Each rule has an identifier and a readable description, and a rule that does not hold says its own name in the
reason, so the refusal names the rule that failed (FR-015).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from ledgerlens.sandbox.projector import ProjectedState

# The states the ledger knows for a transaction and for a refund.
TRANSACTION_STATUSES = frozenset(
    {
        "authorized",
        "captured",
        "failed",
        "refunded",
        "partially_refunded",
        "disputed",
        "charged_back",
    }
)
REFUND_STATUSES = frozenset({"requested", "paid", "rejected"})


@dataclass(frozen=True)
class InvariantResult:
    """The outcome of one rule over one projection."""

    identifier: str
    description: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "description": self.description,
            "passed": self.passed,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Invariant:
    """One named rule of the domain.

    The predicate returns None when the rule holds, and the reason when it does not. The reason names the rule
    that failed, so a refusal is readable without a table of codes.
    """

    identifier: str
    description: str
    predicate: Callable[[ProjectedState], str | None]

    def result(self, state: ProjectedState) -> InvariantResult:
        """The outcome of the rule over one projection."""
        reason = self.predicate(state)
        return InvariantResult(self.identifier, self.description, reason is None, reason or "")


def _fx_rate_positive_and_finite(state: ProjectedState) -> str | None:
    """Every applied rate is a positive and finite number."""
    for row in state.rows.get("fx_applied", []):
        try:
            rate = Decimal(str(row.get("applied_rate")))
        except InvalidOperation:
            return (
                f"the invariant fx_rate_positive_and_finite does not hold:"
                f" the rate of {row.get('id')} is not a number"
            )
        if not rate.is_finite() or rate <= 0:
            return (
                f"the invariant fx_rate_positive_and_finite does not hold:"
                f" the rate of {row.get('id')} is {rate}"
            )
    return None


def _refund_not_above_captured(state: ProjectedState) -> str | None:
    """No refund asks for more than the transaction captured."""
    for row in state.rows.get("refunds", []):
        transaction = state.row("transactions", str(row.get("transaction_id")))
        if transaction is None:
            return (
                f"the invariant refund_not_above_captured does not hold:"
                f" the transaction {row.get('transaction_id')} of the refund {row.get('id')} is not in the projection"
            )
        if row.get("requested_currency") != transaction.get("currency"):
            # The amounts are in two currencies, and comparing them would say nothing.
            continue
        if int(row.get("requested_amount_minor")) > int(transaction.get("amount_minor")):
            return (
                f"the invariant refund_not_above_captured does not hold:"
                f" the refund {row.get('id')} is above the captured amount of {transaction.get('id')}"
            )
    return None


def _chargeback_deadline_not_before_opening(state: ProjectedState) -> str | None:
    """The deadline of a chargeback is not before the day the case was opened."""
    for row in state.rows.get("chargebacks", []):
        try:
            opened = date.fromisoformat(str(row.get("opened_at"))[:10])
            deadline = date.fromisoformat(str(row.get("deadline"))[:10])
        except ValueError:
            return (
                f"the invariant chargeback_deadline_not_before_opening does not hold:"
                f" the dates of the chargeback {row.get('id')} are not days"
            )
        if deadline < opened:
            return (
                f"the invariant chargeback_deadline_not_before_opening does not hold:"
                f" the deadline of {row.get('id')} is before the day it was opened"
            )
    return None


def _valid_state_transition(state: ProjectedState) -> str | None:
    """Every record is in a state the ledger knows."""
    for row in state.rows.get("transactions", []):
        if row.get("status") not in TRANSACTION_STATUSES:
            return (
                f"the invariant valid_state_transition does not hold:"
                f" the transaction {row.get('id')} is in the state {row.get('status')}"
            )
    for row in state.rows.get("refunds", []):
        if row.get("status") not in REFUND_STATUSES:
            return (
                f"the invariant valid_state_transition does not hold:"
                f" the refund {row.get('id')} is in the state {row.get('status')}"
            )
    return None


def _no_double_settlement(state: ProjectedState) -> str | None:
    """A merchant is not settled twice for the same period."""
    seen: set[tuple[Any, Any, Any]] = set()
    for row in state.rows.get("settlements", []):
        key = (row.get("merchant_id"), row.get("period_start"), row.get("period_end"))
        if key in seen:
            return (
                f"the invariant no_double_settlement does not hold:"
                f" the merchant {row.get('merchant_id')} has two settlements for the period {row.get('period_start')}"
            )
        seen.add(key)
    return None


INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "fx_rate_positive_and_finite",
        "every applied FX rate is a positive and finite number",
        _fx_rate_positive_and_finite,
    ),
    Invariant(
        "refund_not_above_captured",
        "no refund asks for more than the transaction captured",
        _refund_not_above_captured,
    ),
    Invariant(
        "chargeback_deadline_not_before_opening",
        "the deadline of a chargeback is not before the day the case was opened",
        _chargeback_deadline_not_before_opening,
    ),
    Invariant(
        "valid_state_transition",
        "every record is in a state the ledger knows",
        _valid_state_transition,
    ),
    Invariant(
        "no_double_settlement",
        "a merchant is not settled twice for the same period",
        _no_double_settlement,
    ),
)


def evaluate(state: ProjectedState) -> list[InvariantResult]:
    """The outcome of every rule over one projection, in the order of the rules."""
    return [invariant.result(state) for invariant in INVARIANTS]


def failures(state: ProjectedState) -> list[InvariantResult]:
    """The rules that do not hold over one projection."""
    return [result for result in evaluate(state) if not result.passed]


__all__ = [
    "INVARIANTS",
    "REFUND_STATUSES",
    "TRANSACTION_STATUSES",
    "Invariant",
    "InvariantResult",
    "evaluate",
    "failures",
]
