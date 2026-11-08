"""Claim extraction: sentences become `Claim`, each with its kind and the evidence it cites."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ledgerlens.schemas import Evidence
from ledgerlens.verify.claims import direction_in_words, extract_claims, find_amounts, has_currency_amount, has_rate

NOW = datetime(2026, 11, 8, tzinfo=UTC)


def ev(evidence_id: str, content: str) -> Evidence:
    source, _, _ = evidence_id.partition(":")
    tool = {"sql": "query_ledger", "policy": "search_policies", "calc": "calculate"}[source]
    return Evidence(id=evidence_id, source_type=source, tool=tool, content=content, ref=evidence_id, retrieved_at=NOW)


def test_amounts_in_english_format_with_currency_codes_and_symbols() -> None:
    assert [(a.value, a.unit) for a in find_amounts("It cost 1,250.00 BRL.")] == [(Decimal("1250.00"), "BRL")]
    assert [(a.value, a.unit) for a in find_amounts("It cost R$ 1,250.00 in total.")] == [(Decimal("1250.00"), "BRL")]
    assert [(a.value, a.unit) for a in find_amounts("It cost $1,250.00 in total.")] == [(Decimal("1250.00"), "USD")]
    assert [(a.value, a.unit) for a in find_amounts("The margin is 2.5%.")] == [(Decimal("2.5"), "%")]
    assert [(a.value, a.unit) for a in find_amounts("The rate was 5.6339")] == [(Decimal("5.6339"), "")]


def test_the_comma_only_groups_thousands_and_the_period_is_the_decimal_point() -> None:
    assert [a.value for a in find_amounts("It was 1,250 BRL.")] == [Decimal("1250")]
    assert [a.value for a in find_amounts("It was 1.250 BRL.")] == [Decimal("1.250")]
    assert [a.value for a in find_amounts("It was 1,234,567.89 BRL.")] == [Decimal("1234567.89")]


def test_ids_and_dates_are_not_amounts() -> None:
    assert find_amounts("TX-2048 and CB-0310 on 2026-10-05 with R-0412") == []


def test_a_date_written_in_words_or_with_slashes_is_not_an_amount() -> None:
    assert find_amounts("Paid on October 14, 2026 and opened on 11/08/2026.") == []
    assert find_amounts("Paid on 14 October 2026 and due on Nov 9 2026.") == []
    assert [(a.value, a.unit) for a in find_amounts("On October 14, 2026 they paid R$ 5.00.")] == [
        (Decimal("5.00"), "BRL")
    ]


def test_a_minus_sign_attached_to_the_number_is_kept() -> None:
    """The sign used to get lost: "-14.08" became 14.08 and the negative difference from `calculate` never matched."""
    assert [a.value for a in find_amounts("The adjustment was -14.08 BRL and R$ -3.00.")] == [
        Decimal("-14.08"),
        Decimal("-3.00"),
    ]
    assert [a.value for a in find_amounts("The math 563.39 - 549.31 gave 14.08 BRL, in 2-3 days.")] == [
        Decimal("563.39"),
        Decimal("549.31"),
        Decimal("14.08"),
        Decimal("2"),
        Decimal("3"),
    ]


def test_a_rate_is_a_decimal_of_three_places_or_more_even_with_a_currency_pair_and_never_a_percentage() -> None:
    rates = (
        "The rate was 5.4931.",
        "The rate was 5.6339.",
        "The rate was 5.6339 BRL per EUR.",
        "The rate was 5.6339 EUR",
    )
    for rate in rates:
        assert has_rate(rate) and not has_currency_amount(rate), rate
    for other in (
        "The amount was 2.90.",
        "The amount was R$ 549.31.",
        "The margin is 2.4992%.",
        "There were 5 attempts.",
    ):
        assert not has_rate(other), other
    assert has_currency_amount("The refund was 549.31 BRL, at a rate of 5.6339 BRL per EUR.")


def test_the_direction_stated_in_words() -> None:
    assert direction_in_words("The refund came in 14.08 BRL lower than expected.") == -1
    assert direction_in_words("The refund came in 14.08 BRL less.") == -1
    assert direction_in_words("The refund was 14.08 BRL below the charge.") == -1
    assert direction_in_words("The rate ended up 14.08 BRL higher.") == 1
    assert direction_in_words("The fee was 14.08 BRL more.") == 1
    assert direction_in_words("The difference was 14.08 BRL.") == 0
    assert direction_in_words("Higher in one sentence and lower in another.") == 0


def test_each_sentence_becomes_a_claim_with_its_citations() -> None:
    answer = "Refund R-0412 was issued on 2026-10-05 [sql:1]. The policy allows 14 days [policy:3]. It looks fine."
    claims = extract_claims(answer, [ev("sql:1", "x"), ev("policy:3", "y")])
    assert [c.id for c in claims] == ["CL1", "CL2", "CL3"]
    assert claims[0].text == "Refund R-0412 was issued on 2026-10-05."
    assert (claims[0].kind, claims[0].evidence_ids) == ("fact", ["sql:1"])
    assert (claims[1].kind, claims[1].evidence_ids) == ("policy", ["policy:3"])
    assert (claims[2].kind, claims[2].evidence_ids) == ("inference", [])


def test_several_ids_in_one_citation() -> None:
    claims = extract_claims("The refund is paid [sql:1, policy:2].", [ev("sql:1", "x"), ev("policy:2", "y")])
    assert claims[0].evidence_ids == ["sql:1", "policy:2"]


def test_a_number_backed_by_calculate_becomes_a_numeric_claim() -> None:
    calc = ev("calc:1", '{"operation": "difference", "result": "17.48", "formula": "566.79 - 549.31"}')
    [claim] = extract_claims("The gap is 17.48 BRL [calc:1].", [calc])
    assert claim.kind == "numeric"
    assert claim.numeric is not None
    assert (claim.numeric.expected, claim.numeric.unit, claim.numeric.calc_evidence_id) == (
        Decimal("17.48"),
        "BRL",
        "calc:1",
    )


def test_a_numeric_claim_picks_the_calculate_field_closest_to_the_stated_number() -> None:
    calc = ev("calc:2", '{"operation": "fx_gap_breakdown", "result": {"gap": "17.48", "markup": "14.08"}}')
    [claim] = extract_claims("The markup is 14.08 BRL [calc:2].", [calc])
    assert claim.numeric is not None and claim.numeric.expected == Decimal("14.08")


def test_a_direction_in_words_pairs_the_magnitude_with_the_signed_calculate_field() -> None:
    calc = ev("calc:2", '{"operation": "fx_gap_breakdown", "result": {"markup": "-14.08", "move": "3.00"}}')
    [claim] = extract_claims("The refund came in 14.08 BRL lower [calc:2].", [calc])
    assert claim.numeric is not None and claim.numeric.expected == Decimal("-14.08")


def test_a_number_without_calculate_evidence_stays_a_text_claim() -> None:
    [claim] = extract_claims("The refund was 549.31 BRL [sql:1].", [ev("sql:1", "refund 549.31")])
    assert claim.kind == "fact" and claim.numeric is None


def test_questions_and_fragments_are_not_claims() -> None:
    assert extract_claims("Anything else? Ok. Thanks!", []) == []


def test_bullets_and_lines_are_split() -> None:
    answer = "- Refund R-0412 was paid [sql:1]\n- Settlement ST-0044 was paid [sql:1]"
    claims = extract_claims(answer, [ev("sql:1", "x")])
    assert [c.text for c in claims] == ["Refund R-0412 was paid.", "Settlement ST-0044 was paid."]


def test_a_citation_after_the_full_stop_belongs_to_the_previous_sentence() -> None:
    claims = extract_claims(
        "Refund R-0412 was paid. [sql:1] The policy allows it. [policy:2]", [ev("sql:1", "x"), ev("policy:2", "y")]
    )
    assert [(c.text, c.evidence_ids) for c in claims] == [
        ("Refund R-0412 was paid.", ["sql:1"]),
        ("The policy allows it.", ["policy:2"]),
    ]


# ---- sentences that claim nothing ---------------------------------------------------------------------


def texts(answer: str) -> list[str]:
    return [c.text for c in extract_claims(answer, [ev("sql:1", "x"), ev("policy:1", "y")])]


def test_a_closing_offer_is_not_a_claim() -> None:
    """'If you wish, I can...' has nothing to check and used to come in as an unsupported claim."""
    answer = (
        "Payout ST-0002 had a net of 741.07 [sql:1]. If you wish, I can detail the fees. "
        "Should you need more information, please contact us. I can check another payout. "
        "I am available for any questions."
    )
    assert texts(answer) == ["Payout ST-0002 had a net of 741.07."]


def test_an_uncited_conclusion_or_hedge_is_not_a_claim_but_a_cited_one_is() -> None:
    answer = (
        "The refund was paid on 2026-10-20 [sql:1]. Therefore, the customer has already received the money. "
        "Maybe the merchant applied a markup. In summary, the case is resolved. "
        "It may be that the customer asked twice. Therefore, the deadline is 14 days [policy:1]."
    )
    assert texts(answer) == ["The refund was paid on 2026-10-20.", "Therefore, the deadline is 14 days."]


def test_a_conditional_statement_is_still_a_claim() -> None:
    """Only 'if you wish' is an offer: 'If the deadline expires, ...' is a policy claim."""
    answer = (
        "If the deadline expires, the case is escalated [policy:1]. If the deadline expires, the case is escalated."
    )
    assert texts(answer) == [
        "If the deadline expires, the case is escalated.",
        "If the deadline expires, the case is escalated.",
    ]


def test_an_english_closing_offer_is_not_a_claim() -> None:
    assert texts("The refund was paid [sql:1]. If you want, I can check the fees. Let me know if you need more.") == [
        "The refund was paid."
    ]


# ---- demonstratives -----------------------------------------------------------------------------------


def test_a_demonstrative_claim_takes_the_entity_of_the_previous_sentence() -> None:
    """'This payout...' reached the NLI model with no id, and a premise with several payouts did not say which one."""
    answer = "Payout ST-0002 was paid on 2026-10-14 [sql:1]. This payout had a net of 741.07 [sql:1]."
    assert texts(answer) == [
        "Payout ST-0002 was paid on 2026-10-14.",
        "This payout (ST-0002) had a net of 741.07.",
    ]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (
            "Dispute CB-0310 is open [sql:1]. This dispute is due on 2026-11-09 [sql:1].",
            "This dispute (CB-0310) is due on 2026-11-09.",
        ),
        (
            "Refund R-0720 was paid [sql:1]. This refund has an amount of 8000 [sql:1].",
            "This refund (R-0720) has an amount of 8000.",
        ),
        (
            "TX-2048 was paid in EUR [sql:1]. That transaction had a refund [sql:1].",
            "That transaction (TX-2048) had a refund.",
        ),
        # two entities of the same kind in the previous sentence: ambiguous, it stays as it came
        (
            "Payouts ST-0002 and ST-0003 were paid [sql:1]. This payout had a net of 741.07 [sql:1].",
            "This payout had a net of 741.07.",
        ),
        # no entity of the kind in the previous sentence
        (
            "Merchant M-02 received the payment [sql:1]. This payout had a net of 741.07 [sql:1].",
            "This payout had a net of 741.07.",
        ),
        # the sentence already cites the id: nothing to add
        (
            "Payout ST-0002 was paid [sql:1]. This payout ST-0002 had a net of 741.07 [sql:1].",
            "This payout ST-0002 had a net of 741.07.",
        ),
    ],
)
def test_the_demonstrative_takes_the_unambiguous_entity_of_the_previous_sentence(answer: str, expected: str) -> None:
    assert texts(answer)[-1] == expected


def test_a_chain_of_demonstratives_keeps_the_same_entity() -> None:
    answer = "Payout ST-0002 was paid [sql:1]. This payout had fees [sql:1]. This payout had a net [sql:1]."
    assert texts(answer)[-1] == "This payout (ST-0002) had a net."


def test_sentences_that_only_look_like_offers_or_hedges_stay_claims() -> None:
    """'I can't find' and 'It may be refunded' claim something; only 'I can check' and 'It may be that' do not."""
    answer = (
        "I can't find the refund [sql:1]. It may be refunded within 14 days. It may be that the customer asked. "
        "I can check another payout."
    )
    assert texts(answer) == ["I can't find the refund.", "It may be refunded within 14 days."]


