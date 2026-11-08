"""Verification: numbers by code, coherence by rules, text by the NLI model, and the final result."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ledgerlens.schemas import (
    Claim,
    Coherence,
    Evidence,
    InvestigationResult,
    NumericClaim,
)
from ledgerlens.verify import verify_result
from ledgerlens.verify.checks import check_coherence, check_numeric, label_from_scores, load_thresholds

NOW = datetime(2026, 11, 8, tzinfo=UTC)


def evidence(evidence_id: str, content: str) -> Evidence:
    source = evidence_id.split(":")[0]
    tool = {"sql": "query_ledger", "calc": "calculate", "policy": "search_policies"}[source]
    return Evidence(id=evidence_id, source_type=source, tool=tool, content=content, ref=evidence_id, retrieved_at=NOW)


def make_result(claims: list[Claim], evidence_list: list[Evidence], **kwargs) -> InvestigationResult:
    return InvestigationResult(
        session_id="s1",
        question="q",
        answer="a",
        claims=claims,
        evidence=evidence_list,
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action=kwargs.pop("recommended_action", "none"),
        requires_human_review=kwargs.pop("requires_human_review", False),
        **kwargs,
    )


def claim(claim_id: str, text: str, evidence_ids: list[str], kind: str = "fact", numeric=None) -> Claim:
    return Claim(id=claim_id, text=text, kind=kind, evidence_ids=evidence_ids, numeric=numeric)


class FakeNli:
    def __init__(self, entailment: float, contradiction: float) -> None:
        self.scores = {
            "entailment": entailment,
            "contradiction": contradiction,
            "neutral": round(1 - entailment - contradiction, 6),
        }
        self.calls: list[tuple[str, str]] = []

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        self.calls.append((premise, hypothesis))
        return dict(self.scores)


class ForbiddenNli:
    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        raise AssertionError("a number must never reach the NLI model")


CALC = evidence("calc:1", json.dumps({"operation": "difference", "result": "17.48", "formula": "x"}))


def numeric_claim(text: str, expected: str = "17.48", unit: str = "BRL") -> Claim:
    return claim(
        "CL1",
        text,
        ["calc:1"],
        "numeric",
        NumericClaim(expected=Decimal(expected), unit=unit, calc_evidence_id="calc:1"),
    )


def test_a_matching_number_is_supported_by_the_numeric_method() -> None:
    verdict = check_numeric(numeric_claim("The gap is 17.48 BRL."), {"calc:1": CALC})
    assert (verdict.label, verdict.method, verdict.scores) == ("supported", "numeric", None)


def test_a_wrong_number_is_contradicted() -> None:
    assert check_numeric(numeric_claim("The gap is 17.84 BRL."), {"calc:1": CALC}).label == "contradicted"


def test_the_tolerance_is_respected() -> None:
    near = numeric_claim("The gap is 17.485 BRL.")
    assert check_numeric(near, {"calc:1": CALC}).label == "supported"


def test_an_expected_value_that_calculate_did_not_produce_is_contradicted() -> None:
    forged = numeric_claim("The gap is 99.00 BRL.", expected="99.00")
    verdict = check_numeric(forged, {"calc:1": CALC})
    assert verdict.label == "contradicted"
    assert verdict.note and "calculate" in verdict.note


def test_a_number_in_another_unit_is_ignored() -> None:
    assert check_numeric(numeric_claim("The gap is 99 USD or 17.48 BRL."), {"calc:1": CALC}).label == "supported"


def test_missing_calculate_evidence_or_number_is_not_enough_evidence() -> None:
    assert check_numeric(numeric_claim("The gap is 17.48 BRL."), {}).label == "not_enough_evidence"
    assert check_numeric(numeric_claim("The gap is small."), {"calc:1": CALC}).label == "not_enough_evidence"
    no_block = claim("CL1", "The gap is 17.48 BRL.", ["calc:1"], "numeric")
    assert check_numeric(no_block, {"calc:1": CALC}).label == "not_enough_evidence"


def calc_evidence(evidence_id: str, result: str, formula: str = "x") -> Evidence:
    return evidence(evidence_id, json.dumps({"operation": "difference", "result": result, "formula": formula}))


def extracted_verdict(text: str, evidence_list: list[Evidence]):
    from ledgerlens.verify.claims import extract_claims

    [extracted] = extract_claims(text, evidence_list)
    return check_numeric(extracted, {e.id: e for e in evidence_list})


def test_a_difference_described_in_words_matches_the_signed_calculation() -> None:
    """`calculate` returns -14.08 and the sentence says "14.08 lower": it was `contradicted` for losing the sign."""
    calc = [calc_evidence("calc:1", "-14.08", "549.31 - 563.39 = -14.08")]
    assert extracted_verdict("The refund came in 14.08 BRL lower [calc:1].", calc).label == "supported"
    assert extracted_verdict("The refund was 14.08 BRL less [calc:1].", calc).label == "supported"
    assert extracted_verdict("The refund came in at -14.08 BRL [calc:1].", calc).label == "supported"


def test_a_direction_in_words_matches_the_magnitude_whichever_way_the_calculation_subtracts() -> None:
    """In an online run "17.48 BRL less" against the +17.48 of `566.79 - 549.31` cannot be an error."""
    positive = [calc_evidence("calc:2", "17.48", "566.79 - 549.31 = 17.48")]
    assert extracted_verdict("The difference is 17.48 BRL less on the refund [calc:2].", positive).label == "supported"
    negative = [calc_evidence("calc:1", "-14.08", "549.31 - 563.39 = -14.08")]
    assert extracted_verdict("The refund came in 14.08 BRL higher [calc:1].", negative).label == "supported"
    assert extracted_verdict("The refund came in 14.00 BRL lower [calc:1].", negative).label == "contradicted"


def test_without_a_direction_in_words_a_sign_error_is_contradicted() -> None:
    negative = [calc_evidence("calc:1", "-14.08")]
    assert extracted_verdict("The difference was 14.08 BRL [calc:1].", negative).label == "contradicted"
    positive = [calc_evidence("calc:1", "14.08")]
    assert extracted_verdict("The difference was -14.08 BRL [calc:1].", positive).label == "contradicted"


def test_a_number_that_no_cited_calculation_produced_is_not_enough_evidence() -> None:
    """In an online run the "100" matched a conversion at rate 1 and 563.39, which nobody computed, got through too."""
    calc = [calc_evidence("calc:1", "100.00", "100.00 * 1 = 100.00")]
    text = "The payment of 100.00 BRL is worth 563.39 BRL at the reference rate [calc:1]."
    verdict = extracted_verdict(text, calc)
    assert verdict.label == "not_enough_evidence"
    assert verdict.note and "563.39" in verdict.note


def test_the_central_number_must_be_a_result_not_just_an_input_of_the_calculation() -> None:
    calc = [calc_evidence("calc:1", "-449.31", "100.00 - 549.31 = -449.31")]
    assert extracted_verdict("The difference is 100.00 BRL [calc:1].", calc).label == "contradicted"
    mixed = "The difference is 449.31 BRL less, over 100.00 BRL and 99.00 BRL [calc:1]."
    assert extracted_verdict(mixed, calc).label == "not_enough_evidence"


def test_every_cited_calculation_counts_and_two_candidates_are_never_a_contradiction() -> None:
    rate_one = calc_evidence("calc:1", "100.00", "100.00 * 1 = 100.00")
    converted = calc_evidence("calc:2", "563.39", "100.00 * 5.6339 = 563.39")
    both = "The payment of 100.00 BRL is worth 563.39 BRL [calc:1] [calc:2]."
    assert extracted_verdict(both, [rate_one, converted]).label == "supported"
    # a single stated value and two results: there is no clear pair to contradict
    assert extracted_verdict("The amount was 17.48 BRL [calc:1] [calc:2].", [rate_one, converted]).label == (
        "not_enough_evidence"
    )


def test_a_number_backed_by_a_cited_ledger_value_is_supported_beside_an_unrelated_calculation() -> None:
    ledger = evidence(
        "sql:2",
        json.dumps(
            {"columns": ["id", "payout_amount_minor", "payout_amount_major"], "rows": [["R-1", 54931, "549.31"]]}
        ),
    )
    calc = calc_evidence("calc:2", "563.39", "100.00 * 5.6339 = 563.39")
    assert extracted_verdict("The refund paid was 549.31 BRL [sql:2] [calc:2].", [ledger, calc]).label == "supported"
    # the minor-unit value (54931) does not count as 54,931.00
    assert extracted_verdict("The refund paid was 54,931.00 BRL [sql:2] [calc:2].", [ledger, calc]).label != "supported"


def test_numeric_claims_never_reach_the_nli_model() -> None:
    result = make_result([numeric_claim("The gap is 17.48 BRL.")], [CALC])
    out = verify_result(result, nli=ForbiddenNli())
    assert [(v.claim_id, v.label, v.method) for v in out.verdicts] == [("CL1", "supported", "numeric")]


def test_text_claims_use_the_nli_with_evidence_as_premise() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    result = make_result([claim("CL1", "Refund R-0412 was paid.", ["sql:1"])], [evidence("sql:1", "R-0412 paid")])
    out = verify_result(result, nli=nli)
    assert nli.calls == [("R-0412 paid", "Refund R-0412 was paid.")]
    [verdict] = out.verdicts
    assert (verdict.label, verdict.method) == ("supported", "nli")
    assert verdict.scores is not None and verdict.scores.entailment == pytest.approx(0.95)
    assert verdict.evidence_ids == ["sql:1"]


def test_a_contradiction_requires_human_review() -> None:
    nli = FakeNli(entailment=0.02, contradiction=0.95)
    result = make_result([claim("CL1", "Refund R-0412 was never paid.", ["sql:1"])], [evidence("sql:1", "paid")])
    out = verify_result(result, nli=nli)
    assert out.verdicts[0].label == "contradicted"
    assert out.requires_human_review is True


def test_all_supported_does_not_require_review_and_never_lowers_an_existing_flag() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    claims = [claim("CL1", "Refund R-0412 was paid.", ["sql:1"])]
    ev_list = [evidence("sql:1", "paid")]
    assert verify_result(make_result(claims, ev_list), nli=nli).requires_human_review is False
    flagged = make_result(claims, ev_list, requires_human_review=True)
    assert verify_result(flagged, nli=nli).requires_human_review is True


def test_a_claim_without_evidence_is_not_enough_evidence_and_listed_as_missing() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    result = make_result([claim("CL1", "The customer is angry.", [])], [], missing_information=["old item"])
    out = verify_result(result, nli=nli)
    assert nli.calls == []
    assert out.verdicts[0].label == "not_enough_evidence" and out.verdicts[0].method == "none"
    assert out.missing_information[0] == "old item"
    assert any("The customer is angry." in item for item in out.missing_information)
    assert out.requires_human_review is True  # 100% with no evidence is over the limit


def test_few_unsupported_claims_stay_under_the_review_threshold() -> None:
    share = load_thresholds()["unsupported_share_review"]
    assert 0 < share < 1
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    claims = [claim(f"CL{i}", f"Fact number {i} holds.", ["sql:1"]) for i in range(1, 6)]
    claims.append(claim("CL6", "Something unverifiable.", []))
    out = verify_result(make_result(claims, [evidence("sql:1", "x")]), nli=nli)
    assert 1 / 6 <= share  # one in six is not over the limit
    assert out.requires_human_review is False
    assert out.missing_information


def test_verify_result_does_not_change_the_input_and_covers_every_claim() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    result = make_result(
        [claim("CL1", "A holds.", ["sql:1"]), claim("CL2", "B holds.", ["sql:1"])], [evidence("sql:1", "x")]
    )
    out = verify_result(result, nli=nli)
    assert result.verdicts == []
    assert [v.claim_id for v in out.verdicts] == ["CL1", "CL2"]


def test_labels_follow_the_thresholds() -> None:
    t = load_thresholds()
    assert label_from_scores({"entailment": 0.97, "neutral": 0.02, "contradiction": 0.01}, t) == "supported"
    assert label_from_scores({"entailment": 0.01, "neutral": 0.02, "contradiction": 0.97}, t) == "contradicted"
    assert label_from_scores({"entailment": 0.1, "neutral": 0.8, "contradiction": 0.1}, t) == "not_enough_evidence"


# ---- coherence ----------------------------------------------------------------------------------


def rules(result: InvestigationResult) -> set[str]:
    return {issue.rule for issue in check_coherence(result).issues}


def supported(result: InvestigationResult, *claim_ids: str) -> InvestigationResult:
    from ledgerlens.schemas import Verdict

    verdicts = [Verdict(claim_id=c, label="supported", method="nli") for c in claim_ids]
    return result.model_copy(update={"verdicts": verdicts})


def test_a_claim_and_its_negation_cannot_both_be_supported() -> None:
    base = make_result(
        [claim("CL1", "The refund was issued.", ["sql:1"]), claim("CL2", "The refund was not issued.", ["sql:1"])],
        [evidence("sql:1", "x")],
    )
    assert "negation_pair" in rules(supported(base, "CL1", "CL2"))
    assert "negation_pair" not in rules(supported(base, "CL1"))


def test_settlement_net_must_equal_gross_minus_refunds_minus_fees() -> None:
    good = {"id": "ST-1", "gross_minor": 100000, "refunds_minor": 5000, "fees_minor": 3000, "net_minor": 92000}
    bad = dict(good, net_minor=93000)
    assert "settlement_net" not in rules(make_result([], [evidence("sql:1", json.dumps({"rows": [good]}))]))
    assert "settlement_net" in rules(make_result([], [evidence("sql:1", json.dumps({"rows": [bad]}))]))


def test_a_paid_refund_needs_a_payout_amount() -> None:
    row = {"id": "R-1", "transaction_id": "TX-1", "status": "paid", "payout_amount_minor": None}
    assert "refund_payout" in rules(make_result([], [evidence("sql:1", json.dumps([row]))]))
    row["payout_amount_minor"] = 100
    assert "refund_payout" not in rules(make_result([], [evidence("sql:1", json.dumps([row]))]))


def test_transaction_status_must_follow_its_latest_refund_or_chargeback() -> None:
    tx = {"id": "TX-1", "status": "captured"}
    refund = {"id": "R-1", "transaction_id": "TX-1", "status": "paid", "payout_amount_minor": 5}
    chargeback = {"id": "CB-1", "transaction_id": "TX-1", "stage": "opened"}
    ev = [evidence("sql:1", json.dumps(tx)), evidence("sql:2", json.dumps(refund))]
    assert "status_event" in rules(make_result([], ev))
    ev = [evidence("sql:1", json.dumps(tx)), evidence("sql:2", json.dumps(chargeback))]
    assert "status_event" in rules(make_result([], ev))
    ok_tx = {"id": "TX-1", "status": "disputed"}
    assert "status_event" not in rules(
        make_result([], [evidence("sql:1", json.dumps(ok_tx)), evidence("sql:2", json.dumps(chargeback))])
    )


def test_issue_refund_needs_a_supported_duplicate_or_discrepancy_claim() -> None:
    base = make_result(
        [claim("CL1", "Transaction TX-1 was captured.", ["sql:1"])],
        [evidence("sql:1", "x")],
        recommended_action="issue_refund",
    )
    assert "action_support" in rules(supported(base, "CL1"))
    dup = make_result(
        [claim("CL1", "TX-2 is a duplicate charge.", ["sql:1"])],
        [evidence("sql:1", "x")],
        recommended_action="issue_refund",
    )
    assert "action_support" not in rules(supported(dup, "CL1"))
    assert "action_support" in rules(dup)  # with no supported verdict yet it does not count


def test_evidence_that_is_not_json_is_skipped_by_the_structured_rules() -> None:
    assert check_coherence(make_result([], [evidence("sql:1", "plain text, no rows")])).passed is True


def test_verify_result_stores_coherence() -> None:
    bad = {"id": "ST-1", "gross_minor": 100, "refunds_minor": 0, "fees_minor": 0, "net_minor": 90}
    out = verify_result(make_result([], [evidence("sql:1", json.dumps(bad))]), nli=FakeNli(0.9, 0.05))
    assert out.coherence.passed is False
    assert out.requires_human_review is True


def test_a_result_without_claims_gets_them_extracted_from_the_answer() -> None:
    result = make_result([], [evidence("sql:1", "Refund R-0412 was paid on 2026-10-05.")]).model_copy(
        update={"answer": "Refund R-0412 was paid on 2026-10-05 [sql:1]. Anything else?"}
    )
    out = verify_result(result, nli=FakeNli(0.95, 0.02))
    assert [c.id for c in out.claims] == ["CL1"]
    assert out.claims[0].evidence_ids == ["sql:1"]
    assert [v.claim_id for v in out.verdicts] == ["CL1"]


# ---- the tools' real format -------------------------------------------------------------------------
# `query_ledger` returns `columns` and `rows` (lists); `get_ledger_record` returns nested objects.
# The coherence rules must read both formats, or they never fire.


def sql_evidence(columns: list[str], *rows: list) -> Evidence:
    data = {
        "sql": "SELECT ...",
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": False,
    }
    return evidence("sql:1", json.dumps(data))


def api_evidence(data: dict) -> Evidence:
    return Evidence(
        id="api:1",
        source_type="ledger_api",
        tool="get_ledger_record",
        content=json.dumps(data),
        ref="TX-1",
        retrieved_at=NOW,
    )


def test_settlement_net_is_checked_on_query_ledger_columns_and_rows() -> None:
    cols = ["id", "gross_minor", "refunds_minor", "fees_minor", "net_minor"]
    bad = make_result([], [sql_evidence(cols, ["ST-1", 1000, 100, 50, 900])])
    good = make_result([], [sql_evidence(cols, ["ST-1", 1000, 100, 50, 850])])
    assert "settlement_net" in rules(bad)
    assert check_coherence(good).passed is True


def test_settlement_net_is_checked_on_the_settlements_of_the_ledger_api() -> None:
    bad = {
        "merchant_id": "M-03",
        "settlements": [{"id": "ST-1", "gross_minor": 1000, "refunds_minor": 0, "fees_minor": 50, "net_minor": 900}],
    }
    assert "settlement_net" in rules(make_result([], [api_evidence(bad)]))


def test_status_rules_see_the_transaction_and_its_children_of_the_ledger_api() -> None:
    paid_on_captured = {
        "transaction": {"id": "TX-1", "status": "captured"},
        "refunds": [{"id": "R-1", "transaction_id": "TX-1", "status": "paid", "payout_amount_minor": 500}],
        "chargebacks": [],
    }
    open_on_captured = {
        "transaction": {"id": "TX-1", "status": "captured"},
        "refunds": [],
        "chargebacks": [{"id": "CB-1", "transaction_id": "TX-1", "stage": "opened"}],
    }
    consistent = {
        "transaction": {"id": "TX-1", "status": "disputed"},
        "refunds": [],
        "chargebacks": [{"id": "CB-1", "transaction_id": "TX-1", "stage": "evidence_requested"}],
    }
    assert "status_event" in rules(make_result([], [api_evidence(paid_on_captured)]))
    assert "status_event" in rules(make_result([], [api_evidence(open_on_captured)]))
    assert check_coherence(make_result([], [api_evidence(consistent)])).passed is True


def test_a_paid_refund_without_payout_is_flagged_on_query_ledger_rows() -> None:
    cols = ["id", "transaction_id", "status", "payout_amount_minor"]
    assert "refund_payout" in rules(make_result([], [sql_evidence(cols, ["R-1", "TX-1", "paid", None])]))


def test_a_closing_offer_and_an_uncited_conclusion_do_not_push_the_answer_to_human_review() -> None:
    """Each sentence with nothing to check counted as 'no evidence' and pushed a good result over the 34% limit."""
    answer = (
        "Payout ST-0002 was paid on 2026-10-14 [sql:1]. The net of payout ST-0002 is 741.07 [sql:1]. "
        "Therefore, the merchant has already been paid. If you wish, I can detail the fees."
    )
    row = evidence("sql:1", '{"id": "ST-0002", "net_minor": 74107}')
    result = make_result([], [row]).model_copy(update={"answer": answer})
    verified = verify_result(result, nli=FakeNli(entailment=0.99, contradiction=0.0))

    assert [c.text for c in verified.claims] == [
        "Payout ST-0002 was paid on 2026-10-14.",
        "The net of payout ST-0002 is 741.07.",
    ]
    assert verified.requires_human_review is False and verified.missing_information == []


# ---- amounts stated with no calculation cited: checked against the cited ledger ----------------------------
# In an online run (S08) "The fees were BRL 926.67 [sql:1]" went to the NLI model, which scored a ledger value low.

SETTLEMENT_COLUMNS = [
    "id",
    "merchant_id",
    "currency",
    "gross_minor",
    "gross_major",
    "refunds_minor",
    "refunds_major",
    "fees_minor",
    "fees_major",
    "net_minor",
    "net_major",
    "status",
    "settlement_currency",
    "refund_window_days",
]
ST_0044 = [
    "ST-0044",
    "M-03",
    "BRL",
    3091954,
    "30919.54",
    0,
    "0.00",
    92667,
    "926.67",
    2999287,
    "29992.87",
    "paid",
    "BRL",
    30,
]


def settlement() -> Evidence:
    """The shape of S08's `sql:1`: `_minor` columns with the `_major` beside them, payout and merchant currency."""
    return sql_evidence(SETTLEMENT_COLUMNS, ST_0044)


