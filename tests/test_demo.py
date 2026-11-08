"""What the demo page shows beyond the agent: questions per statement line, offline scripts and turn summaries.

What they guarantee, and why: (a) the planted complaints are reachable from the line they are about, worded for
the account that asks; (b) every offered planted question has an offline script, so the demo runs with no keys;
(c) the page marks as "read" only ledger records that came back in ledger evidence; (d) the badge counts verdicts
and names the escalation reasons; (e) filters narrow the statement the way a portal does.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ledgerlens import demo
from ledgerlens.schemas import Coherence, Evidence, InvestigationResult, ToolCallRecord, Verdict

MANIFEST = demo.load_manifest()


def _line(ident: str, kind: str = "Payment", **extra) -> dict:
    return {
        "id": ident,
        "type": kind,
        "ids": [ident, *extra.pop("ids", [])],
        "date": "2026-10-15",
        "status": "captured",
        **extra,
    }


def _evidence(ident: str, source: str, content: str, ref: str = "") -> Evidence:
    tool = {"sql": "query_ledger", "ledger_api": "get_ledger_record", "policy": "search_policies"}[source]
    return Evidence(
        id=ident,
        source_type=source,
        tool=tool,
        content=content,
        ref=ref or ident,
        retrieved_at=datetime(2026, 11, 8, tzinfo=UTC),
    )


def _result(**fields) -> InvestigationResult:
    base = {
        "session_id": "s",
        "question": "q",
        "answer": "a",
        "claims": [],
        "evidence": [],
        "verdicts": [],
        "coherence": Coherence(passed=True),
        "recommended_action": "none",
        "requires_human_review": False,
    }
    return InvestigationResult(**{**base, **fields})


def test_a_planted_line_asks_the_planted_question_in_the_account_s_words() -> None:
    s01 = MANIFEST["scenarios"][0]["questions"][0]
    assert demo.ask_question(_line("TX-2048"), "C-0412", MANIFEST) == s01
    assert demo.ask_question(_line("R-0731", "Refund"), "C-0412", MANIFEST) == s01
    assert demo.ask_question(_line("CB-0310", "Chargeback"), "C-0291", MANIFEST).startswith(
        "What is the deadline for my"
    )
    assert demo.ask_question(_line("CB-0310", "Chargeback"), "M-09", MANIFEST).startswith(
        "What is the deadline for dispute"
    )
    assert demo.ask_question(_line("TX-2052"), "C-0733", MANIFEST).startswith("I was charged twice")


def test_another_line_gets_a_question_by_its_type() -> None:
    assert demo.ask_question(_line("TX-0001"), "C-0001", MANIFEST) == "What is the status of TX-0001?"
    refund = _line("R-0001", "Refund", ids=["TX-0001"])
    assert demo.ask_question(refund, "C-0001", MANIFEST) == "What is the status of refund R-0001 for TX-0001?"
    assert "ST-0001" in demo.ask_question(_line("ST-0001", "Payout"), "M-01", MANIFEST)
    # a planted line seen from an account that is not part of the case gets the plain question
    assert demo.ask_question(_line("TX-2048"), "C-0733", MANIFEST) == "What is the status of TX-2048?"


def test_every_offered_planted_question_has_an_offline_script() -> None:
    for question in demo.scripted_questions(MANIFEST):
        script = demo.offline_script(question, MANIFEST)
        assert script is not None, question
        messages, _ = script
        assert messages[-1].content and not messages[-1].tool_calls  # it ends with an answer
    assert demo.offline_script("What is the weather today?", MANIFEST) is None


def test_each_account_is_offered_its_questions_and_an_unknown_id() -> None:
    assert demo.account_questions("M-03", MANIFEST) == [
        "How was payout ST-0044 for merchant M-03 calculated and when is it paid?",
        demo.UNKNOWN_ID_QUESTION,
    ]
    assert demo.account_questions("C-0600", MANIFEST) == [demo.UNKNOWN_ID_QUESTION]


def test_the_context_names_the_account_and_the_line() -> None:
    text = demo.account_context("C-0412", "customer", "Mariana", ["TX-2048"])
    assert "customer C-0412 (Mariana)" in text and "picked TX-2048" in text
    assert "only this account's records" in text
    assert "picked" not in demo.account_context("M-03", "merchant", "Casa", [])


def test_only_ledger_evidence_counts_as_read() -> None:
    result = _result(
        evidence=[
            _evidence(
                "sql:1", "sql", '{"rows": [["charge", "5.6679"]]}', "SELECT ... WHERE transaction_id = 'TX-2048'"
            ),
            _evidence("api:1", "ledger_api", '{"transaction": {"id": "TX-2051", "customer_id": "C-0733"}}', "TX-2051"),
            _evidence("policy:refund-policy#window", "policy", "for example TX-1234 and CB-0042"),
        ]
    )
    assert demo.ids_read(result) == {"TX-2048", "TX-2051", "C-0733"}


def test_the_summary_counts_verdicts_and_names_escalations() -> None:
    result = _result(
        verdicts=[
            Verdict(claim_id="CL1", label="supported", method="numeric"),
            Verdict(claim_id="CL2", label="not_enough_evidence", method="nli"),
        ],
        missing_information=["escalation: CB-0310: card network deadline in 1 day(s)", "fx down"],
        requires_human_review=True,
    )
    summary = demo.verification_summary(result)
    assert (summary["supported"], summary["contradicted"], summary["not_enough_evidence"]) == (1, 0, 1)
    assert summary["review"] and summary["reasons"] == ["CB-0310: card network deadline in 1 day(s)"]


def test_a_short_result_says_how_many_rows_or_why_it_failed() -> None:
    ev = {"sql:1": _evidence("sql:1", "sql", '{"sql": "x", "rows": [["TX-2048", "refunded"]], "row_count": 1}')}
    ok = ToolCallRecord(step=1, tool="query_ledger", input={}, ok=True, evidence_ids=["sql:1"], duration_ms=3)
    assert demo.short_result(ok, ev) == '1 row(s): [["TX-2048", "refunded"]]'
    failed = ToolCallRecord(
        step=2, tool="get_reference_fx", input={}, ok=False, error_code="UPSTREAM_UNAVAILABLE", duration_ms=3
    )
    assert demo.short_result(failed, ev) == "failed: UPSTREAM_UNAVAILABLE"
    long = {"sql:1": _evidence("sql:1", "sql", "x" * 500)}
    assert len(demo.short_result(ok, long)) == 160


def test_filters_narrow_by_period_type_status_and_id() -> None:
    lines = [
        {"id": "TX-1", "type": "Payment", "status": "captured", "date": "2026-11-07", "ids": ["TX-1"]},
        {"id": "R-1", "type": "Refund", "status": "paid", "date": "2026-10-20", "ids": ["R-1", "TX-1"]},
        {"id": "CB-1", "type": "Chargeback", "status": "opened", "date": "2026-09-01", "ids": ["CB-1", "TX-2"]},
    ]
    assert [x["id"] for x in demo.filter_lines(lines)] == ["TX-1", "R-1", "CB-1"]
    assert [x["id"] for x in demo.filter_lines(lines, period="Last 30 days")] == ["TX-1", "R-1"]
    assert [x["id"] for x in demo.filter_lines(lines, period="Last 7 days")] == ["TX-1"]
    assert [x["id"] for x in demo.filter_lines(lines, types=["Refund", "Chargeback"])] == ["R-1", "CB-1"]
    assert [x["id"] for x in demo.filter_lines(lines, statuses=["Disputed"])] == ["CB-1"]  # the pill, not the code
    assert [x["id"] for x in demo.filter_lines(lines, search=" tx-1 ")] == ["TX-1", "R-1"]  # the refund of TX-1 too


def test_status_pills_use_portal_words() -> None:
    assert demo.status_pill({"type": "Payment", "status": "captured"}) == ("Settled", "green")
    assert demo.status_pill({"type": "Payment", "status": "refunded"}) == ("Refunded", "violet")
    assert demo.status_pill({"type": "Refund", "status": "requested"}) == ("Pending", "blue")
    assert demo.status_pill({"type": "Chargeback", "status": "evidence_requested"}) == ("Action needed", "orange")
    assert demo.status_pill({"type": "Payout", "status": "scheduled"}) == ("Pending", "blue")
    assert demo.status_pill({"type": "Payment", "status": "odd_state"}) == ("Odd state", "gray")


def test_money_and_dates_read_like_a_statement() -> None:
    assert demo.money("29992.87", "BRL") == "BRL 29,992.87"
    assert demo.money("-5.00", "USD") == "USD -5.00"
    assert demo.money(None, "USD") == "-"
    assert demo.nice_date("2026-10-15T09:12:00Z") == "Oct 15, 2026"
    assert demo.nice_date("2026-10-15T09:12:00Z", time=True) == "Oct 15, 2026, 09:12 UTC"
    assert demo.nice_date("2026-11-09", time=True) == "Nov 9, 2026"


def _refund_line() -> dict:
    record = {
        "id": "R-0731",
        "transaction_id": "TX-2048",
        "requested_amount_minor": 10000,
        "requested_currency": "EUR",
        "payout_amount_minor": 54931,
        "payout_currency": "BRL",
        "fx_applied_id": "FX-9002",
        "status": "paid",
        "reason": "Customer asked for a full booking refund",
        "created_at": "2026-10-20T14:05:00Z",
        "resolved_at": "2026-10-20T14:30:00Z",
        "fx": [
            {
                "from_currency": "EUR",
                "to_currency": "BRL",
                "applied_rate": "5.4931",
                "applied_at": "2026-10-20T14:30:00Z",
            }
        ],
    }
    return {
        "type": "Refund",
        "id": "R-0731",
        "amount": "100.00",
        "currency": "EUR",
        "status": "paid",
        "date": "2026-10-20",
        "counterparty": "Lumen Travel GmbH",
        "ids": ["R-0731", "TX-2048"],
        "record": record,
    }


def test_a_refund_opens_with_what_was_paid_back_and_the_rate() -> None:
    line = _refund_line()
    details = dict(demo.line_details(line, "customer"))
    assert details["Paid back"] == "BRL 549.31"
    assert details["Exchange rate applied"] == "1 EUR = 5.4931 BRL on Oct 20, 2026"
    assert details["Original payment"] == "TX-2048"
    assert "Status" not in details and "Refund ID" not in details  # the closed line already says them
    assert demo.line_title(line, "customer") == "Refund from Lumen Travel GmbH"


def test_a_card_shows_only_the_end_of_its_fingerprint() -> None:
    record = {
        "created_at": "2026-10-15T09:12:00Z",
        "method": "card",
        "card_brand": "visa",
        "card_fingerprint": "fp_075ebdf3c899",
        "fx": [],
    }
    line = {
        "type": "Payment",
        "id": "TX-2048",
        "amount": "100.00",
        "currency": "EUR",
        "status": "refunded",
        "counterparty": "Lumen Travel GmbH",
        "record": record,
    }
    details = dict(demo.line_details(line, "customer"))
    assert details["Payment method"] == "Visa card, on file as ****c899"
    assert "fp_075ebdf3c899" not in " ".join(details.values())


def test_the_account_card_figures() -> None:
    lines = [
        {"type": "Payment", "status": "captured"},
        {"type": "Refund", "status": "requested"},
        {"type": "Chargeback", "status": "evidence_requested"},
        {"type": "Chargeback", "status": "won"},
    ]
    assert demo.account_summary(lines, "customer") == [
        ("Payments", "1"),
        ("Refunds in progress", "1"),
        ("Open disputes", "1"),
    ]
    payouts = [
        {
            "type": "Payout",
            "status": "scheduled",
            "currency": "BRL",
            "amount": "10.00",
            "date": "2026-11-01",
            "record": {"net_minor": 1000},
        },
        {
            "type": "Payout",
            "status": "paid",
            "currency": "BRL",
            "amount": "29992.87",
            "date": "2026-10-11",
            "record": {"net_minor": 2999287},
        },
    ]
    assert demo.account_summary(payouts, "merchant") == [
        ("Pending settlement", "BRL 10.00"),
        ("Last payout", "BRL 29,992.87"),
        ("Open disputes", "0"),
    ]
