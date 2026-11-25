"""The tiers of a record: gold needs the deterministic verdict and a second reader, and the rest is silver.

What they guarantee, and why: a record becomes `gold` only when the deterministic verdict supports the
correction and a second reader of the repository confirmed it, a record with a verdict of `contradicted` or
`not_enough_evidence` is at most `silver`, and a record with no published evidence is `unverified`. The second
reader is another person and not the same reader twice.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.feedback.tiers import GOLD, SILVER, UNVERIFIED, tier_of


def test_a_record_with_the_support_of_the_verdict_and_a_second_reader_is_gold(record) -> None:
    """The two conditions of the tier gold: the code supports and another person confirms."""
    assert tier_of(record, "supported", second_reader="ana") == GOLD


def test_a_record_without_a_second_reader_is_not_gold(record) -> None:
    """The confirmation of the same person is the first reading repeated, and it is not a second one."""
    assert tier_of(record, "supported") != GOLD
    assert tier_of(record, "supported", second_reader=record.reviewer) != GOLD


def test_a_record_with_a_verdict_that_does_not_support_is_at_most_silver(record) -> None:
    """A record the code did not support is a reviewed observation and never training data."""
    assert tier_of(record, "contradicted", second_reader="ana") == SILVER
    assert tier_of(record, "not_enough_evidence", second_reader="ana") == SILVER


def test_a_record_with_no_published_evidence_is_unverified(record_factory) -> None:
    """A record without evidence is a record nobody can check, and the tier says so."""
    assert tier_of(record_factory(evidence_refs=()), "supported", second_reader="ana") == UNVERIFIED
