"""The license of a document: a document without a declared license is not read.

What they guarantee, and why: (a) every fixture of the manifest carries a license, because the license is what
says the repository may keep it and read it; (b) the extraction refuses a fixture whose license is unknown,
because a document without a declared license is not read.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlens.documents.license import LicenseRefused, license_of

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def test_every_fixture_of_the_manifest_carries_a_license() -> None:
    """The manifest declares the license of every fixture, and the license is known."""
    data = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

    assert data["fixtures"]
    for entry in data["fixtures"]:
        assert entry["license"], f"the fixture {entry['file']} carries no license"
        assert license_of(FIXTURES, entry["file"]) == entry["license"]


def test_the_extraction_refuses_a_fixture_whose_license_is_unknown(tmp_path) -> None:
    """A document without a declared license is not read."""
    (tmp_path / "manifest.json").write_text(
        json.dumps({"fixtures": [{"file": "receipt.txt", "license": "proprietary", "sha256": "a" * 64}]}),
        encoding="utf-8",
    )

    with pytest.raises(LicenseRefused, match="unknown"):
        license_of(tmp_path, "receipt.txt")

    with pytest.raises(LicenseRefused, match="not in the manifest"):
        license_of(tmp_path, "another.txt")
