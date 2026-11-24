"""The redaction of a shared copy of a document: a shared copy is a copy and never the document.

Why the shared copy is redacted: a copy of a document that leaves the session of the person who asked is a
copy that strangers read, and the addresses and the card digits of the document are not for strangers. The
shared copy is redacted, and the flag of the redaction is present, so the reader of the copy knows it is a
copy and not the document.

Why the flag of the redaction is present: a copy that hid that it was redacted would be a copy that asks to
be read as the document, and the shared copy is a copy and never the document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["RedactedCopy", "redact_copy"]

# The shapes of the addresses and of the card digits of a document. The shared copy holds neither.
_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b|\b\d{3}[ .-]?\d{3}[ .-]?\d{3}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


@dataclass(frozen=True)
class RedactedCopy:
    """The shared copy of a document: the text with the addresses and the card digits gone, and the flag of it."""

    text: str
    redacted: bool


def redact_copy(text: str) -> RedactedCopy:
    """The shared copy of a document: the addresses and the card digits are gone from it.

    Why the flag of the redaction travels with the copy: the reader of the copy has to know it is a copy and
    not the document, and a copy that hid the redaction would be a copy that asks to be read as the document.
    """
    redacted = _ADDRESS.sub("[redacted]", text)
    redacted = _CARD.sub("[redacted]", redacted)
    return RedactedCopy(text=redacted, redacted=True)
