"""Pydantic models of the triage, evidence, claim, verdict and result objects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "status_lookup",
    "refund_discrepancy",
    "duplicate_charge",
    "chargeback_status",
    "settlement_question",
    "policy_question",
    "fx_question",
    "other",
]
Urgency = Literal["low", "normal", "high", "critical"]
ToolName = Literal[
    "query_ledger",
    "get_ledger_record",
    "search_policies",
    "get_reference_fx",
    "calculate",
    "recall_cases",
]
EvidenceSource = Literal["sql", "ledger_api", "policy", "fx", "calc", "case"]
ClaimKind = Literal["fact", "numeric", "policy", "inference"]
VerdictLabel = Literal["supported", "contradicted", "not_enough_evidence"]
VerdictMethod = Literal["nli", "numeric", "rule", "none"]
Action = Literal[
    "none",
    "explain_to_customer",
    "issue_refund",
    "reject_refund",
    "submit_chargeback_evidence",
    "escalate_to_human",
    "ask_for_clarification",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Money(Strict):
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Entities(Strict):
    transaction_ids: list[str] = Field(default_factory=list)  # ^TX-\d{4}$
    refund_ids: list[str] = Field(default_factory=list)  # ^R-\d{4}$
    chargeback_ids: list[str] = Field(default_factory=list)  # ^CB-\d{4}$
    settlement_ids: list[str] = Field(default_factory=list)  # ^ST-\d{4}$
    merchant_ids: list[str] = Field(default_factory=list)  # ^M-\d{2}$
    customer_ids: list[str] = Field(default_factory=list)  # ^C-\d{4}$
    amounts: list[Money] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    dates: list[date] = Field(default_factory=list)


class PlanStep(Strict):
    id: str = Field(pattern=r"^S\d+$")
    goal: str
    tool: ToolName | None = None
    depends_on: list[str] = Field(default_factory=list)


class Triage(Strict):
    intent: Intent
    entities: Entities
    urgency: Urgency
    plan: list[PlanStep] = Field(min_length=1)
    needs_clarification: bool = False
    clarification_question: str | None = None


class Evidence(Strict):
    id: str = Field(pattern=r"^(sql|api|policy|fx|calc|case):.+$")
    source_type: EvidenceSource
    tool: ToolName
    content: str
    ref: str
    retrieved_at: datetime


class NumericClaim(Strict):
    expected: Decimal
    unit: str  # ISO currency code or "%"
    tolerance: Decimal = Decimal("0.01")
    calc_evidence_id: str  # evidence id of the calculate call that produced `expected`


class Claim(Strict):
    id: str = Field(pattern=r"^CL\d+$")
    text: str
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    numeric: NumericClaim | None = None


class NliScores(Strict):
    entailment: float = Field(ge=0, le=1)
    contradiction: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)


class Verdict(Strict):
    claim_id: str
    label: VerdictLabel
    method: VerdictMethod
    scores: NliScores | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class CoherenceIssue(Strict):
    rule: str
    message: str
    claim_ids: list[str] = Field(default_factory=list)


class Coherence(Strict):
    passed: bool
    issues: list[CoherenceIssue] = Field(default_factory=list)


class ToolCallRecord(Strict):
    step: int = Field(ge=1)
    tool: ToolName
    input: dict
    ok: bool
    evidence_ids: list[str] = Field(default_factory=list)
    error_code: str | None = None
    duration_ms: int = Field(ge=0)


class InvestigationResult(Strict):
    schema_version: Literal["1"] = "1"
    session_id: str
    question: str
    triage: Triage | None = None
    answer: str
    claims: list[Claim]
    evidence: list[Evidence]
    verdicts: list[Verdict]
    coherence: Coherence
    missing_information: list[str] = Field(default_factory=list)
    recommended_action: Action
    requires_human_review: bool
    tool_trace: list[ToolCallRecord] = Field(default_factory=list)
    plan_deviations: list[str] = Field(default_factory=list)  # where the trace strayed from the triage plan
