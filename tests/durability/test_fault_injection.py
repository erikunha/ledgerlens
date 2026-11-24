"""The fault injection of a run: the same answer over every named kill point, and no duplicated event.

What they guarantee, and why: a run is killed at every named point of the fixture of the kill points, and
every kill recovers with the same answer of the case and no duplicated event of the branch, because a recovery
that was never exercised is a recovery that does not exist, and a kill that duplicated an effect would corrupt
the branch of the visitor.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.durability.journal import RunJournal, Step, StepOutcome
from ledgerlens.durability.restart import restart
from ledgerlens.durability.store import JournalStore
from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import FileBranchStore

SCENARIO_ID = "S01"
SESSION_ID = "Visitor-A"
KILL_POINTS = Path(__file__).resolve().parent / "fixtures" / "kill_points.json"


@pytest.fixture(scope="module")
def base_resolver(tmp_path_factory: pytest.TempPathFactory) -> BaseResolver:
    """The resolver of the immutable base, with its own working folder outside the repository."""
    return BaseResolver(tmp_path_factory.mktemp("durability_kill_base"))


def _kill_points() -> list[str]:
    """The named points at which the run is killed, from the fixture."""
    data = json.loads(KILL_POINTS.read_text(encoding="utf-8"))
    return [str(point["id"]) for point in data["kill_points"]]


def _steps(layer: BranchLayer, branch_id: str) -> list[Step]:
    """The steps of the run: the commit of the branch and the read of the projection."""

    def commit() -> StepOutcome:
        result = layer.commit_mutation(
            SESSION_ID,
            branch_id,
            MutationCommand(
                kind="refund.apply_fx_adjustment",
                payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": "2026-11-24T00:00:00Z"},
                reason="the visitor tries another rate",
                expected_revision=0,
                idempotency_key="cmd-0001",
            ),
        )
        return StepOutcome(output_ref=result.canonical_hash, status="ok")

    def read() -> StepOutcome:
        events = layer.store.read_events(branch_id, canonical_session_id(SESSION_ID))
        return StepOutcome(output_ref=f"{len(events)} event(s)", status="ok")

    return [
        Step(
            step_id="commit-of-the-branch",
            inputs={"command": "refund.apply_fx_adjustment"},
            snapshot="snapshot-of-the-run",
            idempotency_key="cmd-0001",
            idempotent=True,
            execute=commit,
        ),
        Step(
            step_id="read-of-the-branch",
            inputs={"branch": branch_id},
            snapshot="snapshot-of-the-run",
            idempotent=True,
            idempotency_key="cmd-0002",
            execute=read,
        ),
    ]


def test_every_named_kill_recovers_with_the_same_answer_and_no_duplicated_event(
    tmp_path: Path, base_resolver: BaseResolver
) -> None:
    """Every kill point recovers, and the answer of the case is the same over every one of them."""
    answers: dict[str, list[str]] = {}
    for point in _kill_points():
        work = tmp_path / point
        layer = BranchLayer(FileBranchStore(work / "sandbox"), base_resolver)
        branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
        store = JournalStore(work / "session")
        steps = _steps(layer, branch.branch_id)

        def kill(name: str, *, _point: str = point) -> None:
            if name == _point:
                raise RuntimeError(f"the run is killed at {_point}")

        with pytest.raises(RuntimeError, match="the run is killed"):
            RunJournal(store).run(steps, on_point=kill)

        outcome = restart(store, steps, snapshot="snapshot-of-the-run")
        answers[point] = [output.output_ref for output in outcome.outputs]

        events = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
        assert len(events) == 1, f"the kill at {point} duplicated the event of the branch"

    # The answer of the case is the same over every named kill point.
    assert len({tuple(answer) for answer in answers.values()}) == 1