# ---- citations that close the paragraph ---------------------------------------------------------------

# The answer the app returned: a two-sentence paragraph, with every citation at the end.
PARAGRAPH_ANSWER = (
    "The reference rate from EUR to BRL on 2026-10-20 was 5.6339. "
    "The difference of 17.48 BRL comes from that FX movement [api:1] [sql:1] [fx:2026-10-20:EUR-BRL] [calc:1]."
)
PARAGRAPH_EVIDENCE = [
    Evidence(
        id="api:1",
        source_type="ledger_api",
        tool="get_ledger_record",
        ref="api:1",
        retrieved_at=NOW,
        content='{"transaction": {"id": "TX-2048", "currency": "EUR"}}',
    ),
    ev("sql:1", '{"columns": ["id"], "rows": [["TX-2048"]], "row_count": 1}'),
    Evidence(
        id="fx:2026-10-20:EUR-BRL",
        source_type="fx",
        tool="get_reference_fx",
        ref="fx",
        retrieved_at=NOW,
        content='{"from_currency": "EUR", "to_currency": "BRL", "rate": "5.6339", "rate_date": "2026-10-20"}',
    ),
    ev("calc:1", '{"operation": "difference", "result": "17.48"}'),
]
CLOSING_IDS = ["api:1", "sql:1", "fx:2026-10-20:EUR-BRL", "calc:1"]


