"""The uncertainty of a field: the blurred field carries no value, and the case asks the person.

What they guarantee, and why: the blurred field carries no value, its kind of confidence names the doubt, and
the case asks the person, because a value that was not read with certainty is not a value, and a value that
the parser was not certain of would be a value that the verifier would check as if it were read.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.documents.convert import read_text
from ledgerlens.documents.fields import extract_fields

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_the_blurred_field_carries_no_value_and_names_the_doubt() -> None:
    """A value that was not read with certainty is not a value."""
    text = read_text(FIXTURES / "receipt_blurred.txt")
    fields = extract_fields(text)

    total = next(field for field in fields if field.name == "total")
    assert total.value is None
    assert total.confidence == "uncertain"


def test_a_field_read_with_certainty_carries_the_value() -> None:
    """The field that was read with certainty carries the value and the kind of confidence of it."""
    text = read_text(FIXTURES / "receipt_us.txt")
    fields = extract_fields(text)

    total = next(field for field in fields if field.name == "total")
    assert total.value is not None
    assert total.confidence == "read"
