"""The evidence of a document: the `Evidence` records of the extraction, with the page and the position of each one.

Why the evidence is of the repository and not a second kind: the verifier of the repository checks a claim
against the evidence, and the extraction produces the `Evidence` of the repository with a source of `doc`, so
the verifier consumes the extraction without learning a second kind of evidence.

Why a document is a source of a claim and never an authority: the ledger states what happened, and a document
states what someone wrote down about it. The evidence of a document says what the document says, with the page
and the position of it, and the verifier decides whether the claim of the case is supported by it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ledgerlens.documents.fields import Field
from ledgerlens.schemas import Evidence

__all__ = ["document_digest", "evidence_of"]


def document_digest(path: Path) -> str:
    """The digest of the document: the sha256 of the bytes of it, so the evidence names the document it read."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence_of(fields: list[Field], *, digest: str, license_name: str) -> list[Evidence]:
    """The `Evidence` records of the extraction: one per field, with the page and the position in the `ref`.

    Why the `ref` holds the page and the position: the verifier of the repository checks a claim against the
    evidence, and the reader of the evidence has to find the field on the page of the document. A `ref` that
    named no place would be a `ref` that the reader cannot follow.
    """
    now = datetime.now(UTC)
    records: list[Evidence] = []
    for index, field in enumerate(fields, start=1):
        content = (
            f"{field.name}: {field.value}"
            if field.value is not None
            else f"{field.name}: the value was not read with certainty"
        )
        records.append(
            Evidence(
                id=f"doc:{digest[:12]}:{index}",
                source_type="doc",
                tool="extract_document",
                content=f"{content} (page {field.page}, {field.position}, confidence {field.confidence}, "
                f"extractor {field.extraction_version}, license {license_name})",
                ref=f"page {field.page}, {field.position}",
                retrieved_at=now,
            )
        )
    return records
