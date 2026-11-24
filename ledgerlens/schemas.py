"""Pydantic models of the triage, evidence, claim, verdict and result objects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    "extract_document",
]
EvidenceSource = Literal["sql", "ledger_api", "policy", "fx", "calc", "case", "doc"]
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
    id: str = Field(pattern=r"^(sql|api|policy|fx|calc|case|doc):.+$")
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


# An escalation reason enters `missing_information` with this prefix (`verify/escalation.py`); whoever shows the
# result strips it to state only the reason. Both sides read this constant, so the text cannot drift apart.
ESCALATION_PREFIX = "escalation: "

# The status of a step of the studio of the orchestration: it answered, it was refused before it ran, it failed or
# it never ran because the run stopped before it.
StepStatus = Literal["ok", "refused", "failed", "skipped"]


class OrchestrationStep(Strict):
    """One step of the plan of the studio: what it does, which specialist does it and what it waits for.

    Why the plan is typed and not a sentence: the dispatcher reads the steps of the plan and decides what may run,
    and a plan that is a sentence is a plan that only a model can read.

    Why the account is a field of the step and not of the run: the scope of a run is the scope of the parent, and a
    step that names an account has to be checked against it (FR-004).
    """

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    goal: str
    # The specialist of the registry that does the step. None means the step of the run itself.
    specialist: str | None = None
    tool: ToolName | None = None
    depends_on: list[str] = Field(default_factory=list)
    # The account the step reads, when it reads one.
    account: str | None = None
    arguments: dict = Field(default_factory=dict)


class OrchestrationPlan(Strict):
    """The plan of a case of the studio: the steps and the snapshot they were computed against.

    Why the plan carries the snapshot: two steps that read two snapshots are two steps of two questions, and the join
    of their results is a join of nothing (FR-006).
    """

    steps: list[OrchestrationStep] = Field(min_length=1)
    snapshot: str = ""


class StepResult(Strict):
    """The result of one step of the studio: its status, its evidence, what it spent and what stopped it.

    Why the money is a `Decimal` and never a float: the spend of a step is money, and a float is already a rounded
    number (FR-010).

    Why an unknown spend is None and never zero: a price that was never verified leaves the money unmeasured, and a
    zero would say that the step was free (FR-011).
    """

    step_id: str
    status: StepStatus
    evidence_refs: list[str] = Field(default_factory=list)
    spend_usd: Decimal | None = None
    error: str | None = None
    # The row of the ledger the amount is about, and the amount itself. Two results that disagree over the amount of
    # the same row are settled by the calculator and never by a vote (FR-006).
    row: str | None = None
    amount: Decimal | None = None
    # The specialist that answered the step, and the version of its spec.
    specialist: str | None = None
    specialist_version: str | None = None

    @field_validator("spend_usd", "amount", mode="before")
    @classmethod
    def _no_float_money(cls, value: Any) -> Any:
        """The money of a step is a `Decimal`, and a float is refused and not converted.

        Why it is refused and not converted: a float is already a rounded number, and converting it hides the
        rounding inside the money (FR-010).
        """
        if isinstance(value, float):
            raise ValueError("the money of a step is a Decimal, not a float")
        return value


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


# The trust tiers of a record of the versioned memory: what one case observed, what two sources corroborated and
# what a promotion approved. The tier travels with the record, because the reader of a recall has to see how the
# fact entered the memory.
TrustTier = Literal["observed", "corroborated", "approved"]
# The approval state of a record: a record that was never promoted and a record whose promotion was approved.
ApprovalState = Literal["none", "approved"]
# The states of a record: the quarantine is a state and not a deletion, so the attempt stays readable.
RecordState = Literal["active", "quarantined"]


class MemoryRecord(Strict):
    """A record of the versioned memory: what it asserts, which version it is and how much it can be trusted.

    Why the version is monotonic per record: a run of an old case points at the version it read, and a new
    version never overwrites the old one, because the run of last week still points at it.

    Why the record carries the owner: the memory of a session lives in the folder of that session, and a record
    that names no owner is a record that could be read by another session.
    """

    record_id: str = Field(pattern=r"^REC-[0-9a-f]{12}$")
    version: int = Field(ge=1)
    assertion: str
    scope: str
    owner: str
    trust_tier: TrustTier = "observed"
    approval_state: ApprovalState = "none"
    sources: list[str] = Field(default_factory=list)
    valid_until: str | None = None
    state: RecordState = "active"
    quarantine_reason: str | None = None
    created_at: str = ""
