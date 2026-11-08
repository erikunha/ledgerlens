"""Tests of the triage parser.

What they guarantee: valid JSON becomes a `Triage` without calling the model; broken JSON triggers exactly
one repair; if the repair fails, a typed `TriageError` comes back instead of an exception. The repair model
is a `ScriptedChatModel`, which also works as a counter: if the parser tried to repair twice, the script
would run out and the test would fail with `ScriptExhausted`.
"""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from ledgerlens.chains.parsers import (
    TRIAGE_PARSER,
    TriageError,
    make_repairing_parser,
    triage_format_instructions,
)
from ledgerlens.chains.triage import load_triage_cases
from ledgerlens.offline import ScriptedChatModel, ScriptExhausted
from ledgerlens.schemas import Triage

CASE = load_triage_cases()[0]  # T01, the most complete case (five steps, two currencies)
VALID = json.dumps(CASE.expected.model_dump(mode="json"), ensure_ascii=False)
TRUNCATED = VALID[: len(VALID) // 2]  # JSON cut in half, like a model hitting its token limit
WRONG_INTENT = json.dumps({**json.loads(VALID), "intent": "refund"}, ensure_ascii=False)


def _parser(*repair_replies: str) -> tuple:
    model = ScriptedChatModel(script=list(repair_replies))
    return make_repairing_parser(model), model


def test_valid_json_parses_to_triage_without_calling_the_model() -> None:
    parser, model = _parser()
    result = parser.invoke(VALID)
    assert isinstance(result, Triage)
    assert result == CASE.expected
    assert model.calls == []


def test_valid_json_in_a_code_fence_parses() -> None:
    parser, model = _parser()
    assert parser.invoke(f"```json\n{VALID}\n```") == CASE.expected
    assert model.calls == []


def test_a_chat_message_is_parsed_like_its_text() -> None:
    parser, _ = _parser()
    assert parser.invoke(AIMessage(content=VALID)) == CASE.expected


def test_format_instructions_describe_the_schema_in_json() -> None:
    text = triage_format_instructions()
    assert text == TRIAGE_PARSER.get_format_instructions()
    for field in ("intent", "entities", "urgency", "plan", "needs_clarification"):
        assert field in text


def test_malformed_json_triggers_exactly_one_repair_call() -> None:
    parser, model = _parser(VALID)
    result = parser.invoke(TRUNCATED)
    assert result == CASE.expected
    assert len(model.calls) == 1
    assert model.remaining == 0


def test_repair_prompt_receives_the_bad_output_the_error_and_the_format() -> None:
    parser, model = _parser(VALID)
    parser.invoke("this is not JSON")
    (messages,) = model.calls
    text = "\n".join(str(m.content) for m in messages)
    assert "this is not JSON" in text
    assert "Invalid json output" in text
    assert "intent" in text  # the format instructions (the schema) went along


def test_schema_violation_is_repaired_too() -> None:
    parser, model = _parser(VALID)
    result = parser.invoke(WRONG_INTENT)
    assert result == CASE.expected
    assert len(model.calls) == 1
    text = "\n".join(str(m.content) for m in model.calls[0])
    assert "refund" in text and "validation error" in text


def test_repair_that_still_fails_returns_a_typed_error_after_a_single_retry() -> None:
    parser, model = _parser("still broken")
    result = parser.invoke(TRUNCATED)
    assert isinstance(result, TriageError)
    assert len(model.calls) == 1  # a second repair would raise ScriptExhausted
    assert result.repair_attempted is True
    assert result.raw_output == TRUNCATED
    assert result.repaired_output == "still broken"
    assert result.message


def test_error_code_tells_invalid_json_from_a_schema_violation() -> None:
    not_json, _ = _parser("this is not JSON either")
    assert not_json.invoke("this is not JSON").code == "invalid_json"
    bad_schema, _ = _parser(WRONG_INTENT)
    assert bad_schema.invoke(WRONG_INTENT).code == "schema_violation"


@pytest.mark.parametrize("garbage", ["", "   ", "null", "[]", "42", '"text"', "{}", "<html>"])
def test_garbage_never_raises(garbage: str) -> None:
    parser, model = _parser("also bad")
    result = parser.invoke(garbage)
    assert isinstance(result, TriageError)
    assert len(model.calls) == 1


def test_a_failed_repair_is_not_retried_across_calls() -> None:
    """Each input gets its own repair; the parser keeps no attempt state between inputs."""
    parser, model = _parser("bad", VALID)
    first = parser.invoke(TRUNCATED)
    second = parser.invoke(TRUNCATED)
    assert isinstance(first, TriageError)
    assert second == CASE.expected
    assert len(model.calls) == 2


def test_the_typed_error_serializes_to_json() -> None:
    parser, _ = _parser("bad")
    error = parser.invoke(TRUNCATED)
    data = json.loads(error.model_dump_json())
    assert set(data) == {"code", "message", "raw_output", "repair_attempted", "repaired_output"}
    assert data["code"] in {"invalid_json", "schema_violation"}


def test_a_provider_failure_is_not_swallowed_as_a_parse_error() -> None:
    """Only a reading failure becomes a `TriageError`; a broken model call still raises."""
    parser, _ = _parser()
    with pytest.raises(ScriptExhausted):
        parser.invoke(TRUNCATED)
