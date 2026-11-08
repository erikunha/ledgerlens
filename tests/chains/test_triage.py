"""Tests of the triage chain in both styles, `@chain` and LCEL.

What they guarantee: the 10 fixed cases agree with the scenario manifest; both versions give the same result
and send the same prompt to the model; `batch` keeps the input order; `stream` ends in the same result as
`invoke`.

Two fake models come in here. `ScriptedChatModel` answers in call order (that is why its `batch` runs with
`max_concurrency=1`). `ComplaintLookupModel` answers according to the complaint it reads in the prompt,
whatever the order, and so proves that the concurrent `batch` keeps the order.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

from ledgerlens.chains.parsers import TriageError
from ledgerlens.chains.triage import (
    TriageCase,
    build_triage_declarative,
    build_triage_imperative,
    load_triage_cases,
    triage_prompt,
)
from ledgerlens.offline import ScriptedChatModel
from ledgerlens.schemas import Triage

CASES = load_triage_cases()
BUILDERS: dict[str, Callable[[BaseChatModel], Runnable]] = {
    "imperative": build_triage_imperative,
    "declarative": build_triage_declarative,
}
TOOLS = {"query_ledger", "get_ledger_record", "search_policies", "get_reference_fx", "calculate", "recall_cases"}


def reply_for(case: TriageCase) -> str:
    return json.dumps(case.expected.model_dump(mode="json"), ensure_ascii=False)


class ComplaintLookupModel(BaseChatModel):
    """Answers with the reference triage of the complaint it finds in the prompt, in any call order.

    Complaints listed in `broken` get an unreadable answer, and so does every repair prompt.
    """

    broken: frozenset[str] = frozenset()

    @property
    def _llm_type(self) -> str:
        return "complaint-lookup"

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        prompt = "\n".join(str(m.content) for m in messages)
        found = [c for c in CASES if f"<complaint>\n{c.complaint}\n</complaint>" in prompt]
        if not found:  # the repair prompt carries the broken output, not the complaint
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="still broken"))])
        (case,) = found
        content = "{broken" if case.id in self.broken else reply_for(case)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def test_there_are_ten_cases_with_unique_ids() -> None:
    assert len(CASES) == 10
    assert len({c.id for c in CASES}) == 10


def test_cases_include_s01_to_s05_wording_and_one_prompt_injection() -> None:
    scenarios = {c.scenario for c in CASES}
    assert {"S01", "S02", "S03", "S04", "S05"} <= scenarios
    assert [c.id for c in CASES if "prompt_injection" in c.tags] == ["T10"]


def test_cases_agree_with_the_scenario_manifest() -> None:
    import ledgerlens.config as config

    manifest = json.loads((config.PROJECT_ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in manifest["scenarios"]}
    for case in CASES:
        triage = case.expected
        assert {step.tool for step in triage.plan if step.tool} <= TOOLS
        if case.scenario is None:
            continue
        scenario = by_id[case.scenario]
        assert triage.intent == scenario["expected_intent"], case.id
        for field, ids in scenario["ids"].items():
            assert set(getattr(triage.entities, field)) <= set(ids), (case.id, field)
        tools = {step.tool for step in triage.plan if step.tool}
        assert tools <= set(scenario["expected_tools"]), case.id
        if case.scenario in {"S01", "S02", "S03", "S04"}:
            assert tools == set(scenario["expected_tools"]), case.id
        if case.scenario in {"S01", "S02", "S04"}:
            assert set(triage.entities.transaction_ids) == set(scenario["ids"]["transaction_ids"]), case.id


def test_every_reference_id_appears_in_its_complaint() -> None:
    for case in CASES:
        entities = case.expected.entities
        fields = ("transaction_ids", "refund_ids", "chargeback_ids", "settlement_ids", "merchant_ids", "customer_ids")
        for field in fields:
            for identifier in getattr(entities, field):
                assert identifier in case.complaint, (case.id, identifier)


def test_the_injection_case_keeps_the_real_question_and_ignores_the_order() -> None:
    (case,) = [c for c in CASES if "prompt_injection" in c.tags]
    triage = case.expected
    assert triage.intent == "status_lookup"
    assert triage.urgency != "critical"
    assert triage.entities.merchant_ids == []
    assert all("approv" not in step.goal.lower() for step in triage.plan)


def test_plans_have_unique_ids_and_dependencies_that_point_backwards() -> None:
    for case in CASES:
        seen: set[str] = set()
        for step in case.expected.plan:
            assert step.id not in seen, case.id
            assert set(step.depends_on) <= seen, (case.id, step.id)
            seen.add(step.id)


@pytest.mark.parametrize("style", BUILDERS)
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_invoke_returns_the_reference_triage(style: str, case: TriageCase) -> None:
    chain = BUILDERS[style](ScriptedChatModel(script=[reply_for(case)]))
    result = chain.invoke({"complaint": case.complaint})
    assert isinstance(result, Triage)
    assert result == case.expected


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_both_styles_give_equal_results_and_send_the_same_prompt(case: TriageCase) -> None:
    models = {style: ScriptedChatModel(script=[reply_for(case)]) for style in BUILDERS}
    results = {style: BUILDERS[style](models[style]).invoke({"complaint": case.complaint}) for style in BUILDERS}
    assert results["imperative"] == results["declarative"]
    assert models["imperative"].calls == models["declarative"].calls
    system, human = models["declarative"].calls[0]
    assert case.complaint in human.content
    assert "intent" in system.content  # format instructions reached the model


@pytest.mark.parametrize("style", BUILDERS)
def test_both_styles_repair_once_and_return_the_typed_error(style: str) -> None:
    case = CASES[0]
    repaired = BUILDERS[style](ScriptedChatModel(script=["{broken", reply_for(case)]))
    assert repaired.invoke({"complaint": case.complaint}) == case.expected
    failed = BUILDERS[style](ScriptedChatModel(script=["{broken", "still broken"]))
    result = failed.invoke({"complaint": case.complaint})
    assert isinstance(result, TriageError)
    assert result.repair_attempted


@pytest.mark.parametrize("style", BUILDERS)
def test_batch_keeps_input_order_under_concurrency(style: str) -> None:
    order = list(range(len(CASES)))
    random.Random(7).shuffle(order)
    shuffled = [CASES[i] for i in order]
    chain = BUILDERS[style](ComplaintLookupModel())
    results = chain.batch([{"complaint": c.complaint} for c in shuffled])
    assert results == [c.expected for c in shuffled]


@pytest.mark.parametrize("style", BUILDERS)
def test_batch_with_a_scripted_model_needs_one_worker(style: str) -> None:
    """The scripted model answers in call order, so the batch runs one input at a time."""
    chain = BUILDERS[style](ScriptedChatModel(script=[reply_for(c) for c in CASES[:5]]))
    results = chain.batch([{"complaint": c.complaint} for c in CASES[:5]], config={"max_concurrency": 1})
    assert results == [c.expected for c in CASES[:5]]


@pytest.mark.parametrize("style", BUILDERS)
def test_batch_returns_a_typed_error_in_place_of_a_failed_item(style: str) -> None:
    chain = BUILDERS[style](ComplaintLookupModel(broken=frozenset({CASES[1].id})))
    results = chain.batch([{"complaint": CASES[i].complaint} for i in (0, 1, 2)])
    assert results[0] == CASES[0].expected
    assert isinstance(results[1], TriageError)
    assert results[2] == CASES[2].expected


def test_declarative_batch_runs_stage_by_stage_and_imperative_batch_item_by_item() -> None:
    """Why the scripted model needs `max_concurrency=1`: the order of model calls differs between the styles."""
    case, other = CASES[0], CASES[1]
    inputs = [{"complaint": case.complaint}, {"complaint": other.complaint}]
    config = {"max_concurrency": 1}
    # the first item comes broken and needs a repair answer; the script has 3 answers
    script = ["{broken", reply_for(other), reply_for(case)]
    declarative = ScriptedChatModel(script=script)
    build_triage_declarative(declarative).batch(inputs, config=config)
    assert [m[-1].content.startswith("<complaint>") for m in declarative.calls] == [True, True, False]
    imperative = ScriptedChatModel(script=script)
    build_triage_imperative(imperative).batch(inputs, config=config)
    assert [m[-1].content.startswith("<complaint>") for m in imperative.calls] == [True, False, True]


@pytest.mark.parametrize("style", BUILDERS)
def test_stream_ends_with_the_same_result_as_invoke(style: str) -> None:
    case = CASES[0]
    streamed = list(BUILDERS[style](ScriptedChatModel(script=[reply_for(case)])).stream({"complaint": case.complaint}))
    assert streamed
    assert streamed[-1] == case.expected
    assert all(isinstance(chunk, Triage) for chunk in streamed)


def test_stream_of_the_text_stage_yields_chunks_that_join_to_the_reply() -> None:
    """Before the parser the model emits text bit by bit; joined, the pieces validate to the same triage."""
    case = CASES[0]
    model = GenericFakeChatModel(messages=iter([AIMessage(content=reply_for(case))]))
    chunks = list((triage_prompt() | model | StrOutputParser()).stream({"complaint": case.complaint}))
    assert len(chunks) > 1
    assert "".join(chunks) == reply_for(case)
    assert Triage.model_validate_json("".join(chunks)) == case.expected


@pytest.mark.parametrize("style", BUILDERS)
def test_stream_through_a_streaming_model_ends_with_the_validated_triage(style: str) -> None:
    case = CASES[0]
    model = GenericFakeChatModel(messages=iter([AIMessage(content=reply_for(case))]))
    streamed = list(BUILDERS[style](model).stream({"complaint": case.complaint}))
    assert streamed[-1] == case.expected


def test_triage_prompt_has_the_format_instructions_filled_in() -> None:
    prompt = triage_prompt()
    assert prompt.input_variables == ["complaint"]
