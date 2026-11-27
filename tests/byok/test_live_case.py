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
of the same case never see each other (FR-012); (k) the case reads the ledger of the plan of the run, and never the
ledger of its own, so the tools of the agent cannot read the rows of another customer (ADR-038); (l) the wall behind
the tools is on the live path too, so a tool that raises becomes the envelope the model reads and the result names
the code of the failure and goes to a human; (m) a run that the ceiling of the turn cuts ends with what stopped it,
and never with an empty answer for the visitor; (n) a cap of the run is not a failure of a tool, so it still stops
the live run and the report of the run names it (FR-009).

Everything offline, with no key and no network: the provider is the fake adapter of the domain, the model of the demo
is the bridge over the caller of the run, and the ledger and the policy index are built in a temporary folder.
"""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens import embeddings as emb
from ledgerlens.agents.integrator import investigate
from ledgerlens.api import live_case
from ledgerlens.api.accounts import scoped_ledger
from ledgerlens.api.live_case import (
    MAX_BRIDGE_REQUESTS,
    SLOT_AGENT,
    SLOT_POLICY,
    SLOT_SQL,
    SLOT_TRIAGE,
    BridgeChatModel,
    DemoCase,
    build_demo_agent,
    demo_executor,
    wrap_tool,
)
from ledgerlens.api.live_run import LIVE_MODE, LiveRunCoordinator, LiveRunPlan, ModelCaller
from ledgerlens.byok.adapter import FakeProviderAdapter, ProviderAdapter, ProviderResponse
from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.errors import ProviderCallFailed
from ledgerlens.byok.registry import ModelProfile, Pricing, ProviderRegistry
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.run_context import RunBudget
from ledgerlens.sandbox.ledger_view import LedgerView
from ledgerlens.schemas import Coherence, Evidence, InvestigationResult
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
VERIFICATION_ANSWER = "The refund is still pending [sql:1]."

# The account of the scenario of the tests. The ledger of the visitor holds the rows of that account and of no other
# one, and the transaction that the query of the tests asks for belongs to another customer of the same published
# ledger (ADR-038).
ACCOUNT = "C-0412"
# The name of the branch of the visitor and the revision it is at. The case reads the file of the view and never the
# identifiers, but the view has to name the state it holds (ADR-038).
BRANCH_ID = "sb_0123456789abcdef01234567"
REVISION = 0
CANONICAL_HASH = "canonical-hash-of-the-branch-of-the-visitor"

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
    """A plan of a run: the question of the case and the caps of the visitor.

    Why the plan carries no ledger by default: the case of the demo refuses a run without the ledger of the visitor,
    and the tests that need the case of the demo give their plan one (ADR-038).
    """
    values: dict[str, Any] = {
        "run_id": "run-case",
        "session_id": SESSION,
        "model_profile_id": PROFILE_ID,
        "credential_handle": handle,
        "question": QUESTION,
        "budget": RunBudget(max_model_calls=8, max_tool_calls=8, max_wall_seconds=30, max_output_tokens=512),
        "account_id": ACCOUNT,
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
    provider: str = "openai",
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
        provider=provider,
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
def ledger_of_the_visitor(ledger_db: Path, tmp_path: Path) -> LedgerView:
    """The ledger of the visitor: the rows of the account of the scenario, in a file the tools of the agent read.

    Why the rows of one account: the ledger of the visitor holds the records of that visitor and of nobody else, and
    the file is what the tools of the agent read (ADR-038).

    Why the account is scoped here and not in the branch layer: the layer belongs to the sandbox, and the file of the
    view is the artifact the run reads (ADR-038).
    """
    path = scoped_ledger(ledger_db, ACCOUNT, tmp_path / "ledger-of-the-visitor.db")
    return LedgerView(
        path=path,
        account_id=ACCOUNT,
        branch_id=BRANCH_ID,
        revision=REVISION,
        canonical_hash=CANONICAL_HASH,
    )


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


def _the_case_that_remembers_the_bridges(case: DemoCase) -> tuple[Any, list[dict[str, BridgeChatModel]]]:
    """The case of the demo with a spy that keeps the bridges of the run while the run is still running.

    Why the bridges are read during the run: the case forgets the run when the run ends, so the evidence of a run
    that is over is gone, and a reader that wants it has to read it while the run lives (ADR-038).
    """
    kept: list[dict[str, BridgeChatModel]] = []

    def spy(caller: Any, plan: LiveRunPlan) -> str:
        """The case of the demo, which keeps the bridges of the run before the run ends."""
        answer = case(caller, plan)
        kept.append(dict(case.bridges_of(plan.run_id)))
        return answer

    return spy, kept


@pytest.fixture
def cited_case(
    ledger_db: Path, index_root: Path, embeddings: FastEmbedEmbeddings, tmp_path: Path
) -> tuple[DemoCase, FakeProviderAdapter]:
    """An investigation with one cited text claim and four calls before verification."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": QUESTION}))
    adapter.script_answer(SQL_ANSWER)
    adapter.script_answer(VERIFICATION_ANSWER)
    case = DemoCase(db_path=ledger_db, index_root=index_root, embeddings=embeddings, runtime_dir=tmp_path)
    return case, adapter


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


