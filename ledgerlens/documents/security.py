"""The file security of a document: a file that must not be opened is refused before it is converted.

Why the checks happen before the conversion: the conversion of a document is the moment a reader of the file
is attacked, and the checks of the file are the wall before it. A check that happened after the conversion
would be a check of a file that was already converted.

Why there are four checks: each one answers a reader that a hostile file attacks. The executable payload
attacks the machine that opens the file, the compressed bomb attacks the disk of the machine, the password
attacks the reader that asks for a secret, and the size attacks the memory of the machine. The check names
the reader it answers, and the refusal is readable.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

__all__ = ["MAX_BYTES", "MAX_EXPANSION", "SecurityRefused", "check_file"]

# The limits of the file security: the size of the file and the expansion of a compressed form.
MAX_BYTES = 5 * 1024 * 1024
MAX_EXPANSION = 100

# The magic bytes of an executable payload: a file that starts with one of them is not a document.
_EXECUTABLE_MAGICS = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe")


class SecurityRefused(Exception):
    """The file is refused, and the message says which check refused it and why."""


def check_file(path: Path) -> None:
    """The four checks of the file security, each with a readable reason.

    Why the checks are of the bytes and not of the name: the name of a file says nothing about what the file
    is, and the bytes say it. The checks read the bytes of the file, and they never open it for conversion.
    """
    path = Path(path)
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise SecurityRefused(
            f"the file is {size} bytes and the limit is {MAX_BYTES}: the size attacks the memory of the machine "
            "that reads it"
        )
    head = path.read_bytes()[:4]
    for magic in _EXECUTABLE_MAGICS:
        if head.startswith(magic):
            raise SecurityRefused(
                f"the file starts with the magic {magic!r} of an executable payload: the payload attacks the "
                "machine that opens the file"
            )
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.flag_bits & 0x1:
                    raise SecurityRefused(
                        f"the file {info.filename} of the archive is protected by a password: the password "
                        "attacks the reader that asks for a secret"
                    )
                if info.compress_size and info.file_size / info.compress_size > MAX_EXPANSION:
                    raise SecurityRefused(
                        f"the file {info.filename} of the archive expands {info.file_size // info.compress_size} "
                        "times past the limit: the expansion attacks the disk of the machine"
                    )
    if path.suffix.lower() == ".pdf" and b"/Encrypt" in path.read_bytes():
        raise SecurityRefused(
            "the document is protected by a password: the password attacks the reader that asks for a secret"
        )
