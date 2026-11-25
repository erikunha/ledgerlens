"""The property tests of the branch: the invariants over sequences of commands nobody wrote by hand.

Why the property tests exist: the tests of the folder prove the rules of the branch one command at a time, and a
rule that holds for one command can break under a sequence. The properties of the branch are about the sequence:
the revision is the count of the events, the canonical hash is reproduced from the events alone, and a command
that is refused changes neither the revision nor the hash. The sequences come from the seeded generator of
`tests/sandbox/sequences.py`, and the seed of every case is in the message of a failure, so a red case is a case
that can be replayed.
"""

from __future__ import annotations

import pytest

from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationRejected
from ledgerlens.sandbox.projector import project
from ledgerlens.sandbox.snapshot import BaseResolver
from tests.sandbox.sequences import (
    OUTCOME_COMMIT,
    OUTCOME_PREVIEW,
    OUTCOME_REFUSED,
    OUTCOME_RESET,
    command_sequence,
)

# The seeded scenarios of the property tests, and the seeds of the cases. The seeds are few and fixed, so the
# suite is deterministic and a failure names a seed that replays the case.
SCENARIOS = ("S01", "S02", "S03")
SEEDS = (1, 2, 3)


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_generated_sequences_never_break_the_invariants_of_the_branch(
    layer: BranchLayer,
    session_id: str,
    scenario: str,
    seed: int,
    effective_at: str,
    base_resolver: BaseResolver,
    store,
    owner_session: str,
) -> None:
    """The revision is the count of the events, the hash is reproduced from the events alone, and a refused
    command changes neither."""
    branch = layer.fork(session_id, scenario).branch

    for step, case in enumerate(command_sequence(seed, scenario, effective_at)):
        where = f"the seed {seed}, the scenario {scenario}, the step {step}"
        before = layer.status(session_id, branch.branch_id)

        if case.outcome == OUTCOME_RESET:
            layer.reset(session_id, branch.branch_id)
        elif case.outcome == OUTCOME_PREVIEW:
            assert case.command is not None
            layer.preview_mutation(session_id, branch.branch_id, case.command)
        elif case.outcome == OUTCOME_COMMIT:
            assert case.command is not None
            layer.commit_mutation(session_id, branch.branch_id, case.command)
        elif case.outcome == OUTCOME_REFUSED:
            assert case.command is not None
            with pytest.raises(MutationRejected):
                layer.commit_mutation(session_id, branch.branch_id, case.command)
        else:  # pragma: no cover - the generator never produces another outcome
            raise AssertionError(f"the generator produced the outcome {case.outcome}")

        after = layer.status(session_id, branch.branch_id)
        events = store.read_events(branch.branch_id, owner_session)

        # The revision of the branch is the count of its events.
        assert after.revision == len(events), f"the revision is not the count of the events: {where}"
        # The canonical hash of the branch is reproduced from the events alone.
        rebuilt = project(base_resolver(scenario), events)
        assert rebuilt.canonical_hash == after.current_canonical_hash, (
            f"the hash is not reproduced from the events: {where}"
        )
        # A command that was refused or previewed changed neither the revision nor the hash.
        if case.outcome in (OUTCOME_REFUSED, OUTCOME_PREVIEW):
            assert after.revision == before.revision, f"a refused command moved the revision: {where}"
            assert after.current_canonical_hash == before.current_canonical_hash, (
                f"a refused command moved the hash: {where}"
            )
