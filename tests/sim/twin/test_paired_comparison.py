"""The paired comparison of the twin: two policies over one stream, and every money figure recomputable.

What they guarantee, and why: (a) the digest of the arrival stream of the second run is the digest of the
first, and the second run refuses to generate a second stream, because a comparison over two streams measures
the difference between the streams and not the difference between the policies; (b) the comparison names the
cases whose decision changed, because a comparison that did not name them would be a comparison that the
reader cannot check; (c) the cost per case recomputed with `Decimal` is the number the comparison published,
and the cost per case is undefined with a reason when the denominator is zero, because a cost of zero would
say the case was free.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.sim.twin.arrivals import digest_of, generate_stream
from ledgerlens.sim.twin.compare import ComparisonRefused, compare, decide
from ledgerlens.sim.twin.config import TwinConfig


def _configs() -> tuple[TwinConfig, TwinConfig]:
    """The two configurations of the comparison: the shipped policy and the strict one."""
    base = {"seed": 42, "horizon_minutes": 480, "arrival_rate_per_hour": Decimal("6"), "slots": 2}
    return TwinConfig(**base, review_policy="shipped"), TwinConfig(**base, review_policy="strict")


def test_the_second_run_reads_the_stream_of_the_first_and_refuses_to_generate_another() -> None:
    """The digest of the stream of the comparison is the digest of the stream of the first run."""
    config_a, config_b = _configs()
    stream = generate_stream(config_a)
    comparison = compare(config_a, config_b, stream)

    assert comparison.stream_sha256 == digest_of(stream)


def test_the_comparison_names_the_cases_whose_decision_changed() -> None:
    """The cases whose decision changed are the cases the strict policy escalates and the shipped one does not."""
    config_a, config_b = _configs()
    stream = generate_stream(config_a)
    comparison = compare(config_a, config_b, stream)

    assert comparison.changed
    for decision in comparison.changed:
        assert decide(decision.kind, "strict") is True
        assert decide(decision.kind, "shipped") is False


def test_the_cost_per_case_recomputed_with_decimal_is_the_number_the_comparison_published() -> None:
    """The cost per case is the work of the reviews over the cases of the stream, recomputed."""
    config_a, config_b = _configs()
    stream = generate_stream(config_a)
    comparison = compare(config_a, config_b, stream)

    total = len(stream.arrivals)
    escalated_a = sum(1 for arrival in stream.arrivals if decide(arrival.kind, "shipped"))
    escalated_b = sum(1 for arrival in stream.arrivals if decide(arrival.kind, "strict"))
    assert comparison.cost_per_case_a == (config_a.service_time_minutes * escalated_a / total).quantize(
        Decimal("0.01")
    )
    assert comparison.cost_per_case_b == (config_b.service_time_minutes * escalated_b / total).quantize(
        Decimal("0.01")
    )
    assert comparison.cost_per_case_b > comparison.cost_per_case_a


def test_the_cost_per_case_is_undefined_with_a_reason_when_the_denominator_is_zero() -> None:
    """A stream with no cases has no cost per case, and the reason is named."""
    config_a, config_b = _configs()
    stream = generate_stream(TwinConfig(seed=42, horizon_minutes=1, arrival_rate_per_hour=Decimal("0")))
    comparison = compare(config_a, config_b, stream)

    assert comparison.cost_per_case_a is None
    assert comparison.cost_per_case_b is None
    assert "no cases" in comparison.cost_reason


def test_a_comparison_of_one_policy_with_itself_is_refused() -> None:
    """A comparison of one policy with itself measures nothing."""
    config_a, _ = _configs()
    with pytest.raises(ComparisonRefused, match="the same policy"):
        compare(config_a, config_a, generate_stream(config_a))
