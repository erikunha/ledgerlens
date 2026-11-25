"""The registry of the structural functions: the dependencies of the synthetic world, declared over the code.

Why the registry is written by hand over the code: a dependency that is learned from an observation is a
dependency that the data suggests and not a dependency that the code implements. The registry declares the
dependencies of the synthetic world over the code that already exists, and every edge names the function that
implements it, so a reader can open the edge and find the code.

Why the reason of the edge is part of it: an edge that exists because a function reads a value is different
from an edge that exists because a policy says so, and a reader has to be able to tell. The reason of the edge
says which of the two it is.

Why a node outside the registry has no edge at all: the registry is the only source of a dependency, and a
node that is not in the registry is never a descendant of anything.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["EDGES", "NODES", "Edge", "Node", "descendants_of", "edges_from", "node_of"]


@dataclass(frozen=True)
class Node:
    """A node of the registry: a value of the synthetic world that an intervention may target.

    Why the node names its family: the families of the registry are the families of the code of the repository
    (the exchange rate, the policy, the settlement and the review), and the family of a node says which part of
    the code the node belongs to.
    """

    node_id: str
    family: str
    description: str


@dataclass(frozen=True)
class Edge:
    """An edge of the registry: the node that is read, the node that depends on it, the function and the reason.

    Why the edge names the function that implements it: the registry is a declaration of the code and not a
    picture of it, and a reader of the edge opens the function and finds the dependency. An edge whose function
    was renamed is a broken edge, and the test of the registry says so.

    Why the edge names its reason: an edge that exists because a function reads a value is different from an
    edge that exists because a policy says so, and the reason of the edge says which of the two it is.
    """

    source: str
    target: str
    function: str
    reason: str


# The nodes of the four families of the registry: the exchange rate, the policy, the settlement and the review.
NODES: tuple[Node, ...] = (
    Node("fx.reference_rate", "exchange_rate", "the reference rate of a day"),
    Node("fx.applied_rate", "exchange_rate", "the applied rate of a transaction"),
    Node("fx.markup", "exchange_rate", "the markup of a merchant"),
    Node("policy.rule", "policy", "the rule of a policy of the corpus"),
    Node("policy.deadline_window", "policy", "the window of a deadline of a policy"),
    Node("policy.markup_ceiling", "policy", "the ceiling of a markup of a policy"),
    Node("settlement.fee", "settlement", "the fee of a settlement"),
    Node("settlement.net", "settlement", "the net of a settlement"),
    Node("settlement.date", "settlement", "the date of a settlement"),
    Node("review.dispute_deadline", "review", "the deadline of a dispute"),
    Node("review.escalation", "review", "the escalation of a case"),
    Node("review.decision", "review", "the decision of the verifier"),
)

# The edges of the registry: the node that is read, the node that depends on it, the function that implements
# the edge and the reason of the edge. Every function named here exists in the code of the repository, and the
# test of the registry checks it.
EDGES: tuple[Edge, ...] = (
    Edge(
        "fx.reference_rate",
        "fx.applied_rate",
        "ledgerlens.sim.fx.FxTable.rate",
        "the applied rate of a transaction is read from the reference rate of the day of the transaction",
    ),
    Edge(
        "fx.applied_rate",
        "fx.markup",
        "ledgerlens.tools.calculator._implied_markup_pct",
        "the markup of a merchant is computed from the applied rate and the reference rate",
    ),
    Edge(
        "policy.markup_ceiling",
        "fx.markup",
        "ledgerlens.tools.calculator._fx_markup_check",
        "the ceiling of a markup of a policy bounds the markup of a merchant, because the policy says so",
    ),
    Edge(
        "policy.rule",
        "policy.deadline_window",
        "ledgerlens.retrieval.load_policy_documents",
        "the window of a deadline is read from the rule of the policy of the corpus",
    ),
    Edge(
        "settlement.fee",
        "settlement.net",
        "ledgerlens.tools.calculator._net_settlement",
        "the net of a settlement is the gross minus the refunds minus the fees, and the function reads the fee",
    ),
    Edge(
        "settlement.date",
        "settlement.net",
        "ledgerlens.sim.calendars.payout_date",
        "the date of a settlement is computed from the period of it, and the net is read with the date",
    ),
    Edge(
        "review.dispute_deadline",
        "review.escalation",
        "ledgerlens.verify.escalation.escalation_reasons",
        "the escalation of a case reads the deadline of the dispute, because the policy of the escalation says so",
    ),
    Edge(
        "review.escalation",
        "review.decision",
        "ledgerlens.verify.checks.verify_result",
        "the decision of the verifier reads the escalation of the case",
    ),
)

_BY_ID = {node.node_id: node for node in NODES}


def node_of(node_id: str) -> Node | None:
    """The node of the registry, and None when the registry has no such node."""
    return _BY_ID.get(node_id)


def edges_from(node_id: str) -> tuple[Edge, ...]:
    """The edges of the registry whose source is the node: the nodes that depend on it, one step away."""
    return tuple(edge for edge in EDGES if edge.source == node_id)


def descendants_of(node_id: str) -> tuple[str, ...]:
    """The nodes that depend on the node, along the edges of the registry, in the order of the registry.

    Why the descendants are of the registry and not of an observation: only a declared edge makes a
    descendant, and a node that is not in the registry is never a descendant of anything.
    """
    if node_of(node_id) is None:
        return ()
    found: list[str] = []
    frontier = [node_id]
    while frontier:
        current = frontier.pop(0)
        for edge in edges_from(current):
            if edge.target not in found and edge.target != node_id:
                found.append(edge.target)
                frontier.append(edge.target)
    return tuple(found)
