"""The case of the demo runs on a bridge over the caller of the run: every call it makes is reserved, counted,
traced and capped by the budget of the run (FR-012).

What they guarantee, and why: (a) every model call the case makes is a call the adapter of the provider saw and a
call the report of the run counted, and the trace of the run carries one span for each of them (FR-012); (b) the four
model slots of the agent of the demo, the model of the agent, the model that writes the SQL, the policy model and the
triage model, are the model of the run, and every call of each of them is counted (FR-012, FR-013); (c) every
execution of a tool of the case reserves one call of the budget, and the tools of the case never reach the provider
outside the caller (FR-009, FR-012); (d) the cap of the calls of the models stops the case and names the cap, and the
provider is not called for the call that would break it (FR-009); (e) the case never falls back to the model of the
configuration, which online is the server own key and is outside the budget of the run (FR-007, FR-012); (f) the
answer of the provider carries the calls of the tools it asked for, and the request of the bridge carries the schemas
of the tools and the messages of the tools (FR-012); (g) the cancellation of the run stops the next call of the case
and the agent does not swallow it (FR-019); (h) the arguments of a call travel as the text the provider sent, byte for
byte, and a text that is not a JSON text travels as it is (FR-012); (i) a provider that asks for a tool the case does
not have ends the run with a refusal of the family of the product, and never with the error of a library (FR-018);
(j) the history of the session is the one the plan of the run carries, and the bridges belong to the run, so two runs
of the same case never see each other (FR-012).

Everything offline, with no key and no network: the provider is the fake adapter of the domain, the model of the demo
is the bridge over the caller of the run, and the ledger and the policy index are built in a temporary folder.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens import embeddings as emb
from ledgerlens.api.live_case import (
    MAX_BRIDGE_REQUESTS,
    SLOT_AGENT,
    SLOT_POLICY,
    SLOT_SQL,
    SLOT_TRIAGE,
    BridgeChatModel,
    DemoCase,
    demo_executor,
    wrap_tool,
)
from ledgerlens.api.live_run import LIVE_MODE, LiveRunCoordinator, LiveRunPlan, ModelCaller
from ledgerlens.byok.adapter import FakeProviderAdapter, ProviderAdapter, ProviderResponse
from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ModelProfile, Pricing, ProviderRegistry
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.run_context import RunBudget
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from tests.tools import test_policies as base

# The marker of the credential of the run: a shape that no known pattern of the repository matches, so only the
# vault and the adapter of the run can scrub it.
MARKER = "ledgerlens-marker-" + "4f3a9c2b7e1d"

SESSION = "sess-case"
PROFILE_ID = "openai-gpt-4.1-mini"
MODEL_ID = "gpt-4.1-mini"
QUESTION = "What happened to the refund of TX-0001?"

PRICED = ModelProfile(
    profile_id=PROFILE_ID,
    provider="openai",
    model_id=MODEL_ID,
    display_name="GPT-4.1 mini",
    capabilities=("chat", "tool_calling"),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(
        source="manual",
        last_verified=date(2026, 11, 8),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    ),
)

# The answer of the triage: a plan with the two tools the case runs, so the agent does not get a follow-up.
TRIAGE_ANSWER = json.dumps(
    {
        "intent": "refund_discrepancy",
        "entities": {"transaction_ids": ["TX-0001"]},
        "urgency": "normal",
        "plan": [
            {"id": "S1", "goal": "read the ledger", "tool": "query_ledger", "depends_on": []},
            {"id": "S2", "goal": "read the policy", "tool": "search_policies", "depends_on": ["S1"]},
        ],
        "needs_clarification": False,
        "clarification_question": None,
    }
)
# The triage of the case that runs with the configuration of the product: a plan with the only tool it runs, so
# the agent is not asked for a second time.
SIMPLE_TRIAGE_ANSWER = json.dumps(
    {
        "intent": "status_lookup",
        "entities": {"transaction_ids": ["TX-0001"]},
        "urgency": "normal",
        "plan": [{"id": "S1", "goal": "read the ledger", "tool": "query_ledger", "depends_on": []}],
        "needs_clarification": False,
        "clarification_question": None,
    }
)
# The SQL of the ledger: one read-only statement over an allowed table.
SQL_ANSWER = "SELECT id, status, amount_minor, currency FROM transactions WHERE id = 'TX-0001'"
# The rewrite of the policy question: the policy model answers with a question, not with a fact.
POLICY_ANSWER = "refund window after the capture of the payment"
FINAL_ANSWER = "The refund of TX-0001 was paid and the policy allows ten days [sql:1]."

# The arguments of a call exactly as a provider sent them: a number with two decimals, and a text that is not a
# JSON text at all. Both have to travel byte for byte from the answer of the provider to the next request (FR-012).
RAW_ARGUMENTS = '{"question": "the status", "amount": 10.50}'
NOT_JSON_ARGUMENTS = "this is not json at all"


def registry() -> ProviderRegistry:
    """The allowlist of the tests: one model with a price."""
    return ProviderRegistry([PRICED])


def _plan(handle: str, **overrides: Any) -> LiveRunPlan:
    """A plan of a run: the question of the case and the caps of the visitor."""
    values: dict[str, Any] = {
        "run_id": "run-case",
        "session_id": SESSION,
        "model_profile_id": PROFILE_ID,
        "credential_handle": handle,
        "question": QUESTION,
        "budget": RunBudget(max_model_calls=8, max_tool_calls=8, max_wall_seconds=30, max_output_tokens=512),
        "account_id": "C-0412",
        "scenario_id": "S01",
        "variant": "B",
    }
    values.update(overrides)
    return LiveRunPlan(**values)


def _coordinator(
    adapter: ProviderAdapter,
    vault: CredentialVault,
    *,
    executor: Any = None,
) -> LiveRunCoordinator:
    """A coordinator over the fake provider of the test, with no socket anywhere."""
    return LiveRunCoordinator(
        registry=registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=executor,
    )


def _caller(
    adapter: ProviderAdapter,
    *,
    cancel: threading.Event | None = None,
    sink: InMemoryTraceSink | None = None,
    max_model_calls: int = 8,
    max_output_tokens: int = 512,
) -> ModelCaller:
    """A caller of the run outside the coordinator, for the tests that talk to the bridge directly."""
    return ModelCaller(
        adapter=adapter,
        budget=BudgetCoordinator(
            RunBudget(
                max_model_calls=max_model_calls,
                max_tool_calls=8,
                max_wall_seconds=30,
                max_output_tokens=max_output_tokens,
            ),
            registry(),
        ),
        trace=TraceEventStream("run-case", sink if sink is not None else InMemoryTraceSink(), mode=LIVE_MODE),
        cancel=cancel if cancel is not None else threading.Event(),
        provider="openai",
        model_id=MODEL_ID,
        call_timeout=lambda: None,
    )


def _query_tool() -> StructuredTool:
    """The tool of the case that the bridge of the tests may ask for.

    Why the tool is bound in the tests of the bridge: the bridge refuses a provider that asks for a tool it does not
    have, and a model that was given no tool may not ask for one (FR-018).
    """

    class Question(BaseModel):
        """The arguments of the tool of the test."""

        model_config = ConfigDict(extra="forbid")

        question: str = Field(min_length=1)

    return StructuredTool.from_function(
        func=lambda question: question,
        name="query_ledger",
        description="reads the ledger",
        args_schema=Question,
    )


def _spans(coordinator: LiveRunCoordinator, run_id: str, name: str) -> list[dict[str, Any]]:
    """The payloads of the spans of the run with the given name."""
    return [
        dict(event.payload)
        for event in coordinator.events(run_id)
        if event.event_type == "span.started" and event.payload.get("name") == name
    ]


def refusing_verifier() -> Any:
    """A verifier that supports nothing, so the case is never written in the long-term memory."""

    def verify(result: Any, *, nli: Any = None) -> Any:
        return result.model_copy(update={"claims": [], "verdicts": []})

    return verify


def scripted_adapter() -> FakeProviderAdapter:
    """The provider of the case: the triage, the agent, the SQL, the policy and the final answer.

    The order of the script is the order of the calls of the case, and it is what the case must count.
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_tool_call(
        "search_policies",
        json.dumps({"query": "refund window", "transform": "rewrite"}),
        call_id="call_policy",
    )
    adapter.script_answer(POLICY_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    return adapter


class CancellingAdapter(FakeProviderAdapter):
    """The fake of the test: it cancels the run and then breaks, the way a provider that fails after the visitor
    asked for the end of the run does.

    Why the cancellation happens on the second call and not on the first: the triage of the agent catches the
    failures of the model on purpose, so a failure on the first call never reaches the case of the demo, and the
    guard of the cancellation would never be exercised (FR-019).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # What the fake does before it answers, set by the test once the coordinator exists.
        self.on_call: Any = None

    def complete(self, request: Any) -> ProviderResponse:
        """Cancels the run on the second call, and then answers the way the script says."""
        if self.on_call is not None and len(self.calls) >= 1:
            self.on_call()
        return super().complete(request)


@pytest.fixture(autouse=True)
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    """The product is online for the tests of the case: a live run needs a live mode (FR-024)."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The ledger of the sample, built in a temporary folder."""
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """The embeddings of the tests: a word count model, so nothing is downloaded."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> Path:
    """The policy index of the tests, built in a temporary folder."""
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


@pytest.fixture
def case(ledger_db: Path, index_root: Path, embeddings: FastEmbedEmbeddings) -> DemoCase:
    """The case of the demo, with the ledger and the policy index of the tests."""
    return DemoCase(
        db_path=ledger_db,
        index_root=index_root,
        embeddings=embeddings,
        verifier=refusing_verifier(),
    )


# --- the case on the bridge over the caller of the run ----------------------------------------------


def test_every_model_call_of_the_case_goes_through_the_caller_of_the_run(case: DemoCase) -> None:
    """FR-012: the calls the adapter saw are the calls the report of the run counted."""
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert result.answer == FINAL_ANSWER
    # Every call the provider saw is a call the report counted, and the other way around.
    assert len(adapter.calls) == 6
    assert result.report.model_calls == len(adapter.calls)
    # The trace carries one span of the model for each of those calls.
    assert len(_spans(coordinator, "run-case", "model.call")) == len(adapter.calls)
    # Every call of the case asked for the model of the run (FR-013).
    assert {call.model_id for call in adapter.calls} == {MODEL_ID}


def test_the_triage_model_and_the_generator_of_the_sql_are_counted(case: DemoCase) -> None:
    """FR-012: the four model slots of the agent of the demo are the model of the run, and their calls count."""
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    bridges = case.bridges_of("run-case")
    assert set(bridges) == {SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY}
    # Every slot speaks through the model of the run, and the four of them spoke.
    for slot, bridge in bridges.items():
        assert bridge.model_id == MODEL_ID, slot
        assert bridge.requests, slot
    # The triage spoke once, the generator of the SQL once, the policy model once and the agent three times.
    assert len(bridges[SLOT_TRIAGE].requests) == 1
    assert len(bridges[SLOT_SQL].requests) == 1
    assert len(bridges[SLOT_POLICY].requests) == 1
    assert len(bridges[SLOT_AGENT].requests) == 3
    # And every one of those calls is counted by the budget of the run.
    assert result.report.model_calls == len(adapter.calls)
    assert result.report.calls_by_model == {MODEL_ID: len(adapter.calls)}


def test_every_tool_of_the_case_reserves_one_call_of_the_budget(case: DemoCase) -> None:
    """FR-009, FR-012: every execution of a tool reserves one call of the budget of the run."""
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    # Two tools ran, and each of them reserved one call.
    assert result.report.tool_calls == 2
    assert len(_spans(coordinator, "run-case", "tool.call")) == 2
    assert {span["tool"] for span in _spans(coordinator, "run-case", "tool.call")} == {
        "query_ledger",
        "search_policies",
    }


def test_the_cap_of_the_calls_of_the_models_stops_the_case_and_names_the_cap(case: DemoCase) -> None:
    """FR-009: the cap of the calls of the models stops the case and the answer names the cap."""
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(max_model_calls=2, max_tool_calls=8, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_model_calls"
    assert "max_model_calls" in (result.error or "")
    # The call that would break the cap never reached the provider.
    assert len(adapter.calls) == 2


def test_the_case_never_falls_back_to_the_configured_model(case: DemoCase, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007, FR-012: the case never asks the configuration for a model."""

    def refuse(*args: Any, **kwargs: Any) -> BaseChatModel:
        raise AssertionError("the case of the live mode must never build the model of the configuration")

    # Every place of the repository that falls back to the configured model.
    monkeypatch.setattr("ledgerlens.config.get_chat_model", refuse)
    monkeypatch.setattr("ledgerlens.agents.integrator.get_chat_model", refuse)
    monkeypatch.setattr("ledgerlens.tools.sql.get_chat_model", refuse)
    monkeypatch.setattr("ledgerlens.tools.policies.get_chat_model", refuse)

    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert result.answer == FINAL_ANSWER
    assert len(adapter.calls) == 6


def test_the_answer_of_the_provider_carries_its_tool_calls() -> None:
    """FR-012: the answer of the provider carries the calls of the tools it asked for."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_1")
    bridge = BridgeChatModel(caller=_caller(adapter), model_id=MODEL_ID, slot=SLOT_AGENT).bind_tools([_query_tool()])

    answer = bridge.invoke([HumanMessage(content=QUESTION)])

    assert isinstance(answer, AIMessage)
    assert len(answer.tool_calls) == 1
    call = answer.tool_calls[0]
    assert call["name"] == "query_ledger"
    assert call["args"] == {"question": "the status of TX-0001"}
    assert call["id"] == "call_1"
    assert answer.content == ""


def test_the_request_carries_the_tools_and_the_tool_messages() -> None:
    """FR-012: the request of the bridge carries the schemas of the tools and the messages of the tools."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer("the answer")
    bridge = BridgeChatModel(caller=_caller(adapter), model_id=MODEL_ID, slot=SLOT_AGENT)

    class Amount(BaseModel):
        """The arguments of the tool of the test."""

        model_config = ConfigDict(extra="forbid")

        value: str = Field(min_length=1)

    tool = StructuredTool.from_function(
        func=lambda value: value,
        name="calculate",
        description="adds two amounts",
        args_schema=Amount,
    )
    bound = bridge.bind_tools([tool])

    bound.invoke(
        [
            HumanMessage(content=QUESTION),
            AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"value": "10.00"}, "id": "call_1"}],
            ),
            ToolMessage(content="20.00", tool_call_id="call_1"),
        ]
    )

    request = adapter.calls[0]
    assert request.model_id == MODEL_ID
    assert [message.role for message in request.messages] == ["user", "assistant", "tool"]
    assert request.messages[0].content == QUESTION
    # The call of the assistant travels with its identifier and its arguments as a text.
    assert request.messages[1].tool_calls[0].id == "call_1"
    assert request.messages[1].tool_calls[0].name == "calculate"
    assert request.messages[1].tool_calls[0].arguments == '{"value": "10.00"}'
    # The message of the tool carries the identifier of the call it answers.
    assert request.messages[2].tool_call_id == "call_1"
    assert request.messages[2].content == "20.00"
    # The request carries the schema of the tool the model may call.
    assert [schema.name for schema in request.tools] == ["calculate"]
    assert request.tools[0].description == "adds two amounts"
    assert "value" in request.tools[0].parameters.get("properties", {})


