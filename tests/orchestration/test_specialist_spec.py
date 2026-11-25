"""The spec of a specialist: the allowlist of the tools, the scope and what the specialist must return.

What they guarantee, and why: (a) a specialist refuses a tool that is not in its allowlist, because a specialist
that may call anything is a specialist that may read anything; (b) the spec is versioned, because a specialist that
changed under a run is a specialist that nobody measured; (c) the registry holds roles and not models, because the
model of a specialist is the model of the run.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.orchestration.specialists import SPECIALISTS, SpecialistRefused, spec_of


def test_a_specialist_of_the_registry_refuses_a_tool_that_is_not_in_its_allowlist() -> None:
    """The allowlist is the rule and it is checked before the tool is called."""
    spec = spec_of("ledger_reader")

    assert spec.allows("query_ledger") is True
    assert spec.allows("calculate") is False
    assert spec.allows("search_policies") is False


def test_every_specialist_of_the_registry_declares_its_version_and_its_return() -> None:
    """A specialist that nobody versioned is a specialist that nobody measured."""
    for name, spec in SPECIALISTS.items():
        assert spec.version, f"the specialist {name} has no version"
        assert spec.returns, f"the specialist {name} says nothing about what it returns"
        assert spec.tools, f"the specialist {name} may call no tool at all"


def test_the_tools_of_the_registry_are_the_tools_of_the_shipped_agent() -> None:
    """The specialists call the six tools of the shipped path and no other tool."""
    known = {
        "query_ledger",
        "get_ledger_record",
        "search_policies",
        "get_reference_fx",
        "calculate",
        "recall_cases",
    }
    used = {tool for spec in SPECIALISTS.values() for tool in spec.tools}

    assert used <= known
    assert used == known


def test_a_specialist_that_the_registry_does_not_hold_is_refused() -> None:
    """A specialist that nobody wrote has no allowlist, and an empty allowlist is not everything."""
    with pytest.raises(SpecialistRefused, match="no specialist named"):
        spec_of("the_specialist_of_the_imagination")
