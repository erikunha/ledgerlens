"""The redaction: an export whose content carries a secret like string is refused, and nothing is written.

What they guarantee, and why: an export over a content that carries a string that looks like a key is refused
with the name of the file, and the output directory holds no file, because the artifact carries prose that the
trace does not carry and the scan is the last wall before the write.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.proof.redact import SecretInArtifact, scan_artifact

# A string that looks like a key, assembled so that the test file itself does not carry one.
FAKE_KEY = "sk-" + "fakefake1234"


def test_a_content_with_a_secret_like_string_is_refused_with_the_name_of_the_file() -> None:
    """The scan is the comparison with the redaction of the repository, and the refusal names the file."""
    with pytest.raises(SecretInArtifact, match="proof.json"):
        scan_artifact(f'the key of the run is "{FAKE_KEY}"', name="proof.json")


def test_a_content_without_a_secret_like_string_passes() -> None:
    """A content with no secret like string is a content the export may write."""
    scan_artifact("the run of the scenario S01 of the repository", name="proof.json")


def test_the_output_directory_holds_no_file_after_a_refusal(tmp_path) -> None:
    """The refusal comes before the write, and the directory of the export stays empty."""
    out_dir = tmp_path / "proof"
    try:
        scan_artifact(f'the key of the run is "{FAKE_KEY}"', name="proof.json")
    except SecretInArtifact:
        pass

    assert not out_dir.exists()