def test_the_cancellation_of_the_run_stops_the_next_call_of_the_case(case: DemoCase) -> None:
    """FR-019: the cancellation of the run stops the next call of the case, and the agent does not swallow it."""
    gate = threading.Event()
    entered = threading.Event()

    class BlockingAdapter(FakeProviderAdapter):
        """The fake of the test: it holds the first call until the visitor cancels the run."""

        def complete(self, request: Any) -> ProviderResponse:
            entered.set()
            gate.wait(10.0)
            return super().complete(request)

    adapter = BlockingAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert entered.wait(10.0)
    assert coordinator.cancel("run-case")
    gate.set()
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "cancelled"
    assert "cancel" in (result.error or "").lower()
    # The call that was in flight is the last one: the case asked for nothing after the cancellation.
    assert len(adapter.calls) == 1


def test_the_executor_of_the_demo_answers_with_the_answer_of_the_agent(embeddings: FastEmbedEmbeddings) -> None:
    """The case of the demo is a case of the run: it answers with what the agent answered."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=demo_executor)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert result.answer == FINAL_ANSWER
    assert len(adapter.calls) == 4


def test_the_bridge_and_the_tools_of_the_case_are_built_over_the_caller_of_the_run() -> None:
    """The bridge is a chat model over the caller, and the tool reserves its call through the caller."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    sink = InMemoryTraceSink()
    caller = _caller(adapter, sink=sink)

    class Amount(BaseModel):
        """The arguments of the tool of the test."""

        model_config = ConfigDict(extra="forbid")

        value: str = Field(min_length=1)

    tool = StructuredTool.from_function(
        func=lambda value: value.upper(),
        name="calculate",
        description="adds two amounts",
        args_schema=Amount,
    )
    wrapped = wrap_tool(caller, tool)

    assert wrapped.name == "calculate"
    assert wrapped.invoke({"value": "10.00"}) == "10.00"
    # The call of the tool reserved one call of the budget of the run, and the trace says which tool ran.
    spans = [
        event
        for event in sink.read_from("run-case", 0, 100)
        if event.event_type == "span.started" and event.payload.get("name") == "tool.call"
    ]
    assert [span.payload["tool"] for span in spans] == ["calculate"]