def test_a_sentence_without_citation_inherits_the_ones_that_close_its_paragraph() -> None:
    """Without this, sentence 1 had no evidence (`not_enough_evidence`) and pushed the case to review."""
    claims = extract_claims(PARAGRAPH_ANSWER, PARAGRAPH_EVIDENCE)
    assert [c.evidence_ids for c in claims] == [CLOSING_IDS, CLOSING_IDS]
    # the rate in sentence 1 is not the calculation result: it is not checked against it (`check_rates` reads it in FX)
    assert claims[0].kind == "fact" and claims[0].numeric is None
    assert claims[1].kind == "numeric"


def test_inheritance_stops_at_a_blank_line_and_at_a_bullet() -> None:
    blank = "The refund was paid in BRL.\n\nThe deadline is 14 days [policy:1]."
    assert [c.evidence_ids for c in extract_claims(blank, [ev("policy:1", "y")])] == [[], ["policy:1"]]
    bullets = "- The refund was paid in BRL.\n- The deadline is 14 days [policy:1]."
    assert [c.evidence_ids for c in extract_claims(bullets, [ev("policy:1", "y")])] == [[], ["policy:1"]]


def test_a_sentence_keeps_its_own_citation_and_only_the_closing_one_is_inherited() -> None:
    answer = "The refund was paid [sql:1]. The deadline is 14 days. The payout followed the normal flow [policy:1]."
    claims = extract_claims(answer, [ev("sql:1", "x"), ev("policy:1", "y")])
    assert [c.evidence_ids for c in claims] == [["sql:1"], ["policy:1"], ["policy:1"]]


