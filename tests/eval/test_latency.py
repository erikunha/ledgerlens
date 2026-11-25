"""The latency of a turn: the percentile with its method, and the denominator of the cases measured.

What they guarantee, and why: the p50 and the p95 of a known series are the expected numbers by the nearest
rank, and the denominator of the collector is the count of the cases that produced a measurement, because a
case that produced no measurement is not a case that was fast.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.eval.latency import LatencyCollector, percentile


def test_the_p50_and_the_p95_of_a_known_series_are_the_expected_numbers() -> None:
    """The nearest rank: the percentile is a value of the series, never an interpolation."""
    series = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    assert percentile(series, 50) == 50.0
    assert percentile(series, 95) == 100.0
    assert percentile(series, 90) == 90.0
    assert percentile([], 50) is None


def test_the_collector_reads_the_spans_of_a_case_and_counts_the_cases_it_measured() -> None:
    """The end to end of a case is the sum of its stages, and the denominator is the count of the cases."""
    collector = LatencyCollector()
    collector.add_case(
        [
            {"name": "triage", "elapsed_ms": 10.0},
            {"name": "agent", "elapsed_ms": 40.0},
            {"name": "verify", "elapsed_ms": 10.0},
        ]
    )
    collector.add_case(
        [
            {"name": "triage", "elapsed_ms": 20.0},
            {"name": "agent", "elapsed_ms": 80.0},
            {"name": "verify", "elapsed_ms": 20.0},
        ]
    )
    # A case that produced no measurement is not counted.
    collector.add_case([{"name": "something_else", "elapsed_ms": 5.0}])

    assert collector.denominator == 2
    summary = collector.summary()
    assert summary["method"] == "nearest_rank"
    assert summary["denominator"] == 2
    assert summary["end_to_end"]["p50"] == 60.0
    assert summary["end_to_end"]["p95"] == 120.0
    assert summary["per_stage"]["agent"]["p50"] == 40.0
    assert summary["per_stage"]["triage"]["p95"] == 20.0