# --- the arguments of a call travel as the text the provider sent --------------------------------------


def test_the_arguments_of_a_call_travel_as_the_text_the_provider_sent() -> None:
    """FR-012: the arguments of a call are the text the provider sent, byte for byte."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_tool_call("query_ledger", RAW_ARGUMENTS, call_id="call_1")
    adapter.script_answer("the answer")
    caller = _caller(adapter, max_output_tokens=4096)
    bridge = BridgeChatModel(caller=caller, model_id=MODEL_ID, slot=SLOT_AGENT).bind_tools([_query_tool()])

    answer = bridge.invoke([HumanMessage(content=QUESTION)])
    bridge.invoke(
        [
            HumanMessage(content=QUESTION),
            answer,
            ToolMessage(content="the rows", tool_call_id="call_1"),
        ]
    )

    # The request of the second call carries the text of the arguments exactly as it arrived, and the number
    # with two decimals is not a number that lost its decimals on the way.
    request = adapter.calls[1]
    assert request.messages[1].tool_calls[0].name == "query_ledger"
    assert request.messages[1].tool_calls[0].arguments == RAW_ARGUMENTS


def test_the_arguments_that_are_not_a_json_text_travel_unchanged_too() -> None:
    """FR-012: a text that is not a JSON text travels as it is, and it never becomes an empty object."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_tool_call("query_ledger", NOT_JSON_ARGUMENTS, call_id="call_1")
    adapter.script_answer("the answer")
    caller = _caller(adapter, max_output_tokens=4096)
    bridge = BridgeChatModel(caller=caller, model_id=MODEL_ID, slot=SLOT_AGENT).bind_tools([_query_tool()])

    answer = bridge.invoke([HumanMessage(content=QUESTION)])
    bridge.invoke(
        [
            HumanMessage(content=QUESTION),
            answer,
            ToolMessage(content="the rows", tool_call_id="call_1"),
        ]
    )

    request = adapter.calls[1]
    assert request.messages[1].tool_calls[0].arguments == NOT_JSON_ARGUMENTS


