"""The evidence of a document: the id matches the scheme, and the `ref` holds the page and the position.

What they guarantee, and why: (a) the id of a document evidence matches the scheme of
`ledgerlens/tools/envelope.py`, and the `EvidenceSource` and the `ToolName` literals of `ledgerlens/schemas.py`
carry the new member, because the verifier consumes the extraction without learning a second kind of evidence;
(b) the evidence of a document carries the `ref` that holds the page and the position, because the reader of
the evidence has to find the field on the page of the document.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.documents.convert import read_text
from ledgerlens.documents.evidence import document_digest, evidence_of
from ledgerlens.documents.fields import extract_fields
from ledgerlens.schemas import EvidenceSource, ToolName
from ledgerlens.tools.envelope import EVIDENCE_ID

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_the_source_and_the_tool_of_a_document_are_of_the_repository() -> None:
    """The literals of the repository carry the source `doc` and the tool `extract_document`."""
    assert "doc" in EvidenceSource.__args__
    assert "extract_document" in ToolName.__args__


def test_the_id_of_a_document_evidence_matches_the_scheme() -> None:
    """The id of a document evidence matches the scheme of the envelope of the repository."""
    text = read_text(FIXTURES / "receipt_br.txt")
    fields = extract_fields(text)
    digest = document_digest(FIXTURES / "receipt_br.txt")
    evidence = evidence_of(fields, digest=digest, license_name="CC0-1.0")

    assert evidence
    for record in evidence:
        assert EVIDENCE_ID.match(record.id), f"the id {record.id} is outside the scheme of the envelope"
        assert record.id.startswith("doc:")


def test_the_ref_of_a_document_evidence_holds_the_page_and_the_position() -> None:
    """The reader of the evidence finds the field on the page of the document."""
    text = read_text(FIXTURES / "receipt_br.txt")
    fields = extract_fields(text)
    digest = document_digest(FIXTURES / "receipt_br.txt")
    evidence = evidence_of(fields, digest=digest, license_name="CC0-1.0")

    for record in evidence:
        assert "page 1" in record.ref
        assert "line " in record.ref
