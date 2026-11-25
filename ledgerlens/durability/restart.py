"""The restart of a run that died: the outputs that completed are reused, and the branch is where the crash left it.

Why a restart reuses the output of a step that completed: the result of the step is in the journal, and a
restart that ran the step again would spend again what the run already spent. The output of the journal is the
output of the step, and the restart reuses it.

Why a restart runs an interrupted step again only when the step is idempotent: a step that writes without an
idempotency key may have written before the process died, and the repository cannot know, so it is never run
again. A step whose effect is idempotent (a read, or a write the store makes idempotent, like the commit of
the branch) is run again with the same idempotency key, and the effect does not happen twice.

Why a restart refuses a step whose snapshot changed: a number that was read from another branch is not the
number of this case, and a run that read it would answer about a case that is not the case of the run.
"""

from __future__ import annotations

from dataclasses import dataclass

from ledgerlens.durability.journal import Step, StepOutcome
from ledgerlens.durability.store import JournalStore

__all__ = ["RestartOutcome", "restart"]


@dataclass(frozen=True)
class RestartOutcome:
    """The outcome of a restart: the outputs of the run, and what the restart did with each step.

    Why the restart names the steps it reused, the steps it ran again and the steps it refused: a reader of
    the restart has to see what the restart did, and a restart that hid its work would be a restart that
    nobody can check.
    """

    outputs: tuple[StepOutcome, ...]
    reused: tuple[str, ...]
    rerun: tuple[str, ...]
    refused: tuple[str, ...]
    reason: str


def restart(store: JournalStore, steps: list[Step], *, snapshot: str) -> RestartOutcome:
    """The restart of a run from the journal: the completed outputs are reused, the rest is run or refused.

    Why the journal is read and not the memory of the caller: the journal is the durable record of the run,
    and a restart that trusted the memory of the caller would restart from what the caller believes and not
    from what the run did.
    """
    entries = store.entries()
    outputs: list[StepOutcome] = []
    reused: list[str] = []
    rerun: list[str] = []
    refused: list[str] = []
    for step in steps:
        intent = _last_of(entries, step.step_id, "intent")
        result = _last_of(entries, step.step_id, "result")
        if result is not None:
            # The step completed, and the journal holds its output: the restart reuses it and runs nothing.
            outputs.append(
                StepOutcome(output_ref=result.output_ref or "", status=result.status or "", spend_usd=result.spend_usd)
            )
            reused.append(step.step_id)
            continue
        if step.snapshot != snapshot:
            # The snapshot of the step changed, and a number read from another branch is not the number of this
            # case: the step needs a new run.
            refused.append(step.step_id)
            continue
        if intent is not None and not step.idempotent:
            # The step started and did not complete, and its effect is not idempotent: the repository cannot
            # know whether it wrote, so it is never run again.
            refused.append(step.step_id)
            continue
        # The step is idempotent (or the run never reached it): it runs, with the same idempotency key, and the
        # journal records the new attempt.
        store.append(
            _intent_of(step, attempt=2 if intent is not None else 1)
        )
        outcome = step.execute()
        store.append(_result_of(step, outcome, attempt=2 if intent is not None else 1))
        outputs.append(outcome)
        rerun.append(step.step_id)
    reason = (
        f"the restart reused {len(reused)} step(s), ran {len(rerun)} again and refused {len(refused)}"
        if refused or rerun or reused
        else "the run had no steps to restart"
    )
    return RestartOutcome(
        outputs=tuple(outputs),
        reused=tuple(reused),
        rerun=tuple(rerun),
        refused=tuple(refused),
        reason=reason,
    )


def _last_of(entries: list, step_id: str, kind: str):
    """The last entry of a kind for a step, and None when the journal has none."""
    found = None
    for entry in entries:
        if entry.step_id == step_id and entry.kind == kind:
            found = entry
    return found


def _intent_of(step: Step, *, attempt: int):
    """The intent of a step, for the attempt the restart runs."""
    from ledgerlens.durability.journal import JournalEntry

    return JournalEntry(
        number=0,
        kind="intent",
        step_id=step.step_id,
        attempt=attempt,
        inputs_hash=step.inputs_hash,
        snapshot=step.snapshot,
        idempotency_key=step.idempotency_key,
    )


def _result_of(step: Step, outcome: StepOutcome, *, attempt: int):
    """The result of a step, for the attempt the restart ran."""
    from ledgerlens.durability.journal import JournalEntry

    return JournalEntry(
        number=0,
        kind="result",
        step_id=step.step_id,
        attempt=attempt,
        inputs_hash=step.inputs_hash,
        snapshot=step.snapshot,
        idempotency_key=step.idempotency_key,
        output_ref=outcome.output_ref,
        status=outcome.status,
        spend_usd=outcome.spend_usd,
    )
