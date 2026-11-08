"""Tests of the system prompt in the PTCF format.

What they guarantee, and why: the prompt has the four sections (Persona, Task, Context, Format), carries at
least three few-shot examples with real scenario text, describes the step-by-step plan, says to treat text
from data as data and names only tools that exist. They also guarantee that the prompt asks for the real
tool call (not the call or the result written as text), that policy facts come only from `search_policies`
and that the examples show the shape of the answer with no values to copy.
"""

from __future__ import annotations

import json
import re

from langchain_core.prompts import ChatPromptTemplate

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.prompts.system import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT, build_system_prompt

TOOLS = {"query_ledger", "get_ledger_record", "search_policies", "get_reference_fx", "calculate", "recall_cases"}
SECTIONS = ("Persona", "Task", "Context", "Format")


def _real_complaints() -> set[str]:
    cases = (PROJECT_ROOT / "data" / "eval" / "triage_cases.jsonl").read_text(encoding="utf-8").splitlines()
    texts = {json.loads(line)["complaint"] for line in cases if line.strip()}
    policy = (PROJECT_ROOT / "data" / "eval" / "policy_questions.jsonl").read_text(encoding="utf-8").splitlines()
    texts.update(json.loads(line)["question"] for line in policy if line.strip())
    scenarios = json.loads((PROJECT_ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    for scenario in scenarios:
        texts.update(scenario["questions"])
    return texts


def test_has_the_four_ptcf_sections_in_order() -> None:
    positions = [SYSTEM_PROMPT.find(f"## {name}") for name in SECTIONS]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions)


def test_has_at_least_three_few_shot_examples_in_the_prompt() -> None:
    assert len(FEW_SHOT_EXAMPLES) >= 3
    for example in FEW_SHOT_EXAMPLES:
        assert example["complaint"] in SYSTEM_PROMPT
        assert example["plan"], "every example shows a plan"
        assert example["answer"] in SYSTEM_PROMPT


def test_few_shot_examples_use_real_scenario_wording_and_known_tools() -> None:
    real = _real_complaints()
    for example in FEW_SHOT_EXAMPLES:
        assert example["complaint"] in real, example["complaint"]
        used = set(re.findall(r"tool: (\w+)", "\n".join(example["plan"])))
        assert used <= TOOLS | {"none"}, used - TOOLS


def test_states_the_step_by_step_plan_format() -> None:
    assert "S1." in SYSTEM_PROMPT
    assert "tool:" in SYSTEM_PROMPT
    assert "depends on:" in SYSTEM_PROMPT


def test_data_text_is_not_instructions() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "data" in lowered and "never" in lowered and "instruction" in lowered


def test_mentions_every_tool() -> None:
    for tool in TOOLS:
        assert tool in SYSTEM_PROMPT


def test_prompt_has_no_braces_so_it_is_safe_as_literal_text() -> None:
    # A stray `{` would become a slot in a ChatPromptTemplate; with no braces, the text goes in as is.
    assert "{" not in SYSTEM_PROMPT and "}" not in SYSTEM_PROMPT
    template = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{input}")])
    assert template.input_variables == ["input"]


def test_build_system_prompt_puts_the_given_date_in_the_context() -> None:
    text = build_system_prompt("2026-11-10")
    assert "2026-11-10" in text
    assert text.index("2026-11-10") > text.index("## Context")
    assert text.index("2026-11-10") < text.index("## Format")


def test_build_system_prompt_defaults_to_an_iso_date() -> None:
    assert re.search(r"\d{4}-\d{2}-\d{2}", build_system_prompt())


def _section(name: str) -> str:
    start = SYSTEM_PROMPT.index(f"## {name}")
    following = [SYSTEM_PROMPT.find(f"## {other}", start + 1) for other in SECTIONS]
    return SYSTEM_PROMPT[start : min([i for i in following if i > start] or [len(SYSTEM_PROMPT)])]


def test_forbids_writing_tool_calls_and_tool_results_as_text() -> None:
    # A real defect (gpt-4.1-mini, 2 of 3 runs): the model wrote the plan, then "Calling get_reference_fx"
    # and a made-up "Tool response" with a rate no tool returned, and the run ended with no call at all.
    # The prompt has to ask for the real call and forbid the written result.
    rules = _section("Context") + _section("Format")
    assert "real tool call" in rules
    assert re.search(r"never write[^.]*result", rules, re.IGNORECASE)
    assert "no tool returned" in rules


def test_the_plan_message_carries_the_first_real_tool_call() -> None:
    # Without this the plan in text ends the run: the agent only goes on while the message has a tool call.
    format_ = _section("Format")
    assert re.search(r"same message[^.]*call", format_)


def test_policy_facts_come_only_from_search_policies() -> None:
    rule = [line for line in _section("Context").splitlines() if "Policy" in line and "search_policies" in line]
    assert rule, "the context must say where policy facts come from"
    assert "only" in rule[0] and "before answering" in rule[0]


def test_one_example_is_a_pure_policy_question_answered_through_search_policies() -> None:
    pure = [
        e
        for e in FEW_SHOT_EXAMPLES
        if set(re.findall(r"tool: (\w+)", "\n".join(e["plan"]))) == {"search_policies", "none"}
    ]
    assert pure, "a policy question needs its own few-shot, with search_policies as the only tool"
    assert pure[0]["plan"][0].split("|")[1].strip() == "tool: search_policies"


def test_example_answers_show_the_form_only_never_a_value_to_copy() -> None:
    for example in FEW_SHOT_EXAMPLES:
        assert not re.search(r"\d+[.,]\d+", example["answer"]), example["answer"]
        assert "Tool response" not in example["answer"]


def test_no_forbidden_dashes() -> None:
    assert not re.search("[\u2013\u2014]| -- ", SYSTEM_PROMPT)