def ledger_verdict(text: str, *evidence_list: Evidence, nli: object | None = None):
    claim_ = claim("CL1", text, [e.id for e in evidence_list])
    out = verify_result(make_result([claim_], list(evidence_list)), nli=nli or ForbiddenNli())
    return out.verdicts[0]


def test_an_amount_that_is_a_ledger_value_supports_the_sentence_by_code() -> None:
    verdict = ledger_verdict("The fees were BRL 926.67.", settlement())
    assert (verdict.label, verdict.method, verdict.evidence_ids) == ("supported", "numeric", ["sql:1"])


def test_every_amount_of_a_long_sentence_must_be_a_ledger_value() -> None:
    text = (
        "The gross amount was BRL 30,919.54, there were no refunds (BRL 0.00), the fees were R$926.67, "
        "resulting in a net amount of BRL 29,992.87."
    )
    assert ledger_verdict(text, settlement()).label == "supported"
    wrong_net = text.replace("29,992.87", "29,992.88")
    verdict = ledger_verdict(wrong_net, settlement())
    assert (verdict.label, verdict.method) == ("not_enough_evidence", "numeric")  # several values: not the clear pair
    assert "29992.88" in verdict.note


def test_a_minor_column_without_its_major_twin_is_divided_by_100() -> None:
    only_minor = sql_evidence(["id", "currency", "fees_minor"], ["ST-0044", "BRL", 92667])
    assert ledger_verdict("The fees were BRL 926.67.", only_minor).label == "supported"
    assert ledger_verdict("The fees were BRL 92,667.00.", only_minor).label != "supported"  # raw 92667 does not count


