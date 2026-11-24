"""The engine of the causal counterfactual interventions: one field changes, and the rest follows the registry.

Why the engine changes one field and the rest follows the registry: a counterfactual that recomputes the whole
world is a new world and not a comparison, so the engine applies the intervention to one node of the registry,
recomputes the descendants of the node along the edges of the registry, and leaves every other node with the
value it had. The applied rate of a transaction is the rate that was applied on the day of the transaction, and
the reference rate of a later day does not reach into the past: the history is not rewritten.

Why a change without a declared edge is never a cause: the engine reads every node before and after, and a node
that changed without a declared edge from the target is reported as `unknown` with the missing edge named. A
tool that says "because" when it cannot is worse than a tool that says nothing, so the unknown is a first class
result of the engine and not an error.

Why an intervention that breaks the world is not applied: the money invariants of
`ledgerlens/sandbox/invariants.py` are the rules of the world, and an intervention whose recomputation breaks
one of them is refused, and the state of the world is the one before the intervention.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.causal.intervention import CompoundIntervention, Intervention, InterventionRefused, validate
from ledgerlens.causal.registry import EDGES, NODES, descendants_of
from ledgerlens.sandbox import invariants
from ledgerlens.sandbox.projector import ProjectedState
from ledgerlens.sim.calendars import payout_date
from ledgerlens.tools.calculator import _implied_markup_pct, _net_settlement

__all__ = [
    "ASSUMPTION_FIRST_DAY_COVERED",
    "ASSUMPTION_FIRST_DAY_NOT_COVERED",
    "KNOWN_ASSUMPTIONS",
    "CausalResult",
    "Entry",
    "NodeChange",
    "Sensitivity",
    "UnknownChange",
    "WorldState",
    "run",
    "run_and_write",
    "sensitivity",
]

PCT = Decimal("0.0001")
MONEY = Decimal("0.0001")

# The registered assumptions of the engine: each one says how the coverage of a policy period reads its first
# day. The sensitivity of a result to an assumption is a measurement of the assumption and not an interval of
# confidence, because the two runs differ only in the assumption.
ASSUMPTION_FIRST_DAY_COVERED = "the policy covers the entry on the first day of the period"
ASSUMPTION_FIRST_DAY_NOT_COVERED = "the policy does not cover the entry on the first day of the period"
KNOWN_ASSUMPTIONS = (ASSUMPTION_FIRST_DAY_COVERED, ASSUMPTION_FIRST_DAY_NOT_COVERED)

# The rule of the toy world for the review nodes: a dispute whose deadline is five days away or less is
# escalated. The registry names the function of the repository where the full rule of the escalation lives.
_ESCALATION_WITHIN_DAYS = 5


@dataclass(frozen=True)
class Entry:
    """One transaction of the toy world: the identifier, the day and the units of the foreign currency.

    The applied rate of the entry is not stored: it is recomputed from the reference rate of the day and the
    spread of the merchant, so that the base world is consistent by construction and an intervention on the
    reference rate of the day of the entry recomputes the applied rate of the entry and of no other.
    """

    entry_id: str
    day: date
    units: Decimal


@dataclass(frozen=True)
class WorldState:
    """The state of the toy world the engine reads: the parameters and the facts, never the derived values.

    Why the world holds no derived value: the derived values are recomputed by the readers of the nodes, and a
    world that stored them would hold two sources of truth. The digest of the exogenous stream is part of the
    state, because two runs over two different streams are two worlds and not a comparison.
    """

    exogenous_digest: str
    horizon: tuple[date, date]
    reference_rates: Mapping[date, Decimal]
    entries: tuple[Entry, ...]
    merchant_spread: Decimal
    policy_rule: str
    policy_deadline_window: int
    policy_markup_ceiling: Decimal
    policy_periods: tuple[tuple[date, date], ...]
    fee_model: str
    fee_bps: Decimal
    settlement_gross: Decimal
    settlement_refunds: Decimal
    settlement_fees: Decimal
    settlement_period: tuple[date, date]
    settlement_currency: str
    dispute_opened: date
    review_as_of: date


@dataclass(frozen=True)
class NodeChange:
    """The value of a node before and after the intervention, with the difference when the value is an amount."""

    node: str
    before: Any
    after: Any


@dataclass(frozen=True)
class UnknownChange:
    """A node that changed without a declared edge: the status is `unknown` and the missing edge is named.

    Why the unknown names the missing edge: a reader of the result has to be able to open the registry and see
    the edge that is not there, and the claim is listed as an unsupported causal claim, because a change the
    registry does not explain is not a cause the registry supports.
    """

    node: str
    before: Any
    after: Any
    missing_edges: tuple[tuple[str, str], ...]
    reason: str
    status: str = "unknown"


@dataclass(frozen=True)
class CausalResult:
    """The result of a run: the known, the unknown and the unsupported claims, with the two states read.

    The before and after mappings hold the value of every node of the registry, so the report can name the
    amounts that did not change, and a reader can recompute every difference with `Decimal`.
    """

    targets: tuple[str, ...]
    exogenous_digest: str
    assumptions: tuple[str, ...]
    changed: tuple[NodeChange, ...]
    unknown: tuple[UnknownChange, ...]
    unchanged: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    covered_periods: tuple[tuple[date, date], ...]
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    interventions: tuple[Intervention, ...] = ()


@dataclass(frozen=True)
class Sensitivity:
    """The two runs of one intervention under two assumptions, and the movement of the nodes between them.

    Why the sensitivity is a measurement of the assumption and not an interval of confidence: the two runs
    share the base, the exogenous stream and the intervention, and they differ only in the assumption, so the
    movement of a node between the two runs is the sensitivity of the node to the assumption.
    """

    first: CausalResult
    second: CausalResult
    movement: tuple[NodeChange, ...]


# The nodes each reader reads, declared beside the readers: the walk of the missing edges compares what a
# reader reads with what the registry declares, and a change that arrives by an undeclared reading is the
# unknown the engine reports. The fee of a settlement reads the applied rate only when the fee model of the
# world is ad valorem.
_READS: dict[str, tuple[str, ...]] = {
    "fx.reference_rate": (),
    "fx.applied_rate": ("fx.reference_rate",),
    "fx.markup": ("fx.applied_rate", "fx.reference_rate", "policy.markup_ceiling"),
    "policy.rule": (),
    "policy.deadline_window": ("policy.rule",),
    "policy.markup_ceiling": (),
    "settlement.fee": (),
    "settlement.net": ("settlement.fee",),
    "settlement.date": (),
    "review.dispute_deadline": ("policy.deadline_window",),
    "review.escalation": ("review.dispute_deadline",),
    "review.decision": ("review.escalation",),
}

_DECLARED = frozenset((edge.source, edge.target) for edge in EDGES)


def _reads_of(node: str, world: WorldState) -> tuple[str, ...]:
    """The nodes the reader of the node reads in this world: the fee reads the applied rate when it is ad valorem."""
    if node == "settlement.fee" and world.fee_model == "ad_valorem":
        return ("fx.applied_rate",)
    return _READS[node]


def _coverage(assumptions: tuple[str, ...]) -> Callable[[date, tuple[tuple[date, date], ...]], bool]:
    """The rule of coverage of the periods under the assumptions: the first day of a period is in or out."""
    exclusive = ASSUMPTION_FIRST_DAY_NOT_COVERED in assumptions

    def covered(day: date, periods: tuple[tuple[date, date], ...]) -> bool:
        for start, end in periods:
            if exclusive and day == start:
                continue
            if start <= day <= end:
                return True
        return False

    return covered


def _read_all(
    world: WorldState, overrides: Mapping[str, tuple[date | None, Any]], assumptions: tuple[str, ...]
) -> dict[str, Any]:
    """The value of every node of the registry, recomputed from the parameters and the overrides.

    An override is the do operator of the intervention: the node is cut from its readers and takes the value
    of the intervention, and the descendants recompute from it. The readers use the functions the registry
    names, so the recomputation is the recomputation of the code and not a model of it.
    """
    covered = _coverage(assumptions)

    reference = dict(world.reference_rates)
    reference_override = overrides.get("fx.reference_rate")
    if reference_override is not None:
        reference[reference_override[0]] = reference_override[1]

    def reference_of(day: date) -> Decimal:
        return reference[day]

    def applied_of(entry: Entry) -> Decimal:
        override = overrides.get("fx.applied_rate")
        if override is not None and override[0] == entry.day:
            return override[1]
        return reference_of(entry.day) - world.merchant_spread

    applied = {entry.entry_id: applied_of(entry) for entry in world.entries}

    ceiling_override = overrides.get("policy.markup_ceiling")
    ceiling = ceiling_override[1] if ceiling_override is not None else world.policy_markup_ceiling
    markup: dict[str, Decimal] = {}
    for entry in world.entries:
        raw = {"applied_rate": str(applied[entry.entry_id]), "reference_rate": str(reference_of(entry.day))}
        implied, _formula = _implied_markup_pct(
            {"applied_rate": applied[entry.entry_id], "reference_rate": reference_of(entry.day)}, 4, raw
        )
        effective = min(implied, ceiling) if covered(entry.day, world.policy_periods) else implied
        markup[entry.entry_id] = effective.quantize(PCT)

    rule_override = overrides.get("policy.rule")
    window_override = overrides.get("policy.deadline_window")
    window = window_override[1] if window_override is not None else world.policy_deadline_window

    fee_override = overrides.get("settlement.fee")
    if fee_override is not None:
        fee = fee_override[1]
    elif world.fee_model == "ad_valorem":
        start, end = world.settlement_period
        in_period = (entry for entry in world.entries if start <= entry.day <= end)
        total = sum((entry.units * applied[entry.entry_id] * world.fee_bps for entry in in_period), Decimal("0"))
        fee = total.quantize(MONEY)
    else:
        fee = world.settlement_fees

    net_override = overrides.get("settlement.net")
    if net_override is not None:
        net = net_override[1]
    else:
        net, _net_formula = _net_settlement(
            {"gross": world.settlement_gross, "refunds": world.settlement_refunds, "fees": fee},
            2,
            {
                "gross": str(world.settlement_gross),
                "refunds": str(world.settlement_refunds),
                "fees": str(fee),
            },
        )

    date_override = overrides.get("settlement.date")
    settlement_day = (
        date_override[1]
        if date_override is not None
        else payout_date(world.settlement_period[1], world.settlement_currency)
    )

    deadline_override = overrides.get("review.dispute_deadline")
    deadline = (
        deadline_override[1] if deadline_override is not None else world.dispute_opened + timedelta(days=window)
    )
    escalation_override = overrides.get("review.escalation")
    days_to_deadline = (deadline - world.review_as_of).days
    escalation = (
        escalation_override[1]
        if escalation_override is not None
        else (("dispute_deadline_within_days",) if days_to_deadline <= _ESCALATION_WITHIN_DAYS else ())
    )
    decision_override = overrides.get("review.decision")
    decision = (
        decision_override[1] if decision_override is not None else ("escalate" if escalation else "no_escalation")
    )

    return {
        "fx.reference_rate": reference,
        "fx.applied_rate": applied,
        "fx.markup": markup,
        "policy.rule": rule_override[1] if rule_override is not None else world.policy_rule,
        "policy.deadline_window": window,
        "policy.markup_ceiling": ceiling,
        "settlement.fee": fee,
        "settlement.net": net,
        "settlement.date": settlement_day,
        "review.dispute_deadline": deadline,
        "review.escalation": escalation,
        "review.decision": decision,
    }


def _check_invariants(after: Mapping[str, Any]) -> None:
    """The money invariants of the sandbox over the world after the intervention, or the refusal of it.

    The rows of the projection are built from the values of the nodes, and the evaluation is the evaluation of
    `ledgerlens/sandbox/invariants.py`, so a world the sandbox would refuse is a world the engine refuses.
    """
    rows = {
        "fx_applied": [
            {"id": entry_id, "applied_rate": str(rate)} for entry_id, rate in after["fx.applied_rate"].items()
        ],
        "transactions": [],
        "refunds": [],
        "chargebacks": [],
        "settlements": [],
    }
    conn = sqlite3.connect(":memory:")
    try:
        state = ProjectedState(conn=conn, canonical_hash="", rows=rows)
        failures = invariants.failures(state)
    finally:
        conn.close()
    if failures:
        named = "; ".join(f"{failure.identifier}: {failure.reason}" for failure in failures)
        raise InterventionRefused(f"the intervention breaks a money invariant of the world: {named}")


def run(base: WorldState, intervention: Intervention | CompoundIntervention) -> CausalResult:
    """One run of the engine: the intervention is validated, the world recomputed and the changes classified.

    The validation comes before anything else, and a refusal raises before anything is written. The changed
    nodes that are descendants of the target are the explained changes, and the changed nodes that are not
    descendants are the unknowns, each with the missing edge named.
    """
    if isinstance(intervention, CompoundIntervention):
        items = (intervention.first, intervention.second)
    else:
        items = (intervention,)
    reasons: list[str] = []
    for item in items:
        reasons.extend(validate(item, base.horizon, KNOWN_ASSUMPTIONS))
    if reasons:
        raise InterventionRefused("; ".join(reasons))

    assumptions = tuple(dict.fromkeys(assumption for item in items for assumption in item.assumptions))
    overrides: dict[str, tuple[date | None, Any]] = {item.target: (item.day, item.do_value) for item in items}

    before = _read_all(base, {}, assumptions)
    after = _read_all(base, overrides, assumptions)
    _check_invariants(after)

    targets = tuple(item.target for item in items)
    descendants: set[str] = set()
    for target in targets:
        descendants.update(descendants_of(target))

    changed: list[NodeChange] = []
    unknown: list[UnknownChange] = []
    unchanged: list[str] = []
    changed_ids = {node.node_id for node in NODES if before[node.node_id] != after[node.node_id]}
    for node in NODES:
        node_id = node.node_id
        if node_id not in changed_ids:
            unchanged.append(node_id)
        elif node_id in descendants:
            changed.append(NodeChange(node_id, before[node_id], after[node_id]))
        elif node_id not in targets:
            missing = tuple(
                (reader, node_id)
                for reader in _reads_of(node_id, base)
                if reader in changed_ids and (reader, node_id) not in _DECLARED
            )
            if missing:
                named = ", ".join(f"{source} -> {target}" for source, target in missing)
                reason = f"the change of {node_id} has no declared edge, and the missing edge is {named}"
            else:
                reason = (
                    f"the change of {node_id} has no declared edge from the target, "
                    "and none is missing in the readers"
                )
            unknown.append(UnknownChange(node_id, before[node_id], after[node_id], missing, reason))

    claims = tuple(
        f"the change of {change.node} is not a cause the registry of the simulation supports: "
        f"no declared edge reaches it from {', '.join(targets)}"
        for change in unknown
    )
    is_policy_target = any(target.startswith("policy.") for target in targets)
    covered_periods = (
        tuple(
            period
            for period in base.policy_periods
            if any(period[0] <= entry.day <= period[1] for entry in base.entries)
        )
        if is_policy_target
        else ()
    )
    return CausalResult(
        targets=targets,
        exogenous_digest=base.exogenous_digest,
        assumptions=assumptions,
        changed=tuple(changed),
        unknown=tuple(unknown),
        unchanged=tuple(unchanged),
        unsupported_claims=claims,
        covered_periods=covered_periods,
        before=before,
        after=after,
        interventions=items,
    )


def run_and_write(base: WorldState, intervention: Intervention | CompoundIntervention, out_dir: Path) -> Path:
    """The run and the write of its result, in this order: a refusal raises before the directory exists.

    Why the refusal writes nothing: a refusal that left a result behind would be a result without a cause, so
    the directory of the result is created only after the run has produced one.
    """
    result = run(base, intervention)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "causal-result.json"
    path.write_text(json.dumps(_to_dict(result), indent=2, sort_keys=True), encoding="utf-8")
    return path


def sensitivity(
    base: WorldState,
    intervention: Intervention,
    first_assumptions: tuple[str, ...],
    second_assumptions: tuple[str, ...],
) -> Sensitivity:
    """One intervention under two assumptions: the movement of the nodes between the two runs.

    Why the sensitivity is a measurement of the assumption and not an interval of confidence: the two runs
    share the base, the exogenous stream and the intervention, and they differ only in the assumption, so the
    movement of a node is what the assumption moves and nothing else.
    """
    first = run(base, Intervention(intervention.target, intervention.do_value, intervention.day, first_assumptions))
    second = run(base, Intervention(intervention.target, intervention.do_value, intervention.day, second_assumptions))
    movement = tuple(
        NodeChange(node.node_id, first.after[node.node_id], second.after[node.node_id])
        for node in NODES
        if first.after[node.node_id] != second.after[node.node_id]
    )
    return Sensitivity(first=first, second=second, movement=movement)


def _to_dict(result: CausalResult) -> dict[str, Any]:
    """The result as a mapping of plain values, for the JSON of the output directory."""

    def plain(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {str(key): plain(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [plain(item) for item in value]
        return value

    return {
        "targets": list(result.targets),
        "exogenous_digest": result.exogenous_digest,
        "assumptions": list(result.assumptions),
        "changed": [
            {"node": change.node, "before": plain(change.before), "after": plain(change.after)}
            for change in result.changed
        ],
        "unknown": [
            {
                "node": change.node,
                "before": plain(change.before),
                "after": plain(change.after),
                "missing_edges": [list(edge) for edge in change.missing_edges],
                "reason": change.reason,
                "status": change.status,
            }
            for change in result.unknown
        ],
        "unchanged": list(result.unchanged),
        "unsupported_claims": list(result.unsupported_claims),
        "covered_periods": [[start.isoformat(), end.isoformat()] for start, end in result.covered_periods],
        "before": plain(result.before),
        "after": plain(result.after),
    }
