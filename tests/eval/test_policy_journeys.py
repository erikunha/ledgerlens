"""Exercise the journey report against the real investigator with scripted model replies."""

import json
import sys
from datetime import date

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.agents import integrator
from ledgerlens.agents.budget import shipped_turn_budget
from ledgerlens.agents.integrator import build_integrator
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.run_context import RunBudget
from ledgerlens.verify.escalation import _previous_business_day
from scripts import report_policy_journeys
from scripts.report_policy_journeys import CHARGEBACK, PET_INSURANCE, report_journey
from tests.agents.test_integrator import triage_script
from tests.tools.test_policies import WordCountModel

CUTOFF = "policy:chargeback-handling#response-deadline"
ORPHAN = "policy:chargeback-handling#fake-passage"
SEARCH = tool_call_message("search_policies", {"query": "chargeback evidence deadline", "k": 1, "transform": "none"})


@pytest.fixture
def investigator(tmp_path, monkeypatch):
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)
    embeddings = FastEmbedEmbeddings()
    index_root = tmp_path / "index"
    cutoff = next(doc for doc in load_policy_documents() if f"policy:{doc.metadata['chunk_id']}" == CUTOFF)
    build_policy_index([cutoff], embeddings, index_dir_for(index_root, embeddings))

    def build(script, *, with_index=True, triage=None, model=None):
        return build_integrator(
            model or ScriptedChatModel(script=script),
            triage_model=triage or ScriptedChatModel(script=[]),
            case_memory=CaseMemory(tmp_path / "memory", embeddings=embeddings),
            embeddings=embeddings,
            db_path=tmp_path / "unused.db",
            index_root=index_root if with_index else tmp_path / "missing-index",
        )

    return build, cutoff.page_content


def test_preserves_answer_search_and_exact_cited_passage(investigator):
    build, passage = investigator
    answer = (
        f"Acme requires evidence one business day before the dispute response deadline [{CUTOFF}, {ORPHAN}]. "
        "[policy:another#passage, ordinary text]"
    )
    report = report_journey(build([SEARCH, answer]), CHARGEBACK)
    assert report["status"] == "answered"
    assert report["answer"] == answer
    assert report["claims"]
    assert {v["claim_id"] for v in report["verdicts"]} == {c["id"] for c in report["claims"]}
    assert isinstance(report["review_reasons"], list)
    assert report["judgment"] == "pending"
    assert report["search_observed"] is True
    assert report["searches"][0]["candidate_ids"] == [CUTOFF]
    assert report["searches"][0]["queries_used"] == ["chargeback evidence deadline"]
    assert report["searches"][0]["transform_used"] == "none"
    assert report["policy_citations"] == [{"id": CUTOFF, "passage": passage}, {"id": ORPHAN, "passage": None}]


def test_final_answer_without_search_is_still_observed(investigator):
    build, _ = investigator
    answer = "I can't establish pet insurance coverage from the payment policies."
    report = report_journey(build([answer]), PET_INSURANCE)
    assert report["status"] == "answered"
    assert report["answer"] == answer
    assert report["search_observed"] is False
    assert report["searches"] == []
    assert report["policy_citations"] == []


def test_error_preserves_prior_search_without_fabricating_final_answer(investigator):
    build, _ = investigator
    report = report_journey(build([SEARCH]), CHARGEBACK)
    assert report["status"] == "error"
    assert report["error"].startswith("ScriptExhausted:")
    assert report["answer"] is None
    assert report["judgment"] is None
    assert report["policy_citations"] is None
    assert report["search_observed"] is True
    assert report["searches"][0]["candidate_ids"] == [CUTOFF]


def test_error_without_search_has_unknown_search_status(investigator):
    build, _ = investigator
    report = report_journey(build([]), CHARGEBACK)
    assert report["status"] == "error"
    assert report["search_observed"] is None


def test_observed_search_error_leaves_candidate_ids_unknown(investigator):
    build, _ = investigator
    report = report_journey(build([SEARCH, "The policy index is unavailable."], with_index=False), CHARGEBACK)
    assert report["search_observed"] is True
    assert report["judgment"] is None
    assert report["searches"][0]["error"] == "INDEX_UNAVAILABLE"
    assert report["searches"][0]["candidate_ids"] is None


