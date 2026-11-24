"""The paired comparison of the twin: two policies over one stream of arrivals, and the cases whose decision changed.

Why the comparison reads one stream: a comparison over two streams measures the difference between the
streams and not the difference between the policies, and the second run of a comparison reads the stored
stream of the first run and refuses to generate another one.

Why the comparison is a difference inside the synthetic world and never a statement about a real operation:
the twin simulates a synthetic world, and the comparison of two policies over it is a number about the world
it simulated, with the assumptions that produced it, and never a claim about a real operation.

Why every money figure is a `Decimal`: the cost per case is an exact division, and it is undefined with a
reason when the denominator is zero, because a cost of zero would say the case was free.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.sim.twin.arrivals import ArrivalStream
from ledgerlens.sim.twin.arrivals import digest_of as stream_digest
from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.queue import QueueOutcome, serve

__all__ = ["Comparison", "ComparisonRefused", "PolicyDecision", "compare", "decide"]

# The review policies of the twin: which kinds of the cases of the stream each one escalates to a review.
# The policy "shipped" is the policy of the repository: a dispute goes to a person. The policy "strict" is the
# variant of the comparison: a dispute and a refund go to a person.
_POLICIES: dict[str, frozenset[str]] = {
    "shipped": frozenset({"chargeback"}),
    "strict": frozenset({"chargeback", "refund"}),
}


class ComparisonRefused(Exception):
    """The comparison is refused, and the message says why."""


@dataclass(frozen=True)
class PolicyDecision:
    """The decision of a policy over one arrival: the arrival and whether it was escalated to a review."""

    minute: int
    kind: str
    escalated: bool


@dataclass(frozen=True)
class Comparison:
    """The comparison of two policies over one stream: the changed cases and the figures of the two runs."""

    stream_sha256: str
    policy_a: str
    policy_b: str
    changed: tuple[PolicyDecision, ...]
    queue_a: QueueOutcome
    queue_b: QueueOutcome
    cost_per_case_a: Decimal | None
    cost_per_case_b: Decimal | None
    cost_reason: str


def decide(kind: str, policy: str) -> bool:
    """The decision of a review policy over a kind of case: whether the case is escalated to a review."""
    escalated_kinds = _POLICIES.get(policy)
    if escalated_kinds is None:
        raise ComparisonRefused(f"the review policy {policy!r} is not a policy of the twin: {sorted(_POLICIES)}")
    return kind in escalated_kinds


def compare(config_a: TwinConfig, config_b: TwinConfig, stream: ArrivalStream) -> Comparison:
    """The comparison of two policies over one stream of arrivals.

    Why the stream is an argument and not generated here: the comparison reads one stream, and a comparison
    that generated its own stream would be a comparison over a stream that the first run did not read.
    """
    if config_a.review_policy == config_b.review_policy:
        raise ComparisonRefused(
            f"the two runs of the comparison read the same policy {config_a.review_policy!r}, and a comparison "
            "of one policy with itself measures nothing"
        )
    digest = stream_digest(stream)
    decisions_a = [PolicyDecision(a.minute, a.kind, decide(a.kind, config_a.review_policy)) for a in stream.arrivals]
    decisions_b = [PolicyDecision(b.minute, b.kind, decide(b.kind, config_b.review_policy)) for b in stream.arrivals]
    changed = tuple(
        decision_b
        for decision_a, decision_b in zip(decisions_a, decisions_b, strict=True)
        if decision_a.escalated != decision_b.escalated
    )
    queue_a = serve(config_a, stream)
    queue_b = serve(config_b, stream)
    cost_a, cost_b, reason = _costs(config_a, config_b, stream)
    return Comparison(
        stream_sha256=digest,
        policy_a=config_a.review_policy,
        policy_b=config_b.review_policy,
        changed=changed,
        queue_a=queue_a,
        queue_b=queue_b,
        cost_per_case_a=cost_a,
        cost_per_case_b=cost_b,
        cost_reason=reason,
    )


def _costs(
    config_a: TwinConfig, config_b: TwinConfig, stream: ArrivalStream
) -> tuple[Decimal | None, Decimal | None, str]:
    """The cost per case of the two runs, with the reason when a cost is undefined.

    Why the cost is the work of the reviews over the cases of the stream: the cost of the operation of a
    policy is the work of the reviews it asked for, and the cost per case is that work over the cases of the
    stream. A stream with no cases has no cost per case, and the cost is undefined with the reason, because a
    cost of zero would say the operation was free.
    """
    total = len(stream.arrivals)
    if not total:
        return None, None, "the stream has no cases, so there is no cost per case to compute"
    costs: list[Decimal | None] = []
    for config in (config_a, config_b):
        escalated = sum(1 for arrival in stream.arrivals if decide(arrival.kind, config.review_policy))
        work = config.service_time_minutes * escalated
        costs.append((work / total).quantize(Decimal("0.01")))
    return costs[0], costs[1], ""
