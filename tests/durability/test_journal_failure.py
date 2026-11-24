"""The failure of the journal: a run that cannot write its journal stops with the reason.

What they guarantee, and why: when the write of the journal fails, the run stops with the reason, because a
run that continues without a journal is a run that cannot be restarted, and a run that cannot be restarted is
a run that loses its evidence. The failure of the journal is the failure of the run, never a silent skip.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.durability.journal import RunJournal, Step, StepOutcome
from ledgerlens.durability.store import JournalStore, JournalWriteFailed


def _step(step_id: str) -> Step:
    """A step of a run, with the metadata the journal records."""
    return Step(
        step_id=step_id,
        inputs={"question": "the status of the refund"},
        snapshot="snapshot-of-the-run",
        idempotency_key=f"key-{step_id}",
        idempotent=True,
        execute=lambda: StepOutcome(output_ref=f"out-{step_id}", status="ok"),
    )


def test_a_run_that_cannot_write_its_journal_stops_with_the_reason(tmp_path) -> None:
    """The failure of the journal is the failure of the run, with the reason."""
    # A folder that is a file: the write of the journal fails, because the folder cannot be created.
    blocked = tmp_path / "blocked"
    blocked.write_text("this is a file, not a folder", encoding="utf-8")
    store = JournalStore(blocked / "session")

    with pytest.raises(JournalWriteFailed, match="cannot be restarted"):
        RunJournal(store).run([_step("read")])
