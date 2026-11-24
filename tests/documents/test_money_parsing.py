"""The money of a document: the amount of the Brazilian fixture is one thousand, and both are `Decimal`.

What they guarantee, and why: (a) the amount of the Brazilian fixture is one thousand and not one, because the
Brazilian form uses the point for the thousands and the comma for the decimals, and a parse that ignored the
locale would read one thousand as one; (b) the amount of the American fixture is one thousand, because the
American form uses the comma for the thousands and the point for the decimals; (c) both are `Decimal`, because
the money of a document is a `Decimal` and never a float.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.documents.money import locale_of, parse_amount


def test_the_amount_of_the_brazilian_fixture_is_one_thousand() -> None:
    """`1.000,00` in the Brazilian locale is one thousand, and not one."""
    amount = parse_amount("1.000,00", locale_of("", "BRL"))

    assert amount == Decimal("1000.00")
    assert isinstance(amount, Decimal)


def test_the_amount_of_the_american_fixture_is_one_thousand() -> None:
    """`1,000.00` in the American locale is one thousand."""
    amount = parse_amount("1,000.00", locale_of("", "USD"))

    assert amount == Decimal("1000.00")
    assert isinstance(amount, Decimal)


def test_the_locale_of_the_document_decides_the_parse() -> None:
    """The same form is two amounts in two locales, and the locale of the document decides."""
    assert parse_amount("1.000,00", "br") == Decimal("1000.00")
    assert parse_amount("1,000.00", "us") == Decimal("1000.00")
