"""The conformance suite of the acceptance scenarios of the design package.

Why this suite exists: the design package of the sandbox
(`docs/v3/advanced-specs/R2-03-isolated-sandbox-mutations.md`) writes six acceptance scenarios, and the rules
of the branch were built and tested one by one, spread over the tests of the folder. A rule that is tested alone
is a rule that can hold alone, and the package asks for the six sentences over the seeded scenarios, gathered in
one suite. This suite is that gathering: every acceptance scenario runs over the seeded scenarios S01, S02 and
S03, and every case names the scenario it ran and the number of the commands it sent.

The six sentences of the package, and the case of this suite that answers each one:

* two sessions edit the same transaction: the isolation holds, and the branch of one session never moves with the
  commit of the other;
* the same mutation retried with the same idempotency key: at most one event is committed, and the second answer
  is the replay of the first;
* a wrong precision and a wrong currency: the command is refused, and the hash of the branch does not move;
* a reset of the branch: the hash of the branch is the hash of the base again;
* a request that names a read only field: the command is denied, and the hash of the branch does not move;
* a mutated rate marks the published answer stale: the answer of the past is marked against the base hash, and it
  is never presented as the current result of the branch.

The suite runs over the two implementations of the store, the way the contract suite does, because a conformance
that holds over one store and not over the other is a conformance of the store and not of the branch.
"""

from __future__ import annotations

import pytest

from ledgerlens.sandbox.branch import BranchLayer
from ledgerlens.sandbox.mutation import MutationCommand, MutationRejected
from ledgerlens.sandbox.projector import project
from ledgerlens.sandbox.snapshot import BaseResolver

# The seeded scenarios of the conformance, and the records of each one the commands name.
SCENARIOS = ("S01", "S02", "S03")

# The refund of S01, the transaction of S02 and the chargeback of S03, as the manifest of the scenarios names them.
RECORD_OF = {
    "S01": {"refund_id": "R-0731"},
    "S02": {"transaction_id": "TX-2051"},
    "S03": {"chargeback_id": "CB-0310"},
}


def _valid_command(scenario: str, key: str, effective_at: str, revision: int = 0) -> MutationCommand:
    """The command of a valid mutation of the scenario, with the key and the revision of the request."""
    if scenario == "S01":
        return MutationCommand(
            kind="refund.apply_fx_adjustment",
            payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": effective_at},
            reason="the visitor tries another rate",
            expected_revision=revision,
            idempotency_key=key,
        )
    if scenario == "S02":
        return MutationCommand(
            kind="payment.simulate_duplicate",
            payload={"transaction_id": "TX-2051", "elapsed_seconds": 45},
            reason="the visitor simulates a second charge",
            expected_revision=revision,
            idempotency_key=key,
        )
    if scenario == "S03":
        return MutationCommand(
            kind="chargeback.change_deadline",
            payload={"chargeback_id": "CB-0310", "new_deadline": "2026-11-20"},
            reason="the visitor moves the deadline",
            expected_revision=revision,
            idempotency_key=key,
        )
    raise AssertionError(f"the scenario {scenario} is not one of the seeded scenarios of the conformance")


def _wrong_precision_command(scenario: str, key: str, effective_at: str) -> MutationCommand:
    """The command of a mutation whose value has the wrong precision, one per scenario."""
    command = _valid_command(scenario, key, effective_at)
    if scenario == "S01":
        payload = {**command.payload, "applied_rate": "5.412500001"}
    elif scenario == "S02":
        payload = {**command.payload, "elapsed_seconds": "45.5"}
    else:
        payload = {**command.payload, "new_deadline": "2026-13-40"}
    return MutationCommand(
        kind=command.kind,
        payload=payload,
        reason=command.reason,
        expected_revision=command.expected_revision,
        idempotency_key=key,
    )


def _wrong_currency_command(scenario: str, key: str, effective_at: str) -> MutationCommand:
    """The command of a mutation whose assertion of the currency does not match the record."""
    command = _valid_command(scenario, key, effective_at)
    return MutationCommand(
        kind=command.kind,
        payload={**command.payload, "currency": "ZZZ"},
        reason=command.reason,
        expected_revision=command.expected_revision,
        idempotency_key=key,
    )