@pytest.mark.parametrize(
    ("classifier_reply", "summary", "review_required"),
    [
        ("entailment", "1 supported, 0 contradicted, 0 with insufficient evidence", False),
        ("contradiction", "0 supported, 1 contradicted, 0 with insufficient evidence", True),
        ("neutral", "0 supported, 0 contradicted, 1 with insufficient evidence", True),
        ("unexpected private provider text", "Verification could not be completed", True),
    ],
)
def test_openai_live_verifier_reads_cited_evidence_through_the_run_budget(
    cited_case: tuple[DemoCase, FakeProviderAdapter],
    classifier_reply: str,
    summary: str,
    review_required: bool,
) -> None:
    """The metered visitor model checks cited claims and the answer shows the outcome."""
    case, adapter = cited_case
    adapter.script_answer(classifier_reply, input_tokens=41, output_tokens=2)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert result.report.calls_by_model == {MODEL_ID: 5}
    assert result.report.input_tokens == 41
    assert result.report.output_tokens == 2
    assert len(_spans(coordinator, "run-case", "model.call")) == 5
    request = adapter.calls[-1]
    assert request.model_id == MODEL_ID
    assert not request.tools
    pair = json.loads(request.messages[-1]["content"])
    assert pair["claim"] == "The refund is still pending."
    assert "id: TX-0001" in pair["evidence"]
    assert "status:" in pair["evidence"]
    assert summary in result.answer
    assert ("Human review required" in result.answer) is review_required
    assert result.answer.endswith(VERIFICATION_ANSWER)
    assert classifier_reply not in result.answer


@pytest.mark.parametrize(("provider", "offline_mode"), [("anthropic", "0"), ("openai", "1")])
def test_non_openai_and_offline_cases_keep_deterministic_verification(
    cited_case: tuple[DemoCase, FakeProviderAdapter],
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    offline_mode: str,
) -> None:
    """The case does not call a provider for verification outside the OpenAI online route."""
    case, adapter = cited_case
    monkeypatch.setenv("LEDGERLENS_OFFLINE", offline_mode)

    max_output_tokens = 4096
    caller = _caller(adapter, provider=provider, max_output_tokens=max_output_tokens)
    plan = _plan("unused")
    plan = replace(plan, budget=replace(plan.budget, max_output_tokens=max_output_tokens))
    answer = case(caller, plan)

    assert answer == VERIFICATION_ANSWER
    assert len(adapter.calls) == 4


