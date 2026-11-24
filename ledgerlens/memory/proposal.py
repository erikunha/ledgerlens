"""The proposal of a record: a record enters the memory with a source, and only with a verified source.

Why it exists: the case memory of `ledgerlens/memory/long_term.py` refuses an investigation whose verdict is
not `supported`, and the versioned memory holds the same rule read from the other side: a proposal that names
no verified source is refused, because a record that entered the memory without a verification would come back
as a claim in the next session with the authority of a memory.

Why the proposal carries the scope and the reviewer: the scope says which session the record belongs to, and
the reviewer says who asked for the promotion, so the record can answer for both.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Proposal", "ProposalRefused", "propose"]


class ProposalRefused(Exception):
    """The proposal is refused, and the message says why."""


@dataclass(frozen=True)
class Proposal:
    """What a case proposes to the memory: the assertion, the source and the validity of it.

    Why the verdict of the source travels with the proposal: the rule of the memory is that only what was
    verified gets in, and a proposal that does not say how its source was verified is a proposal that asks the
    memory to trust it blindly.
    """

    scope: str
    assertion: str
    source: str
    source_verdict: str
    valid_until: str | None = None
    reviewer: str | None = None


def propose(
    *,
    scope: str,
    assertion: str,
    source: str,
    source_verdict: str,
    valid_until: str | None = None,
    reviewer: str | None = None,
) -> Proposal:
    """The proposal of a record, and a refusal when the source was not verified.

    Why the refusal is of the proposal and not of the write: a proposal that may not enter the memory is
    refused before anything is written, so the store never holds a record without a verified source.
    """
    if not assertion.strip():
        raise ProposalRefused("a proposal with no assertion is a proposal of nothing")
    if not source.strip():
        raise ProposalRefused("a proposal with no source is a proposal that asks the memory to trust it blindly")
    if source_verdict != "supported":
        raise ProposalRefused(
            f"the source of the proposal was not verified: the verdict is {source_verdict!r} and only "
            "'supported' enters the memory"
        )
    return Proposal(
        scope=scope,
        assertion=assertion.strip(),
        source=source.strip(),
        source_verdict=source_verdict,
        valid_until=valid_until,
        reviewer=reviewer,
    )