def test_incomplete_followup_keeps_partial_answer_and_names_the_limit(investigator, monkeypatch):
    build, _ = investigator
    monkeypatch.setattr(integrator, "turn_budget_for", lambda _: shipped_turn_budget(RunBudget(max_model_calls=2)))
    agent = build(["I need policy evidence."], triage=triage_script(("search the handbook", "search_policies")))
    report = report_journey(agent, CHARGEBACK)
    assert report["status"] == "partial"
    assert report["answer"] == "I need policy evidence."
    assert report["judgment"] is None
    assert report["usage"]["cut_by"] == "max_model_calls"
    assert any("model calls" in reason for reason in report["missing_information"])


def test_cli_uses_openai_for_a_single_case(monkeypatch, capsys):
    async def run_journeys(root, case_ids, *, configuration):
        assert configuration["model"] == "gpt-4.1"
        assert case_ids == ["pet-insurance"]
        return [{"case_id": "pet-insurance"}]

    monkeypatch.setattr(report_policy_journeys, "run_journeys", run_journeys)
    monkeypatch.setattr(sys, "argv", ["report_policy_journeys", "--case", "pet-insurance"])
    report_policy_journeys.main()
    assert json.loads(capsys.readouterr().out)["model"] == "gpt-4.1"


def test_journey_clients_share_direct_openai_transport(tmp_path, monkeypatch):
    import asyncio
    import os

    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("LEDGERLENS_ENV_FILE", str(tmp_path / "unused.env"))
    clients = {}

    def chat(settings, **options):
        clients.update(options)

    def embeddings(**options):
        assert options["base_url"] == clients["base_url"] == report_policy_journeys.OPENAI_URL
        for key in ("http_client", "http_async_client"):
            assert options[key] is clients[key]
            assert options[key].trust_env is False
        assert "OPENAI_BASE_URL" not in os.environ
        raise RuntimeError("stop before inference")

    monkeypatch.setattr(report_policy_journeys, "get_chat_model", chat)
    monkeypatch.setattr(report_policy_journeys, "OpenAIEmbeddings", embeddings)
    with pytest.raises(RuntimeError, match="stop before inference"):
        asyncio.run(report_policy_journeys.run_journeys(tmp_path, []))
    assert os.environ["OPENAI_BASE_URL"] == "http://localhost:1"


def test_investigator_receives_policy_evidence_instructions(investigator):
    build, _ = investigator
    model = ScriptedChatModel(script=["I could not establish the coverage."])
    report_journey(build([], model=model), PET_INSURANCE)
    messages = model.calls[0]
    assert any(msg.type == "system" and integrator.POLICY_EVIDENCE_RULE.strip() in msg.content for msg in messages)


def test_successful_search_before_failed_retry_stays_reviewable(investigator, monkeypatch):
    from ledgerlens.tools import policies

    build, passage = investigator
    search = policies.search_policy_index
    calls = []

    def fail_on_retry(*args):
        if calls:
            raise RuntimeError("index read failed")
        calls.append(True)
        return search(*args)

    monkeypatch.setattr(policies, "search_policy_index", fail_on_retry)
    retry = tool_call_message("search_policies", {"query": "submission cutoff", "transform": "none"}, call_id="retry")
    report = report_journey(
        build([SEARCH, retry, f"The cutoff is one business day before the deadline [{CUTOFF}]."]), CHARGEBACK
    )
    assert [hit["candidate_ids"] for hit in report["searches"]] == [[CUTOFF], None]
    assert report["searches"][1]["error"] == "INDEX_SEARCH_FAILED"
    assert report["policy_citations"] == [{"id": CUTOFF, "passage": passage}]
    assert report["judgment"] == "pending"


@pytest.mark.parametrize(("currency", "expected"), [("USD", date(2025, 7, 3)), ("EUR", date(2025, 7, 4))])
def test_published_holiday_example_matches_calendar(currency, expected):
    assert _previous_business_day(date(2025, 7, 7), currency) == expected
    passages = [
        doc.page_content
        for doc in load_policy_documents()
        if doc.metadata["chunk_id"].startswith("chargeback-handling#response-deadline")
    ]
    example = f"{currency} cutoff is {expected:%A, %B} {expected.day}"
    assert any(example in passage for passage in passages)
