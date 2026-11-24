"""The report of a run of the causal engine: the known, the unknown and the unsupported claims, in text.

Why a difference without its two values is not a result: a report that says "the cost went up" without the
two values is a report a reader cannot check, so every amount of the report carries the value before, the
value after and the difference, and the difference recomputes exactly with `Decimal`, because the values are
`Decimal` and the subtraction is exact.

Why every sentence of cause names the simulation: the result of an intervention is a statement about the
synthetic world of the repository, and a sentence of cause that did not name the simulation would read as a
statement about the world outside it. No sentence of the report says what a merchant outside the simulation
received, because the engine knows nothing about a merchant outside the simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from ledgerlens.causal.engine import CausalResult, Sensitivity

__all__ = ["render", "render_sensitivity"]

_HEADER = (
    "Every value of this report is a value of the simulation, "
    "and no value of this report is a prediction for a merchant outside the simulation."
)


def _difference_line(label: str, before: Decimal, after: Decimal) -> str:
    """One amount of the report: the two values and the difference, which recomputes exactly."""
    return f"- {label}: before {before}, after {after}, difference {after - before}"


def _plain(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value) if value else "(none)"
    return str(value)


def _node_lines(node: str, before: Any, after: Any) -> list[str]:
    """The lines of one node of the report: one line per amount that changed, and the rest named unchanged."""
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        lines: list[str] = []
        unchanged: list[str] = []
        for key in before:
            if before[key] == after[key]:
                unchanged.append(str(key))
            elif isinstance(before[key], Decimal) and isinstance(after[key], Decimal):
                lines.append(_difference_line(f"{node} {key}", before[key], after[key]))
            else:
                lines.append(f"- {node} {key}: before {_plain(before[key])}, after {_plain(after[key])}")
        if unchanged:
            lines.append(f"  (the amounts of {node} that did not change: {', '.join(unchanged)})")
        return lines
    if isinstance(before, Decimal) and isinstance(after, Decimal):
        return [_difference_line(node, before, after)]
    return [f"- {node}: before {_plain(before)}, after {_plain(after)}"]


def render(result: CausalResult) -> str:
    """The report of a run: the intervention, the known, the unknown, the claims and the unchanged."""
    lines = ["Causal report of a simulation run.", _HEADER]
    for intervention in result.interventions:
        day = f" on {intervention.day}" if intervention.day is not None else ""
        lines.append(f"Intervention: {intervention.target}{day}, do_value {_plain(intervention.do_value)}")
    lines.append(f"Exogenous digest: {result.exogenous_digest}")
    assumptions = "; ".join(result.assumptions) if result.assumptions else "(none)"
    lines.append(f"Assumptions: {assumptions}")
    if result.covered_periods:
        named = ", ".join(f"{start} to {end}" for start, end in result.covered_periods)
        lines.append(f"Covered periods: {named}")

    lines.append("Changed nodes, explained by the registry of the simulation:")
    if result.changed:
        for change in result.changed:
            lines.extend(_node_lines(change.node, change.before, change.after))
    else:
        lines.append("- (no node of the registry changed)")

    if result.unknown:
        lines.append("Unknown changes, with the missing edge named:")
        for change in result.unknown:
            for line in _node_lines(change.node, change.before, change.after):
                lines.append(f"{line}; status {change.status}")
            lines.append(f"  {change.reason}")

    if result.unsupported_claims:
        lines.append("Unsupported causal claims:")
        for claim in result.unsupported_claims:
            lines.append(f"- {claim}")

    lines.append(f"Unchanged nodes: {', '.join(result.unchanged)}")
    return "\n".join(lines) + "\n"


def render_sensitivity(measured: Sensitivity) -> str:
    """The report of the sensitivity: the two assumptions and the movement of the nodes between the two runs.

    The movement is a measurement of the assumption and not an interval of confidence: the two runs share the
    base, the exogenous stream and the intervention, and they differ only in the assumption.
    """
    lines = [
        "Sensitivity report of a simulation run.",
        _HEADER,
        f"First assumption: {'; '.join(measured.first.assumptions)}",
        f"Second assumption: {'; '.join(measured.second.assumptions)}",
        "Movement of the nodes between the two runs, which is a measurement of the assumption:",
    ]
    if measured.movement:
        for change in measured.movement:
            lines.extend(_node_lines(change.node, change.before, change.after))
    else:
        lines.append("- (no node moved between the two runs)")
    return "\n".join(lines) + "\n"
