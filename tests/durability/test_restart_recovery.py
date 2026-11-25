"""The restart of a run that died: one event of the branch, an unchanged projection and the same answer.

What they guarantee, and why: a run that dies between the commit of the branch and the journal restarts from
the journal, the commit of the branch does not happen twice (the idempotency key of the sandbox), the
projection of the branch is unchanged, and the answer of the case is the same as the answer of a run that
never died, because a restart that duplicated an effect or changed the answer would be a restart that corrupts
the branch of the visitor.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.durability.journal import JournalEntry, RunJournal, Step, StepOutcome
from ledgerlens.durability.restart import restart
from ledgerlens.durability.store import JournalStore
from ledgerlens.run_context import canonical_session_id
from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand
from ledgerlens.sandbox.projector import project
from ledgerlens.sandbox.snapshot import BaseResolver
from ledgerlens.sandbox.store import FileBranchStore

SCENARIO_ID = "S01"
SESSION_ID = "Visitor-A"


@pytest.fixture(scope="module")
def base_resolver(tmp_path_factory: pytest.TempPathFactory) -> BaseResolver:
    """The resolver of the immutable base, with its own working folder outside the repository."""
    return BaseResolver(tmp_path_factory.mktemp("durability_restart_base"))


def _command() -> MutationCommand:
    """The command of the adjustment of the rate of the refund of S01, with its key."""
    return MutationCommand(
        kind="refund.apply_fx_adjustment",
        payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": "2026-11-24T00:00:00Z"},
        reason="the visitor tries another rate",
        expected_revision=0,
        idempotency_key="cmd-0001",
    )


def _commit_step(layer: BranchLayer, branch_id: str, answer: dict) -> Step:
    """The step of the run that commits the command of the branch, idempotent by the key of the sandbox."""

    def execute() -> StepOutcome:
        result = layer.commit_mutation(SESSION_ID, branch_id, _command())
        answer["hash"] = result.canonical_hash
        return StepOutcome(output_ref=result.canonical_hash, status="ok")

    return Step(
        step_id="commit-of-the-branch",
        inputs={"command": "refund.apply_fx_adjustment"},
        snapshot="snapshot-of-the-run",
        idempotency_key="cmd-0001",
        idempotent=True,
        execute=execute,
    )


def test_a_run_that_dies_between_the_commit_and_the_journal_restarts_without_duplicating(
    tmp_path: Path, base_resolver: BaseResolver
) -> None:
    """The restart re-runs the commit with the same key, and the branch does not move twice."""
    base = base_resolver(SCENARIO_ID)
    layer = BranchLayer(FileBranchStore(tmp_path / "sandbox"), base_resolver)
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    store = JournalStore(tmp_path / "session")
    answer: dict = {}
    step = _commit_step(layer, branch.branch_id, answer)

    # The run writes the intent, commits the branch and dies before it writes the result.
    store.append(
        JournalEntry(
            number=0,
            kind="intent",
            step_id=step.step_id,
            attempt=1,
            inputs_hash=step.inputs_hash,
            snapshot=step.snapshot,
            idempotency_key=step.idempotency_key,
        )
    )
    step.execute()
    events_after_crash = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
    projection_after_crash = project(base, events_after_crash)

    # The restart: the step has an intent and no result, and its effect is idempotent, so it runs again with
    # the same key, and the commit of the branch does not happen twice.
    outcome = restart(store, [step], snapshot="snapshot-of-the-run")

    events_after_restart = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
    projection_after_restart = project(base, events_after_restart)
    assert len(events_after_restart) == 1
    assert projection_after_restart.canonical_hash == projection_after_crash.canonical_hash
    assert outcome.rerun == ("commit-of-the-branch",)
    assert outcome.outputs[0].output_ref == answer["hash"]


def test_the_answer_of_a_restarted_run_is_the_answer_of_a_run_that_never_died(
    tmp_path: Path, base_resolver: BaseResolver
) -> None:
    """The outputs of the restart are the outputs of the run, reused or recomputed."""
    base = base_resolver(SCENARIO_ID)
    layer = BranchLayer(FileBranchStore(tmp_path / "sandbox"), base_resolver)
    branch = layer.fork(SESSION_ID, SCENARIO_ID).branch
    store = JournalStore(tmp_path / "session")
    answer: dict = {}
    step = _commit_step(layer, branch.branch_id, answer)

    # The run that never died: the intent, the commit and the result.
    journal = RunJournal(store)
    outcomes = journal.run([step])
    never_died = outcomes[0].output_ref

    # The restart over the same journal: the step completed, so the output is reused and nothing runs again.
    outcome = restart(store, [step], snapshot="snapshot-of-the-run")

    assert outcome.reused == ("commit-of-the-branch",)
    assert outcome.rerun == ()
    assert outcome.outputs[0].output_ref == never_died
    events = layer.store.read_events(branch.branch_id, canonical_session_id(SESSION_ID))
    assert len(events) == 1
    assert project(base, events).canonical_hash == answer["hash"]
