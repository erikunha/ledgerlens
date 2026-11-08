"""The common tool result envelope (`docs/contracts/tools.md`): success, error and invalid input."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ledgerlens.tools.envelope import error, invalid_input, ok


def test_ok_has_exactly_the_three_keys() -> None:
    assert ok(["sql:1"], {"rows": []}) == {"ok": True, "evidence_ids": ["sql:1"], "data": {"rows": []}}


@pytest.mark.parametrize("bad", ["sql1", "other:1", "sql:", ""])
def test_ok_refuses_an_evidence_id_outside_the_scheme(bad: str) -> None:
    with pytest.raises(ValueError, match="evidence id"):
        ok([bad], {})


def test_error_has_code_message_and_retryable() -> None:
    assert error("SQL_TIMEOUT", "slow", False) == {
        "ok": False,
        "error": {"code": "SQL_TIMEOUT", "message": "slow", "retryable": False},
    }


def test_invalid_input_turns_a_validation_error_into_the_error_envelope_as_text() -> None:
    class Model(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str = Field(min_length=3)

    with pytest.raises(ValidationError) as info:
        Model(name="a")
    payload = json.loads(invalid_input(info.value))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT" and payload["error"]["retryable"] is True
    assert "name" in payload["error"]["message"]


def test_invalid_input_accepts_any_exception() -> None:
    assert json.loads(invalid_input(RuntimeError("boom")))["error"]["message"] == "boom"
