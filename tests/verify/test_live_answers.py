"""Real agent answers, with the real tool envelopes, checked end to end by the verifier.

Each case here came from a correct answer the verifier sent to human review. The answer text and the
evidence content have the shape `gpt-4.1-mini` and the tools returned (the `get_ledger_record` evidence
comes from the sample ledger). The NLI model is forbidden: what is a number has to be decided by code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ledgerlens.schemas import Coherence, Evidence, InvestigationResult
from ledgerlens.verify.checks import verify_result

NOW = datetime(2026, 11, 8, tzinfo=UTC)

# S01: "Why was the BRL refund for TX-2048 lower than the EUR payment?". A one-paragraph answer, with every
# citation at the end, separated by ". ".
S01_ANSWER = (
    "The BRL refund for transaction TX-2048 was lower than the original EUR payment because the FX rate "
    "applied in the EUR to BRL conversion on the refund (5.4931) was below the market reference rate "
    "on the refund date, which was 5.6339. "
    "Therefore, applying the lower rate of 5.4931 to convert 100.00 EUR, the amount paid in BRL was 549.31, "
    "while the correct amount at the reference rate would be 563.39 BRL. "
    "This explains the smaller amount received in the refund [api:1]. [sql:1]. [fx:2026-10-20:EUR-BRL]. [calc:1]."
)

API_1 = {
    "transaction": {
        "id": "TX-2048",
        "merchant_id": "M-17",
        "amount_minor": 10000,
        "amount_major": "100.00",
        "currency": "EUR",
        "status": "refunded",
        "created_at": "2026-10-15T09:12:00Z",
    },
    "refunds": [
        {
            "id": "R-0731",
            "transaction_id": "TX-2048",
            "requested_amount_minor": 10000,
            "requested_amount_major": "100.00",
            "requested_currency": "EUR",
            "payout_amount_minor": 54931,
            "payout_amount_major": "549.31",
            "payout_currency": "BRL",
            "fx_applied_id": "FX-9002",
            "status": "paid",
        }
    ],
    "chargebacks": [],
    "fx_applied": [
        {
            "id": "FX-9001",
            "transaction_id": "TX-2048",
            "refund_id": None,
            "kind": "charge",
            "from_currency": "EUR",
            "to_currency": "BRL",
            "applied_rate": "5.6679",
            "applied_at": "2026-10-15T09:12:04Z",
        },
        {
            "id": "FX-9002",
            "transaction_id": "TX-2048",
            "refund_id": "R-0731",
            "kind": "refund",
            "from_currency": "EUR",
            "to_currency": "BRL",
            "applied_rate": "5.4931",
            "applied_at": "2026-10-20T14:30:00Z",
        },
    ],
}
SQL_1 = {
    "sql": "SELECT * FROM (SELECT refunds.id, refunds.transaction_id, refunds.requested_amount_minor, "
    "refunds.requested_currency, refunds.payout_amount_minor, refunds.payout_currency, refunds.status FROM refunds "
    "WHERE refunds.transaction_id = 'TX-2048') LIMIT 50",
    "columns": [
        "id",
        "transaction_id",
        "requested_amount_minor",
        "requested_amount_major",
        "requested_currency",
        "payout_amount_minor",
        "payout_amount_major",
        "payout_currency",
        "status",
    ],
    "rows": [["R-0731", "TX-2048", 10000, "100.00", "EUR", 54931, "549.31", "BRL", "paid"]],
    "row_count": 1,
    "truncated": False,
}
FX_1 = {
    "requested_date": "2026-10-20",
    "rate_date": "2026-10-20",
    "from_currency": "EUR",
    "to_currency": "BRL",
    "rate": "5.6339",
    "source": "frankfurter",
    "note": "ECB reference rate (Frankfurter v1). It is a reference, not the rate any acquirer applied.",
    "from_cache": False,
}
CALC_1 = {"operation": "convert", "result": "563.39", "formula": "100.00 * 5.6339 = 563.39"}


class ForbiddenNli:
    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        raise AssertionError(f"a number went to the NLI model: {hypothesis}")


def evidence(evidence_id: str, source_type: str, tool: str, content: dict) -> Evidence:
    return Evidence(
        id=evidence_id,
        source_type=source_type,
        tool=tool,
        content=json.dumps(content),
        ref=evidence_id,
        retrieved_at=NOW,
    )


def s01_result(answer: str = S01_ANSWER) -> InvestigationResult:
    return InvestigationResult(
        session_id="s01",
        question="Why was the BRL refund for TX-2048 lower than the EUR payment?",
        answer=answer,
        claims=[],
        evidence=[
            evidence("api:1", "ledger_api", "get_ledger_record", API_1),
            evidence("sql:1", "sql", "query_ledger", SQL_1),
            evidence("fx:2026-10-20:EUR-BRL", "fx", "get_reference_fx", FX_1),
            evidence("calc:1", "calc", "calculate", CALC_1),
        ],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )


def test_a_correct_answer_with_its_citations_at_the_end_is_checked_by_code_and_needs_no_review() -> None:
    out = verify_result(s01_result(), nli=ForbiddenNli())
    assert [c.text.split(",")[0] for c in out.claims] == [
        "The BRL refund for transaction TX-2048 was lower than the original EUR payment because the FX rate "
        "applied in the EUR to BRL conversion on the refund (5.4931) was below the market reference rate "
        "on the refund date",
        "Therefore",
    ]  # the third sentence only refers back and the closing citations do not become sentences
    assert [(v.label, v.method) for v in out.verdicts] == [("supported", "numeric"), ("supported", "numeric")]
    assert [c.evidence_ids for c in out.claims] == [["api:1", "sql:1", "fx:2026-10-20:EUR-BRL", "calc:1"]] * 2
    assert out.requires_human_review is False
    assert out.missing_information == []


def test_a_wrong_rate_in_the_same_answer_is_never_supported() -> None:
    wrong = S01_ANSWER.replace("(5.4931)", "(5.4932)")
    out = verify_result(s01_result(wrong), nli=ForbiddenNli())
    assert out.verdicts[0].label == "not_enough_evidence"
    assert out.verdicts[0].method == "numeric"
    assert "5.4932" in out.verdicts[0].note
    assert out.requires_human_review is True
