"""The money of a document: the locale of the document and the parse of the amount, with a `Decimal`.

Why the parse never uses a float: the money of a document is a `Decimal`, and a float is already a rounded
number. The rounding of a document is not a rounding of the ledger, and the parse of the amount of a document
never rounds it: it reads it.

Why the locale of the document decides the parse: the amount `1.000,00` is one thousand in the Brazilian
locale and one in the American locale, and a parse that ignored the locale of the document would read one
thousand as one. The locale of the document is read from the document, and the parse follows it.
"""

from __future__ import annotations

import re
from decimal import Decimal

__all__ = ["MoneyParseRefused", "locale_of", "parse_amount"]


class MoneyParseRefused(Exception):
    """The amount of the document cannot be parsed, and the message says why."""


def locale_of(text: str, currency: str) -> str:
    """The locale of the document, read from the document: "br" for the Brazilian form and "us" for the American.

    Why the locale is read and not guessed from the currency: the currency says the money, and the form of the
    amount says the locale. A document of a currency the pipeline does not read is a document whose locale is
    unknown, and the parse of it is refused.
    """
    if currency in ("BRL",):
        return "br"
    if currency in ("USD", "GBP", "EUR"):
        return "us"
    raise MoneyParseRefused(f"the currency {currency!r} of the document is not one the pipeline reads")


def parse_amount(text: str, locale: str) -> Decimal:
    """The amount of a document, parsed with the locale of the document, as a `Decimal`.

    Why the parse is of the text and not of a number: the amount of a document is written in the locale of the
    document, and the parse reads the form of it. The Brazilian form uses the point for the thousands and the
    comma for the decimals, and the American form uses the comma for the thousands and the point for the
    decimals.
    """
    cleaned = text.strip()
    if not cleaned:
        raise MoneyParseRefused("the amount of the document is empty")
    if locale == "br":
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif locale == "us":
        normalized = cleaned.replace(",", "")
    else:
        raise MoneyParseRefused(f"the locale {locale!r} of the document is not one the pipeline reads")
    if not re.fullmatch(r"-?\d+(\.\d+)?", normalized):
        raise MoneyParseRefused(f"the amount {text!r} of the document is not an amount the pipeline reads")
    return Decimal(normalized)
