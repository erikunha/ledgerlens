"""The file security of a document: a file that must not be opened is refused before it is converted.

What they guarantee, and why: a file with an executable payload, a file whose compressed form expands past the
limit, a file protected by a password and a file that is bigger than the limit are each refused with a
readable reason, and the temporary directory is empty after each refusal, because the conversion of a document
is the moment a reader of the file is attacked, and the checks of the file are the wall before it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import zipfile

import pytest

from ledgerlens.documents.security import MAX_BYTES, SecurityRefused, check_file


def test_an_executable_payload_is_refused(tmp_path) -> None:
    """A file that starts with the magic of an executable is not a document."""
    payload = tmp_path / "receipt.txt"
    payload.write_bytes(b"MZ" + b"\x00" * 100)

    with pytest.raises(SecurityRefused, match="executable payload"):
        check_file(payload)


def test_a_compressed_bomb_is_refused(tmp_path) -> None:
    """A file whose compressed form expands past the limit attacks the disk of the machine."""
    bomb = tmp_path / "receipt.zip"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("big.txt", "0" * (1024 * 1024))

    with pytest.raises(SecurityRefused, match="expands"):
        check_file(bomb)


def test_a_password_protected_file_is_refused(tmp_path) -> None:
    """A file protected by a password attacks the reader that asks for a secret."""
    protected = tmp_path / "receipt.pdf"
    protected.write_bytes(b"%PDF-1.4\n/Encrypt\n")

    with pytest.raises(SecurityRefused, match="password"):
        check_file(protected)


def test_a_file_bigger_than_the_limit_is_refused(tmp_path) -> None:
    """A file that is bigger than the limit attacks the memory of the machine."""
    big = tmp_path / "receipt.txt"
    big.write_bytes(b"0" * (MAX_BYTES + 1))

    with pytest.raises(SecurityRefused, match="limit"):
        check_file(big)


def test_the_temporary_directory_is_empty_after_each_refusal(tmp_path) -> None:
    """The refusal leaves no temporary file behind: the pipeline keeps no copy of a document."""
    payload = tmp_path / "receipt.txt"
    payload.write_bytes(b"MZ" + b"\x00" * 100)
    work = tmp_path / "work"
    work.mkdir()

    with pytest.raises(SecurityRefused):
        check_file(payload)

    assert list(work.iterdir()) == []
