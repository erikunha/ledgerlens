"""Query transforms of `search_policies`: `rewrite`, `multi_query`, `hyde` and the fallback to `none`.

The fast tests use the fake vector model from `test_policies.py` and a chat model that answers from a table
(`LookupChatModel`), so they run offline in milliseconds. The test marked `slow` uses the real vector model
and the committed index in `data/index/`, and measures the recall@3 of the 12 questions before and after each
transform (the number shows with `-s`).

A note on the measurement: offline there is no real language model. The rewrites, variations and
hypothetical passages below were written by hand, once, the way a reasonable rewriter would write them, and
`LookupChatModel` returns them per question. A real model can do better or worse; what the test proves is the
mechanism (the transformed query reaches the index, the merge and the fallback work) and whether, with
plausible rewrites, the recall of the hard questions goes up.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ledgerlens import embeddings as emb
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.retrieval import (
    build_policy_index,
    index_dir_for,
    load_policy_documents,
    load_policy_index,
    search_policy_index,
)
from ledgerlens.tools import policies
from ledgerlens.tools.policies import (
    HYDE_PROMPT,
    MULTI_QUERY_PROMPT,
    REWRITE_PROMPT,
    build_search_policies_tool,
)
from tests.tools import test_policies as base

COMMITTED, QUESTIONS = base.COMMITTED, base.QUESTIONS


@pytest.fixture
def built_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A full policy index with the fake vector model from `test_policies.py`."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    root = tmp_path / "index"
    embeddings = FastEmbedEmbeddings()
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


PROMPTS = {"rewrite": REWRITE_PROMPT, "multi_query": MULTI_QUERY_PROMPT, "hyde": HYDE_PROMPT}

# One entry per hard question (PQ-07 to PQ-12). Written once, with no tuning after measuring.
PREPARED: dict[str, dict[str, str]] = {
    "rewrite": {
        "PQ-07": "Can I request a refund of the amount paid after 30 days?",
        "PQ-08": "Refund amount difference in another currency because of the exchange rate on the refund date",
        "PQ-09": "Settlement and payout timing to the merchant in business days when there is a holiday",
        "PQ-10": "Deadline to respond to a chargeback opened by the issuing bank",
        "PQ-11": "Duplicate charge: full refund of the later charge",
        "PQ-12": "Processing fee on the gross volume of each sale",
    },
    "multi_query": {
        "PQ-07": "\n".join(
            (
                "Maximum time to request a refund",
                "Refund after 30 days from capture",
                "Getting the amount paid back after the deadline",
            )
        ),
        "PQ-08": "\n".join(
            (
                "Refund in another currency with a different exchange rate",
                "Exchange rate applied on the refund date",
                "Smaller amount returned because of exchange rate movement",
            )
        ),
        "PQ-09": "\n".join(
            (
                "Settlement timing in business days",
                "Payout to the merchant when the day is a holiday",
                "Settlement calendar",
            )
        ),
        "PQ-10": "\n".join(
            (
                "Response deadline for a chargeback",
                "Documents requested by the issuing bank in a dispute",
                "Defending a disputed payment",
            )
        ),
        "PQ-11": "\n".join(
            (
                "Duplicate charge and full refund",
                "Two identical charges on the same card",
                "Duplicate detection rule",
            )
        ),
        "PQ-12": "\n".join(
            (
                "Processing fee per sale",
                "Percentage charged on the gross volume",
                "How much the platform keeps from each transaction",
            )
        ),
    },
    "hyde": {
        "PQ-07": (
            "Refunds can be requested within 30 days of the payment capture. After that the request needs a review."
        ),
        "PQ-08": (
            "For a refund in another currency, the exchange rate is the one on the refund "
            "date, not the purchase date, so the amount returned can differ."
        ),
        "PQ-09": (
            "Settlement happens on business days. "
            "If the payout day is a holiday, the payout to the merchant moves to the next business day."
        ),
        "PQ-10": (
            "The issuing bank opens a chargeback and asks for documents. "
            "The merchant must respond within the dispute response deadline."
        ),
        "PQ-11": ("For a duplicate charge, the later charge is refunded in full, at no cost to the customer."),
        "PQ-12": ("The processing fee is a percentage of the gross volume of each sale, kept by the platform."),
    },
}


class LookupChatModel(BaseChatModel):
    """A chat model that answers from a table `(system instruction, question) -> text`."""

    answers: dict[tuple[str, str], str]
    fail: bool = False

    @property
    def _llm_type(self) -> str:
        return "ledgerlens-lookup"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        if self.fail:
            raise ConnectionError("model offline")
        system, question = messages[0].content, messages[-1].content
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.answers.get((system, question), "")))]
        )


def questions() -> list[dict[str, Any]]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines()]


def lookup_model(*, fail: bool = False) -> LookupChatModel:
    by_id = {q["id"]: q["question"] for q in questions()}
    answers = {(PROMPTS[kind], by_id[qid]): text for kind, table in PREPARED.items() for qid, text in table.items()}
    return LookupChatModel(answers=answers, fail=fail)


def make_tool(index_root: Path, llm: BaseChatModel | None = None):
    return build_search_policies_tool(index_root=index_root, llm=llm or lookup_model())


HARD = {q["id"]: q for q in questions() if q["difficulty"] == "hard"}
PQ12 = HARD["PQ-12"]["question"]


# --- mechanism (index with fake vectors) ------------------------------------------------------


def test_rewrite_searches_with_the_rewritten_question(built_index: Path) -> None:
    data = make_tool(built_index).invoke({"query": PQ12, "transform": "rewrite"})["data"]
    # the original question goes along with the rewrite (in that order), and results merge by best score
    assert data["transform"] == "rewrite" and data["query_used"] == [PQ12, PREPARED["rewrite"]["PQ-12"]]
    assert len(data["results"]) == 4


def test_a_rewrite_that_drifts_does_not_lose_what_the_original_question_finds(built_index: Path) -> None:
    # A real defect (gpt-4.1-mini, recall@3 on the 12 questions): the rewriter swapped the question's words for a
    # formal paragraph and lost chunks the original question found (PQ-01, PQ-03, PQ-05): 0.50 fell to 0.39.
    easy = [q for q in questions() if q["difficulty"] == "easy"]
    drifted = "zzz qqq with no word in common with the handbook"
    llm = LookupChatModel(answers={(REWRITE_PROMPT, q["question"]): drifted for q in easy})
    found_by_original = [q for q in easy if _finds(make_tool(built_index, llm), q, "none")]
    assert found_by_original, "the fixture needs easy questions the plain search answers"
    for q in found_by_original:
        assert _finds(make_tool(built_index, llm), q, "rewrite"), q["id"]


def _finds(tool: Any, question: dict[str, Any], transform: str) -> bool:
    data = tool.invoke({"query": question["question"], "k": 3, "transform": transform})["data"]
    return bool({r["chunk_id"] for r in data["results"]} & set(question["gold_chunk_ids"]))


def test_hyde_searches_with_the_hypothetical_passage(built_index: Path) -> None:
    data = make_tool(built_index).invoke({"query": PQ12, "transform": "hyde"})["data"]
    assert data["transform"] == "hyde" and data["query_used"] == [PREPARED["hyde"]["PQ-12"]]
    assert len(data["results"]) == 4


def test_multi_query_sends_every_variation_and_merges_by_best_score(built_index: Path) -> None:
    result = make_tool(built_index).invoke({"query": PQ12, "transform": "multi_query", "k": 4})
    data = result["data"]
    assert data["transform"] == "multi_query" and len(data["query_used"]) == 3
    ids = [r["chunk_id"] for r in data["results"]]
    assert len(ids) == len(set(ids)) <= 4, "a chunk found by two variations appears once"
    scores = [r["score"] for r in data["results"]]
    assert scores == sorted(scores)
    assert result["evidence_ids"] == [f"policy:{i}" for i in ids]
    first_variation = make_tool(built_index).invoke({"query": data["query_used"][0], "transform": "none", "k": 4})
    assert min(scores) <= first_variation["data"]["results"][0]["score"]


def test_the_merge_keeps_the_best_score_of_each_chunk() -> None:
    hit = lambda cid, score: {"chunk_id": cid, "score": score}  # noqa: E731
    merged = policies._merge([[hit("a", 0.5), hit("b", 0.9)], [hit("b", 0.2), hit("c", 0.7)]], k=2)
    assert merged == [hit("b", 0.2), hit("a", 0.5)]


@pytest.mark.parametrize("transform", ["rewrite", "multi_query", "hyde"])
def test_a_failing_model_falls_back_to_none(
    built_index: Path, transform: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=policies.log.name):
        result = make_tool(built_index, lookup_model(fail=True)).invoke({"query": PQ12, "transform": transform})
    assert result["ok"] is True
    assert result["data"]["transform"] == "none" and result["data"]["query_used"] == [PQ12]
    assert any("model offline" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("transform", ["rewrite", "multi_query", "hyde"])
def test_an_empty_answer_falls_back_to_none(built_index: Path, transform: str) -> None:
    unknown = "A question the table does not know, about payouts"
    data = make_tool(built_index).invoke({"query": unknown, "transform": transform})["data"]
    assert data["transform"] == "none" and data["query_used"] == [unknown]


def test_none_never_calls_the_model(built_index: Path) -> None:
    class Forbidden(LookupChatModel):
        def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
            raise AssertionError("transform none must not call the model")

    data = make_tool(built_index, Forbidden(answers={})).invoke({"query": PQ12, "transform": "none"})["data"]
    assert data["transform"] == "none"


def test_every_search_logs_the_returned_chunks(built_index: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=policies.log.name):
        data = make_tool(built_index).invoke({"query": PQ12, "transform": "none", "k": 3})["data"]
    line = next(r.getMessage() for r in caplog.records if "returned=" in r.getMessage())
    assert "transform=none" in line
    for result in data["results"]:
        assert result["chunk_id"] in line


# --- recall with the real vector model --------------------------------------------------------

needs_committed_index = pytest.mark.skipif(not COMMITTED.is_dir(), reason="data/index/ not built yet")


@needs_committed_index
@pytest.mark.slow
def test_recall_at_3_on_the_hard_set_is_higher_after_transformation(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    store = load_policy_index(COMMITTED, FastEmbedEmbeddings())
    root = COMMITTED.parent
    lookup = lookup_model()
    hits: dict[str, dict[str, bool]] = {name: {} for name in ("none", "rewrite", "multi_query", "hyde")}
    returned: dict[str, list[str]] = {}
    with caplog.at_level(logging.INFO, logger=policies.log.name):
        for transform in hits:
            tool = build_search_policies_tool(index_root=root, llm=lookup)
            for question in questions():
                found = tool.invoke({"query": question["question"], "k": 3, "transform": transform})["data"]
                ids = [r["chunk_id"] for r in found["results"]]
                hits[transform][question["id"]] = bool(set(ids) & set(question["gold_chunk_ids"]))
                if transform == "none":
                    returned[question["id"]] = ids
    assert hits["none"] == {q["id"]: bool(set(returned[q["id"]]) & set(q["gold_chunk_ids"])) for q in questions()}
    # the index, searched directly, gives the same as the tool with `none`
    direct = {
        q["id"]: bool({r["chunk_id"] for r in search_policy_index(store, q["question"], 3)} & set(q["gold_chunk_ids"]))
        for q in questions()
    }
    assert direct == hits["none"]

    hard_ids = list(HARD)
    with capsys.disabled():
        print("\nrecall@3 per question (Y = found the right chunk):")
        print("id     " + "  ".join(f"{name:<11}" for name in hits))
        for q in questions():
            print(f"{q['id']}  " + "  ".join(f"{'Y' if hits[name][q['id']] else 'n':<11}" for name in hits))
        for name, table in hits.items():
            hard = sum(table[i] for i in hard_ids)
            print(f"{name:<12} total {sum(table.values())}/12 = {sum(table.values()) / 12:.2f}, hard {hard}/6")
    baseline_hard = sum(hits["none"][i] for i in hard_ids)
    improved = {name: sum(hits[name][i] for i in hard_ids) for name in ("rewrite", "multi_query", "hyde")}
    assert max(improved.values()) > baseline_hard, improved

    # a baseline miss stays in the log with the chunks it returned, none of them the right one
    missed = next(qid for qid in hard_ids if not hits["none"][qid])
    gold = set(HARD[missed]["gold_chunk_ids"])
    lines = [
        r.getMessage() for r in caplog.records if "transform=none" in r.getMessage() and "returned=" in r.getMessage()
    ]
    logged = next(line for line in lines if HARD[missed]["question"] in line)
    assert all(chunk not in logged for chunk in gold)
    assert all(chunk in logged for chunk in returned[missed])
