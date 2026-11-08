"""Long-term memory: writing the verified case, the FAISS index, the entity filter and the expired fact.

What they guarantee, and why: a case only enters memory when every verdict of the investigation was
supported, because an unverified conclusion becomes a lie for the next session; the entity filter applies
before the cut to `k` results, so a case of another merchant does not "fit" in the answer; the seeded case
`CASE-0001` shows up in a new session, which is scenario S12; and a semantic fact past its validity is not
returned.
"""

from __future__ import annotations

import json
import re
import zlib
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest

from ledgerlens import embeddings as emb
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.schemas import (
    Claim,
    Coherence,
    Entities,
    Evidence,
    InvestigationResult,
    PlanStep,
    Triage,
    Verdict,
)

DIM = 64


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


def _result(
    *,
    label: str = "supported",
    answer: str = "TX-2048 was refunded in BRL, with a difference of 17.48.",
    merchant_ids: list[str] | None = None,
    session_id: str = "s1",
) -> InvestigationResult:
    entities = Entities(merchant_ids=merchant_ids or ["M-17"])
    return InvestigationResult(
        session_id=session_id,
        question="Why did the refund come in lower?",
        triage=Triage(
            intent="refund_discrepancy",
            entities=entities,
            urgency="normal",
            plan=[PlanStep(id="S1", goal="check the refund")],
        ),
        answer=answer,
        claims=[Claim(id="CL1", text="TX-2048 was refunded in BRL.", kind="fact", evidence_ids=["sql:1"])],
        evidence=[
            Evidence(
                id="sql:1",
                source_type="sql",
                tool="query_ledger",
                content="TX-2048 refunded in BRL 549.31",
                ref="TX-2048",
                retrieved_at=datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
            )
        ],
        verdicts=[Verdict(claim_id="CL1", label=label, method="rule", evidence_ids=["sql:1"])],
        coherence=Coherence(passed=True, issues=[]),
        recommended_action="explain_to_customer",
        requires_human_review=False,
    )


def test_a_case_is_written_only_when_every_verdict_is_supported(
    tmp_path: Path, fake_embeddings: FastEmbedEmbeddings
) -> None:
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)

    refused = memory.write_case(_result(label="contradicted"))
    assert refused["written"] is False
    assert refused["reason"] == "verdict_not_supported"
    assert not (tmp_path / "cases.jsonl").exists()

    written = memory.write_case(_result())
    assert written["written"] is True
    assert written["case_id"] == "CASE-0002"
    records = {record["case_id"] for record in memory.records()}
    assert records == {"CASE-0001", "CASE-0002"}


def test_the_case_record_carries_the_entities_and_the_evidence(
    tmp_path: Path, fake_embeddings: FastEmbedEmbeddings
) -> None:
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)

    memory.write_case(_result(merchant_ids=["M-05"]))

    record = next(item for item in memory.records() if item["case_id"] == "CASE-0002")
    assert record["kind"] == "episodic"
    assert record["session_id"] == "s1"
    assert record["entities"]["merchant_ids"] == ["M-05"]
    assert record["evidence_refs"] == ["sql:1"]
    assert record["confidence"] == "high"
    assert record["valid_until"] is None
    assert record["finding"].startswith("TX-2048 was refunded in BRL")


def test_the_seed_case_is_recalled_in_a_new_session(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings) -> None:
    """S12: a new session, with no history, asks about M-17 and gets CASE-0001."""
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)

    hits = memory.recall("M-17 refund with FX", entity_ids={"merchant_ids": ["M-17"]})

    assert [hit["case_id"] for hit in hits] == ["CASE-0001"]
    assert hits[0]["kind"] == "semantic"
    assert hits[0]["confidence"] == "high"
    assert hits[0]["entities"]["merchant_ids"] == ["M-17"]
    assert "M-17" in hits[0]["finding"]
    assert isinstance(hits[0]["score"], float)


def test_the_entity_filter_applies_before_the_ranking(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings) -> None:
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)
    memory.write_case(_result(answer="M-05 refund with FX of 17.48 BRL at M-05.", merchant_ids=["M-05"]))

    hits = memory.recall("M-05 refund with FX", entity_ids={"merchant_ids": ["M-17"]}, k=1)

    assert [hit["case_id"] for hit in hits] == ["CASE-0001"]


def test_expired_facts_are_skipped(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings) -> None:
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)
    memory.write_case(
        _result(answer="M-17 refund with FX of 17.48 BRL."), kind="semantic", valid_until=date(2020, 1, 1)
    )

    hits = memory.recall("M-17 refund with FX", entity_ids={"merchant_ids": ["M-17"]})

    assert [hit["case_id"] for hit in hits] == ["CASE-0001"]


def test_the_seed_file_is_the_source_of_the_first_case(tmp_path: Path, fake_embeddings: FastEmbedEmbeddings) -> None:
    memory = CaseMemory(tmp_path, embeddings=fake_embeddings)

    records = memory.records()

    assert [record["case_id"] for record in records] == ["CASE-0001"]
    assert records[0]["kind"] == "semantic"
    assert json.loads(json.dumps(records[0]))["case_id"] == "CASE-0001"
