"""The conversion of a document: the text layer of a fixture, and the refusal when the converter is absent.

What they guarantee, and why: (a) the text layer of a fixture is read, because the fixtures of the repository
carry the text layer of the document; (b) a file that needs a converter that is not installed is refused with
a readable reason, because the offline gate runs with no key and no network, and a pipeline whose only path
asks for a converter that is not installed could never be part of it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.documents.convert import ConversionRefused, read_text

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_the_text_layer_of_a_fixture_is_read() -> None:
    """The fixtures carry the text layer of the document, and the conversion reads it."""
    text = read_text(FIXTURES / "receipt_br.txt")

    assert "Casa Verde Foods" in text
    assert "1.000,00 BRL" in text


def test_a_pdf_is_refused_when_the_reader_is_not_installed(tmp_path, monkeypatch) -> None:
    """The refusal names the converter that is missing, and it is not a crash."""
    import builtins

    real_import = builtins.__import__

    def no_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("No module named 'pypdf'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pypdf)
    pdf = tmp_path / "receipt.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(ConversionRefused, match="pypdf"):
        read_text(pdf)


def test_a_file_with_no_text_layer_is_refused(tmp_path) -> None:
    """An image goes to the vision path, and the deterministic path refuses it."""
    image = tmp_path / "receipt.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(ConversionRefused, match="no text layer"):
        read_text(image)