def test_the_amount_of_a_nested_ledger_record_counts_too() -> None:
    record = api_evidence(
        {"transaction": {"id": "TX-1", "amount_minor": 10000, "amount_major": "100.00", "currency": "EUR"}}
    )
    assert ledger_verdict("The payment was 100.00 EUR.", record).label == "supported"


def test_a_ledger_value_in_another_currency_does_not_support_the_amount() -> None:
    verdict = ledger_verdict("The fees were 926.67 EUR.", settlement())
    assert verdict.label == "not_enough_evidence"  # the ledger says BRL: neither support nor a clear contradiction
    assert ledger_verdict("The amount was USD 30.00.", settlement()).label == "not_enough_evidence"


def test_a_money_amount_is_never_matched_to_a_column_that_is_not_money() -> None:
    """`refund_window_days` is 30: "BRL 30.00" is not the refund window."""
    assert ledger_verdict("The cost was BRL 30.00.", settlement()).label == "not_enough_evidence"


def test_an_amount_with_no_exact_ledger_value_stays_not_enough_evidence() -> None:
    for text in ("The payout was BRL 926.68.", "The payout was BRL 926.6.", "The payout was BRL 927.00."):
        verdict = ledger_verdict(text, settlement())
        assert (verdict.label, verdict.method) == ("not_enough_evidence", "numeric"), text