def test_model_call_cap_stops_openai_live_verification(cited_case: tuple[DemoCase, FakeProviderAdapter]) -> None:
    """Verification stops the run at the shared model cap before calling the provider."""
    case, adapter = cited_case
    adapter.script_answer("entailment")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    plan = _plan(handle.handle)
    plan = replace(plan, budget=replace(plan.budget, max_model_calls=4))

    coordinator.start(plan)
    result = coordinator.wait(plan.run_id, timeout=20.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_model_calls"
    assert result.report.model_calls == len(adapter.calls) == 4


def test_classifier_failure_preserves_numeric_verification_and_escalation(ledger_db: Path) -> None:
    """A text provider failure leaves amount checks and ledger-based review rules active."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_failure(RuntimeError("private provider error"))
    demo = build_demo_agent(_caller(adapter), db_path=ledger_db)
    draft = InvestigationResult(
        session_id=SESSION,
        question=QUESTION,
        answer=(
            "The payment was captured [sql:1]. The payment amount was 6000.00 USD [sql:1]. "
            "The transaction was successful [sql:1]."
        ),
        claims=[],
        evidence=[
            Evidence(
                id="sql:1",
                source_type="sql",
                tool="query_ledger",
                content=json.dumps(
                    {"rows": [{"id": "TX-0001", "status": "captured", "amount_minor": 600000, "currency": "USD"}]}
                ),
                ref="sql:1",
                retrieved_at=datetime(2026, 11, 8, tzinfo=UTC),
            )
        ],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )

    verified = demo.agent.verifier(draft)

    assert [(verdict.method, verdict.label) for verdict in verified.verdicts] == [
        ("nli", "not_enough_evidence"),
        ("numeric", "supported"),
        ("nli", "not_enough_evidence"),
    ]
    assert "Verification could not be completed." in verified.missing_information
    assert any("amount above 5000" in reason for reason in verified.missing_information)
    assert verified.requires_human_review
    assert verified.recommended_action == "escalate_to_human"
    assert len(adapter.calls) == 1


def test_the_triage_model_and_the_generator_of_the_sql_are_counted(case: DemoCase) -> None:
    """FR-012: the four model slots of the agent of the demo are the model of the run, and their calls count."""
    adapter = scripted_adapter()
    vault = CredentialVault()
    the_case, kept = _the_case_that_remembers_the_bridges(case)
    coordinator = _coordinator(adapter, vault, executor=the_case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert kept, "the case never kept the bridges of the run"
    bridges = kept[0]
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


def test_the_executor_of_the_demo_answers_with_the_answer_of_the_agent(
    monkeypatch: pytest.MonkeyPatch, ledger_of_the_visitor: LedgerView
) -> None:
    """The run returns the agent's draft with its metered verification outcome.

    Why the plan carries the ledger of the visitor: the case of the demo has no ledger of its own, and a run without
    the ledger of the visitor is a refusal, because the fallback would hand the model the rows of every account of the
    repository (ADR-038).
    """

    def unexpected_inference(*args, **kwargs):
        pytest.fail("Live retrieval and verification must not use a configured inference backend.")

    monkeypatch.setattr("ledgerlens.tools.policies.get_embeddings", unexpected_inference)
    monkeypatch.setattr("ledgerlens.memory.long_term.get_embeddings", unexpected_inference)
    monkeypatch.setattr("ledgerlens.verify.nli.get_nli", unexpected_inference)
    adapter = scripted_adapter()
    adapter.script_answer("contradiction")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=demo_executor)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=ledger_of_the_visitor))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    assert result.answer == (
        "Human review required. Verification found 0 supported, 1 contradicted, 0 with insufficient evidence."
        f"\n\n{FINAL_ANSWER}"
    )
    assert len(adapter.calls) == 7


def test_the_case_reads_the_ledger_of_the_plan_and_never_the_ledger_of_the_case(
    case: DemoCase, ledger_of_the_visitor: LedgerView
) -> None:
    """ADR-038: the tools of the agent read the ledger of the plan, and never the ledger of the case.

    Why the case keeps the ledger of the repository: the case of the test is built with the whole published ledger,
    and a case that preferred its own ledger would answer about the rows of every account of it. The query of the
    test asks for the transaction of another customer, so the tool of the run finds nothing in the ledger of the
    visitor, and it would find the row in the ledger of the configuration (ADR-038).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=ledger_of_the_visitor))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    # The tool of the agent read the ledger of the visitor: the transaction of the other customer is not in it.
    answers_of_the_tools = [
        message.content for call in adapter.calls for message in call.messages if message.role == "tool"
    ]
    assert answers_of_the_tools
    assert _the_rows_of_the_tool(answers_of_the_tools[0]) == []


