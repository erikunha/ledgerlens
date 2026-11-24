"""The record of a failure: the fields, the refusal of a record that misses one, and the Decimal of an amount.

What they guarantee, and why: a feedback record names its bundle, its claim, its evidence and its verdict, a
record that misses one of the fields is refused with the name of the field, and a corrected amount is a
`Decimal` whose comparison with the value of the ledger is exact, because a float would make the comparison a
comparison of roundings.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.feedback.record import FeedbackRecord, RecordError


def test_the_record_names_the_bundle_the_claim_the_evidence_and_the_correction(record) -> None:
    """The record carries the fields that let a reader find the evidence of the failure."""
    assert record.bundle == "data/eval/replay/s02"
    assert record.bundle_digest
    assert record.claim_id == "CL3"
    assert record.evidence_refs == ("TX:1001",)
    assert record.corrected_value == Decimal("12.50")


@pytest.mark.parametrize(
    "field",
    ["record_id", "bundle", "bundle_digest", "claim_id", "failure", "reviewer", "reviewer_role", "source"],
)
def test_a_record_that_misses_a_field_is_refused_with_the_name_of_the_field(record_factory, field) -> None:
    """A record without a field is a record that cannot be checked, and the refusal names the field."""
    with pytest.raises(RecordError, match=field):
        record_factory(**{field: ""})


def test_a_record_with_a_catalog_or_a_permission_the_loop_does_not_know_is_refused(record_factory) -> None:
    """The catalogs and the permissions are closed vocabularies."""
    with pytest.raises(RecordError, match="catalog"):
        record_factory(catalog="elsewhere")
    with pytest.raises(RecordError, match="permission"):
        record_factory(permission="everything")


def test_the_corrected_amount_is_a_decimal_and_the_comparison_with_the_ledger_is_exact(record) -> None:
    """A corrected amount is a `Decimal`, and the comparison with the value of the ledger is exact."""
    assert record.corrects_amount
    assert record.matches_ledger(Decimal("12.50"))
    assert not record.matches_ledger(Decimal("12.51"))


def test_the_record_round_trips_through_its_json_mapping(record) -> None:
    """The record of the registry is read back with the amount a `Decimal` again."""
    restored = FeedbackRecord.from_dict(record.to_dict())

    assert restored == record
    assert restored.corrects_amount