def test_a_different_value_is_contradicted_only_for_the_one_column_the_sentence_names() -> None:
    wrong_fee = ledger_verdict("The fees were BRL 900.00.", settlement())
    assert (wrong_fee.label, wrong_fee.method) == ("contradicted", "numeric")
    assert "fees" in wrong_fee.note and "926.67" in wrong_fee.note
    assert ledger_verdict("The gross amount was BRL 31,000.00.", settlement()).label == "contradicted"
    assert ledger_verdict("The net amount was BRL 1.00.", settlement()).label == "contradicted"
    assert ledger_verdict("The fee was R$900.00.", settlement()).label == "contradicted"
    assert ledger_verdict("The payout was BRL 900.00.", settlement()).label == "not_enough_evidence"  # no column
    # two columns in the sentence: no single field matches the value
    assert ledger_verdict("The gross minus the fees was BRL 900.00.", settlement()).label == "not_enough_evidence"


def test_a_different_value_is_not_contradicted_when_the_query_has_several_rows_or_another_currency() -> None:
    other = [
        *ST_0044[:1],
        "M-04",
        "BRL",
        100000,
        "1000.00",
        0,
        "0.00",
        3000,
        "30.00",
        97000,
        "970.00",
        "paid",
        "BRL",
        30,
    ]
    two_rows = sql_evidence(SETTLEMENT_COLUMNS, ST_0044, other)
    assert ledger_verdict("The fees were BRL 900.00.", two_rows).label == "not_enough_evidence"
    assert ledger_verdict("The fees were BRL 926.67.", two_rows).label == "supported"  # one of the rows has the value
    assert ledger_verdict("The fees were 900.00 EUR.", settlement()).label == "not_enough_evidence"