def _the_rows_of_the_tool(content: str) -> list[Any]:
    """The rows the tool of the agent returned, read from the text the agent received.

    Why the text is read and not the tool: the run never holds the tool, and the text the agent got is the evidence
    of what the tool read (ADR-038).
    """
    answer = json.loads(content)
    return list(answer["data"]["rows"])


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


def test_the_bridge_refuses_a_number_that_arrives_in_the_arguments() -> None:
    """FR-012: the rule of the arguments is the rule of the domain, and the bridge refuses what the domain refuses.

    Why the number matters: a number that arrives as a number has already lost the exact text of the amount, so
    the domain refuses it. A bridge that wrote the number as a text would invent a text the provider never sent,
    and the budget and the trace of the run would read it as if it were true (FR-012).
    """
    # The public rule of the domain, imported here so that the file of the test reads even before the rule is
    # public: the rule is the one of the domain, and the bridge may not be more permissive than it.
    from ledgerlens.byok import arguments_text

    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer("the answer")
    bridge = BridgeChatModel(caller=_caller(adapter), model_id=MODEL_ID, slot=SLOT_AGENT).bind_tools([_query_tool()])
    number = 10.5

    with pytest.raises(ProviderCallFailed) as refusal:
        bridge.invoke(
            [
                HumanMessage(content=QUESTION),
                AIMessage(
                    content="",
                    additional_kwargs={
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "query_ledger", "arguments": number},
                            }
                        ]
                    },
                ),
            ]
        )

    # The refusal of the bridge is the refusal of the domain, with the same words.
    with pytest.raises(ProviderCallFailed) as domain_refusal:
        arguments_text(number, name="query_ledger")
    assert str(refusal.value) == str(domain_refusal.value)
    # And the provider was never asked: the turn was refused before it left the bridge.
    assert adapter.calls == []


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
    first_case, first_kept = _the_case_that_remembers_the_bridges(case)
    second_case, second_kept = _the_case_that_remembers_the_bridges(case)
    first_coordinator = _coordinator(first, vault, executor=first_case)
    second_coordinator = _coordinator(second, vault, executor=second_case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    first_coordinator.start(_plan(handle.handle, run_id="run-first"))
    second_coordinator.start(_plan(handle.handle, run_id="run-second"))
    first_result = first_coordinator.wait("run-first", timeout=20.0)
    second_result = second_coordinator.wait("run-second", timeout=20.0)

    assert first_result is not None
    assert first_result.status == "completed"
    assert second_result is not None
    assert second_result.status == "completed"
    assert first_kept, "the case never kept the bridges of the first run"
    assert second_kept, "the case never kept the bridges of the second run"
    first_bridges = first_kept[0]
    second_bridges = second_kept[0]
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


# --- the wall behind the tools and the cut of the ceiling, on the live path -----------------------------

# The answer of the agent when a tool of the case broke: the agent says what it could not get and stops.
ANSWER_AFTER_A_BROKEN_TOOL = "I could not read the ledger, so a person has to take this case over."

# The failure of a tool that broke, the way a corrupt index or a ledger that cannot be opened breaks.
BROKEN_TOOL_FAILURE = RuntimeError("the index file is corrupt")


def _a_tool_that_raises(tool: Any, failure: BaseException) -> StructuredTool:
    """The tool of the case with the name and the schema of the original, and the failure of a broken tool.

    Why a tool that raises and not a tool that returns an envelope: the tools of the contract return the envelope
    themselves, and the wall behind them exists for the tool whose implementation breaks anyway.
    """

    def broken(**kwargs: Any) -> Any:
        """The body of a tool whose implementation is broken."""
        raise failure

    broken.__name__ = tool.name
    return StructuredTool.from_function(
        func=broken,
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
    )


def _the_case_with_a_tool_that_raises(monkeypatch: pytest.MonkeyPatch, name: str, failure: BaseException) -> None:
    """Makes one tool of the case of the demo raise, the way a broken tool does in production.

    Why the tool is replaced and not the index corrupted: the wall of the live path is about the tool that raises,
    and the way the tool breaks is not what the wall sees.
    """
    original = live_case.build_integrator

    def patched(*args: Any, **kwargs: Any) -> Any:
        """The integrator of the case, with one of its tools replaced by a broken one."""
        agent = original(*args, **kwargs)
        tools = [_a_tool_that_raises(tool, failure) if tool.name == name else tool for tool in agent.tools]
        return replace(agent, tools=tools)

    monkeypatch.setattr(live_case, "build_integrator", patched)


def _the_adapter_of_a_broken_tool() -> FakeProviderAdapter:
    """The provider of the test: the triage, the call of the tool that breaks and the answer of the agent."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_broken")
    adapter.script_answer(ANSWER_AFTER_A_BROKEN_TOOL)
    return adapter


def test_a_tool_that_raises_does_not_take_the_live_run_down(case: DemoCase, monkeypatch: pytest.MonkeyPatch) -> None:
    """The wall behind the tools is on the live path too: a tool that raises does not take the run down.

    Why the live path needs the wall of the demo path: the contract of the tools says that a tool that raises does
    not take the run down, and the live path is the path a visitor walks.
    """
    _the_case_with_a_tool_that_raises(monkeypatch, "query_ledger", BROKEN_TOOL_FAILURE)
    adapter = _the_adapter_of_a_broken_tool()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    # The run did not die with the error of the tool: the model read the failure and answered.
    assert result.status == "completed"
    assert result.answer == ANSWER_AFTER_A_BROKEN_TOOL
    # And the visitor never saw the error of the tool.
    assert result.error is None


def test_the_failure_of_a_tool_that_raises_is_named_in_the_result_of_the_live_path(
    ledger_db: Path, index_root: Path, embeddings: FastEmbedEmbeddings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The result of the live path carries the code of the failure and goes to a human, like the demo path."""
    _the_case_with_a_tool_that_raises(monkeypatch, "query_ledger", BROKEN_TOOL_FAILURE)
    adapter = _the_adapter_of_a_broken_tool()
    # The caller of the run plans its output tokens against the cap of the run, the way the coordinator does it.
    caller = ModelCaller(
        adapter=adapter,
        budget=BudgetCoordinator(
            RunBudget(max_model_calls=8, max_tool_calls=8, max_wall_seconds=30, max_output_tokens=512), registry()
        ),
        trace=TraceEventStream("run-case", InMemoryTraceSink(), mode=LIVE_MODE),
        cancel=threading.Event(),
        provider="openai",
        model_id=MODEL_ID,
        call_timeout=lambda: None,
        max_output_tokens=512,
    )
    demo = build_demo_agent(
        caller,
        db_path=ledger_db,
        verifier=refusing_verifier(),
        index_root=index_root,
        embeddings=embeddings,
    )

    result = investigate(demo.agent, QUESTION, thread_id="thread-live")

    # The trace of the turn names the code of the failure.
    assert [record.error_code for record in result.tool_trace] == ["TOOL_FAILED"]
    assert not result.tool_trace[0].ok
    # And the result goes to a person, because the run could not answer with what it found.
    assert result.requires_human_review
    assert any("TOOL_FAILED" in entry for entry in result.missing_information)
    # The model read the envelope of the failure, and not a stack trace.
    request = adapter.calls[-1]
    tool_messages = [message for message in request.messages if message.role == "tool"]
    assert tool_messages, "the model never received the result of the tool that broke"
    envelope = json.loads(tool_messages[-1].content)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "TOOL_FAILED"
    assert "Traceback" not in tool_messages[-1].content


def test_the_cap_of_the_calls_of_the_tools_still_stops_the_live_run_and_names_the_cap(case: DemoCase) -> None:
    """FR-009: a cap of the run is not a failure of a tool: it stops the run and the report names the cap.

    Why the cap is not enveloped: the model must never read a cap of the run as something it can work around, and
    the run has to end with the reason that names the cap (ADR-054).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    for index in range(2):
        adapter.script_tool_call(
            "calculate",
            json.dumps({"operation": "difference", "values": {"a": "10.00", "b": "2.00"}}),
            call_id=f"call_{index}",
        )
    adapter.script_answer(FINAL_ANSWER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    # The cap of the tools of the run allows one call, and the second one stops the run.
    budget = RunBudget(max_model_calls=8, max_tool_calls=1, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_tool_calls"
    assert "max_tool_calls" in (result.error or "")
    # The model never read the cap as the failure of a tool, so it never answered around it.
    assert len(adapter.calls) == 3


def test_a_run_that_the_ceiling_of_the_turn_cuts_never_ends_with_an_empty_answer(case: DemoCase) -> None:
    """A run that a ceiling cuts says what stopped it: the visitor never reads an empty answer.

    Why the agent loops: a model that asks for a tool forever is what a ceiling of the turn cuts, and the run has
    to end with a reason the visitor can read instead of with nothing at all.

    Why the ceiling that cuts is the cap of the plan: the coordinator of the run is the budget of the agent
    (ADR-054), so the ceiling of the turn is the cap of the visitor, and the run that the cap cuts ends with
    the cap named and never with an empty answer.
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(SIMPLE_TRIAGE_ANSWER)
    for index in range(20):
        adapter.script_tool_call(
            "calculate",
            json.dumps({"operation": "difference", "values": {"a": "10.00", "b": "2.00"}}),
            call_id=f"call_{index}",
        )
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    # The cap of the plan is the ceiling of the turn: the run stops when the cap of the models is reached.
    budget = RunBudget(max_model_calls=4, max_tool_calls=60, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-case", timeout=30.0)

    assert result is not None
    # The visitor reads what stopped the run, and not an empty answer: the cap is named.
    assert result.status == "failed"
    assert result.report.cut_by == "max_model_calls"
    assert "max_model_calls" in (result.error or "")
    assert (result.answer or result.error or "") != ""
    # The call that would break the cap never reached the provider.
    assert len(adapter.calls) == 4


def test_the_live_path_of_the_visitor_builds_no_runner_of_the_retry(
    ledger_db: Path, index_root: Path, embeddings: FastEmbedEmbeddings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live path holds the credential of the visitor and not the key of the server, so it has no runner.

    Why it matters: a retry built with the key of the server would be a call that the visitor did not ask for,
    that nobody counts and that the caps of the visitor do not hold (ADR-037, ADR-054).

    Why the consent is on: a deployment that consented to no retry would have no runner in any path, and the
    test would pass without proving anything about the live path.
    """
    monkeypatch.setenv("LEDGERLENS_FALLBACK_ATTEMPTS", "1")
    caller = _caller(scripted_adapter())
    demo = build_demo_agent(
        caller,
        db_path=ledger_db,
        verifier=refusing_verifier(),
        index_root=index_root,
        embeddings=embeddings,
    )

    assert demo.agent.fallback is None
    assert demo.agent.triage_fallback is None


def test_the_coordinator_of_the_run_is_the_budget_of_the_agent_and_the_calls_are_counted_once(
    case: DemoCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The coordinator of the live run is passed to the agent, without a second counter.

    Why it matters: the usage of the turn of the agent is the usage of the coordinator of the run, and a
    second counter would count every call of the provider twice (ADR-054).
    """
    from ledgerlens.api import live_case as live_case_module

    seen: dict[str, Any] = {}
    real_investigate = live_case_module.investigate

    def spying_investigate(agent: Any, question: str, **kwargs: Any) -> Any:
        seen["budget"] = kwargs.get("budget")
        result = real_investigate(agent, question, **kwargs)
        seen["usage"] = result.usage
        return result

    monkeypatch.setattr(live_case_module, "investigate", spying_investigate)
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    turn = seen["budget"]
    assert turn is not None, "the case did not pass the coordinator of the run to the agent"
    assert turn.owner == "caller"
    # The coordinator of the turn is the coordinator of the run: one counter, and no call counted twice.
    assert turn.coordinator is not None
    usage = seen["usage"]
    assert usage, "the result of the agent carries no usage"
    assert usage["model_calls"] == len(adapter.calls)
    assert result.report.model_calls == len(adapter.calls)
