"""The context of an execution: identity, scope and the memory that is no longer global.

What they guarantee, and why: (a) the context is frozen, because it is the portrait of an execution and nobody changes
a portrait after it left; (b) the mode comes from the process configuration when the context does not declare another
one, and the declared mode wins, because a deterministic execution cannot be labelled as live by the carelessness of
the caller; (c) the memory folder is the session one, so two visitors do not share the same case memory; (d) with a
context the integrator writes the memory in the folder of the context, and without a context it stays in the global
folder, as it always was, because the change has to be migratable; (e) the trace coordinator comes from the context,
with the identifier, the mode and the snapshot hash; (f) the identity of the execution reaches the agent, so the trace
and the result can say whose execution it was; (g) a mode outside the contract and a session id that is not an
identifier are refused at construction; (h) the isolation is proven in the data, not only in the path.

Everything offline, with no key and no model: the `ScriptedChatModel` answers what is needed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.agents.integrator import build_integrator
from ledgerlens.config import get_settings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.observability.trace_event import InMemoryTraceSink
from ledgerlens.offline import ScriptedChatModel
from ledgerlens.run_context import RunBudget, RunContext
from ledgerlens.schemas import Coherence, InvestigationResult, Verdict


def _integrator(**kwargs):
    """A minimal integrator, with the scripted model and no injected memory."""
    return build_integrator(ScriptedChatModel(script=[]), **kwargs)


def test_the_context_is_frozen():
    """The context is a portrait: changing a field after it left is an error."""
    context = RunContext(run_id="r1", session_id="s1")
    with pytest.raises(FrozenInstanceError):
        context.run_id = "r2"  # type: ignore[misc]


def test_the_mode_comes_from_the_configuration_when_the_context_does_not_declare_one(monkeypatch):
    """Without a declared mode, the label is what the machine is doing."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    context = RunContext(run_id="r1", session_id="s1")
    assert context.resolved_mode() == "deterministic_sandbox"

    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    assert context.resolved_mode() == "live_agent"


