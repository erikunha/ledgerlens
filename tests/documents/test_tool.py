"""The tool of the extraction: the shape of the envelope for a success and for each refusal.

What they guarantee, and why: the tool of the extraction returns the envelope of the repository for a success
and for each refusal, because the agent of the repository reads the envelope and a refusal that was not an
envelope would be a refusal the agent could not read.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.tools.documents import build_extract_document_tool, extract_document

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_the_envelope_of_a_success_carries_the_fields_and_the_evidence() -> None:
    """The success of the tool: the fields of the document and the ids of the evidence."""
    out = extract_document(str(FIXTURES / "receipt_br.txt"))

    assert out["ok"] is True
    assert out["evidence_ids"]
    assert all(evidence_id.startswith("doc:") for evidence_id in out["evidence_ids"])
    total = next(field for field in out["data"]["fields"] if field["name"] == "total")
    assert total["value"] == "1000.00"
    assert total["confidence"] == "read"
    assert out["data"]["license"] == "CC0-1.0"


def test_the_envelope_of_a_path_outside_the_fixtures_is_a_refusal() -> None:
    """A path outside the fixtures is refused, and the refusal is an envelope."""
    out = extract_document("/etc/passwd")

    assert out["ok"] is False
    assert out["error"]["code"] == "DOCUMENT_REFUSED"
    assert "outside" in out["error"]["message"]


def test_the_envelope_of_a_file_with_no_text_layer_is_a_refusal(tmp_path) -> None:
    """A file with no text layer is refused, and the refusal is an envelope."""
    image = FIXTURES / "receipt.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    try:
        out = extract_document(str(image))
    finally:
        image.unlink()

    assert out["ok"] is False
    assert out["error"]["code"] == "DOCUMENT_REFUSED"


def test_the_tool_is_built_with_the_envelope_of_the_repository() -> None:
    """The tool of the extraction is a tool of the repository, with the name of the catalog."""
    tool = build_extract_document_tool()

    assert tool.name == "extract_document"
