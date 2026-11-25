"""The typed record of an intervention over the synthetic world, and its validation.

Why an intervention is a typed record: an intervention says which node of the registry is intervened on, the
value the node takes, the day the intervention applies to when the node is dated, and the assumptions the run
carries. A record that is not typed cannot be checked, and an intervention that is not checked is an
intervention that writes a result nobody can trust.

Why a refused intervention writes nothing: a refusal that left a result behind would be a result without a
cause, and the engine refuses before anything is written. The reasons of the refusal name the field that is
wrong, so the caller fixes the field and not the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ledgerlens.causal.registry import node_of

__all__ = [
    "DATED_NODES",
    "CompoundIntervention",
    "Intervention",
    "InterventionRefused",
    "validate",
]

# The nodes whose intervention is scoped to one day: the rate of a day and the values of the entries of a day.
DATED_NODES = frozenset({"fx.reference_rate", "fx.applied_rate", "fx.markup"})


class InterventionRefused(ValueError):
    """The intervention is not valid, and nothing was written. The message names the fields that are wrong."""


@dataclass(frozen=True)
class Intervention:
    """One intervention over the synthetic world: the node, the value it takes, the day and the assumptions.

    The do value is typed per node of the registry: a positive Decimal for a rate, a Decimal for an amount or
    a percentage, an int for a window of days, a date for a date, and a non empty string for a rule or a
    decision. The day is required for the dated nodes, because the rate of a day and the entries of a day are
    not the rate of another day.
    """

    target: str
    do_value: object
    day: date | None = None
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompoundIntervention:
    """Two interventions applied at once, named one by one, because a compound result hides no target.

    Why the compound intervention names both of its targets: a compound result that named one target would be
    a silent cause, and the report of the engine names the two targets one by one. The result of the compound
    intervention is not the sum of the results of the two single interventions, because the descendants of one
    target can read the value of the other.
    """

    first: Intervention
    second: Intervention


def _is_decimal(value: object) -> bool:
    """A Decimal and not a bool, because a bool is an int and an int is not a Decimal."""
    return isinstance(value, Decimal)


def _positive_decimal(value: object) -> str | None:
    if not _is_decimal(value):
        return "the do_value is not a Decimal"
    if not value.is_finite() or value <= 0:
        return f"the do_value {value} is not a positive and finite Decimal"
    return None


def _non_negative_decimal(value: object) -> str | None:
    if not _is_decimal(value):
        return "the do_value is not a Decimal"
    if not value.is_finite() or value < 0:
        return f"the do_value {value} is not a non negative and finite Decimal"
    return None


def _any_decimal(value: object) -> str | None:
    if not _is_decimal(value):
        return "the do_value is not a Decimal"
    if not value.is_finite():
        return f"the do_value {value} is not a finite Decimal"
    return None


def _window_of_days(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return "the do_value is not an int"
    if value <= 0:
        return f"the do_value {value} is not a positive number of days"
    return None


def _non_empty_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "the do_value is not a non empty string"
    return None


def _tuple_of_text(value: object) -> str | None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item.strip() for item in value):
        return "the do_value is not a tuple of non empty strings"
    return None


_VALUE_CHECKS = {
    "fx.reference_rate": _positive_decimal,
    "fx.applied_rate": _positive_decimal,
    "fx.markup": _non_negative_decimal,
    "policy.rule": _non_empty_text,
    "policy.deadline_window": _window_of_days,
    "policy.markup_ceiling": _non_negative_decimal,
    "settlement.fee": _non_negative_decimal,
    "settlement.net": _any_decimal,
    "review.escalation": _tuple_of_text,
    "review.decision": _non_empty_text,
}

# The nodes whose do value is a date of the horizon: the date of a settlement and the deadline of a dispute.
_DATE_VALUED_NODES = frozenset({"settlement.date", "review.dispute_deadline"})


def _validate_one(
    intervention: Intervention, horizon: tuple[date, date], known_assumptions: tuple[str, ...]
) -> tuple[str, ...]:
    """The reasons the intervention is refused, each naming the field that is wrong. Empty when it is valid."""
    reasons: list[str] = []
    node = node_of(intervention.target)
    if node is None:
        return (f"the target {intervention.target!r} is not a node of the registry",)

    if intervention.target in _DATE_VALUED_NODES:
        value = intervention.do_value
        if not isinstance(value, date):
            reasons.append("the do_value is not a date")
        elif not horizon[0] <= value <= horizon[1]:
            reasons.append(f"the do_value {value} is outside the horizon {horizon[0]} to {horizon[1]}")
    else:
        check = _VALUE_CHECKS[intervention.target]
        invalid = check(intervention.do_value)
        if invalid is not None:
            reasons.append(invalid)

    if intervention.target in DATED_NODES:
        if intervention.day is None:
            reasons.append("the day is missing, and the node is dated")
        elif not horizon[0] <= intervention.day <= horizon[1]:
            reasons.append(f"the day {intervention.day} is outside the horizon {horizon[0]} to {horizon[1]}")
    elif intervention.day is not None:
        reasons.append(f"the day is read only by a dated node, and {intervention.target} is not dated")

    for assumption in intervention.assumptions:
        if assumption not in known_assumptions:
            reasons.append(f"the assumption {assumption!r} is not a registered assumption")
    return tuple(reasons)


def validate(
    intervention: Intervention | CompoundIntervention,
    horizon: tuple[date, date],
    known_assumptions: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """The reasons the intervention is refused, each naming the field that is wrong. Empty when it is valid.

    A compound intervention is valid when both of its interventions are valid and the two targets differ,
    because a compound intervention over one target twice is a single intervention written twice.
    """
    if isinstance(intervention, CompoundIntervention):
        reasons = list(_validate_one(intervention.first, horizon, known_assumptions))
        reasons.extend(_validate_one(intervention.second, horizon, known_assumptions))
        if intervention.first.target == intervention.second.target:
            reasons.append(f"the two targets of the compound intervention are both {intervention.first.target!r}")
        return tuple(reasons)
    return _validate_one(intervention, horizon, known_assumptions)
