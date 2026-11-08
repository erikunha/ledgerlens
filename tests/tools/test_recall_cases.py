"""The `recall_cases` tool: what long-term memory returns to the agent.

What they guarantee, and why: the result comes in the common envelope, with the evidence id
`case:<case_id>` for the agent to cite; the merchant and customer filters work; a search with no result is a
success with an empty list, not an error; invalid input is refused before any search; and an unavailable
memory does not break the agent, it returns an empty list with a note, because memory is optional.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ledgerlens import embeddings as emb
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseIndexUnavailable, CaseMemory
from ledgerlens.tools.cases import build_recall_cases_tool

DIM = 64
EVIDENCE = re.compile(r"^case:CASE-[0-9]{4}$")


class WordCountModel:
    """Stands in for fastembed's `TextEmbedding`: each word adds 1 at a fixed position out of 64."""

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        vector = np.zeros(DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % DIM] += 1.0
        return vector

    def passage_embed(self, texts, **kwargs):
        return (self._vector(text) for text in texts)

    def query_embed(self, query, **kwargs):
        return (self._vector(text) for text in ([query] if isinstance(query, str) else query))


@pytest.fixture
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """Fake local embeddings, so the test does not download the real model."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def tool(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings):
    """The tool bound to a test memory, with the seeded case loaded."""
    return build_recall_cases_tool(memory=CaseMemory(tmp_path, embeddings=fake_embeddings))


@pytest.fixture
def empty_tool(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings):
    """The tool bound to a memory with no case at all (not even the seeded one)."""
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings, seed_path=tmp_path / "no-seed.jsonl")
    return build_recall_cases_tool(memory=memory)


class BrokenMemory:
    """Memory with no index: what happens when the index folder does not exist."""

    def recall(self, query: str, entity_ids: Any = None, k: int = 3, kind: str = "any") -> list[dict[str, Any]]:
        raise CaseIndexUnavailable("case index files missing; run the memory writer first")


def test_the_tool_returns_the_case_with_its_evidence_id(tool) -> None:
    result = tool.invoke({"query": "M-17 refund with FX", "merchant_id": "M-17"})

    assert result["ok"] is True
    assert set(result) == {"ok", "evidence_ids", "data"}
    assert result["evidence_ids"] == ["case:CASE-0001"]
    assert all(EVIDENCE.match(evidence_id) for evidence_id in result["evidence_ids"])

    first = result["data"]["results"][0]
    assert set(first) == {"case_id", "kind", "finding", "created_at", "confidence", "entities", "score"}
    assert first["case_id"] == "CASE-0001"
    assert first["kind"] == "semantic"
    assert first["confidence"] == "high"
    assert first["entities"]["merchant_ids"] == ["M-17"]
    assert isinstance(first["score"], float)


def test_the_merchant_filter_is_applied(tool) -> None:
    result = tool.invoke({"query": "refund with FX", "merchant_id": "M-09"})

    assert result["ok"] is True
    assert result["data"]["results"] == []


def test_a_search_without_hits_is_a_success(empty_tool) -> None:
    result = empty_tool.invoke({"query": "cloud software subscription"})

    assert result["ok"] is True
    assert result["data"]["results"] == []
    assert result["evidence_ids"] == []


def test_the_kind_filter_is_applied(tool) -> None:
    assert tool.invoke({"query": "M-17 FX", "kind": "episodic"})["data"]["results"] == []
    assert tool.invoke({"query": "M-17 FX", "kind": "semantic"})["data"]["results"]


def test_k_limits_the_number_of_results(tool) -> None:
    result = tool.invoke({"query": "M-17 FX", "k": 1})

    assert len(result["data"]["results"]) == 1


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"query": "ab"}, "INVALID_INPUT"),
        ({"query": "x" * 301}, "INVALID_INPUT"),
        ({"query": "refund", "k": 0}, "INVALID_INPUT"),
        ({"query": "refund", "k": 6}, "INVALID_INPUT"),
        ({"query": "refund", "kind": "magic"}, "INVALID_INPUT"),
        ({"query": "refund", "merchant_id": "X-99"}, "INVALID_ID"),
        ({"query": "refund", "customer_id": "C-1"}, "INVALID_ID"),
    ],
)
def test_the_input_is_validated_before_any_search(tool, arguments: dict[str, Any], code: str) -> None:
    assert code in str(tool.invoke(arguments))


def test_a_missing_index_returns_an_empty_result_with_a_note() -> None:
    result = build_recall_cases_tool(memory=BrokenMemory()).invoke({"query": "M-17 refund"})

    assert result["ok"] is True
    assert result["data"]["results"] == []
    assert "CASE_INDEX_UNAVAILABLE" in result["data"]["note"]


def test_the_tool_is_described_for_the_model() -> None:
    tool = build_recall_cases_tool(memory=BrokenMemory())

    assert tool.name == "recall_cases"
    assert "long-term case memory" in tool.description
    assert "not facts about today's data" in tool.description
    assert set(tool.args) == {"query", "merchant_id", "customer_id", "kind", "k"}
    assert tool.args["kind"]["default"] == "any"
    assert tool.args["k"]["default"] == 3
