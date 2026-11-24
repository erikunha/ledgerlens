"""The conversion of a document: the text layer of a PDF and the decoding of an image, without a shell.

Why the conversion never calls a shell: a shell that converts a document is a shell that runs a program of
the machine, and the pipeline of the repository converts a document with the readers of the dependencies and
never with a process. A conversion that called a shell would be a conversion that the sandbox of the
repository cannot bound.

Why the conversion never leaves a temporary file behind: a temporary file that survives the conversion is a
copy of the document that the pipeline did not name, and the pipeline keeps no copy of a document beyond the
read of it.

Why the reader of a format that is not installed is a refusal and not a crash: the offline gate runs with no
key and no network, and a pipeline whose only path asks for a converter that is not installed could never be
part of it. The refusal names the converter that is missing.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["ConversionRefused", "read_text"]


class ConversionRefused(Exception):
    """The document cannot be converted, and the message names the converter that is missing."""


def read_text(path: Path) -> str:
    """The text layer of a document: the text of a text file, or the text layer of a PDF.

    Why the text file is read directly: the fixtures of the repository carry the text layer of the document,
    and a text file is the text layer itself. A PDF needs the reader of the text layer, and a reader that is
    not installed is a refusal, not a crash.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ConversionRefused(
                "the text layer of a PDF needs the reader pypdf, which is not installed: the offline gate runs "
                "with no key and no network, and the refusal names the converter that is missing"
            ) from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ConversionRefused(
        f"the pipeline reads the text layer of a document, and {suffix or 'this file'} has no text layer: an "
        "image goes to the vision path, and this file is not one the deterministic path reads"
    )
