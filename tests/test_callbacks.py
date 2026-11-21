"""Tests of the JSON lines callback handler.

What they guarantee, and why: each LLM, tool and chain event becomes a JSON line with ids and duration; API
keys are removed before writing; the full text of a prompt is never written, only sizes and ids; the handler
accepts an open file or a path.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from ledgerlens.observability.callbacks import JsonlCallbackHandler, redact

KEYS = ("sk-" + "abcdefghij1234567890", "lsv" + "2_pt_0123456789abcdef", "Bearer abc.def-123")


def _lines(sink: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in sink.getvalue().splitlines()]


@tool
def echo(text: str) -> str:
    """Devolve o texto recebido."""
    return text


def test_one_json_line_per_llm_tool_and_chain_event() -> None:
    sink = io.StringIO()
    handler = JsonlCallbackHandler(sink)
    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | FakeListChatModel(responses=["ok"])
    chain.invoke({"q": "oi"}, config={"callbacks": [handler]})
    echo.invoke({"text": "TX-2048"}, config={"callbacks": [handler]})

    events = [(row["event"]) for row in _lines(sink)]
    for expected in ("chain_start", "chain_end", "llm_start", "llm_end", "tool_start", "tool_end"):
        assert expected in events, events


def test_every_line_has_ids_and_end_events_have_a_duration() -> None:
    sink = io.StringIO()
    handler = JsonlCallbackHandler(sink)
    echo.invoke({"text": "x"}, config={"callbacks": [handler]})
    rows = _lines(sink)
    assert [r["event"] for r in rows] == ["tool_start", "tool_end"]
    start, end = rows
    assert start["run_id"] == end["run_id"]
    assert start["name"] == "echo"
    assert re.match(r"\d{4}-\d{2}-\d{2}T", start["ts"])
    assert end["status"] == "ok"
    assert end["duration_ms"] >= 0
    assert "duration_ms" not in start


def test_parent_run_id_links_children_to_the_chain() -> None:
    sink = io.StringIO()
    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | FakeListChatModel(responses=["ok"])
    chain.invoke({"q": "oi"}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    rows = _lines(sink)
    top = next(r for r in rows if r["event"] == "chain_start" and r["parent_run_id"] is None)
    llm = next(r for r in rows if r["event"] == "llm_start")
    assert llm["parent_run_id"] is not None
    assert top["run_id"] != llm["run_id"]


def test_errors_are_logged_with_status_error_and_the_exception_type() -> None:
    sink = io.StringIO()

    @tool
    def boom(text: str) -> str:
        """Sempre falha."""
        raise ValueError("falhou")

    with pytest.raises(ValueError):
        boom.invoke({"text": "x"}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    end = _lines(sink)[-1]
    assert end["event"] == "tool_error"
    assert end["status"] == "error"
    assert end["error_type"] == "ValueError"
    assert end["duration_ms"] >= 0


@pytest.mark.parametrize("key", KEYS)
def test_redact_removes_keys(key: str) -> None:
    out = redact(f"before {key} after")
    assert key not in out
    assert "[REDACTED]" in out
    assert out.startswith("before ") and out.endswith(" after")


# Synthetic bodies only: each one is the fake word repeated up to the length floor of its family.
OTHER_KEY_SHAPES = (
    "ghp_" + "fakefakefakefakefake1234",
    "AKIA" + "FAKEFAKEFAKE1234",
    "AIza" + "FakeFakeFakeFakeFake12345",
)


@pytest.mark.parametrize("key", OTHER_KEY_SHAPES)
def test_redact_removes_github_aws_and_google_key_shapes(key: str) -> None:
    out = redact(f"deploy failed for tenant acme with token {key} in the header")
    assert key not in out
    assert "[REDACTED]" in out
    assert out.startswith("deploy failed for tenant acme with token ") and out.endswith(" in the header")


def test_redact_leaves_short_lookalikes_that_are_not_keys_alone() -> None:
    # Below the length floor of each family, so an ordinary word is never mangled.
    for lookalike in ("AKIA12345678", "ghp_fakefake", "AIzaFakeFake12"):
        assert redact(f"id {lookalike} is not a key") == f"id {lookalike} is not a key"


def test_keys_in_tool_input_and_errors_never_reach_the_sink() -> None:
    sink = io.StringIO()

    @tool
    def leak(text: str) -> str:
        """Falha repetindo o texto."""
        raise RuntimeError(f"erro com {text}")

    secret_text = " ".join(KEYS)
    with pytest.raises(RuntimeError):
        leak.invoke({"text": secret_text}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    raw = sink.getvalue()
    for key in KEYS:
        assert key not in raw
    assert "[REDACTED]" in raw


def test_full_prompt_text_is_never_logged_only_lengths() -> None:
    sink = io.StringIO()
    private = "Cliente Maria Souza CPF 123.456.789-00 reclama da TX-2048"
    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | FakeListChatModel(responses=["resposta longa"])
    chain.invoke({"q": private}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    raw = sink.getvalue()
    assert "Maria" not in raw and "123.456.789-00" not in raw and "resposta longa" not in raw
    llm = next(r for r in _lines(sink) if r["event"] == "llm_start")
    assert llm["prompt_chars"] == len(private)
    assert llm["message_count"] == 1
    llm_end = next(r for r in _lines(sink) if r["event"] == "llm_end")
    assert llm_end["output_chars"] == len("resposta longa")


def test_chain_events_log_input_keys_not_values() -> None:
    sink = io.StringIO()
    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | FakeListChatModel(responses=["ok"])
    chain.invoke({"q": "segredo do cliente"}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    assert "segredo do cliente" not in sink.getvalue()
    first = _lines(sink)[0]
    assert first["input_keys"] == ["q"]


def test_tool_input_is_truncated() -> None:
    sink = io.StringIO()
    echo.invoke({"text": "a" * 5000}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    start = _lines(sink)[0]
    assert len(start["input"]) < 600
    assert start["input_chars"] >= 5000


def test_path_sink_appends_json_lines(tmp_path: Path) -> None:
    target = tmp_path / "logs" / "run.jsonl"
    handler = JsonlCallbackHandler(target)
    echo.invoke({"text": "x"}, config={"callbacks": [handler]})
    echo.invoke({"text": "y"}, config={"callbacks": [handler]})
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["tool_start", "tool_end"] * 2


def test_non_ascii_text_is_written_as_utf8() -> None:
    sink = io.StringIO()
    echo.invoke({"text": "duplicate charge of \u20ac10.00"}, config={"callbacks": [JsonlCallbackHandler(sink)]})
    assert "\u20ac10.00" in sink.getvalue()