def test_the_currency_of_an_amount_column_comes_from_its_own_prefix_then_from_the_row() -> None:
    refund = sql_evidence(
        ["id", "requested_amount_minor", "requested_currency", "payout_amount_minor", "payout_currency"],
        ["R-1", 10000, "USD", 54931, "BRL"],
    )
    assert ledger_verdict("The refund paid was 549.31 BRL.", refund).label == "supported"
    assert ledger_verdict("The refund paid was 549.31 USD.", refund).label != "supported"  # 549.31 is BRL
    assert ledger_verdict("The refund requested was 100.00 USD.", refund).label == "supported"
    only_settlement_currency = sql_evidence(["id", "fees_minor", "settlement_currency"], ["ST-1", 92667, "BRL"])
    assert ledger_verdict("The fees were BRL 926.67.", only_settlement_currency).label == "supported"
    assert ledger_verdict("The fees were 926.67 EUR.", only_settlement_currency).label != "supported"


def test_a_major_column_alone_is_money_and_a_percentage_is_never_a_ledger_value() -> None:
    major_only = sql_evidence(["id", "fees_major", "currency"], ["ST-1", "2.90", "BRL"])
    assert ledger_verdict("The fees were BRL 2.90.", major_only).label == "supported"
    unknown_currency = sql_evidence(["id", "gross_minor", "fees_minor"], ["ST-1", 10000, 290])
    verdict = ledger_verdict("The gross was BRL 100.00 and the fees 2.90% of the volume.", unknown_currency)
    assert verdict.label == "not_enough_evidence"  # 2.90% is not the 2.90 of fees


