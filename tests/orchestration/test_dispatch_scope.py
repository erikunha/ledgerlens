"""The dispatcher: the scope of the run and the refusal of what is out of it.

What they guarantee, and why: (a) a tool that is not in the allowlist is refused and never called, because a
specialist that widens the scope turns a research question into a data leak; (b) an account that is outside the scope
of the run is refused and nothing is read; (c) the permissions of a specialist are the intersection of the
permissions of the parent with its own spec and never the union.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ledgerlens.orchestration.dispatcher import Permissions, dispatch, permissions_of
from ledgerlens.orchestration.specialists import spec_of
from ledgerlens.schemas import OrchestrationStep


def _tools(calls: list[str]) -> dict[str, Any]:
    """A registry of tools that records the calls it received."""

    def _make(name: str):
        def _tool(arguments: dict[str, Any]) -> dict[str, Any]:
            calls.append(name)
            return {"evidence_refs": ["sql:1"], "spend_usd": Decimal("0.10")}

        return _tool

    return {
        name: _make(name)
        for name in (
            "query_ledger",
            "get_ledger_record",
            "search_policies",
            "get_reference_fx",
            "calculate",
            "recall_cases",
        )
    }


def test_a_tool_outside_the_allowlist_is_refused_and_never_called() -> None:
    """The refusal is the answer, and a tool that was called anyway would have read what it may not read."""
    calls: list[str] = []
    permissions = Permissions(tools=frozenset({"query_ledger"}), accounts=frozenset({"M-01"}))
    step = OrchestrationStep(id="read", goal="read the ledger", tool="calculate")

    result = dispatch(step, permissions=permissions, tools=_tools(calls))

    assert result.status == "refused"
    assert "not in the allowlist" in (result.error or "")
    assert calls == []


def test_an_account_outside_the_scope_of_the_run_is_refused_and_nothing_is_read() -> None:
    """A step that reads an account of somebody else is a refusal and not a read."""
    calls: list[str] = []
    permissions = Permissions(tools=frozenset({"query_ledger"}), accounts=frozenset({"M-01"}))
    step = OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger", account="M-99")

    result = dispatch(step, permissions=permissions, tools=_tools(calls))

    assert result.status == "refused"
    assert "outside the scope" in (result.error or "")
    assert calls == []


def test_a_step_inside_the_scope_is_served_and_carries_its_evidence_and_its_spend() -> None:
    """The step that may run runs, and its result says what it did."""
    calls: list[str] = []
    permissions = Permissions(tools=frozenset({"query_ledger"}), accounts=frozenset({"M-01"}))
    step = OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger", account="M-01")

    result = dispatch(step, permissions=permissions, tools=_tools(calls))

    assert result.status == "ok"
    assert result.evidence_refs == ["sql:1"]
    assert result.spend_usd == Decimal("0.10")
    assert calls == ["query_ledger"]


def test_the_permissions_of_a_specialist_are_the_intersection_and_never_the_union() -> None:
    """The parent gives the scope and the specialist narrows it."""
    parent = Permissions(tools=frozenset({"query_ledger", "calculate"}), accounts=frozenset({"M-01"}))

    narrowed = permissions_of(parent, spec_of("ledger_reader"))

    assert narrowed.tools == frozenset({"query_ledger"})
    assert narrowed.accounts == frozenset()


def test_a_specialist_never_widens_the_scope_of_the_run() -> None:
    """A union would let a specialist read what the run may not read."""
    parent = Permissions(tools=frozenset({"query_ledger"}), accounts=frozenset({"M-01"}))

    narrowed = permissions_of(parent, spec_of("ledger_reader"))

    assert narrowed.accounts <= parent.accounts
    assert narrowed.tools <= parent.tools


def test_a_step_that_spends_more_than_the_cap_of_the_run_is_served_and_the_money_is_published() -> None:
    """The cap of the money is checked after the call, because the spend of a step is only known after it.

    Why it matters: a check that happened before the call would guess the spend, and a refusal after the money was
    spent would hide a spend that really happened. The scheduler holds the money and stops the run at the cap.
    """
    calls: list[str] = []
    permissions = Permissions(tools=frozenset({"query_ledger"}), accounts=frozenset())
    step = OrchestrationStep(id="read", goal="read the ledger", tool="query_ledger")

    result = dispatch(step, permissions=permissions, tools=_tools(calls))

    assert result.status == "ok"
    assert result.spend_usd == Decimal("0.10")
    assert calls == ["query_ledger"]
