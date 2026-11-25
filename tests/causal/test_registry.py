"""The registry of the structural functions: the declaration of the dependencies of the synthetic world.

What they guarantee, and why: the registry names the nodes of the four families (the exchange rate, the
policy, the settlement and the review), every edge names the two nodes it connects, the function that
implements it and the reason of the edge, and a node outside the registry has no edge at all, because the
registry is the only source of a dependency. Every function named by an edge exists in the code of the
repository, because the registry is a declaration of the code and not a picture of it: an edge whose function
was renamed is a broken edge, and the test says so.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import importlib

from ledgerlens.causal.registry import EDGES, NODES, descendants_of, edges_from, node_of


def test_the_registry_names_the_nodes_of_the_four_families() -> None:
    """The families of the registry are the families of the code of the repository."""
    families = {node.family for node in NODES}

    assert families == {"exchange_rate", "policy", "settlement", "review"}
    assert {node.node_id for node in NODES} == {
        "fx.reference_rate",
        "fx.applied_rate",
        "fx.markup",
        "policy.rule",
        "policy.deadline_window",
        "policy.markup_ceiling",
        "settlement.fee",
        "settlement.net",
        "settlement.date",
        "review.dispute_deadline",
        "review.escalation",
        "review.decision",
    }


def test_every_edge_names_the_two_nodes_the_function_and_the_reason() -> None:
    """An edge without the two nodes, the function or the reason is not an edge of the registry."""
    node_ids = {node.node_id for node in NODES}
    for edge in EDGES:
        assert edge.source in node_ids, f"the edge names a source outside the registry: {edge.source}"
        assert edge.target in node_ids, f"the edge names a target outside the registry: {edge.target}"
        assert edge.function, f"the edge {edge.source} -> {edge.target} names no function"
        assert edge.reason, f"the edge {edge.source} -> {edge.target} names no reason"


def test_a_node_outside_the_registry_has_no_edge_at_all() -> None:
    """The registry is the only source of a dependency, and a node outside it is never a descendant."""
    assert node_of("fx.spread") is None
    assert edges_from("fx.spread") == ()
    assert descendants_of("fx.spread") == ()


def test_the_descendants_are_of_the_registry_and_not_of_an_observation() -> None:
    """Only a declared edge makes a descendant, and the walk follows the edges of the registry."""
    assert descendants_of("fx.reference_rate") == ("fx.applied_rate", "fx.markup")
    assert descendants_of("policy.markup_ceiling") == ("fx.markup",)
    assert descendants_of("review.dispute_deadline") == ("review.escalation", "review.decision")


def test_every_function_named_by_an_edge_exists_in_the_code() -> None:
    """The registry is a declaration of the code: an edge whose function was renamed is a broken edge."""
    for edge in EDGES:
        parts = edge.function.split(".")
        module = None
        split = 0
        for index in range(len(parts) - 1, 0, -1):
            try:
                module = importlib.import_module(".".join(parts[:index]))
                split = index
                break
            except ModuleNotFoundError:
                continue
        assert module is not None, f"the edge {edge.source} -> {edge.target} names a module that does not exist"
        value = module
        for attribute in parts[split:]:
            assert hasattr(value, attribute), (
                f"the edge {edge.source} -> {edge.target} names {edge.function}, "
                f"and {attribute} does not exist"
            )
            value = getattr(value, attribute)
