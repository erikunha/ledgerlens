"""The result of an exercise of the laboratory: what was attacked, which layer answered and what is still open.

Why the result carries six things: the surface that was attacked, the boundary that was expected, the reference
of the trace, the actions that were blocked with the reason of the layer that stopped them, and the risk that
is still open. The open risk is not decoration: an exercise that passed says that the attack it holds did not
pass, and the risk that is still open names what the exercise did not settle.

Why the count of the unauthorized actions is computed and not written: a count of zero that was written by hand
is a claim, and a count of zero that the test computes is evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["BlockedAction", "ExerciseResult"]


@dataclass(frozen=True)
class BlockedAction:
    """An action that an exercise attempted and a layer of the repository stopped.

    Why the action carries the layer and the reason: a reader of the result has to see which layer answered
    and why, and a blocked action that names neither is a claim and not a measurement.
    """

    action: str
    layer: str
    reason: str


@dataclass(frozen=True)
class ExerciseResult:
    """The result of an exercise: the six fields, and the count of the actions that were not blocked.

    Why the unauthorized actions are a field of the result: the count of the laboratory is the sum of the
    counts of the exercises, and a result that does not carry its count makes the sum a reading of the code
    instead of a reading of the results.
    """

    exercise_id: str
    surface: str
    expected_boundary: str
    trace_ref: str
    blocked_actions: tuple[BlockedAction, ...]
    open_risk: str
    unauthorized_actions: int = 0
    events: tuple[object, ...] = field(default_factory=tuple)

    @property
    def held(self) -> bool:
        """Whether every action of the exercise was blocked by a layer of the repository."""
        return self.unauthorized_actions == 0 and bool(self.blocked_actions)
