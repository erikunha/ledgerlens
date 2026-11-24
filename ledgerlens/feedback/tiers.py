"""The tiers of a feedback record: gold, silver and unverified, and the rules that promote a record.

Why the second reader is another person and not the same reader twice: a record is `gold` when the
deterministic verdict supports the correction and a second reader of the repository confirmed it, and the
confirmation of the same person who wrote the record is not a second reading, it is the first one repeated.
The name of the second reader is kept beside the tier, so a reader of the registry sees who confirmed what.

Why a record with a verdict of `contradicted` or `not_enough_evidence` is at most `silver`: the deterministic
verdict did not support the correction, and a record the code did not support is a record the repository keeps
as a reviewed observation and never as training data.
"""

from __future__ import annotations

from ledgerlens.feedback.record import FeedbackRecord

__all__ = ["GOLD", "SILVER", "UNVERIFIED", "TIERS", "tier_of"]

GOLD = "gold"
SILVER = "silver"
UNVERIFIED = "unverified"
TIERS = (GOLD, SILVER, UNVERIFIED)


def tier_of(record: FeedbackRecord, verdict: str, *, second_reader: str | None = None) -> str:
    """The tier of the record under the rules of the loop.

    The rules, in the order they are applied: a record with no published evidence is `unverified`; a record
    becomes `gold` only when the deterministic verdict supports the correction and a second reader, another
    person than the reviewer, confirmed it; and a record with a verdict of `contradicted` or
    `not_enough_evidence`, or a record the second reader did not confirm, is at most `silver`.
    """
    if not record.evidence_refs:
        return UNVERIFIED
    if verdict == "supported" and second_reader is not None and second_reader != record.reviewer:
        return GOLD
    return SILVER
