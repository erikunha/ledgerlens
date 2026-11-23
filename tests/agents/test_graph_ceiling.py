"""The ceiling of the graph of the agent: the limit of the steps, the paths that carry it and the cut it names.

What they guarantee, and why: (a) the limit of the steps of the graph is derived from the cap of the calls
of the models, and the value of the derivation is pinned, so a change of it breaks a test and not a run;
(b) every path that reaches the graph carries the limit, also the one that calls the integrator outside
`investigate`, and a limit that the configuration already carries is never loosened; (c) a turn that the
graph cuts when the caller gave no cap of the calls of the models is cut by the ceiling of the graph and
not by a cap that nobody gave, and the sentence that names the cut reads well. The model is a
`ScriptedChatModel`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.agents import budget as budget_module
from ledgerlens.agents.budget import (
    GRAPH_STEP_BACKSTOP,
    GRAPH_STEPS,
    TurnBudget,
    cap_sentence,
    derived_recursion_limit,
    recursion_limit_for,
    shipped_turn_budget,
)
from ledgerlens.agents.integrator import Integrator, build_integrator, investigate
from ledgerlens.byok.budget import BudgetCoordinator
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.run_context import RunBudget
from ledgerlens.schemas import InvestigationResult
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient
from tests.tools import test_policies as base

RECORD = {"kind": "transaction", "id": "TX-2048"}


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The ledger of the sample, so the tools of the agent have something to read."""
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """The embeddings of the tests, without the download of the real model."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> Path:
    """The index of the policies of the tests."""
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


@pytest.fixture
def cases(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> CaseMemory:
    """The memory of the cases of the tests."""
    return CaseMemory(tmp_path / "cases", embeddings=embeddings)


class RecordingGraph:
    """A graph that records the configuration it received and answers with nothing.

    It stands for the graph of the agent in the tests about the ceiling of the steps: what matters there
    is the configuration that reaches the graph and not the answer of the graph.
    """

    def __init__(self) -> None:
        self.config: Any = None
        self.kwargs: dict[str, Any] = {}

    def invoke(self, payload: Any, config: Any = None, **kwargs: Any) -> Any:
        """Records the configuration of the call and answers with no state."""
        self.config = config
        self.kwargs = kwargs
        return {"messages": []}


def turn_with(caps: RunBudget, *, owner: str = "none") -> TurnBudget:
    """The ceiling of a turn with these caps, counting them or not.

    The owner decides who counts the calls of the turn: `none` leaves the counting to the side that holds
    the provider, so the graph is the only thing that can stop the turn (ADR-054).
    """
    return TurnBudget(caps=caps, coordinator=BudgetCoordinator(caps, ProviderRegistry([])), owner=owner)


def test_the_limit_of_the_steps_is_the_steps_of_the_calls_of_the_models_plus_the_headroom() -> None:
    """The number that stops the loop of the graph is derived from the cap of the calls, and it is pinned.

    The numbers are written down here on purpose: a test that computes the expectation with the constants
    of the module would pass with any value of them, and the value that stops a run would never be checked.
    """
    assert derived_recursion_limit(RunBudget(max_model_calls=3)) == 10  # 2 steps per call and 4 of headroom
    assert derived_recursion_limit(RunBudget(max_model_calls=12)) == 28
    assert recursion_limit_for(RunBudget(max_model_calls=3)) == 10
    assert recursion_limit_for(RunBudget(max_model_calls=12)) == 28


def test_a_turn_with_no_cap_of_calls_gets_the_backstop_and_not_an_invented_cap() -> None:
    """What is not given is not a limit: no cap of the calls derives no limit of the steps.

    The graph still gets the backstop of the product, so no path that reaches it is unbounded, and the
    backstop is not a cap of the run: a cut of the graph is never named after a cap that nobody gave.
    """
    assert derived_recursion_limit(RunBudget()) is None
    assert recursion_limit_for(RunBudget()) == GRAPH_STEP_BACKSTOP == 28


def test_every_call_that_reaches_the_graph_carries_the_limit_of_the_steps() -> None:
    """The defect of the finding: the configuration that reached the graph carried no limit at all.

    The integrator here counts nothing (`counts_calls=False`, the shape of the live path), so the limit of
    the steps is the only thing that can stop the call.
    """
    graph = RecordingGraph()
    agent = Integrator(graph=graph, tools=[], counts_calls=False)

    agent.invoke({"messages": []})

    assert graph.config is not None
    assert graph.config["recursion_limit"] == 28  # the limit the caps of the shipped paths derive


def test_the_limit_of_the_configuration_is_never_loosened_and_never_above_the_derived_one() -> None:
    """A caller that brought a smaller limit keeps it, and a bigger one never lifts the ceiling."""
    graph = RecordingGraph()
    agent = Integrator(graph=graph, tools=[])

    agent.invoke({"messages": []}, {"recursion_limit": 5})
    assert graph.config["recursion_limit"] == 5

    agent.invoke({"messages": []}, {"recursion_limit": 9999, "configurable": {"thread_id": "t"}})
    assert graph.config["recursion_limit"] == 28  # never above the derived one
    assert graph.config["configurable"] == {"thread_id": "t"}  # the rest of the configuration survives


def test_a_turn_with_n_calls_of_a_model_is_cut_by_the_graph(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """The backstop of the ceiling: the graph stops the turn and the cut names the cap that derived it.

    The cap of three calls of a model gives a limit of ten steps, so the graph stops the turn after five
    calls of the model. A limit that grew would let the turn run on, and the test would fail.
    """
    script = [tool_call_message("get_ledger_record", RECORD) for _ in range(20)]
    model = ScriptedChatModel(script=script)
    agent = build_integrator(
        model,
        db_path=ledger_db,
        verifier=lambda result, *, nli=None: result,
        query_model=ScriptedChatModel(script=[]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
        triage_model=ScriptedChatModel(script=[]),
    )
    turn = turn_with(RunBudget(max_model_calls=3))

    result = investigate(agent, "Where is my refund?", thread_id="t-cut", budget=turn)

    assert isinstance(result, InvestigationResult)  # a result, not an exception
    assert result.requires_human_review is True
    assert result.recommended_action == "escalate_to_human"
    assert any("max_model_calls" in item for item in result.missing_information)  # the cap that stopped it
    assert any("3 model calls" in item for item in result.missing_information)  # and its value
    assert len(model.calls) == 5  # the limit of ten steps is five calls of the model


def test_a_turn_with_no_cap_of_calls_is_cut_by_the_ceiling_of_the_graph_and_not_by_a_cap(
    ledger_db: Path, index_root: Path, cases: CaseMemory
) -> None:
    """A run that gave no cap of the calls of the models is not cut by a cap that nobody gave.

    The graph still stops the turn, and the sentence names the ceiling of the graph and not a cap of the
    run, because naming a cap that nobody gave would be a lie.
    """
    script = [tool_call_message("get_ledger_record", RECORD) for _ in range(30)]
    model = ScriptedChatModel(script=script)
    agent = build_integrator(
        model,
        db_path=ledger_db,
        verifier=lambda result, *, nli=None: result,
        query_model=ScriptedChatModel(script=[]),
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
        triage_model=ScriptedChatModel(script=[]),
    )
    turn = turn_with(RunBudget(), owner="integrator")

    result = investigate(agent, "Where is my refund?", thread_id="t-no-cap", budget=turn)

    assert isinstance(result, InvestigationResult)
    assert result.requires_human_review is True
    assert result.recommended_action == "escalate_to_human"
    assert not any("max_model_calls" in item for item in result.missing_information)  # no cap was given
    assert any("the ceiling of the graph" in item for item in result.missing_information)
    assert any(f"{GRAPH_STEP_BACKSTOP} steps" in item for item in result.missing_information)


def test_the_sentence_of_a_cap_that_has_no_value_reads_well() -> None:
    """The sentence of a cut names what stopped the turn, and it reads as a sentence."""
    assert cap_sentence("max_model_calls", RunBudget(max_model_calls=12)) == (
        "the cap 'max_model_calls' stopped the turn: the turn reached the cap of 12 model calls, "
        "so the turn stops and a person takes it over"
    )
    without_value = cap_sentence("max_model_calls", RunBudget())
    assert "the limit" not in without_value
    assert without_value == (
        "the cap 'max_model_calls' stopped the turn: the turn reached the cap of model calls, "
        "so the turn stops and a person takes it over"
    )


def test_the_sentence_of_the_ceiling_of_the_graph_names_the_steps_and_not_a_cap() -> None:
    """The cut of the graph is the ceiling of the graph, and the sentence says so."""
    sentence = cap_sentence(GRAPH_STEPS, RunBudget())

    assert sentence == (
        "the ceiling of the graph stopped the turn: the turn reached the ceiling of "
        f"{GRAPH_STEP_BACKSTOP} steps of the graph, so the turn stops and a person takes it over"
    )
    assert "cap '" not in sentence


def test_the_public_api_of_the_budget_module_is_complete() -> None:
    """Every public name of the module is exported, and every exported name exists."""
    for name in budget_module.__all__:
        assert hasattr(budget_module, name), name
    for name in (
        "Owner",
        "TurnBudget",
        "BudgetReservationMiddleware",
        "GRAPH_STEPS",
        "GRAPH_STEP_BACKSTOP",
        "cap_sentence",
        "caps_of",
        "derived_recursion_limit",
        "model_id_of",
        "recursion_limit_for",
        "shipped_turn_budget",
        "turn_of",
        "usage_of",
    ):
        assert name in budget_module.__all__, name


def test_the_ceiling_of_a_turn_without_a_cap_carries_the_caps_it_was_given() -> None:
    """The ceiling of a turn is the one the caller gave, and not the one of the shipped paths."""
    turn = shipped_turn_budget(RunBudget(), owner="integrator")

    assert turn.caps == RunBudget()
    assert turn.caps.max_model_calls is None
