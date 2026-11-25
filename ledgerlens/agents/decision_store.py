"""The store of the routing decisions: a decision is written once and never changed.

Why the store refuses a second write: the decision of a run is the fact of what was decided, and a fact that
can be rewritten is not a fact. A run whose decision changed in the middle is a run that can be read as two
runs, and the store refuses the second write of the same decision so that the decision of a run is one
decision.

Why the decision is readable after the run ended: the decision is the metadata of the trace, and a reader of
the run reads what was decided after the run ended. The store keeps the decision so that the reading does not
depend on the run still being alive.
"""

from __future__ import annotations

from ledgerlens.agents.routing import RoutingDecision


class DecisionStoreError(Exception):
    """The decision cannot be written or read, and the message says why."""


class DecisionStore:
    """The store of the routing decisions of the runs.

    The store is in memory, because the decision of a run is the metadata of the trace of the run and it lives
    as long as the run is read. A decision is written once, under the case and the slot it was decided for, and
    a second write of the same decision is refused.
    """

    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], RoutingDecision] = {}

    def write(self, slot: str, decision: RoutingDecision) -> None:
        """Writes the decision of a slot of a run, and refuses a second write of the same decision.

        Why the key is the case and the slot: the decision of a run is one decision per slot, and a second
        write of the same slot of the same case is the decision changing in the middle of the run.
        """
        key = (decision.case_id, slot)
        if key in self._decisions:
            raise DecisionStoreError(
                f"the decision of the slot {slot} of the case {decision.case_id} was already written, and a "
                "decision is written once and never changed"
            )
        self._decisions[key] = decision

    def read(self, case_id: str, slot: str) -> RoutingDecision | None:
        """Reads the decision of a slot of a run, after the run ended, or None when no decision was written."""
        return self._decisions.get((case_id, slot))