def test_the_run_carries_the_text_of_the_arguments_of_the_provider(case: DemoCase) -> None:
    """FR-012: the text the provider sent is the text that the next call of the run carries."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", RAW_ARGUMENTS, call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_tool_call(
        "search_policies",
        json.dumps({"query": "refund window", "transform": "rewrite"}),
        call_id="call_policy",
    )
    adapter.script_answer(POLICY_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    # The call of the agent that follows the tool carries the arguments exactly as the provider sent them.
    request = adapter.calls[3]
    assistant = [message for message in request.messages if message.role == "assistant"]
    assert assistant
    assert assistant[0].tool_calls[0].arguments == RAW_ARGUMENTS


# --- the cancellation, the refusal and the shape of the case -------------------------------------------


def test_the_case_does_not_swallow_the_cancellation_of_a_run_that_failed(case: DemoCase) -> None:
    """FR-019: the failure of a cancelled run is the cancellation, and the case never swallows it."""
    adapter = CancellingAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    adapter.script_failure(RuntimeError("the provider broke"))
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    adapter.on_call = lambda: coordinator.cancel("run-case")
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    # The run ends as cancelled and not as a failure: the visitor asked for the end of the run (FR-019).
    assert result.status == "cancelled"
    assert "cancel" in (result.error or "").lower()
    # The case asked the provider for nothing after the cancellation.
    assert len(adapter.calls) == 2


def test_the_run_ends_with_a_refusal_when_the_provider_asks_for_a_tool_that_does_not_exist(
    case: DemoCase,
) -> None:
    """FR-018: a provider that asks for a tool the case does not have ends the run with a reason, not with the
    error of a library."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    adapter.script_tool_call("teleport_the_money", json.dumps({"question": "the status"}), call_id="call_x")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "failed"
    # The reason names the tool the provider asked for.
    assert "teleport_the_money" in (result.error or "")
    # And the reason is a refusal of the family of the product, not the error of a library.
    assert "ValidationError" not in (result.error or "")