def test_inheritance_does_not_turn_an_offer_or_an_uncited_conclusion_into_a_claim() -> None:
    answer = (
        "The refund was paid in BRL. Therefore, the customer has already received it. I can detail the fees. "
        "The deadline is 14 days [policy:1]."
    )
    assert texts(answer) == ["The refund was paid in BRL.", "The deadline is 14 days."]


def test_citations_split_by_full_stops_at_the_end_close_the_paragraph_and_are_not_sentences() -> None:
    """Four citations split by ". " became fragments and only the last one, `calc:1`, closed the paragraph."""
    answer = (
        "The reference rate from EUR to BRL on 2026-10-20 was 5.6339. "
        "The difference of 17.48 BRL comes from that FX movement [api:1]. [sql:1]. [fx:2026-10-20:EUR-BRL]. [calc:1]."
    )
    claims = extract_claims(answer, PARAGRAPH_EVIDENCE)
    assert [c.evidence_ids for c in claims] == [CLOSING_IDS, CLOSING_IDS]
    assert claims[1].text == "The difference of 17.48 BRL comes from that FX movement."


def test_a_citation_run_keeps_the_full_stop_of_the_sentence_it_closes_and_the_next_sentence_apart() -> None:
    answer = "The refund was paid [sql:1]. [policy:1]. The deadline is 14 days [policy:1]."
    claims = extract_claims(answer, [ev("sql:1", "x"), ev("policy:1", "y")])
    assert [(c.text, c.evidence_ids) for c in claims] == [
        ("The refund was paid.", ["sql:1", "policy:1"]),
        ("The deadline is 14 days.", ["policy:1"]),
    ]