def test_the_rate_of_the_fx_evidence_supports_a_rate_stated_beside_a_ledger_amount() -> None:
    fx = Evidence(
        id="fx:1",
        source_type="fx",
        tool="get_reference_fx",
        content='{"from_currency": "EUR", "to_currency": "BRL", "rate": "5.6339", "rate_date": "2026-10-20"}',
        ref="fx:1",
        retrieved_at=NOW,
    )
    paid = sql_evidence(
        ["id", "payout_amount_minor", "payout_amount_major", "payout_currency"], ["R-1", 54931, "549.31", "BRL"]
    )
    ok = ledger_verdict("The refund was 549.31 BRL, with the reference rate 5.6339.", paid, fx)
    assert ok.label == "supported"
    assert ledger_verdict("The refund was 549.31 BRL, with the reference rate 5.6340.", paid, fx).label != "supported"
    # nobody read 563.39: the rate alone does not support it
    assert ledger_verdict("The rate of 5.6339 gives 563.39 BRL.", fx).label == "not_enough_evidence"


def test_sentences_the_ledger_check_does_not_own_still_go_to_the_nli() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    # no currency value: the ledger has nothing to check
    assert ledger_verdict("The payout is paid.", settlement(), nli=nli).method == "nli"
    # a currency value, but only the policy was cited: there is no ledger to check
    policy = evidence("policy:1", json.dumps({"chunk_id": "p#1", "text": "The fee is BRL 5.00 per dispute."}))
    assert ledger_verdict("The fee is BRL 5.00 per dispute.", policy, nli=nli).method == "nli"
    # only a percentage
    assert ledger_verdict("The fee is 2.9% of the volume.", settlement(), nli=nli).method == "nli"
    assert len(nli.calls) == 3


def test_a_date_written_in_words_is_not_an_amount() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    text = "The payout was paid on October 14, 2026, as expected."
    assert ledger_verdict(text, settlement(), nli=nli).method == "nli"


def test_a_sentence_whose_amounts_are_ledger_values_is_supported_end_to_end_from_the_answer() -> None:
    result = make_result([], [settlement()]).model_copy(
        update={"answer": "Payout ST-0044 had fees of BRL 926.67 and a net of BRL 29,992.87 [sql:1]."}
    )
    out = verify_result(result, nli=ForbiddenNli())
    assert [(v.label, v.method) for v in out.verdicts] == [("supported", "numeric")]
    assert out.requires_human_review is False


# ---- rates (decimals with three places or more, no currency) ----------------------------------------------

FX_RATE = Evidence(
    id="fx:2026-10-20:EUR-BRL",
    source_type="fx",
    tool="get_reference_fx",
    content='{"from_currency": "EUR", "to_currency": "BRL", "rate": "5.6339", "rate_date": "2026-10-20"}',
    ref="fx",
    retrieved_at=NOW,
)


def applied_rates() -> Evidence:
    return api_evidence(
        {"fx_applied": [{"id": "FX-9002", "kind": "refund", "applied_rate": "5.4931"}], "refunds": [{"id": "R-1"}]}
    )


