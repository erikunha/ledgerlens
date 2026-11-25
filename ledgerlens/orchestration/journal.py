"""The journal of a run: the steps of the run, their attempts, their inputs and their outputs.

Why the journal exists: a suspended run continues from what it already did, and a journal that does not record the
inputs of a step cannot tell a step that may be reused from a step that may not.

Why the journal refuses an entry whose output does not match the digest it was given: the journal is what a resume
trusts, and a resume that trusts an entry whose output was replaced answers with the result of another run (FR-008).

Why the entry keeps the digest of the inputs of the step: a resume reuses an output only when the inputs of the step
are the same as they were, and the digest of the inputs is what says so.

Why the journal is a value and not a file: where a journal lives is the decision of another milestone, and a journal
that writes itself to a place nobody decided is a journal that a reader cannot find.

Why the history of the journal is append only: the journal is the proof of what a run already did, and a journal
that rewrites an entry is a journal that cannot prove anything.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Journal", "JournalEntry", "JournalRefused", "digest_of"]


class JournalRefused(Exception):
    """The journal refuses the entry, and the message says why."""


def digest_of(value: Any) -> str:
    """The digest of a value, with the canonical form of the repository.

    Why the canonical form and not the representation of the language: the digest has to be the same on every run and
    on every machine, and the order of the keys of a dictionary is not.
    """
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JournalEntry:
    """One attempt of one step: what it read, what it wrote and what it cost.

    Why the attempt is a number and not a boolean: a step that failed and was tried again is two attempts, and a
    resume has to know that the first one happened.
    """

    step_id: str
    attempt: int
    inputs_digest: str
    output: Mapping[str, Any]
    output_digest: str
    status: str
    snapshot: str
    config_version: str

    def to_dict(self) -> dict[str, Any]:
        """The entry as a dictionary, for the journal that is written."""
        return {
            "step_id": self.step_id,
            "attempt": self.attempt,
            "inputs_digest": self.inputs_digest,
            "output": dict(self.output),
            "output_digest": self.output_digest,
            "status": self.status,
            "snapshot": self.snapshot,
            "config_version": self.config_version,
        }


@dataclass
class Journal:
    """The journal of a run: the attempts of the steps, in the order they happened."""

    entries: list[JournalEntry] = field(default_factory=list)

    def record(
        self,
        *,
        step_id: str,
        inputs: Any,
        output: Any,
        output_digest: str,
        status: str,
        snapshot: str,
        config_version: str,
    ) -> JournalEntry:
        """The entry of the attempt, and a refusal when the output does not match the digest it was given.

        Why the digest is an argument and not computed here: the caller is the one that knows the output it wrote,
        and a digest that the journal computes over its own copy of the output would always agree with itself.
        """
        if digest_of(output) != output_digest:
            raise JournalRefused(
                f"the output of the step {step_id} does not match the digest {output_digest} it was given, so the "
                "journal refuses the entry"
            )
        entry = JournalEntry(
            step_id=step_id,
            attempt=self._attempts_of(step_id) + 1,
            inputs_digest=digest_of(inputs),
            output=dict(output) if isinstance(output, Mapping) else {"value": output},
            output_digest=output_digest,
            status=status,
            snapshot=snapshot,
            config_version=config_version,
        )
        self.entries.append(entry)
        return entry

    def _attempts_of(self, step_id: str) -> int:
        """The number of attempts the step already has in the journal."""
        return len([entry for entry in self.entries if entry.step_id == step_id])

    def attempts_of(self, step_id: str) -> tuple[JournalEntry, ...]:
        """The entries of the step, in the order they happened."""
        return tuple(entry for entry in self.entries if entry.step_id == step_id)

    def completed(self, step_id: str) -> JournalEntry | None:
        """The last entry of the step that completed, or None when the step never completed."""
        done = [entry for entry in self.attempts_of(step_id) if entry.status == "ok"]
        return done[-1] if done else None

    def to_records(self) -> list[dict[str, Any]]:
        """The journal as a list of records, for the journal that is written."""
        return [entry.to_dict() for entry in self.entries]

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, Any]]) -> Journal:
        """The journal of the records that were written."""
        return Journal(
            entries=[
                JournalEntry(
                    step_id=str(record["step_id"]),
                    attempt=int(record["attempt"]),
                    inputs_digest=str(record["inputs_digest"]),
                    output=dict(record.get("output", {})),
                    output_digest=str(record["output_digest"]),
                    status=str(record["status"]),
                    snapshot=str(record.get("snapshot", "")),
                    config_version=str(record.get("config_version", "")),
                )
                for record in records
            ]
        )
