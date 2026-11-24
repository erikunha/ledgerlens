"""The report of the twin: every figure carries the assumptions, and no sentence claims a saving in a real operation.

What they guarantee, and why: (a) every figure of the report carries the reference to the run it came from
and the assumptions that produced it, because a figure without its assumptions is a figure that a reader
would take for a measurement of a real operation; (b) the report holds no sentence that claims a saving or a
loss in a real operation, because the twin simulates a synthetic world, and a report that read as a claim
about a real operation would be a false claim.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.twin.compare import compare
from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.report import render_report
from ledgerlens.sim.twin.run import run_twin

ROOT = Path(__file__).resolve().parents[3]


def _report() -> dict:
    """The report of a run of the twin, with the comparison of the two policies."""
    base = {"seed": 42, "horizon_minutes": 480, "arrival_rate_per_hour": Decimal("6"), "slots": 2}
    config_a = TwinConfig(**base, review_policy="shipped")
    config_b = TwinConfig(**base, review_policy="strict")
    run = run_twin(config_a, truth_path=ROOT / "data" / "scenarios.json", commit="abc123")
    comparison = compare(config_a, config_b, run.stream)
    return render_report(run.manifest, comparison)


def test_every_figure_of_the_report_carries_the_run_and_the_assumptions() -> None:
    """A figure without its assumptions is a figure that a reader would take for a measurement."""
    report = _report()

    assert report["figures"]
    for figure in report["figures"]:
        assert figure["run"], f"the figure {figure['figure']} names no run"
        assert figure["assumptions"], f"the figure {figure['figure']} names no assumptions"


def test_the_report_holds_no_sentence_that_claims_a_saving_in_a_real_operation() -> None:
    """The report is a number about the synthetic world, and never a statement about a real operation."""
    report = _report()
    text = str(report).lower()

    assert "saved" not in text
    assert "real operation" not in text or "never a statement about a real operation" in text
    assert "synthetic world" in text
