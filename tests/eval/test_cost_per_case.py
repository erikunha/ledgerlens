"""The cost of a turn in the report: the total refused when the price is unknown, and the case a cap cut.

What they guarantee, and why: the report refuses to publish a total when the price of the model is unknown,
because an unknown price is unknown and never zero, and a case whose turn a cap cut is named as cut and not
as a wrong answer, because a case that was cut did not answer wrong, it was cut.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.eval.run import _cost_of

ROWS = [
    {
        "case": "EC-01",
        "variant": "C",
        "usage": {"price_known": False, "cut_by": None, "observed_cost_usd": None, "estimated_cost_usd": None},
    },
    {
        "case": "EC-02",
        "variant": "C",
        "usage": {
            "price_known": False,
            "cut_by": "max_model_calls",
            "observed_cost_usd": None,
            "estimated_cost_usd": None,
        },
    },
    {"case": "EC-01", "variant": "A", "usage": None},
]


def test_the_report_refuses_to_publish_a_total_when_the_price_is_unknown() -> None:
    """The total of the run is nothing when the price is unknown, and the reason names the missing pricing."""
    cost = _cost_of(ROWS)

    assert cost["total_cost_usd"] is None
    assert cost["reason"] is not None
    assert "unknown" in cost["reason"]
    assert "never zero" in cost["reason"]


def test_a_case_that_a_cap_cut_is_named_as_cut_and_not_as_a_wrong_answer() -> None:
    """The case a cap cut is in the list of the cut cases, and the report says it was cut."""
    cost = _cost_of(ROWS)

    assert cost["cut_by_cap"] == ["EC-02"]

