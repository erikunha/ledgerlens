"""The guard of the runtime numbers: a published number names the set, the role, the denominator and the hardware.

What they guarantee, and why: the report of the latency and the report of the cost name the set they were
measured over, the role of that set, the denominator of the cases and the hardware of the machine, because a
number without the set and the denominator is a number a reader cannot check, and a number without the
hardware is a number that cannot be compared with another machine.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATENCY = ROOT / "data" / "eval" / "report_latency.md"
COST = ROOT / "data" / "eval" / "report_cost.md"


def test_the_report_of_the_latency_names_the_set_the_role_the_denominator_and_the_hardware() -> None:
    """The four things a reader needs to check the number of the latency."""
    report = LATENCY.read_text(encoding="utf-8")

    assert "eval_cases" in report
    assert "role `" in report
    assert "The denominator:" in report
    assert "The hardware:" in report


def test_the_report_of_the_cost_names_the_set_the_role_and_the_provenance_of_every_price() -> None:
    """The set, the role and the provenance of the prices of the report of the cost."""
    report = COST.read_text(encoding="utf-8")

    assert "eval_cases" in report
    assert "role `tuning`" in report
    assert "from the assumption of the maintainer" in report
    assert "never zero" in report


def test_the_report_of_the_cost_publishes_no_total_while_the_price_of_the_model_is_unknown() -> None:
    """The total of the run is not published while the price of the model is unknown."""
    report = COST.read_text(encoding="utf-8")

    assert "the total of the run is not published" in report
    assert "The cost of the review of the run:" in report
    assert "The sensitivity to the rate of the review" in report
