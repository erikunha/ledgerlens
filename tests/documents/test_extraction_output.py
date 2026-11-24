"""The extraction of the fields of a document: every field says where it was read, and the version is required.

What they guarantee, and why: (a) every field of the result carries the digest of the document, the page, the
position, the name, the value, the kind of confidence, the version of the extractor and the license, because
the verifier of the repository checks a claim against the evidence, and the evidence of a document is the
field with the page and the position it was read from; (b) the extraction is refused when the version is
missing, because a result that names no version is a result that the reader cannot place.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.documents.convert import read_text
from ledgerlens.documents.evidence import document_digest, evidence_of
from ledgerlens.documents.fields import extract_fields

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_every_field_carries_where_it_was_read_and_the_version() -> None:
    """The digest, the page, the position, the name, the value, the confidence, the version and the license."""
    text = read_text(FIXTURES / "receipt_br.txt")
    fields = extract_fields(text)
    digest = document_digest(FIXTURES / "receipt_br.txt")
    evidence = evidence_of(fields, digest=digest, license_name="CC0-1.0")

    assert fields
    total = next(field for field in fields if field.name == "total")
    assert str(total.value) == "1000.00"
    assert total.page == 1
    assert total.position.startswith("line ")
    assert total.confidence == "read"
    assert total.extraction_version
    for record in evidence:
        assert record.id.startswith(f"doc:{digest[:12]}")
        assert record.source_type == "doc"
        assert "page 1" in record.ref
        assert "CC0-1.0" in record.content


def test_the_extraction_is_refused_when_the_version_is_missing() -> None:
    """A result that names no version is a result that the reader cannot place."""
    with pytest.raises(ValueError, match="version of the extractor is missing"):
        extract_fields("Total: 100.00 USD", extractor_version="")