def test_rates_stated_without_a_currency_are_checked_by_code_against_the_cited_ledger_and_fx() -> None:
    both = ledger_verdict("The applied rate was 5.4931 and the reference one was 5.6339.", applied_rates(), FX_RATE)
    assert (both.label, both.method) == ("supported", "numeric")
    assert sorted(both.evidence_ids) == ["api:1", "fx:2026-10-20:EUR-BRL"]
    assert ledger_verdict("The applied rate was 5.4931 BRL per EUR.", applied_rates()).label == "supported"


def test_a_rate_that_is_not_in_the_cited_evidence_is_not_supported_and_never_reaches_the_nli() -> None:
    for text in ("The applied rate was 5.4932.", "The applied rate was 5.4931 and the reference one was 5.6340."):
        verdict = ledger_verdict(text, applied_rates(), FX_RATE)
        assert (verdict.label, verdict.method) == ("not_enough_evidence", "numeric"), text
    assert "5.4932" in ledger_verdict("The applied rate was 5.4932.", applied_rates(), FX_RATE).note


def test_a_rate_only_counts_in_the_evidence_the_sentence_cites() -> None:
    claim_ = claim("CL1", "The applied rate was 5.4931.", ["fx:2026-10-20:EUR-BRL"])
    out = verify_result(make_result([claim_], [applied_rates(), FX_RATE]), nli=ForbiddenNli())
    assert out.verdicts[0].label == "not_enough_evidence"


def test_a_rate_beside_a_figure_the_code_cannot_confirm_goes_to_the_nli() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    verdict = ledger_verdict("The applied rate was 5.4931, a difference of 2 days.", applied_rates(), nli=nli)
    assert (verdict.label, verdict.method) == ("supported", "nli")


def test_only_decimals_with_three_places_are_rates_and_the_nli_keeps_the_rest() -> None:
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    # two places with no currency ("2.90") and a whole number are not rates
    assert ledger_verdict("The fee was 2.90 per dispute.", applied_rates(), nli=nli).method == "nli"
    assert ledger_verdict("There were 5 refund attempts.", applied_rates(), nli=nli).method == "nli"
    # a rate with no structured evidence cited (only the policy) has nothing to check
    policy = evidence("policy:1", json.dumps({"chunk_id": "p#1", "text": "The rate is 5.4931."}))
    assert ledger_verdict("The applied rate was 5.4931.", policy, nli=nli).method == "nli"
    assert len(nli.calls) == 3


def test_a_percentage_is_never_confirmed_by_code_and_a_rate_is_only_confirmed_by_the_ledger_not_by_policy_text() -> (
    None
):
    nli = FakeNli(entailment=0.95, contradiction=0.02)
    # 5.6339% is a percentage, not the 5.6339 FX rate: code does not confirm it and the NLI model judges the sentence
    mixed = ledger_verdict("The applied rate was 5.4931 and the margin was 5.6339%.", applied_rates(), FX_RATE, nli=nli)
    assert (mixed.label, mixed.method) == ("supported", "nli")
    assert ledger_verdict("The margin was 2.4992%.", applied_rates(), nli=nli).method == "nli"
    # cited policy that repeats the number does not confirm it: the ledger does not have it
    policy = evidence("policy:1", "The applied rate is 5.4932.")
    from_policy = ledger_verdict("The applied rate was 5.4932.", applied_rates(), policy, nli=nli)
    assert (from_policy.label, from_policy.method) == ("not_enough_evidence", "numeric")


def test_a_rate_quoted_with_its_currency_pair_is_a_rate_and_not_a_money_amount() -> None:
    """ "5.6339 BRL per EUR" took the currency as if it were money, and no money column has 5.6339."""
    ok = ledger_verdict("The day's reference rate was 5.6339 BRL per EUR.", FX_RATE)
    assert (ok.label, ok.method) == ("supported", "numeric")
    wrong = ledger_verdict("The day's reference rate was 5.6340 BRL per EUR.", FX_RATE)
    assert (wrong.label, wrong.method) == ("not_enough_evidence", "numeric")
    both = ledger_verdict(
        "The applied rate was 5.4931 BRL per EUR and the reference one 5.6339 BRL per EUR.", applied_rates(), FX_RATE
    )
    assert both.label == "supported"
    paid = sql_evidence(
        ["id", "payout_amount_minor", "payout_amount_major", "payout_currency"], ["R-1", 54931, "549.31", "BRL"]
    )
    mixed = ledger_verdict("The refund was 549.31 BRL, at a rate of 5.6339 BRL per EUR.", paid, FX_RATE)
    assert mixed.label == "supported"
    # money stays exact: a refund of 549.32 BRL is not in the ledger, even with the right rate
    assert (
        ledger_verdict("The refund was 549.32 BRL, at a rate of 5.6339 BRL per EUR.", paid, FX_RATE).label
        != "supported"
    )


# ---- FX date with no origin in the ledger -------------------------------------------------------


