"""The result models validate their samples, reject extra fields, and a generated
InvestigationResult validates against the JSON schema in the contracts folder."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ledgerlens.schemas import (
    Claim,
    Coherence,
    CoherenceIssue,
    Entities,
    Evidence,
    InvestigationResult,
    Money,
    NliScores,
    NumericClaim,
    PlanStep,
    ToolCallRecord,
    Triage,
    Verdict,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "contracts" / "investigation_result.schema.json"
RETRIEVED_AT = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def sample_triage() -> Triage:
    return Triage(
        intent="refund_discrepancy",
        entities=Entities(
            transaction_ids=["TX-2048"],
            amounts=[Money(amount=Decimal("566.79"), currency="BRL")],
            currencies=["BRL", "EUR"],
            dates=[date(2026, 10, 15)],
        ),
        urgency="normal",
        plan=[
            PlanStep(id="S1", goal="Look up the transaction", tool="query_ledger"),
            PlanStep(id="S2", goal="Fetch the reference rate", tool="get_reference_fx", depends_on=["S1"]),
            PlanStep(id="S3", goal="Compute the gap", tool="calculate", depends_on=["S1", "S2"]),
        ],
    )


def sample_result() -> InvestigationResult:
    return InvestigationResult(
        session_id="session-1",
        question="Why was the BRL refund for TX-2048 lower than the EUR payment?",
        triage=sample_triage(),
        answer="The refund was converted at the refund-date rate minus a markup, a gap of BRL 17.48.",
        claims=[
            Claim(
                id="CL1",
                text="The refund gap is BRL 17.48.",
                kind="numeric",
                evidence_ids=["calc:1"],
                numeric=NumericClaim(expected=Decimal("17.48"), unit="BRL", calc_evidence_id="calc:1"),
            ),
            Claim(id="CL2", text="TX-2048 was refunded.", kind="fact", evidence_ids=["sql:1"]),
        ],
        evidence=[
            Evidence(
                id="sql:1",
                source_type="sql",
                tool="query_ledger",
                content="status=refunded",
                ref="transactions:TX-2048",
                retrieved_at=RETRIEVED_AT,
            ),
            Evidence(
                id="calc:1",
                source_type="calc",
                tool="calculate",
                content="17.48",
                ref="calc:1",
                retrieved_at=RETRIEVED_AT,
            ),
        ],
        verdicts=[
            Verdict(claim_id="CL1", label="supported", method="numeric", evidence_ids=["calc:1"]),
            Verdict(
                claim_id="CL2",
                label="supported",
                method="nli",
                scores=NliScores(entailment=0.9, contradiction=0.02, neutral=0.08),
                evidence_ids=["sql:1"],
            ),
        ],
        coherence=Coherence(passed=True),
        missing_information=["The exact rate the acquirer applied."],
        recommended_action="explain_to_customer",
        requires_human_review=False,
        tool_trace=[
            ToolCallRecord(
                step=1, tool="query_ledger", input={"sql": "select 1"}, ok=True, evidence_ids=["sql:1"], duration_ms=12
            ),
            ToolCallRecord(
                step=2, tool="calculate", input={"op": "gap"}, ok=True, evidence_ids=["calc:1"], duration_ms=1
            ),
        ],
    )


# --- samples validate -------------------------------------------------------------------------


def test_sample_result_validates_against_the_json_schema(validator: Draft202012Validator) -> None:
    payload = sample_result().model_dump(mode="json")
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    assert errors == []


def test_minimal_result_validates_against_the_json_schema(validator: Draft202012Validator) -> None:
    minimal = InvestigationResult(
        session_id="s",
        question="q",
        answer="a",
        claims=[],
        evidence=[],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )
    assert list(validator.iter_errors(minimal.model_dump(mode="json"))) == []


def test_decimals_are_serialized_as_strings() -> None:
    payload = sample_result().model_dump(mode="json")
    assert payload["claims"][0]["numeric"]["expected"] == "17.48"
    assert payload["claims"][0]["numeric"]["tolerance"] == "0.01"
    assert payload["triage"]["entities"]["amounts"][0] == {"amount": "566.79", "currency": "BRL"}


def test_round_trip_through_json() -> None:
    original = sample_result()
    again = InvestigationResult.model_validate_json(original.model_dump_json())
    assert again == original


def test_defaults() -> None:
    result = sample_result()
    assert result.schema_version == "1"
    triage = Triage(intent="other", entities=Entities(), urgency="low", plan=[PlanStep(id="S1", goal="g")])
    assert triage.needs_clarification is False
    assert Entities().transaction_ids == []
    assert NumericClaim(expected=Decimal("1"), unit="BRL", calc_evidence_id="calc:1").tolerance == Decimal("0.01")


# --- strictness -------------------------------------------------------------------------------

SAMPLES: dict[str, dict[str, Any]] = {
    "Money": {"amount": "1.50", "currency": "EUR"},
    "Entities": {"transaction_ids": ["TX-0001"]},
    "PlanStep": {"id": "S1", "goal": "g"},
    "Triage": {"intent": "other", "entities": {}, "urgency": "low", "plan": [{"id": "S1", "goal": "g"}]},
    "Evidence": {
        "id": "sql:1",
        "source_type": "sql",
        "tool": "query_ledger",
        "content": "c",
        "ref": "r",
        "retrieved_at": "2026-11-07T12:00:00Z",
    },
    "NumericClaim": {"expected": "1", "unit": "BRL", "calc_evidence_id": "calc:1"},
    "Claim": {"id": "CL1", "text": "t", "kind": "fact"},
    "NliScores": {"entailment": 0.5, "contradiction": 0.25, "neutral": 0.25},
    "Verdict": {"claim_id": "CL1", "label": "supported", "method": "none"},
    "CoherenceIssue": {"rule": "r", "message": "m"},
    "Coherence": {"passed": True},
    "ToolCallRecord": {"step": 1, "tool": "calculate", "input": {}, "ok": True, "duration_ms": 0},
}
MODELS = {
    "Money": Money,
    "Entities": Entities,
    "PlanStep": PlanStep,
    "Triage": Triage,
    "Evidence": Evidence,
    "NumericClaim": NumericClaim,
    "Claim": Claim,
    "NliScores": NliScores,
    "Verdict": Verdict,
    "CoherenceIssue": CoherenceIssue,
    "Coherence": Coherence,
    "ToolCallRecord": ToolCallRecord,
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_each_model_accepts_its_sample(name: str) -> None:
    MODELS[name].model_validate(SAMPLES[name])


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_each_model_rejects_an_extra_field(name: str) -> None:
    with pytest.raises(ValidationError) as info:
        MODELS[name].model_validate({**SAMPLES[name], "surprise": 1})
    assert info.value.errors()[0]["type"] == "extra_forbidden"


def test_investigation_result_rejects_an_extra_field() -> None:
    payload = sample_result().model_dump(mode="json")
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate({**payload, "surprise": 1})


# --- pydantic and the JSON schema agree on what is invalid -----------------------------------


def _mutations() -> list[tuple[str, Any]]:
    def set_path(path: list[Any], value: Any):
        def mutate(payload: dict) -> None:
            node: Any = payload
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value

        return mutate

    def drop(path: list[Any]):
        def mutate(payload: dict) -> None:
            node: Any = payload
            for key in path[:-1]:
                node = node[key]
            del node[path[-1]]

        return mutate

    return [
        ("extra top-level field", set_path(["surprise"], 1)),
        ("schema_version 2", set_path(["schema_version"], "2")),
        ("unknown action", set_path(["recommended_action"], "wire_money")),
        ("unknown intent", set_path(["triage", "intent"], "gossip")),
        ("empty plan", set_path(["triage", "plan"], [])),
        ("bad urgency", set_path(["triage", "urgency"], "whenever")),
        ("lowercase currency", set_path(["triage", "entities", "amounts", 0, "currency"], "brl")),
        ("unknown tool in trace", set_path(["tool_trace", 0, "tool"], "shell")),
        ("negative duration", set_path(["tool_trace", 0, "duration_ms"], -1)),
        ("step zero", set_path(["tool_trace", 0, "step"], 0)),
        ("bad evidence id", set_path(["evidence", 0, "id"], "web:1")),
        ("bad claim id", set_path(["claims", 0, "id"], "claim-1")),
        ("unknown claim kind", set_path(["claims", 0, "kind"], "rumor")),
        ("unknown verdict label", set_path(["verdicts", 0, "label"], "maybe")),
        ("nli score above one", set_path(["verdicts", 1, "scores", "entailment"], 1.5)),
        ("missing answer", drop(["answer"])),
        ("missing coherence", drop(["coherence"])),
        ("missing requires_human_review", drop(["requires_human_review"])),
        ("extra field in evidence", set_path(["evidence", 0, "surprise"], 1)),
    ]


@pytest.mark.parametrize(("label", "mutate"), _mutations(), ids=[m[0] for m in _mutations()])
def test_pydantic_and_json_schema_both_reject(label: str, mutate, validator: Draft202012Validator) -> None:
    payload = sample_result().model_dump(mode="json")
    mutate(payload)
    assert list(validator.iter_errors(payload)), f"JSON schema accepted: {label}"
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(payload)