def test_an_uncited_conclusion_that_states_figures_is_a_claim_when_its_paragraph_cites_evidence() -> None:
    """Dropping "Therefore, ... was 549.31" took out of the claims the numbers the answer most wants to prove."""
    answer = (
        "The refund rate was 5.4931. Therefore, the amount paid was 549.31 BRL and the customer has received it. "
        "Therefore, the customer has already received the money. The deadline is 14 days [policy:1]."
    )
    claims = extract_claims(answer, [ev("policy:1", "y")])
    assert [(c.text, c.evidence_ids) for c in claims] == [
        ("The refund rate was 5.4931.", ["policy:1"]),
        ("Therefore, the amount paid was 549.31 BRL and the customer has received it.", ["policy:1"]),
        ("The deadline is 14 days.", ["policy:1"]),
    ]


def test_an_uncited_conclusion_with_figures_and_no_citation_in_its_paragraph_is_still_not_a_claim() -> None:
    assert texts("The refund was paid in BRL. Therefore, the amount paid was 549.31 BRL.") == [
        "The refund was paid in BRL."
    ]


def test_a_conclusion_or_hedge_with_its_own_citation_is_a_claim_whatever_it_says() -> None:
    answer = (
        "Therefore, the customer has already received the money [sql:1]. Perhaps the merchant applied a markup [sql:1]."
    )
    assert texts(answer) == [
        "Therefore, the customer has already received the money.",
        "Perhaps the merchant applied a markup.",
    ]


def test_a_hedge_with_figures_is_still_not_a_claim() -> None:
    """ "Perhaps" does not claim the value: a ledger check would support a sentence that claims nothing."""
    assert texts("The refund was paid [sql:1]. Perhaps the amount was 549.31 BRL.") == ["The refund was paid."]


def test_a_sentence_that_only_points_back_without_a_figure_or_an_entity_is_not_a_claim() -> None:
    """ "This explains the difference..." repeats what earlier sentences claim and went to the NLI model, which
    contradicted it."""
    answer = "The refund was 549.31 BRL [sql:1]. This explains the smaller amount received in the refund [sql:1]."
    assert texts(answer) == ["The refund was 549.31 BRL."]
    assert texts("The refund was paid [sql:1]. This shows that the customer has already received it [sql:1].") == [
        "The refund was paid."
    ]


def test_a_sentence_that_points_back_but_adds_a_figure_or_an_entity_is_still_a_claim() -> None:
    assert texts("The refund was paid [sql:1]. This explains the difference of 14.08 BRL [sql:1].") == [
        "The refund was paid.",
        "This explains the difference of 14.08 BRL.",
    ]
    assert texts("The refund was paid [sql:1]. This shows that TX-2048 was refunded [sql:1].") == [
        "The refund was paid.",
        "This shows that TX-2048 was refunded.",
    ]
    # a verb that does not point back claims something about the case
    assert len(texts("The refund was paid [sql:1]. This happened after the deadline [sql:1].")) == 2


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_real_nli_judges_the_inherited_sentence_against_the_closing_evidence() -> None:
    from ledgerlens.schemas import Coherence, InvestigationResult
    from ledgerlens.verify import verify_result
    from ledgerlens.verify.nli import get_nli

    # without the 5.6339 rate, which code checks: sentence 1 is text and the NLI model judges it
    answer = PARAGRAPH_ANSWER.replace("was 5.6339.", "was looked up.")
    claims = extract_claims(answer, PARAGRAPH_EVIDENCE)
    result = InvestigationResult(
        session_id="s",
        question="q",
        answer=answer,
        claims=claims,
        evidence=PARAGRAPH_EVIDENCE,
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )
    verdicts = verify_result(result, nli=get_nli(False, require_real=True)).verdicts
    assert (verdicts[0].method, verdicts[0].label) == ("nli", "supported")
    assert verdicts[1].label == "supported"