def fx_on(day: str, rate: str = "5.4330") -> Evidence:
    return Evidence(
        id=f"fx:{day}:EUR-BRL",
        source_type="fx",
        tool="get_reference_fx",
        content=json.dumps(
            {"requested_date": day, "rate_date": day, "from_currency": "EUR", "to_currency": "BRL", "rate": rate}
        ),
        ref="fx",
        retrieved_at=NOW,
    )


def refund_rows() -> Evidence:
    return sql_evidence(
        ["kind", "applied_rate", "applied_at"],
        ["charge", "5.6679", "2026-10-15T09:12:04Z"],
        ["refund", "5.4931", "2026-10-20T14:30:00Z"],
    )


def fx_turn(day: str, *others: Evidence, question: str = "q", answer: str | None = None) -> InvestigationResult:
    """A turn whose only claim cites the FX rate of `day`."""
    fx = fx_on(day)
    text = answer or f"The reference rate was 5.4330. [{fx.id}]"
    result = make_result([claim("CL1", text, [fx.id])], [*others, fx])
    return result.model_copy(update={"question": question, "answer": text})


def test_a_rate_for_a_date_that_is_nowhere_in_the_ledger_evidence_fails_the_coherence_and_names_the_date() -> None:
    """Live, the agent asked for the FX rate of 2024-04-10, not in the ledger (the refund is from 2026-10-20)."""
    result = fx_turn("2024-04-10", refund_rows())
    issues = check_coherence(result).issues
    assert [i.rule for i in issues] == ["fx_date_origin"]
    assert "FX rate for a date with no origin in the ledger" in issues[0].message and "2024-04-10" in issues[0].message
    assert issues[0].claim_ids == ["CL1"]

    out = verify_result(result, nli=FakeNli(0.97, 0.01))
    assert out.requires_human_review is True
    assert any("2024-04-10" in item for item in out.missing_information)


def test_a_rate_for_the_date_of_a_ledger_column_passes() -> None:
    assert check_coherence(fx_turn("2026-10-20", refund_rows())).passed is True
    assert check_coherence(fx_turn("2026-10-15", refund_rows())).passed is True  # the charge date is in the ledger too


def test_the_date_may_come_from_any_date_column_of_the_ledger_api_record() -> None:
    record = api_evidence({"transaction": {"id": "TX-2048", "created_at": "2026-10-15T09:12:04Z"}})
    assert check_coherence(fx_turn("2026-10-15", record)).passed is True
    assert "fx_date_origin" in rules(fx_turn("2026-10-16", record))


def test_without_ledger_evidence_the_rule_does_not_fire() -> None:
    assert check_coherence(fx_turn("2024-04-10")).passed is True
    policy_only = evidence("policy:1", "The deadline is 2026-10-20.")
    assert check_coherence(fx_turn("2024-04-10", policy_only)).passed is True


def test_a_date_the_user_wrote_in_the_question_has_an_origin() -> None:
    result = fx_turn("2024-04-10", refund_rows(), question="What was the FX rate on 2024-04-10?")
    assert check_coherence(result).passed is True


def test_a_rate_the_answer_does_not_use_is_not_checked() -> None:
    """A wrong lookup followed by the right one: only the one the answer cites counts."""
    stray, good = fx_on("2024-04-10"), fx_on("2026-10-20")
    text = f"The reference rate was 5.4330. [{good.id}]"
    result = make_result([claim("CL1", text, [good.id])], [refund_rows(), stray, good]).model_copy(
        update={"answer": text}
    )
    assert check_coherence(result).passed is True


def test_a_rate_cited_only_in_the_answer_text_counts_as_used() -> None:
    fx = fx_on("2024-04-10")
    result = make_result([], [refund_rows(), fx]).model_copy(update={"answer": f"The rate was 5.4330 [{fx.id}]."})
    assert rules(result) == {"fx_date_origin"}


def test_a_date_written_with_slashes_in_the_question_has_an_origin() -> None:
    result = fx_turn("2024-04-10", refund_rows(), question="And the FX rate on 04/10/2024?")
    assert check_coherence(result).passed is True
    assert "fx_date_origin" in rules(fx_turn("2024-04-11", refund_rows(), question="And the FX rate on 04/10/2024?"))


def test_a_date_inside_free_text_of_the_ledger_is_not_an_origin() -> None:
    reason = sql_evidence(["id", "reason"], ["R-1", "Customer asked on 2024-04-10"], ["R-2", "2026-10-20"])
    assert rules(fx_turn("2024-04-10", reason)) == {"fx_date_origin"}


def test_the_requested_day_is_what_counts_when_the_rate_comes_from_the_previous_business_day() -> None:
    """A ledger Sunday comes back with Friday's rate: the requested day has an origin, the id's need not."""
    sunday = Evidence(
        id="fx:2026-10-16:EUR-BRL",
        source_type="fx",
        tool="get_reference_fx",
        content=json.dumps({"requested_date": "2026-10-18", "rate_date": "2026-10-16", "rate": "5.4330"}),
        ref="fx",
        retrieved_at=NOW,
    )
    text = f"The rate was 5.4330. [{sunday.id}]"
    ledger = sql_evidence(["id", "created_at"], ["R-1", "2026-10-18T10:00:00Z"])
    result = make_result([claim("CL1", text, [sunday.id])], [ledger, sunday])
    assert check_coherence(result).passed is True
