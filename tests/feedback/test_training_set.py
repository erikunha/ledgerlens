"""The training set holds only the records of the tier gold, and never a record of an evaluation.

What they guarantee, and why: a set built from a mixture of the three tiers holds only the records of the tier
`gold`, and a record whose permission is an evaluation never enters it, because the tier and the permission
are the two conditions of the door: the tier says how much the repository trusts a record, and the permission
says what the record may be used for.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.feedback.tiers import GOLD, SILVER, UNVERIFIED
from ledgerlens.feedback.training_set import build_training_set


def test_a_set_built_from_a_mixture_of_the_three_tiers_holds_only_the_gold(record_factory) -> None:
    """The door of the training set opens only for the tier gold."""
    gold = record_factory(record_id="FR-GOLD")
    silver = record_factory(record_id="FR-SILVER")
    unverified = record_factory(record_id="FR-UNVERIFIED")
    tiers = {"FR-GOLD": GOLD, "FR-SILVER": SILVER, "FR-UNVERIFIED": UNVERIFIED}

    training_set = build_training_set([gold, silver, unverified], tiers=tiers)

    assert {record.record_id for record in training_set.records} == {"FR-GOLD"}
    assert training_set.digest


def test_a_record_whose_permission_is_an_evaluation_never_enters_the_set(record_factory) -> None:
    """A record the reviewer measured and did not release for training stays out, whatever its tier."""
    measured = record_factory(record_id="FR-EVAL", permission="evaluation")

    training_set = build_training_set([measured], tiers={"FR-EVAL": GOLD})

    assert training_set.records == ()


def test_the_digest_of_the_set_moves_with_the_records(record_factory) -> None:
    """The digest covers the content of the records, so a set whose records moved has another digest."""
    first = build_training_set([record_factory(record_id="FR-1")], tiers={"FR-1": GOLD})
    second = build_training_set([record_factory(record_id="FR-2")], tiers={"FR-2": GOLD})

    assert first.digest != second.digest
