"""Chooses the model of each slot of a run, by the task the slot does.

Why it exists: one model for the whole run is money spent in the wrong place. The triage reads a question and
writes a plan, the rewrite of the search of the policies is one sentence, the statement that reads the ledger is
one query, and the answer with the tools is the hard part. Those are four tasks with four levels of demand, and
the deployment used to pay for the hard one on every one of them. This module names the task of each slot, the
level the task demands, and the model that fits it, and it writes down the decision it took.

The table of the slots is the heart of the module. Every slot of the run appears there with the task it does, the
level of the task and the capability the task needs. The level is what the cascade is read against: a cascade is
an ordered list of models, from the lightest to the most capable, and the slot takes the cheapest model of the
cascade that is at or above the level its task demands. A slot whose task demands more than the cascade holds
takes the most capable model of the cascade, and the decision says so in words, because a silent downgrade is a
lie about what ran.

Two rules keep the decision honest. The first is that a model only runs a task when the capability that task
needs was really verified for it: a model that never called a tool does not plan the answer with the tools. The
second is that a model a human chose is never silently replaced. The router chooses among the models the
deployment allowed, and the decision it writes says which models were allowed, which one was chosen, and why.

The decision is a value and never a side effect. It is written once, when the run starts, and it is carried by
the trace as it is. A decision cannot change while the run goes on, because a run whose model changes in the
middle is a run nobody can reason about (ADR-037).

The money is text or nothing. A price that was never verified is unknown, and unknown is never zero, because a
price of zero would say that the call was free (ADR-078).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CONFIDENCE_UNDECLARED",
    "CONFIDENCE_VERIFIED",
    "SLOTS",
    "SLOT_AGENT",
    "SLOT_POLICY",
    "SLOT_SQL",
    "SLOT_TASKS",
    "SLOT_TRIAGE",
    "TIERS",
    "TIER_LIGHT",
    "TIER_ROBUST",
    "TIER_STANDARD",
    "ModelCandidate",
    "RoutingDecision",
    "RoutingError",
    "budget_of",
    "candidates_of",
    "describe",
    "models_of",
    "route",
    "slot_task",
]

# The four slots of a run. The names are the ones the integrator uses for the four models it takes, so that the
# decision of the router and the code of the integrator speak the same word about the same slot.
SLOT_AGENT = "agent"
SLOT_TRIAGE = "triage"
SLOT_SQL = "sql"
SLOT_POLICY = "policy"
SLOTS: tuple[str, ...] = (SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY)

# The levels of the tasks, from the lightest to the most demanding. A slot takes the cheapest model of the
# cascade that is at or above the level of its task.
TIER_LIGHT = "light"
TIER_STANDARD = "standard"
TIER_ROBUST = "robust"

# The levels, from the lightest to the most demanding. The index of a level in this tuple is the position in the
# cascade that the level asks for, and the last position of the cascade answers the most demanding level.
TIERS: tuple[str, ...] = (TIER_LIGHT, TIER_STANDARD, TIER_ROBUST)

# The kind of confidence a decision has when the capabilities of the model came from the allowlist of the
# server, which means that the tool calling of that model was really exercised.
CONFIDENCE_VERIFIED = "verified_capability"

# The kind of confidence a decision has when the capabilities of the model were not verified by the repository.
# The decision still runs, and it says that the capability is a claim and not a verification.
CONFIDENCE_UNDECLARED = "undeclared_capability"


class RoutingError(Exception):
    """The router cannot choose a model for a slot.

    Why the refusal exists: a task with no model that may run it is a task that would fail in the middle of the
    run, after the money of the run was already spent. The router refuses it before the run starts, and it
    names the slot and the capability that is missing.
    """


@dataclass(frozen=True)
class SlotTask:
    """What a slot of the run does, and what a model needs to do it well.

    Why the table is data and not code: the adequacy of a model for a task is a judgement about the work, and it
    has to be readable, comparable and testable without reading a chain of calls. A task that is not in the table
    has no model, and the router refuses it rather than guessing.
    """

    slot: str
    task: str
    tier: str
    capabilities: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        """The task as a dictionary, for the trace and for the reader of the decision."""
        return {
            "slot": self.slot,
            "task": self.task,
            "tier": self.tier,
            "capabilities": sorted(self.capabilities),
        }


# The tasks of the slots, and the level each one demands.
#
# The triage reads the question and writes the plan: it needs to understand a sentence and to follow a shape, and
# it does not call a tool. The rewrite of the search of the policies is one sentence that has to carry the
# question of the analyst into the words of the corpus: the lightest work of the run. The statement that reads
# the ledger has to be correct against a schema nobody sees, so it asks for more than the two above. The agent
# plans the investigation and answers with the tools, and it is the task that needs a model that really calls a
# tool, because the whole answer is made of tool calls.
SLOT_TASKS: Mapping[str, SlotTask] = {
    SLOT_TRIAGE: SlotTask(
        slot=SLOT_TRIAGE,
        task="read the question and write the plan of the investigation",
        tier=TIER_LIGHT,
        capabilities=frozenset({"chat"}),
    ),
    SLOT_POLICY: SlotTask(
        slot=SLOT_POLICY,
        task="rewrite the question of the analyst into the words of the corpus of the policies",
        tier=TIER_LIGHT,
        capabilities=frozenset({"chat"}),
    ),
    SLOT_SQL: SlotTask(
        slot=SLOT_SQL,
        task="write the statement that reads the ledger",
        tier=TIER_STANDARD,
        capabilities=frozenset({"chat"}),
    ),
    SLOT_AGENT: SlotTask(
        slot=SLOT_AGENT,
        task="plan the investigation and answer with the tools",
        tier=TIER_ROBUST,
        capabilities=frozenset({"chat", "tool_calling"}),
    ),
}


def slot_task(slot: str) -> SlotTask:
    """The task of a slot, or a refusal when the slot is not one of the four.

    Why the refusal names the slot: the caller asked for a slot that does not exist, and the slot is a name of
    the code of the repository, not a value of a visitor.
    """
    task = SLOT_TASKS.get(slot)
    if task is None:
        raise RoutingError(f"the slot {slot!r} is not one of the slots of a run: {list(SLOTS)}")
    return task


@dataclass(frozen=True)
class ModelCandidate:
    """A model the deployment may run, with what is known about it.

    Why the price is text or nothing: the price of a model is money, and the contract of this repository carries
    money as a Decimal and never as a float. A price that was never verified is absent, and an absent price means
    unknown and never means zero.
    """

    name: str
    capabilities: frozenset[str]
    price_snapshot: str | None = None
    confidence_kind: str = CONFIDENCE_UNDECLARED

    def to_dict(self) -> dict[str, Any]:
        """The candidate as a dictionary, for the trace."""
        return {
            "model": self.name,
            "capabilities": sorted(self.capabilities),
            "price_snapshot": self.price_snapshot,
            "confidence_kind": self.confidence_kind,
        }


@dataclass(frozen=True)
class RoutingDecision:
    """The decision of the router for one slot, written once and never changed.

    The fields are the ones the routing specification of the design package names: the case, the type of the
    case, the risk tier, the models that were allowed, the model that was chosen, the reason, the budget, the
    price and the kind of confidence. The decision is a value, so a reader can check what was decided and when,
    and a run whose decision changed in the middle is a run that can be read as two runs.
    """

    case_id: str
    case_type: str
    risk_tier: str
    allowed_provider_models: tuple[str, ...]
    chosen_model: str
    reason: str
    budget: str
    price_snapshot: str | None = None
    confidence_kind: str = CONFIDENCE_UNDECLARED

    def to_dict(self) -> dict[str, Any]:
        """The decision as a dictionary, for the trace and for the published recording."""
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "risk_tier": self.risk_tier,
            "allowed_provider_models": list(self.allowed_provider_models),
            "chosen_model": self.chosen_model,
            "reason": self.reason,
            "budget": self.budget,
            "price_snapshot": self.price_snapshot,
            "confidence_kind": self.confidence_kind,
        }


def budget_of(budget: Any) -> str:
    """The budget of a run in words, for the decision.

    Why the words and not a number: the budget of a run is a set of ceilings, and some of them are money that
    may be unknown. The words say what the ceiling was and, when the money is unknown, they say that it is
    unknown instead of saying zero.
    """
    if budget is None:
        return "no budget declared"
    parts: list[str] = []
    model_calls = getattr(budget, "max_model_calls", None)
    if model_calls is not None:
        parts.append(f"model calls at most {model_calls}")
    tool_calls = getattr(budget, "max_tool_calls", None)
    if tool_calls is not None:
        parts.append(f"tool calls at most {tool_calls}")
    usd = getattr(budget, "max_estimated_usd", None)
    if usd is None:
        parts.append("money unknown")
    else:
        parts.append(f"money at most {usd}")
    return ", ".join(parts) if parts else "no budget declared"


def candidates_of(
    cascade: Sequence[str],
    profiles: Mapping[str, Any],
) -> list[ModelCandidate]:
    """The candidates of a cascade, in the order the cascade declares, with what the allowlist knows of them.

    Why the cascade is ordered and not sorted by price: the cascade is the order the deployment declares from the
    lightest model to the most capable one, and the router reads the level of a task against that order. A price
    that was not verified never reorders the cascade, because a price nobody checked cannot decide anything.

    Why a model of the allowlist carries the capabilities that were really exercised: the allowlist is the only
    place where the repository says that a model really calls a tool. A model outside the allowlist still becomes
    a candidate, because a deployment may run a model the repository never exercised, but its capabilities are
    undeclared and the decision says so.
    """
    candidates: list[ModelCandidate] = []
    for name in cascade:
        profile = profiles.get(name)
        if profile is None:
            candidates.append(ModelCandidate(name=name, capabilities=frozenset(), price_snapshot=None))
            continue
        capabilities = frozenset(str(item) for item in getattr(profile, "capabilities", ()) or ())
        price = _price_of(profile)
        candidates.append(
            ModelCandidate(
                name=name,
                capabilities=capabilities,
                price_snapshot=price,
                confidence_kind=CONFIDENCE_VERIFIED,
            )
        )
    return candidates


def _price_of(profile: Any) -> str | None:
    """The verified price of a profile as text, or None when the price was never verified.

    Why the text: the price is money, and the contract of this repository carries money as a Decimal and never as
    a float. Why the absence: a price that was not checked is unknown, and a price of zero would say that the
    call was free.
    """
    pricing = getattr(profile, "pricing", None)
    if pricing is None:
        return None
    if not getattr(pricing, "is_verified", False):
        return None
    input_amount = getattr(pricing, "input_per_1m_usd", None)
    output_amount = getattr(pricing, "output_per_1m_usd", None)
    if input_amount is None or output_amount is None:
        return None
    return f"{input_amount}/{output_amount} usd per million tokens"


def route(
    candidates: Sequence[ModelCandidate],
    *,
    case_id: str,
    case_type: str = "unspecified",
    risk_tier: str = TIER_STANDARD,
    budget: str = "no budget declared",
) -> dict[str, RoutingDecision]:
    """The decision of the router for every slot of the run.

    The decision of a slot is the cheapest model of the cascade that is at or above the level of the task of the
    slot and that really has the capability the task needs. When the cascade holds no model that reaches the
    level, the most capable model of the cascade runs the task and the reason says that the level was not
    reached, because a silent downgrade is a lie about what ran.

    The router refuses a slot that no model may run: a task with no model is a task that fails in the middle of
    the run, after the money was already spent.
    """
    if not candidates:
        raise RoutingError("the deployment declared no model, so no slot of the run has one")
    for candidate in candidates:
        if "://" in candidate.name:
            # The router chooses among the models of the registry, and it never accepts an address of a server
            # that a visitor wrote: an address is not a model, and a model of an address of a visitor is a
            # model the deployment never allowed.
            raise RoutingError(
                f"the candidate {candidate.name!r} is an address of a server and not a model of the registry, "
                "and the router never accepts an address of a server that a visitor wrote"
            )
    decisions: dict[str, RoutingDecision] = {}
    for slot in SLOTS:
        task = slot_task(slot)
        needed = task.capabilities
        eligible = [candidate for candidate in candidates if needed <= candidate.capabilities]
        if not eligible:
            missing = sorted(
                capability
                for candidate in candidates
                for capability in (needed - candidate.capabilities)
            )
            raise RoutingError(
                f"no model of the deployment may run the slot {slot}: the task needs the capability "
                f"{', '.join(missing)} and no model of the cascade has it"
            )
        chosen, reason = _choose(eligible, candidates, task.tier)
        decisions[slot] = RoutingDecision(
            case_id=case_id,
            case_type=case_type,
            risk_tier=risk_tier,
            allowed_provider_models=tuple(candidate.name for candidate in candidates),
            chosen_model=chosen.name,
            reason=reason,
            budget=budget,
            price_snapshot=chosen.price_snapshot,
            confidence_kind=chosen.confidence_kind,
        )
    return decisions


def _choose(
    eligible: Sequence[ModelCandidate],
    candidates: Sequence[ModelCandidate],
    tier: str,
) -> tuple[ModelCandidate, str]:
    """The model that runs a task of a level, and the reason in words.

    The cascade is ordered from the lightest model to the most capable one, and the level of the task asks for a
    position in that order. The router takes the first model of the eligible ones at or after that position, and
    when the cascade holds no model there, it takes the most capable eligible one and says that the level was
    not reached.
    """
    position = _position_of(tier, len(candidates))
    for candidate in eligible:
        if candidates.index(candidate) >= position:
            return candidate, (
                f"the task asks for the level {tier} and the model {candidate.name} is the lightest of the "
                f"cascade that reaches it and calls the tools the task needs"
            )
    fallback = eligible[-1]
    return fallback, (
        f"the task asks for the level {tier} and no model of the cascade reaches it, so the most capable model of "
        f"the cascade, {fallback.name}, runs the task"
    )


def _position_of(tier: str, length: int) -> int:
    """The position of the cascade that a level of a task asks for.

    Why the last position answers every level: a cascade with one model has no room for a cheaper one, and the
    run then behaves as it always behaved, with the same model in every slot.
    """
    if length <= 1:
        return 0
    if tier not in TIERS:
        return length - 1
    wanted = TIERS.index(tier)
    return min(wanted, length - 1)


def models_of(decisions: Mapping[str, RoutingDecision]) -> dict[str, str]:
    """The model of each slot, from the decisions, for the caller that builds the models.

    Why this function exists: the caller needs the names, not the decisions, and the decisions are what the
    trace carries. Reading the names from the decisions keeps one source of truth, so the model that ran and
    the model that was decided can never be two different models.
    """
    return {slot: decision.chosen_model for slot, decision in decisions.items()}


def describe(candidates: Iterable[ModelCandidate]) -> list[dict[str, Any]]:
    """The candidates as dictionaries, for the trace of the run.

    Why the list: a reader of the trace has to see the models the decision was made among, and not only the one
    that won.
    """
    return [candidate.to_dict() for candidate in candidates]