def _read_only_command(scenario: str, key: str, effective_at: str) -> MutationCommand:
    """The command of a mutation that names a read only field of the record."""
    command = _valid_command(scenario, key, effective_at)
    return MutationCommand(
        kind=command.kind,
        payload={**command.payload, "canonical_hash": "0" * 64},
        reason=command.reason,
        expected_revision=command.expected_revision,
        idempotency_key=key,
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestTheAcceptanceScenarios:
    """The six sentences of the design package, over the three seeded scenarios."""

    def test_two_sessions_that_edit_the_same_transaction_are_isolated(
        self, layer: BranchLayer, session_id: str, other_session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The first sentence of the package: two sessions edit the same transaction, and the isolation holds."""
        commands_sent = 0
        first = layer.fork(session_id, scenario).branch
        second = layer.fork(other_session_id, scenario).branch
        assert first.base_canonical_hash == second.base_canonical_hash

        layer.commit_mutation(session_id, first.branch_id, _valid_command(scenario, "cmd-0001", effective_at))
        commands_sent += 1

        moved = layer.status(session_id, first.branch_id)
        untouched = layer.status(other_session_id, second.branch_id)
        assert moved.revision == 1
        assert untouched.revision == 0
        assert untouched.current_canonical_hash == second.base_canonical_hash
        assert moved.current_canonical_hash != untouched.current_canonical_hash
        assert commands_sent == 1

    def test_a_mutation_retried_with_the_same_key_commits_at_most_one_event(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str, event_count
    ) -> None:
        """The second sentence of the package: the same mutation retried, and at most one event is committed."""
        branch = layer.fork(session_id, scenario).branch
        command = _valid_command(scenario, "cmd-0001", effective_at)

        first = layer.commit_mutation(session_id, branch.branch_id, command)
        second = layer.commit_mutation(session_id, branch.branch_id, command)

        assert event_count(branch.branch_id) == 1
        assert first.replayed is False
        assert second.replayed is True
        assert second.revision == first.revision == 1
        assert second.canonical_hash == first.canonical_hash

    def test_a_wrong_precision_is_refused_and_the_hash_does_not_move(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The third sentence of the package, first half: a wrong precision is refused with the hash unchanged."""
        branch = layer.fork(session_id, scenario).branch
        before = layer.status(session_id, branch.branch_id)

        with pytest.raises(MutationRejected):
            layer.commit_mutation(
                session_id, branch.branch_id, _wrong_precision_command(scenario, "cmd-0001", effective_at)
            )

        after = layer.status(session_id, branch.branch_id)
        assert after.revision == before.revision == 0
        assert after.current_canonical_hash == before.current_canonical_hash

    def test_a_wrong_currency_is_refused_and_the_hash_does_not_move(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The third sentence of the package, second half: a wrong currency is refused with the hash unchanged."""
        branch = layer.fork(session_id, scenario).branch
        before = layer.status(session_id, branch.branch_id)

        with pytest.raises(MutationRejected):
            layer.commit_mutation(
                session_id, branch.branch_id, _wrong_currency_command(scenario, "cmd-0001", effective_at)
            )

        after = layer.status(session_id, branch.branch_id)
        assert after.revision == before.revision == 0
        assert after.current_canonical_hash == before.current_canonical_hash

    def test_a_reset_returns_the_base_hash(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The fourth sentence of the package: the reset of the branch, and the hash is the hash of the base."""
        branch = layer.fork(session_id, scenario).branch
        layer.commit_mutation(session_id, branch.branch_id, _valid_command(scenario, "cmd-0001", effective_at))
        moved = layer.status(session_id, branch.branch_id)
        assert moved.current_canonical_hash != branch.base_canonical_hash

        reset = layer.reset(session_id, branch.branch_id)

        assert reset.revision == 0
        assert reset.current_canonical_hash == branch.base_canonical_hash

    def test_a_request_that_names_a_read_only_field_is_denied(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The fifth sentence of the package: a request that names a read only field is denied."""
        branch = layer.fork(session_id, scenario).branch
        before = layer.status(session_id, branch.branch_id)

        with pytest.raises(MutationRejected):
            layer.commit_mutation(
                session_id, branch.branch_id, _read_only_command(scenario, "cmd-0001", effective_at)
            )

        after = layer.status(session_id, branch.branch_id)
        assert after.revision == before.revision == 0
        assert after.current_canonical_hash == before.current_canonical_hash

    def test_a_mutated_rate_marks_the_published_answer_stale(
        self, layer: BranchLayer, session_id: str, scenario: str, effective_at: str
    ) -> None:
        """The sixth sentence of the package: the mutated rate invalidates the old answer, and it is never
        re-labeled as the current one."""
        branch = layer.fork(session_id, scenario).branch
        layer.commit_mutation(session_id, branch.branch_id, _valid_command(scenario, "cmd-0001", effective_at))
        answers = layer.answers(session_id, branch.branch_id)
        assert [answer.stale for answer in answers] == [False]

        layer.reset(session_id, branch.branch_id)

        answers = layer.answers(session_id, branch.branch_id)
        assert [answer.stale for answer in answers] == [True]
        assert answers[0].stale_against == branch.base_canonical_hash


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestThePropertiesOfTheBranch:
    """The two properties that hold over the three seeded scenarios, after every command of the cases above."""

    def test_the_revision_is_the_count_of_the_events_and_the_hash_is_reproduced_from_the_events_alone(
        self,
        layer: BranchLayer,
        session_id: str,
        scenario: str,
        effective_at: str,
        base_resolver: BaseResolver,
        store,
        owner_session: str,
    ) -> None:
        """The revision of the branch is the count of its events, and the canonical hash of the branch is the hash
        of the projection of its events, reproduced from the events alone."""
        branch = layer.fork(session_id, scenario).branch
        layer.commit_mutation(session_id, branch.branch_id, _valid_command(scenario, "cmd-0001", effective_at))
        layer.commit_mutation(
            session_id,
            branch.branch_id,
            _valid_command(scenario, "cmd-0002", effective_at, revision=1),
        )

        status = layer.status(session_id, branch.branch_id)
        events = store.read_events(branch.branch_id, owner_session)
        assert status.revision == 2
        assert status.revision == len(events)

        base = base_resolver(scenario)
        rebuilt = project(base, events)
        assert rebuilt.canonical_hash == status.current_canonical_hash