def test_the_declared_mode_wins_over_the_configuration(monkeypatch):
    """A declared mode wins over the configuration: a deterministic execution cannot be labelled as live."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    context = RunContext(run_id="r1", session_id="s1", mode="deterministic_sandbox")
    assert context.resolved_mode() == "deterministic_sandbox"


def test_a_mode_outside_the_contract_is_refused():
    """A mode that the public schema does not allow never becomes a context."""
    with pytest.raises(ValueError):
        RunContext(run_id="r1", session_id="s1", mode="banana")  # type: ignore[arg-type]


def test_a_session_id_that_is_not_an_identifier_is_refused():
    """The session id lands in a path, so a separator or a dot segment is refused at construction."""
    for session_id in ("../../tmp/pwned", "a/b", "", "with space", "-leading"):
        with pytest.raises(ValueError):
            RunContext(run_id="r1", session_id=session_id)


def test_the_memory_dir_is_the_session_dir():
    """The memory folder is the session one, inside the runtime folder of the configuration."""
    context = RunContext(run_id="r1", session_id="sess-7")
    expected = get_settings().runtime_dir / "sessions" / "sess-7"
    assert context.resolve_memory_dir() == expected


def test_two_sessions_do_not_share_the_memory_dir():
    """Two visitors have different folders: the memory of one does not appear in the other."""
    first = RunContext(run_id="r1", session_id="sess-a")
    second = RunContext(run_id="r2", session_id="sess-b")
    assert first.resolve_memory_dir() != second.resolve_memory_dir()


def test_with_a_context_the_memory_goes_to_the_session_folder():
    """With a context, the integrator writes the memory in the session folder, not in the global one."""
    context = RunContext(run_id="r1", session_id="sess-a")
    agent = _integrator(run_context=context)
    assert agent.case_memory.runtime_dir == context.resolve_memory_dir()
    assert agent.case_memory.runtime_dir != get_settings().runtime_dir


def test_without_a_context_the_memory_stays_where_it_was():
    """Without a context, nothing changes: the memory stays in the global folder, and the old tests keep holding."""
    agent = _integrator()
    assert agent.case_memory.runtime_dir == get_settings().runtime_dir


def test_an_explicit_memory_still_wins():
    """An injected memory still wins: the context does not override what was given by hand."""
    memory = CaseMemory(Path("/tmp/ledgerlens-test-memory"))
    context = RunContext(run_id="r1", session_id="sess-a")
    agent = _integrator(case_memory=memory, run_context=context)
    assert agent.case_memory is memory


def test_one_session_does_not_see_the_case_written_by_another(tmp_path: Path):
    """The isolation is proven in the data, not only in the path: what one session writes, the other does not read.

    The seed of cases is shared and read-only by design, so both sessions see it. What a session writes is private:
    the case of one session does not appear in the records of the other.
    """
    first = RunContext(run_id="r1", session_id="sess-a")
    second = RunContext(run_id="r2", session_id="sess-b")

    memory_a = CaseMemory(first.resolve_memory_dir(tmp_path))
    memory_b = CaseMemory(second.resolve_memory_dir(tmp_path))

    written = memory_a.write_case(_supported_result("sess-a"))
    assert written["written"] is True, written
    case_id = written["case_id"]

    assert memory_a.runtime_file.exists()
    assert not memory_b.runtime_file.exists()

    ids_a = {record["case_id"] for record in memory_a.records()}
    ids_b = {record["case_id"] for record in memory_b.records()}
    assert case_id in ids_a
    assert case_id not in ids_b
    # The seeded case is shared and read-only, so both sessions see it.
    assert ids_a - ids_b == {case_id}


def _supported_result(session_id: str) -> InvestigationResult:
    """A result whose verdicts are all supported, which is what the memory accepts."""
    return InvestigationResult(
        session_id=session_id,
        question="the refund came in lower than the payment",
        answer="The difference is the refund fee.",
        claims=[],
        evidence=[],
        verdicts=[Verdict(claim_id="CL1", label="supported", method="rule")],
        coherence=Coherence(passed=True),
        recommended_action="explain_to_customer",
        requires_human_review=False,
    )


def test_the_trace_stream_comes_from_the_context():
    """The trace coordinator comes from the context, with identifier, mode and snapshot hash."""
    context = RunContext(
        run_id="r1",
        session_id="sess-a",
        mode="deterministic_sandbox",
        snapshot_sha256="a" * 64,
    )
    sink = InMemoryTraceSink()
    stream = context.trace_stream(sink)

    assert stream.run_id == "r1"
    assert stream.mode == "deterministic_sandbox"

    from ledgerlens.observability.trace_event import TraceEventDraft

    stream.emit(TraceEventDraft("run.started", {"scenario": "S01"}))
    event = sink.read_from("r1", after_seq=0, limit=10)[0]
    assert event.mode == "deterministic_sandbox"
    assert event.snapshot_sha256 == "a" * 64


def test_the_identity_reaches_the_agent():
    """The identity of the execution travels with the agent, so the trace and the result can say whose it was."""
    context = RunContext(
        run_id="r1",
        session_id="sess-a",
        account_id="acc-1",
        branch_id="branch-9",
        snapshot_sha256="a" * 64,
    )
    agent = _integrator(run_context=context)

    identity = agent.identity()
    assert identity["run_id"] == "r1"
    assert identity["session_id"] == "sess-a"
    assert identity["account_id"] == "acc-1"
    assert identity["branch_id"] == "branch-9"
    assert identity["snapshot_sha256"] == "a" * 64


def test_without_a_context_the_agent_has_no_identity():
    """Without a context there is no identity to claim, and the agent says so instead of inventing one."""
    agent = _integrator()
    assert agent.identity() == {}


def test_the_budget_carries_the_limits_that_were_given():
    """The budget carries the ceilings that were given, and what was not given is not a limit."""
    context = RunContext(
        run_id="r1",
        session_id="s1",
        budget=RunBudget(max_model_calls=4, max_estimated_usd=Decimal("0.25")),
    )
    assert context.budget.max_model_calls == 4
    assert context.budget.max_estimated_usd == Decimal("0.25")
    assert context.budget.max_sql_rows is None
    assert context.budget.max_wall_seconds is None
