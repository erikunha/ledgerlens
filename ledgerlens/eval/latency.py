"""The latency of a turn: the names of the stages, the percentile with its method, and the collector of the spans.

Why the percentile names the method it uses: a percentile without its method is a number a reader cannot
recompute, and two methods give two numbers over the same series. The method of the repository is the nearest
rank: the percentile of a series is the value of the case at the rank that the percentile names, rounded up,
so the p50 of a series is a value of the series and never an interpolation between two cases.

Why the denominator is the count of the cases that produced a measurement: a case that produced no measurement
is not a case that was fast, and a denominator that counted it would make the latency of the set look better
than it is. The collector counts the cases it measured, and the report names the count.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["STAGES", "LatencyCollector", "percentile"]

# The stages of a turn, in the order of the run: the triage, the loop of the agent, the verification and the
# escalation. The end to end latency of a turn is the sum of the stages of the turn.
STAGES = ("triage", "agent", "verify", "escalation")

# The method of the percentile of the repository: the nearest rank, so the percentile is a value of the series.
METHOD = "nearest_rank"


def percentile(series: Sequence[float], pct: float) -> float | None:
    """The percentile of the series by the nearest rank, or None when the series is empty.

    The rank of the percentile is the ceiling of the percentile over the count, and the value is the value of
    the case at that rank, so the p50 and the p95 of a series are values of the series and never an
    interpolation between two cases.
    """
    if not series:
        return None
    ordered = sorted(series)
    rank = max(1, math.ceil(len(ordered) * pct / 100))
    return ordered[rank - 1]


@dataclass
class LatencyCollector:
    """The collector of the latency of the cases of a run: the end to end and the per stage, with the denominator.

    The collector reads the spans of the trace of each case and keeps the latency of the case end to end and
    of each stage. A case that produced no measurement is not counted, and the denominator of the report is
    the count of the cases that produced a measurement.
    """

    end_to_end: list[float] = field(default_factory=list)
    per_stage: dict[str, list[float]] = field(default_factory=lambda: {stage: [] for stage in STAGES})

    def add_case(self, spans: Sequence[Any]) -> None:
        """The latency of one case, read from the spans of its trace.

        The spans of a case carry the name of the stage and the milliseconds of the stage, as the objects of
        the tracer or as mappings. A case whose spans carry no stage of the run is a case that produced no
        measurement, and it is not counted.
        """
        stages: dict[str, float] = {}
        for span in spans:
            if isinstance(span, Mapping):
                name = str(span.get("name", ""))
                elapsed = span.get("latency_ms", span.get("elapsed_ms"))
            else:
                name = str(getattr(span, "name", ""))
                elapsed = getattr(span, "latency_ms", None)
            if name in STAGES and isinstance(elapsed, (int, float)):
                stages[name] = stages.get(name, 0.0) + float(elapsed)
        if not stages:
            return
        for stage, elapsed in stages.items():
            self.per_stage[stage].append(elapsed)
        self.end_to_end.append(sum(stages.values()))

    @property
    def denominator(self) -> int:
        """The count of the cases that produced a measurement, and never the count of the cases of the set."""
        return len(self.end_to_end)

    def summary(self) -> dict[str, Any]:
        """The p50 and the p95 of the end to end and of each stage, with the method and the denominator."""
        return {
            "method": METHOD,
            "denominator": self.denominator,
            "end_to_end": {"p50": percentile(self.end_to_end, 50), "p95": percentile(self.end_to_end, 95)},
            "per_stage": {
                stage: {"p50": percentile(values, 50), "p95": percentile(values, 95)}
                for stage, values in self.per_stage.items()
            },
        }
