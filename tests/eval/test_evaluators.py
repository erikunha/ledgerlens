"""Evaluators: correctness, groundedness and the four `openevals` trajectory modes.

What they guarantee, and why: (a) the tool trace becomes one message per call, because calls in the same
message compare as a group and hide the order; (b) each mode (`strict`, `unordered`, `subset`, `superset`)
answers as its name promises on the same reference; (c) only tool names count, arguments are left out;
(d) correctness measures the share of expected facts that show up in the answer, with thousands separators
and minor units read; (e) groundedness measures the share of supported claims; (f) the evaluators work with
no key and no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.eval.evaluators import (
    TRAJECTORY_MODES,
    calls_to_messages,
    correctness,
    groundedness,
    reference_messages,
    trace_to_messages,
    trajectory_evaluator,
    verdict_match,
    verification_summary,
)
from ledgerlens.schemas import ToolCallRecord

REFERENCE = ["query_ledger", "search_policies", "calculate"]


def outputs_for(tools: list[str]) -> dict:
    return {"trajectory": calls_to_messages([(name, {"x": 1}) for name in tools])}


def score(mode: str, tools: list[str]) -> float:
    evaluator = trajectory_evaluator(mode)
    result = evaluator(outputs=outputs_for(tools), reference_outputs={"trajectory": reference_messages(REFERENCE)})
    return result["score"]


def test_the_modes_are_the_four_of_the_evaluation_design() -> None:
    assert TRAJECTORY_MODES == ("strict", "unordered", "subset", "superset")


def test_each_call_is_its_own_assistant_message() -> None:
    messages = calls_to_messages([("query_ledger", {"question": "q"}), ("calculate", {"operation": "difference"})])
    assistants = [m for m in messages if m["role"] == "assistant"]
    assert [len(m["tool_calls"]) for m in assistants] == [1, 1]
    assert [m["role"] for m in messages] == ["assistant", "tool", "assistant", "tool"]
    assert assistants[0]["tool_calls"][0]["function"]["name"] == "query_ledger"


def test_the_tool_trace_converts_in_order() -> None:
    trace = [
        ToolCallRecord(step=1, tool="query_ledger", input={"question": "q"}, ok=True, duration_ms=1),
        ToolCallRecord(step=2, tool="calculate", input={}, ok=False, error_code="X", duration_ms=1),
    ]
    names = [m["tool_calls"][0]["function"]["name"] for m in trace_to_messages(trace) if m["role"] == "assistant"]
    assert names == ["query_ledger", "calculate"]


@pytest.mark.parametrize(
    ("mode", "tools", "expected"),
    [
        ("strict", REFERENCE, 1.0),
        ("strict", list(reversed(REFERENCE)), 0.0),
        ("strict", REFERENCE[:2], 0.0),
        ("strict", [*REFERENCE, "recall_cases"], 0.0),
        ("unordered", list(reversed(REFERENCE)), 1.0),
        ("unordered", REFERENCE[:2], 0.0),
        ("unordered", [*REFERENCE, "recall_cases"], 0.0),
        ("subset", REFERENCE[:2], 1.0),
        ("subset", [], 1.0),
        ("subset", [*REFERENCE, "recall_cases"], 0.0),
        ("superset", [*REFERENCE, "recall_cases"], 1.0),
        ("superset", REFERENCE[:2], 0.0),
    ],
)
def test_trajectory_modes(mode: str, tools: list[str], expected: float) -> None:
    assert score(mode, tools) == expected


def test_the_feedback_key_names_the_mode() -> None:
    result = trajectory_evaluator("subset")(
        outputs=outputs_for(REFERENCE), reference_outputs={"trajectory": reference_messages(REFERENCE)}
    )
    assert result["key"] == "trajectory_subset_match"


def test_arguments_do_not_count_only_tool_names() -> None:
    evaluator = trajectory_evaluator("strict")
    other_args = {"trajectory": calls_to_messages([(name, {"y": 2}) for name in REFERENCE])}
    reference = {"trajectory": reference_messages(REFERENCE)}
    assert evaluator(outputs=other_args, reference_outputs=reference)["score"] == 1.0


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(ValueError):
        trajectory_evaluator("fuzzy")


def test_correctness_is_the_share_of_expected_facts_in_the_answer() -> None:
    reference = {"facts": ["549.31", "17.48", "2026-10-20", "TX-2048"]}
    full = correctness(
        outputs={"answer": "TX-2048: refund 549.31, difference 17.48 on 2026-10-20."}, reference_outputs=reference
    )
    half = correctness(outputs={"answer": "TX-2048 refunded at 549.31"}, reference_outputs=reference)
    none = correctness(outputs={"answer": "I do not know."}, reference_outputs=reference)
    assert (full["score"], half["score"], none["score"]) == (1.0, 0.5, 0.0)
    assert full["key"] == "correctness"


def test_correctness_accepts_a_currency_symbol_before_the_amount() -> None:
    result = correctness(outputs={"answer": "The refund was R$549.31."}, reference_outputs={"facts": ["549.31"]})
    assert result["score"] == 1.0


def test_correctness_does_not_match_inside_a_longer_number() -> None:
    result = correctness(outputs={"answer": "The amount was 1549.317."}, reference_outputs={"facts": ["549.31"]})
    assert result["score"] == 0.0


def test_groundedness_is_the_share_of_supported_claims() -> None:
    labels = ["supported", "supported", "contradicted", "not_enough_evidence"]
    result = groundedness(outputs={"verdicts": labels})
    assert result["key"] == "groundedness" and result["score"] == 0.5


def test_groundedness_without_claims_is_zero_and_says_so() -> None:
    result = groundedness(outputs={"verdicts": []})
    assert result["score"] == 0.0 and "claims" in result["comment"]


# ---- correctness: amounts, dates and ids written another way --------------------------------------------


def _hit(answer: str, *facts: str) -> float:
    return correctness(outputs={"answer": answer}, reference_outputs={"facts": list(facts)})["score"]


@pytest.mark.parametrize(
    ("answer", "fact"),
    [
        ("Both charges were USD 49.90.", "4990"),  # minor units expected, major units in the answer
        ("The net payout was BRL 29,992.87.", "29992.87"),  # thousands separator
        ("The net payout was BRL 29,992.87.", "2999287"),
        ("Net payout was $29,992.87.", "29992.87"),
        ("The amount was R$1,234.56.", "1234.56"),
        ("The payout was 2999287 cents.", "29992.87"),  # minor units in the answer, major units expected
        ("The limit is BRL 8,000.00.", "8000"),
        ("The difference is 0.00.", "0.00"),
    ],
)
def test_correctness_normalizes_amounts(answer: str, fact: str) -> None:
    assert _hit(answer, fact) == 1.0


@pytest.mark.parametrize(
    ("answer", "fact"),
    [
        ("The amount was 1549.317.", "549.31"),
        ("There were 80 transactions.", "8000"),  # a whole number with no decimals is not a major-unit amount
        ("The amount was USD 49.91.", "4990"),
        ("The amount was BRL 12,992.87.", "29992.87"),
        ("Code TX-2048 opened.", "2048"),  # a number inside an id is not an amount
        ("The amount was 29.992,87.", "29992.87"),  # a comma decimal is not read
    ],
)
def test_correctness_does_not_invent_matches(answer: str, fact: str) -> None:
    assert _hit(answer, fact) == 0.0


@pytest.mark.parametrize(
    ("answer", "fact"),
    [
        ("Refund on 10/20/2026.", "2026-10-20"),
        ("Refund on 2026-10-20.", "2026-10-20"),
        ("Refund on October 20, 2026.", "2026-10-20"),
        ("Refund on 20 October 2026.", "2026-10-20"),
        ("Transaction tx-2048 was captured.", "TX-2048"),
        ("The stage is evidence requested.", "evidence_requested"),
        ("The stage is evidence_requested.", "evidence_requested"),
    ],
)
def test_correctness_normalizes_dates_and_ids(answer: str, fact: str) -> None:
    assert _hit(answer, fact) == 1.0


def test_correctness_keeps_a_different_date_and_id_apart() -> None:
    assert _hit("Refund on 10/21/2026.", "2026-10-20") == 0.0
    assert _hit("Refund on October 21, 2026.", "2026-10-20") == 0.0
    assert _hit("Transaction TX-20480 was captured.", "TX-2048") == 0.0


# ---- trajectory with declared equivalence --------------------------------------------------------------

LOOKUP_GROUPS = [["get_ledger_record", "query_ledger"]]


def equiv_score(mode: str, used: list[str], expected: list[str], groups: list[list[str]] | None) -> float:
    reference = {"trajectory": reference_messages(expected), "equivalent_tools": groups or []}
    return trajectory_evaluator(mode, equivalent=True)(outputs=outputs_for(used), reference_outputs=reference)["score"]


def test_the_strict_mode_stays_exact_for_a_record_lookup() -> None:
    reference = {"trajectory": reference_messages(["get_ledger_record"]), "equivalent_tools": LOOKUP_GROUPS}
    assert (
        trajectory_evaluator("strict")(outputs=outputs_for(["query_ledger"]), reference_outputs=reference)["score"]
        == 0.0
    )


@pytest.mark.parametrize("mode", ["strict", "unordered"])
def test_the_equivalent_mode_accepts_a_declared_substitution(mode: str) -> None:
    assert equiv_score(mode, ["query_ledger"], ["get_ledger_record"], LOOKUP_GROUPS) == 1.0


@pytest.mark.parametrize("mode", ["strict", "unordered"])
def test_the_equivalent_mode_refuses_a_substitution_nobody_declared(mode: str) -> None:
    assert equiv_score(mode, ["query_ledger"], ["get_ledger_record"], None) == 0.0
    assert equiv_score(mode, ["search_policies"], ["get_ledger_record"], LOOKUP_GROUPS) == 0.0


def test_the_equivalent_mode_still_counts_missing_and_extra_calls() -> None:
    assert equiv_score("strict", ["query_ledger", "calculate"], ["get_ledger_record"], LOOKUP_GROUPS) == 0.0
    assert equiv_score("strict", [], ["get_ledger_record"], LOOKUP_GROUPS) == 0.0


def test_the_equivalent_feedback_key_is_separate_from_the_exact_one() -> None:
    reference = {"trajectory": reference_messages(["calculate"]), "equivalent_tools": []}
    result = trajectory_evaluator("unordered", equivalent=True)(
        outputs=outputs_for(["calculate"]), reference_outputs=reference
    )
    assert result["key"] == "trajectory_equivalent_unordered_match"


# ---- verification: predicted verdict against the expected one -------------------------------------------


def test_verdict_match_compares_the_predicted_label_with_the_expected_one() -> None:
    ok = verdict_match(outputs={"verdict": "supported"}, reference_outputs={"verdict": "supported"})
    bad = verdict_match(outputs={"verdict": "supported"}, reference_outputs={"verdict": "contradicted"})
    assert (ok["score"], bad["score"]) == (1.0, 0.0) and ok["key"] == "verdict_match"
    assert verdict_match(outputs=None, reference_outputs={"verdict": "supported"})["score"] == 0.0


def test_the_summary_has_contradiction_recall_and_false_positive_rate() -> None:
    pairs = [
        ("contradicted", "contradicted"),
        ("contradicted", "supported"),  # a planted contradiction that got through: lowers recall
        ("supported", "contradicted"),  # a false accusation: raises the false positive rate
        ("supported", "supported"),
        ("supported", "supported"),
        ("not_enough_evidence", "not_enough_evidence"),
    ]
    summary = verification_summary([(predicted, expected) for expected, predicted in pairs])
    assert summary["contradiction_recall"] == 0.5
    assert summary["false_positive_rate"] == pytest.approx(1 / 3)
    assert summary["accuracy"] == pytest.approx(4 / 6)
    assert summary["planted"] == 2 and summary["supported"] == 3


def test_a_missing_prediction_counts_as_a_miss_not_as_a_crash() -> None:
    summary = verification_summary([(None, "contradicted"), ("supported", "supported")])
    assert summary["contradiction_recall"] == 0.0 and summary["accuracy"] == 0.5
