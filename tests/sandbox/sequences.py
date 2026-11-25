"""The seeded generator of the sequences of commands of the property tests.

Why the generator is seeded and deterministic: a property test that cannot be replayed is a property test that
cannot be debugged, so every sequence comes out of a seed, the same seed produces the same sequence, and the seed
of every case is in the message of a failure. The repository carries no property testing library, and the decision
of the milestone (the record of the milestone in `docs/decisions/`) is a seeded generator inside `tests/sandbox/`
and not a new dependency of the suite: the sequences of the branch are short, the commands are few, and a library
would buy the shrinking that these sequences do not need.

Why the generator never touches `data/runtime/sandbox-bases/`: the bases of the runtime are the bases of the
visitors of the demo, and a test that wrote there would be a test that leaves a branch behind. The generator only
produces commands, and the property test runs them over the temporary store of the tests, the way every test of
the folder does.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ledgerlens.sandbox.mutation import MutationCommand

# The outcomes a generated command can have: a commit that moves the branch, a command that is refused and moves
# nothing, a preview that writes nothing, and a reset that returns the branch to the base.
OUTCOME_COMMIT = "commit"
OUTCOME_REFUSED = "refused"
OUTCOME_PREVIEW = "preview"
OUTCOME_RESET = "reset"


@dataclass(frozen=True)
class GeneratedCommand:
    """One generated step of a sequence: the command, and the outcome the layer must answer.

    The command is None for the reset, because the reset is not a command of the catalog and the layer has a door
    of its own for it.
    """

    command: MutationCommand | None
    outcome: str


def _valid_command(scenario: str, key: str, effective_at: str, revision: int) -> MutationCommand:
    """The command of a valid mutation of the scenario, at the revision the branch is at."""
    if scenario == "S01":
        return MutationCommand(
            kind="refund.apply_fx_adjustment",
            payload={"refund_id": "R-0731", "applied_rate": "5.41250000", "effective_at": effective_at},
            reason="the generator tries another rate",
            expected_revision=revision,
            idempotency_key=key,
        )
    if scenario == "S02":
        return MutationCommand(
            kind="payment.simulate_duplicate",
            payload={"transaction_id": "TX-2051", "elapsed_seconds": 45},
            reason="the generator simulates a second charge",
            expected_revision=revision,
            idempotency_key=key,
        )
    if scenario == "S03":
        return MutationCommand(
            kind="chargeback.change_deadline",
            payload={"chargeback_id": "CB-0310", "new_deadline": "2026-11-20"},
            reason="the generator moves the deadline",
            expected_revision=revision,
            idempotency_key=key,
        )
    raise AssertionError(f"the scenario {scenario} is not one of the seeded scenarios of the generator")


def _refused_command(scenario: str, key: str, effective_at: str, revision: int, rng: random.Random) -> MutationCommand:
    """The command of a mutation that is refused, drawn from the refusals of the catalog."""
    valid = _valid_command(scenario, key, effective_at, revision)
    refusal = rng.choice(("precision", "currency", "read-only", "stale-revision"))
    if refusal == "precision":
        if scenario == "S01":
            payload = {**valid.payload, "applied_rate": "5.412500001"}
        elif scenario == "S02":
            payload = {**valid.payload, "elapsed_seconds": "45.5"}
        else:
            payload = {**valid.payload, "new_deadline": "2026-13-40"}
    elif refusal == "currency":
        payload = {**valid.payload, "currency": "ZZZ"}
    elif refusal == "read-only":
        payload = {**valid.payload, "canonical_hash": "0" * 64}
    else:
        # A revision that is not the revision of the branch: the conflict of the revision refuses the command.
        return MutationCommand(
            kind=valid.kind,
            payload=dict(valid.payload),
            reason=valid.reason,
            expected_revision=revision + 1,
            idempotency_key=key,
        )
    return MutationCommand(
        kind=valid.kind,
        payload=payload,
        reason=valid.reason,
        expected_revision=revision,
        idempotency_key=key,
    )


def command_sequence(seed: int, scenario: str, effective_at: str, length: int = 12) -> list[GeneratedCommand]:
    """The sequence of commands of the seed, deterministic: the same seed produces the same sequence.

    Why the revision is tracked by the generator: a commit moves the revision of the branch, a reset returns it
    to zero, and a refused command or a preview moves nothing, so the expected revision of the next valid command
    is a fact of the sequence and not a guess of the test.
    """
    rng = random.Random(f"{seed}:{scenario}")
    sequence: list[GeneratedCommand] = []
    revision = 0
    for index in range(length):
        key = f"cmd-{seed}-{index:04d}"
        roll = rng.random()
        if roll < 0.45:
            command = _valid_command(scenario, key, effective_at, revision)
            sequence.append(GeneratedCommand(command=command, outcome=OUTCOME_COMMIT))
            revision += 1
        elif roll < 0.65:
            command = _refused_command(scenario, key, effective_at, revision, rng)
            sequence.append(GeneratedCommand(command=command, outcome=OUTCOME_REFUSED))
        elif roll < 0.8:
            command = _valid_command(scenario, key, effective_at, revision)
            sequence.append(GeneratedCommand(command=command, outcome=OUTCOME_PREVIEW))
        else:
            sequence.append(GeneratedCommand(command=None, outcome=OUTCOME_RESET))
            revision = 0
    return sequence