def test_the_case_keeps_the_history_of_the_session_that_the_plan_carries(case: DemoCase) -> None:
    """FR-012: the messages the plan of the run carries are the history the case of the demo works with."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    history = (
        {"role": "user", "content": "the first question of the session"},
        {"role": "assistant", "content": "the first answer of the session"},
    )

    coordinator.start(_plan(handle.handle, messages=history))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    # The agent asked the provider with the history of the session in front of the question of the run.
    request = adapter.calls[1]
    contents = [message.content for message in request.messages]
    assert "the first question of the session" in contents
    assert "the first answer of the session" in contents


def test_two_concurrent_runs_of_the_same_case_do_not_see_each_other(case: DemoCase) -> None:
    """The bridges belong to the run, so two runs of the same case never share their calls."""
    first = scripted_adapter()
    second = scripted_adapter()
    vault = CredentialVault()
    first_coordinator = _coordinator(first, vault, executor=case)
    second_coordinator = _coordinator(second, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    first_coordinator.start(_plan(handle.handle, run_id="run-first"))
    second_coordinator.start(_plan(handle.handle, run_id="run-second"))
    first_result = first_coordinator.wait("run-first", timeout=20.0)
    second_result = second_coordinator.wait("run-second", timeout=20.0)

    assert first_result is not None
    assert first_result.status == "completed"
    assert second_result is not None
    assert second_result.status == "completed"
    first_bridges = case.bridges_of("run-first")
    second_bridges = case.bridges_of("run-second")
    assert set(first_bridges) == {SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY}
    assert set(second_bridges) == {SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY}
    # The bridges of one run are not the bridges of the other, and the calls of one are not in the other.
    for slot in first_bridges:
        assert first_bridges[slot] is not second_bridges[slot]
    assert len(first_bridges[SLOT_AGENT].requests) == 3
    assert len(second_bridges[SLOT_AGENT].requests) == 3


def test_the_requests_of_the_bridge_are_bounded() -> None:
    """The bridge keeps the last requests only, so a long run does not grow without bound."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    calls = MAX_BRIDGE_REQUESTS + 5
    for _ in range(calls):
        adapter.script_answer("the answer")
    bridge = BridgeChatModel(
        caller=_caller(adapter, max_model_calls=calls + 1, max_output_tokens=calls * 512),
        model_id=MODEL_ID,
        slot=SLOT_AGENT,
    )

    for _ in range(calls):
        bridge.invoke([HumanMessage(content=QUESTION)])

    assert len(bridge.requests) == MAX_BRIDGE_REQUESTS
