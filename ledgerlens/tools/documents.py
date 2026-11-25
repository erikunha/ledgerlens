"""The tool of the extraction of a document: the fields of a document, with the evidence of the repository.

Why the tool exists: the agent of the repository reads a document through this tool, and the tool returns the
`Evidence` of the repository with a source of `doc`, so the verifier consumes the extraction without learning
a second kind of evidence. A document is a source of a claim and never an authority.

What the tool refuses: a path outside the fixtures of the repository (the refusal happens before the file is
opened), a file that fails the file security, a file whose license is unknown and a file with no text layer.
The refusals are the envelope of the repository, with the reason, and never a stack of a library.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from pydantic import Field as PydanticField

from ledgerlens.documents.convert import ConversionRefused, read_text
from ledgerlens.documents.detect import DocumentRefused, check_path
from ledgerlens.documents.evidence import document_digest, evidence_of
from ledgerlens.documents.fields import extract_fields
from ledgerlens.documents.license import LicenseRefused, license_of
from ledgerlens.documents.security import SecurityRefused, check_file
from ledgerlens.tools.envelope import error, ok

__all__ = ["build_extract_document_tool", "extract_document"]

DESCRIPTION = (
    "Read the fields of a document of the fixtures of the repository and return them as evidence, with the page "
    "and the position of each field. A document is a source of a claim and never an authority: the ledger keeps "
    "the authority of what happened, and a disagreement between a document and the ledger is a finding that a "
    "person has to look at. The tool reads only the fixtures of the repository and refuses every other path."
)


class ExtractDocumentInput(BaseModel):
    """The input of the tool: the path of the document, inside the fixtures of the repository."""

    path: str = PydanticField(description="the path of the document, inside data/fixtures/documents/")


def extract_document(path: str) -> dict[str, Any]:
    """The extraction of a document: the fields of it as evidence, or the refusal with the reason."""
    try:
        resolved = check_path(path)
        check_file(resolved)
        license_name = license_of(resolved.parent, resolved.name)
        text = read_text(resolved)
    except (DocumentRefused, SecurityRefused, LicenseRefused, ConversionRefused) as refusal:
        return error("DOCUMENT_REFUSED", str(refusal), False)
    fields = extract_fields(text)
    digest = document_digest(resolved)
    records = evidence_of(fields, digest=digest, license_name=license_name)
    return ok(
        [record.id for record in records],
        {
            "fields": [
                {
                    "name": field.name,
                    "value": None if field.value is None else str(field.value),
                    "page": field.page,
                    "position": field.position,
                    "confidence": field.confidence,
                    "extraction_version": field.extraction_version,
                }
                for field in fields
            ],
            "digest": digest,
            "license": license_name,
        },
    )


def build_extract_document_tool() -> StructuredTool:
    """The tool of the extraction, with the envelope of the repository and the `Evidence` of the repository."""
    return StructuredTool.from_function(
        func=extract_document,
        name="extract_document",
        description=DESCRIPTION,
        args_schema=ExtractDocumentInput,
    )
