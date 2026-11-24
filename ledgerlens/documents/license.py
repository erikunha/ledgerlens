"""The license of a document: a document without a declared license is not read.

Why the license is checked: the fixtures of the documents are synthetic and they carry a license, and a
document whose license is unknown is a document the repository may not read, because the license is what says
the repository may keep it and read it. A document without a declared license is not read.

Why the check is of the manifest and not of the file: the manifest of the fixtures declares the license of
each fixture, and the check reads the declaration. A file that declares no license in the manifest is a file
whose license is unknown.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["KNOWN_LICENSES", "LicenseRefused", "check_license", "license_of"]

# The licenses the repository knows: the licenses under which a fixture may be kept and read.
KNOWN_LICENSES = frozenset({"CC0-1.0", "CC-BY-4.0", "MIT"})


class LicenseRefused(Exception):
    """The license of the document is unknown, and the document is not read."""


def license_of(fixtures_dir: Path, file_name: str) -> str:
    """The license of a fixture, from the manifest of the fixtures, and the refusal of an unknown one.

    Why the refusal names the file: a refusal that does not name the file is a refusal the caller cannot act
    on, and the license of a document is a fact of the document.
    """
    manifest = Path(fixtures_dir) / "manifest.json"
    if not manifest.is_file():
        raise LicenseRefused(
            f"the manifest of the fixtures is not on the disk, so the license of {file_name} is unknown"
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in data.get("fixtures", []):
        if entry.get("file") == file_name:
            license_name = str(entry.get("license", ""))
            if license_name not in KNOWN_LICENSES:
                raise LicenseRefused(
                    f"the license {license_name!r} of the fixture {file_name} is unknown, and a document without "
                    "a declared license is not read"
                )
            return license_name
    raise LicenseRefused(f"the fixture {file_name} is not in the manifest of the fixtures, so its license is unknown")


def check_license(fixtures_dir: Path, file_name: str) -> str:
    """The license of a fixture, checked. The same as `license_of`, for the caller that reads the license."""
    return license_of(fixtures_dir, file_name)
