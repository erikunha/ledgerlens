"""The journal of a run: an intent and a result for every step, and the numbers grow monotonically.

What they guarantee, and why: (a) every step of a run has an intent and a result in the journal, because a step
that ran and left no result is visible as such and a run that died between the two writes is a run whose
restart knows where it stopped; (b) the numbers of the journal grow by one and never go back, because the
order of a run is readable after the fact and a number that could be reused would say nothing about the order.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.durability.journal import RunJournal, Step, StepOutcome
from ledgerlens.durability.store import JournalStore


def _step(step_id: str, snapshot: str = "snapshot-of-the-run") -> Step:
    """A step of a run, with the metadata the journal records."""
    return Step(
        step_id=step_id,
        inputs={"question": "the status of the refund"},
        snapshot=snapshot,
        idempotency_key=f"key-{step_id}",
        idempotent=True,
        execute=lambda: StepOutcome(output_ref=f"out-{step_id}", status="ok", spend_usd=Decimal("0.001")),
    )


def test_every_step_of_a_run_has_an_intent_and_a_result(tmp_path) -> None:
    """The intent is written before the step runs, and the result after it ran."""
    store = JournalStore(tmp_path)
    RunJournal(store).run([_step("read"), _step("compute")])

    entries = store.entries()
    kinds = [(entry.step_id, entry.kind) for entry in entries]
    assert kinds == [("read", "intent"), ("read", "result"), ("compute", "intent"), ("compute", "result")]


def test_the_numbers_of_the_journal_grow_monotonically(tmp_path) -> None:
    """The numbers grow by one and never go back: the order of the run is readable after the fact."""
    store = JournalStore(tmp_path)
    RunJournal(store).run([_step("read"), _step("compute"), _step("verify")])

    numbers = [entry.number for entry in store.entries()]
    assert numbers == sorted(numbers)
    assert numbers == list(range(1, len(numbers) + 1))
