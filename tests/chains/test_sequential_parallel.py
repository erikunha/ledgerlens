"""Tests of the sequential and parallel chains and of the memory configured in the chain.

What they guarantee, and why: "look up, then explain" runs in order (the explainer only sees what the lookup
found); the policy search and the FX lookup run at the same time (a two-thread barrier only opens if both are
running together) and the results merge; the token-limited summary memory summarizes what goes past the
limit; the modern equivalent `compact_history` does the same without the legacy class.
"""

from __future__ import annotations

import threading
import warnings

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ledgerlens.chains.sequential import (
    build_investigation_chain,
    build_lookup_then_explain,
    build_parallel_fetch,
    build_summary_buffer_memory,
    compact_history,
)
from ledgerlens.offline import ScriptedChatModel


def test_lookup_runs_before_explain_and_feeds_it() -> None:
    order: list[str] = []

    def lookup(question: str) -> dict:
        order.append("lookup")
        return {"transaction": "TX-2048", "status": "refunded"}

    model = ScriptedChatModel(script=["The refund for TX-2048 was made."])
    chain = build_lookup_then_explain(model, lookup)
    answer = chain.invoke({"question": "What is the status of TX-2048?"})

    order.append("done")
    assert order == ["lookup", "done"]
    assert answer == "The refund for TX-2048 was made."
    prompt_text = "\n".join(str(m.content) for m in model.calls[0])
    assert "refunded" in prompt_text, "the explain step sees the lookup result"
    assert "What is the status of TX-2048?" in prompt_text


def test_policy_and_fx_fetches_run_in_parallel_and_merge() -> None:
    # The barrier only opens when both threads reach it: if they ran one after the other, it would time out.
    barrier = threading.Barrier(2, timeout=5)
    threads: dict[str, int] = {}

    def policy(inputs: dict) -> str:
        threads["policy"] = threading.get_ident()
        barrier.wait()
        return "30-day window"

    def fx(inputs: dict) -> str:
        threads["fx"] = threading.get_ident()
        barrier.wait()
        return "EUR/BRL 5.6679"

    merged = build_parallel_fetch(policy, fx).invoke({"question": "q"})
    assert merged == {"question": "q", "policy": "30-day window", "fx": "EUR/BRL 5.6679"}
    assert threads["policy"] != threads["fx"]


def test_investigation_chain_is_lookup_then_parallel_then_explain() -> None:
    order: list[str] = []

    def lookup(question: str) -> dict:
        order.append("lookup")
        return {"transaction": "TX-2048"}

    def policy(inputs: dict) -> str:
        assert "lookup" in order, "the parallel step starts after the lookup"
        order.append("policy")
        return "rule X"

    def fx(inputs: dict) -> str:
        assert "lookup" in order
        order.append("fx")
        return "quote Y"

    model = ScriptedChatModel(script=["final answer"])
    chain = build_investigation_chain(model, lookup, policy, fx)
    assert chain.invoke({"question": "why lower?"}) == "final answer"
    assert order[0] == "lookup" and set(order[1:]) == {"policy", "fx"}
    prompt_text = "\n".join(str(m.content) for m in model.calls[0])
    assert "rule X" in prompt_text and "quote Y" in prompt_text and "TX-2048" in prompt_text


def test_investigation_chain_batch_keeps_order() -> None:
    model = ScriptedChatModel(script=["a", "b"])
    chain = build_investigation_chain(model, lambda q: {"q": q}, lambda i: "p", lambda i: "f")
    # ScriptedChatModel is not thread safe: max_concurrency=1.
    out = chain.batch([{"question": "one"}, {"question": "two"}], config={"max_concurrency": 1})
    assert out == ["a", "b"]


def test_summary_buffer_memory_summarizes_past_the_token_limit() -> None:
    model = ScriptedChatModel(script=["Summary: the customer asked about TX-2048."])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        memory = build_summary_buffer_memory(model, max_token_limit=20)
        memory.save_context({"input": "What is the status of TX-2048? " * 6}, {"output": "Refunded. " * 6})
        variables = memory.load_memory_variables({})
    history = variables["history"]
    assert "Summary: the customer asked about TX-2048." in str(history)
    assert model.remaining == 0


def test_summary_buffer_memory_keeps_short_history_verbatim() -> None:
    model = ScriptedChatModel(script=[])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        memory = build_summary_buffer_memory(model, max_token_limit=2000)
        memory.save_context({"input": "hi"}, {"output": "hello"})
        history = memory.load_memory_variables({})["history"]
    assert "hi" in str(history) and "hello" in str(history)
    assert model.calls == []


def test_compact_history_summarizes_old_messages_and_keeps_the_last() -> None:
    messages = [
        HumanMessage("What is the status of TX-2048?"),
        AIMessage("Refunded."),
        HumanMessage("And the FX rate?"),
        AIMessage("5.6679."),
    ]
    model = ScriptedChatModel(script=["Summary: TX-2048 refunded."])
    out = compact_history(messages, model, keep_last=2)
    assert isinstance(out[0], SystemMessage)
    assert "TX-2048 refunded" in str(out[0].content)
    assert out[1:] == messages[-2:]
    prompt_text = "\n".join(str(m.content) for m in model.calls[0])
    assert "What is the status of TX-2048?" in prompt_text and "5.6679" not in prompt_text


def test_compact_history_leaves_short_history_alone_without_calling_the_model() -> None:
    messages = [HumanMessage("hi"), AIMessage("hello")]
    model = ScriptedChatModel(script=[])
    assert compact_history(messages, model, keep_last=4) == messages
    assert model.calls == []
