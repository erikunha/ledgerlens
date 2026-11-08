"""Retrieval agent: answers from the prebuilt FAISS index and never rebuilds it.

The agent model is a `ScriptedChatModel` (one tool call, then the answer) and the index is the one built with
the fake vector model, so nothing downloads a model or uses the network. What the tests guarantee: (a) the
agent's only tool is `search_policies`; (b) the final answer cites the id of the chunk the tool returned;
(c) the index files stay byte for byte the same before and after, and no build function is called.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from ledgerlens import embeddings as emb
from ledgerlens import retrieval
from ledgerlens.agents.retrieval_agent import build_retrieval_agent, build_retrieval_tool, retrieve
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from tests.tools import test_policies as base


@pytest.fixture
def built_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A full policy index with the fake vector model from `test_policies.py`."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    root = tmp_path / "index"
    embeddings = FastEmbedEmbeddings()
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


QUESTION = "refund window days after the payment is captured"
GOLD = "refund-policy#refund-window"


def digests(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def scripted() -> ScriptedChatModel:
    return ScriptedChatModel(
        script=[
            tool_call_message("search_policies", {"query": QUESTION, "k": 3, "transform": "none"}),
            text_message(f"The deadline is in the policy (policy:{GOLD})."),
        ]
    )


def test_the_agent_has_one_tool_and_it_is_the_policy_search(built_index: Path) -> None:
    tool = build_retrieval_tool(index_root=built_index)
    assert tool.name == "search_policies"


def test_the_agent_answers_from_the_index_and_cites_the_chunk(built_index: Path) -> None:
    agent = build_retrieval_agent(scripted(), index_root=built_index)
    state = agent.invoke({"messages": [HumanMessage(content=QUESTION)]})
    tool_messages = [m for m in state["messages"] if m.type == "tool"]
    assert len(tool_messages) == 1 and GOLD in tool_messages[0].content
    assert f"policy:{GOLD}" in state["messages"][-1].content


def test_retrieve_returns_the_answer_and_the_evidence_ids(built_index: Path) -> None:
    answer, evidence = retrieve(QUESTION, scripted(), index_root=built_index)
    assert f"policy:{GOLD}" in answer and f"policy:{GOLD}" in evidence


def test_the_index_files_are_byte_identical_after_a_run(built_index: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = built_index / "policies_fastembed"
    before = digests(folder)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the retrieval agent must not build the index")

    monkeypatch.setattr(retrieval, "build_policy_index", forbidden)
    for _ in range(2):
        retrieve(QUESTION, scripted(), index_root=built_index)
    assert digests(folder) == before
    assert {p.name for p in folder.iterdir()} == set(before)


def test_without_an_index_the_agent_reports_it_and_builds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    root = tmp_path / "empty"
    answer, evidence = retrieve(QUESTION, scripted(), index_root=root)
    assert evidence == [] and not root.exists()
