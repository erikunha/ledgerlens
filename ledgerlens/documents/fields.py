"""The fields of a document: every field says where it was read, and an uncertain value is not a value.

Why a field carries the page and the position: the verifier of the repository checks a claim against the
evidence, and the evidence of a document is the field with the page and the position it was read from. A field
that named no place would be a field that the verifier cannot check.

Why a value that was not read with certainty is not a value: a blurred field carries no value, and its kind of
confidence names the doubt, and the case asks the person. A value that the parser was not certain of would be
a value that the verifier would check as if it were read, and the pipeline never publishes a value it did not
read with certainty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.documents.money import locale_of, parse_amount

__all__ = ["CONFIDENCE_KINDS", "EXTRACTION_VERSION", "Field", "extraction_refused", "extract_fields"]

# The kinds of confidence of a field: the value was read with certainty, the value names a doubt, or the value
# was not read. A value that was not read with certainty is not a value.
CONFIDENCE_KINDS = ("read", "uncertain", "not_read")

# The version of the extractor of the repository: the fields of a result carry it, so the reader of a result
# knows which extractor read them.
EXTRACTION_VERSION = "v1"

# The fields of the repository: the name of each one and the line of the document it is read from.
_FIELD_LINES = {
    "merchant": re.compile(r"^(?:Loja|Store|Geschaft):\s*(?P<value>.+)$"),
    "date": re.compile(r"^(?:Data|Date|Datum):\s*(?P<value>.+)$"),
    "transaction": re.compile(r"^(?:Transacao|Transaction):\s*(?P<value>.+)$"),
    "total": re.compile(r"^(?:Total|Gesamtbetrag):\s*(?P<value>.+?)\s+(?P<currency>[A-Z]{3})$"),
}


@dataclass(frozen=True)
class Field:
    """A field of a document: the name, the value, the page, the position, the confidence and the version.

    Why the value is a `Decimal` or a text or nothing: the amount of a document is a `Decimal`, the name of a
    merchant is a text, and a value that was not read with certainty is nothing, with the kind of confidence
    that names the doubt.
    """

    name: str
    value: Decimal | str | None
    page: int
    position: str
    confidence: str
    extraction_version: str


def extraction_refused(reason: str) -> Exception:
    """The refusal of an extraction, with the reason."""
    return ValueError(f"the extraction is refused: {reason}")


def extract_fields(text: str, *, extractor_version: str = EXTRACTION_VERSION) -> list[Field]:
    """The fields of a document, with the page and the position of each one.

    Why the version is an argument and not a default of the result: a result that names no version is a result
    that the reader cannot place, and the version of the extractor is a fact of the extraction.
    """
    if not extractor_version:
        raise extraction_refused(
            "the version of the extractor is missing, and a result that names no version is refused"
        )
    fields: list[Field] = []
    for position, line in enumerate(text.splitlines(), start=1):
        for name, pattern in _FIELD_LINES.items():
            match = pattern.match(line.strip())
            if match is None:
                continue
            value, confidence = _value_of(name, match)
            fields.append(
                Field(
                    name=name,
                    value=value,
                    page=1,
                    position=f"line {position}",
                    confidence=confidence,
                    extraction_version=extractor_version,
                )
            )
    return fields


def _value_of(name: str, match: re.Match[str]) -> tuple[Decimal | str | None, str]:
    """The value of a field and its kind of confidence: the amount with the locale, or the doubt of a blur."""
    raw = match.group("value").strip()
    if name != "total":
        return raw, "read"
    currency = match.group("currency")
    if "?" in raw:
        # The blurred field: the value is not read with certainty, and the kind of confidence names the doubt.
        return None, "uncertain"
    try:
        return parse_amount(raw, locale_of("", currency)), "read"
    except Exception:
        return None, "not_read"
