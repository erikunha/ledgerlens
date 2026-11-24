"""The journal of a run: the intent of a step before it runs, and its result after it ran.

Why the intent is written before the step runs: a step that ran and left no result is visible as such, and a
run that died between the two writes is a run whose restart knows exactly where it stopped. A journal that
wrote the result first would lose the step that died in the middle.

Why the numbers of the journal grow by one and never go back: the order of a run is readable after the fact,
and a number that could be reused is a number that says nothing about the order. The store of the journal
assigns the numbers under a lock, so two writers never get the same number and never leave a gap.

Why the journal carries the hash of the inputs and the snapshot of every step: a step whose inputs changed is
not the same step, and a step whose snapshot changed is not the same step either, and the restart of a run
refuses both.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

__all__ = [
    "JournalEntry",
    "RunJournal",
    "Step",
    "StepOutcome",
    "inputs_hash_of",
]


def inputs_hash_of(inputs: Mapping[str, Any]) -> str:
    """The hash of the inputs of a step: the canonical bytes of them, so two equal inputs have one hash."""
    canonical = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StepOutcome:
    """What a step produced: the reference of the output, the status and what it spent.

    Why the spend is a `Decimal` or nothing: the spend of a step is money, and an unknown spend is None and
    never a zero, because a zero would say the step was free (FR-011).
    """

    output_ref: str
    status: str
    spend_usd: Decimal | None = None


@dataclass(frozen=True)
class Step:
    """A step of a run: what it reads, what it costs and how it runs.

    Why the step carries the idempotency key and the snapshot: the restart of a run runs an interrupted step
    again with the same idempotency key, and it refuses a step whose snapshot changed, because a number that
    was read from another branch is not the number of this case.

    Why the step says whether it is idempotent: a step that writes without an idempotency key may have written
    before the process died, and the repository cannot know, so it is never run again after a restart. A step
    whose effect is idempotent (a read, or a write the store makes idempotent, like the commit of the branch)
    is run again with the same idempotency key, and the effect does not happen twice.
    """

    step_id: str
    inputs: Mapping[str, Any]
    snapshot: str
    idempotency_key: str
    idempotent: bool
    execute: Callable[[], StepOutcome]

    @property
    def inputs_hash(self) -> str:
        """The hash of the inputs of the step, computed once."""
        return inputs_hash_of(self.inputs)


@dataclass(frozen=True)
class JournalEntry:
    """One entry of the journal of a run: the number, the kind, the step and what the kind carries.

    Why the entry has a number and not a clock: the number grows by one and never goes back, so the order of
    the run is readable after the fact, and a clock would say when and not in which order.
    """

    number: int
    kind: str  # "intent" or "result"
    step_id: str
    attempt: int
    inputs_hash: str
    snapshot: str
    idempotency_key: str
    output_ref: str | None = None
    status: str | None = None
    spend_usd: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """The entry as a dictionary, for the file of the journal."""
        return {
            "number": self.number,
            "kind": self.kind,
            "step_id": self.step_id,
            "attempt": self.attempt,
            "inputs_hash": self.inputs_hash,
            "snapshot": self.snapshot,
            "idempotency_key": self.idempotency_key,
            "output_ref": self.output_ref,
            "status": self.status,
            "spend_usd": None if self.spend_usd is None else str(self.spend_usd),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> JournalEntry:
        """The entry back, from the dictionary read from the file."""
        spend = data.get("spend_usd")
        return cls(
            number=int(data["number"]),
            kind=str(data["kind"]),
            step_id=str(data["step_id"]),
            attempt=int(data["attempt"]),
            inputs_hash=str(data["inputs_hash"]),
            snapshot=str(data["snapshot"]),
            idempotency_key=str(data["idempotency_key"]),
            output_ref=data.get("output_ref"),
            status=data.get("status"),
            spend_usd=None if spend is None else Decimal(str(spend)),
        )


class RunJournal:
    """The journal of a run: it writes the intent of a step before the step runs and the result after.

    Why the run stops when the journal fails: a run that continues without a journal is a run that cannot be
    restarted, and a run that cannot be restarted is a run that loses its evidence. The failure of the journal
    is the failure of the run, with the reason.
    """

    def __init__(self, store: Any) -> None:
        self.store = store

    def run(self, steps: list[Step], *, on_point: Callable[[str], None] | None = None) -> list[StepOutcome]:
        """Runs the steps, writing the intent of each before it runs and the result after it ran.

        Why the points of the run are named: the fault injection of the continuous integration kills a run at
        a named point, and a point that had no name could not be killed on purpose. The `on_point` hook is
        called at each named point, and a hook that raises is the kill of the run.
        """
        outcomes: list[StepOutcome] = []
        for index, step in enumerate(steps):
            if on_point is not None:
                on_point(f"before-the-intent-of-{step.step_id}")
            self.store.append(
                JournalEntry(
                    number=0,  # the store assigns the number, under its lock
                    kind="intent",
                    step_id=step.step_id,
                    attempt=1,
                    inputs_hash=step.inputs_hash,
                    snapshot=step.snapshot,
                    idempotency_key=step.idempotency_key,
                )
            )
            if on_point is not None:
                on_point(f"after-the-intent-of-{step.step_id}")
            outcome = step.execute()
            if on_point is not None:
                on_point(f"after-the-execute-of-{step.step_id}")
            self.store.append(
                JournalEntry(
                    number=0,
                    kind="result",
                    step_id=step.step_id,
                    attempt=1,
                    inputs_hash=step.inputs_hash,
                    snapshot=step.snapshot,
                    idempotency_key=step.idempotency_key,
                    output_ref=outcome.output_ref,
                    status=outcome.status,
                    spend_usd=outcome.spend_usd,
                )
            )
            outcomes.append(outcome)
            if on_point is not None and index < len(steps) - 1:
                on_point(f"between-the-steps-of-{step.step_id}")
        return outcomes
