"""The report of a run of the twin: every figure carries the assumptions that produced it.

Why every figure carries the assumptions: a figure of the twin is a number about the synthetic world it
simulated, and a number without its assumptions is a number that a reader would take for a measurement of a
real operation. The assumptions are part of the number and not a footnote of it.

Why the report never says that a policy saved money in a real operation: the twin simulates a synthetic
world, and a comparison of two policies over it is a difference inside that world. A report that read as a
claim about a real operation would be a false claim, and the twin exists to avoid false claims.
"""

from __future__ import annotations

from typing import Any

from ledgerlens.sim.twin.compare import Comparison
from ledgerlens.sim.twin.manifest import TwinManifest
from ledgerlens.sim.twin.queue import STEADY_STATE

__all__ = ["render_report"]


def render_report(manifest: TwinManifest, comparison: Comparison | None = None) -> dict[str, Any]:
    """The report of a run of the twin: the figures of the run, each with the assumptions that produced it.

    Why the report names the run every figure came from: a reader of the report checks a figure against the
    run that produced it, and not only against the total of the report.
    """
    assumptions = list(manifest.assumptions)
    figures: list[dict[str, Any]] = [
        {
            "figure": "the condition of the run",
            "value": manifest.label,
            "run": manifest.stream_sha256,
            "assumptions": assumptions,
        },
    ]
    if manifest.label == STEADY_STATE:
        figures.append(
            {
                "figure": "the queue drained over the horizon",
                "value": True,
                "run": manifest.stream_sha256,
                "assumptions": assumptions,
            }
        )
    else:
        figures.append(
            {
                "figure": "the throughput of the run",
                "value": None,
                "reason": "the queue never drains, and the throughput of such a run is a property of the horizon "
                "and not of the system",
                "run": manifest.stream_sha256,
                "assumptions": assumptions,
            }
        )
    if comparison is not None:
        figures.append(
            {
                "figure": "the cases whose decision changed between the two policies",
                "value": len(comparison.changed),
                "run": comparison.stream_sha256,
                "assumptions": assumptions,
            }
        )
        pairs = ((comparison.policy_a, comparison.cost_per_case_a), (comparison.policy_b, comparison.cost_per_case_b))
        for name, cost in pairs:
            figures.append(
                {
                    "figure": f"the cost per case of the policy {name}",
                    "value": None if cost is None else str(cost),
                    "reason": comparison.cost_reason if cost is None else "",
                    "run": comparison.stream_sha256,
                    "assumptions": assumptions,
                }
            )
    return {
        "manifest": manifest.to_dict(),
        "figures": figures,
        "note": "every figure of this report is a number about the synthetic world the twin simulated, with the "
        "assumptions that produced it, and never a statement about a real operation",
    }
