"""The redaction of a shared copy of a document: the addresses and the card digits are gone, and the flag is present.

What they guarantee, and why: (a) the addresses and the card digits of the fixture are gone from the shared
copy, because a copy of a document that leaves the session of the person who asked is a copy that strangers
read; (b) the flag of the redaction is present, because a copy that hid that it was redacted would be a copy
that asks to be read as the document, and a shared copy is a copy and never the document.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.documents.redact import redact_copy


def test_the_addresses_and_the_card_digits_are_gone_from_the_shared_copy() -> None:
    """The shared copy holds neither the addresses nor the card digits of the document."""
    text = "Receipt\nEmail: customer@example.com\nCard: 4111 1111 1111 1111\nTotal: 100.00 USD\n"
    copy = redact_copy(text)

    assert "customer@example.com" not in copy.text
    assert "4111 1111 1111 1111" not in copy.text
    assert "[redacted]" in copy.text
    assert copy.redacted is True


def test_the_flag_of_the_redaction_is_present() -> None:
    """The reader of the copy knows it is a copy and not the document."""
    copy = redact_copy("Total: 100.00 USD\n")

    assert copy.redacted is True
