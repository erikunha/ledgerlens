"""The scan of the finished artifact: the last wall before the file is written.

Why the scan is the last wall: the trace is redacted when it is written, and the finished artifact is scanned
again, because the artifact carries prose and a report that the trace does not carry. The scan uses the
`redact` of `ledgerlens/observability/callbacks.py`, and an export whose content carries a secret like string
is refused with the name of the file, and nothing is written.
"""

from __future__ import annotations

from ledgerlens.observability.callbacks import redact

__all__ = ["SecretInArtifact", "scan_artifact"]


class SecretInArtifact(ValueError):
    """The finished artifact carries a string that looks like a key, and the message names the file."""


def scan_artifact(text: str, *, name: str) -> None:
    """The refusal of an artifact whose content carries a secret like string, with the name of the file.

    The scan is the comparison of the content with the content the redaction of the repository would write:
    when the two differ, the content carries a secret like string, and the export is refused before anything
    is written.
    """
    if redact(text) != text:
        raise SecretInArtifact(f"the artifact {name} carries a string that looks like a key")
