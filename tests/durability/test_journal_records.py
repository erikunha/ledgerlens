"""The records of the journal: the hash of the inputs, the snapshot, the attempt, the key, the output and the spend.

What they guarantee, and why: the intent of a step carries the hash of its inputs, the snapshot it reads, the
attempt and the idempotency key, and the result carries the reference of the output, the status and what the
step spent, because the restart of a run reads the journal to know what ran, with what inputs, over which
snapshot and at what cost, and a journal that misses one of them is a journal that cannot restart a run.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.durability.journal import RunJournal, Step, StepOutcome, inputs_hash_of
from ledgerlens.durability.store import JournalStore


def test_the_intent_and_the_result_of_a_step_carry_what_the_restart_reads(tmp_path) -> None:
    """The hash of the inputs, the snapshot, the attempt, the key, the output and the spend."""
    store = JournalStore(tmp_path)
    step = Step(
        step_id="read",
        inputs={"question": "the status of the refund", "account": "C-0205"},
        snapshot="snapshot-of-the-run",
        idempotency_key="key-read",
        idempotent=True,
        execute=lambda: StepOutcome(output_ref="out-read", status="ok", spend_usd=Decimal("0.002")),
    )
    RunJournal(store).run([step])

    intent, result = store.entries()
    assert intent.inputs_hash == inputs_hash_of(step.inputs)
    assert intent.snapshot == "snapshot-of-the-run"
    assert intent.attempt == 1
    assert intent.idempotency_key == "key-read"
    assert intent.output_ref is None

    assert result.output_ref == "out-read"
    assert result.status == "ok"
    assert result.spend_usd == Decimal("0.002")
    assert result.inputs_hash == intent.inputs_hash


def test_the_hash_of_the_inputs_changes_when_the_inputs_change() -> None:
    """A step whose inputs changed is not the same step, and the hash says so."""
    first = inputs_hash_of({"question": "a"})
    second = inputs_hash_of({"question": "b"})

    assert first != second
    assert inputs_hash_of({"question": "a"}) == first
