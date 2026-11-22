"""Tests of the check that keeps the manifest of the eval datasets honest.

Why they exist: the numbers the reports of the repository publish depend on the datasets of `data/eval/`, and a
dataset that moves without the manifest moving makes a number describe a file that is not on the disk. The check
`scripts/check_eval_datasets.py` is what stops that, so it needs a test for every way it can fail.

The tests never touch the real repository: every fixture is built inside a temporary directory, with its own copy
of the data folder and its own copy of the manifest, and the script is called as a subprocess against that
temporary root. The exit code and the message of the failure are the contract of the script, and they are what
the assertions below check. The manifest of the repository is only read, to prove that a check of another root
does not write it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from ledgerlens.eval.manifest import verify_manifests

REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts" / "check_eval_datasets.py"

CONTAMINATION_POLICY = "the rule of the test fixture, which says what may be done with the dataset"


def _sha256(path: Path) -> str:
    """The sha256 of the bytes of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, records: int) -> None:
    """A JSONL file with the number of records asked for, one record per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"case_id": f"c{index}", "text": f"record {index}"}) for index in range(records)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _entry(dataset_id: str, relative: str, digest: str, records: int, role: str = "tuning") -> dict:
    """One entry of the manifest, with every field the contract declares."""
    return {
        "dataset_id": dataset_id,
        "path": relative,
        "sha256": digest,
        "records_count": records,
        "source": "the fixture of the test",
        "labeling_version": "v1",
        "split_role": role,
        "scenario_seed": 42,
        "contamination_policy": CONTAMINATION_POLICY,
        "notes": "a note of the fixture",
    }


def _write_manifest(root: Path, entries: list[dict]) -> Path:
    """The manifest file of a temporary root, written as the canonical text."""
    path = root / "data" / "eval" / "datasets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"datasets": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_root(tmp_path: Path, records: int = 3) -> tuple[Path, Path]:
    """A temporary root with one dataset and a manifest that matches it."""
    root = tmp_path / "repo"
    dataset = root / "data" / "eval" / "cases.jsonl"
    _write_jsonl(dataset, records)
    manifest = _write_manifest(
        root,
        [_entry("cases", "data/eval/cases.jsonl", _sha256(dataset), records)],
    )
    return root, manifest


def _run(
    root: Path,
    *arguments: str,
    with_manifest: bool = True,
) -> subprocess.CompletedProcess[str]:
    """The check, called as a subprocess against a temporary root.

    The environment stops git from finding a repository above the temporary root, so a temporary root that is not
    a repository of its own has no committed manifest and the tests do not depend on where they run.
    """
    command = [sys.executable, str(SCRIPT), "--root", str(root)]
    if with_manifest:
        command += ["--manifest", str(root / "data" / "eval" / "datasets.json")]
    command += list(arguments)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(root)},
    )


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """A git command inside a temporary repository."""
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )


def test_passing_manifest_says_that_every_dataset_matches(tmp_path: Path) -> None:
    """A manifest that matches the disk passes with the code zero and one line of output."""
    root, _manifest = _build_root(tmp_path)

    done = _run(root)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "every dataset matches the manifest" in done.stdout


def test_a_dataset_that_moved_fails_and_names_the_two_values(tmp_path: Path) -> None:
    """A file whose sha256 does not match the manifest fails, naming the dataset, the file and both values."""
    root, _manifest = _build_root(tmp_path)
    dataset = root / "data" / "eval" / "cases.jsonl"
    declared = _sha256(dataset)
    _write_jsonl(dataset, 4)

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "cases" in output
    assert "data/eval/cases.jsonl" in output
    assert declared in output
    assert _sha256(dataset) in output


def test_a_dataset_with_a_different_count_fails_and_names_the_two_counts(tmp_path: Path) -> None:
    """A file whose record count does not match the manifest fails, naming both counts."""
    root, manifest = _build_root(tmp_path, records=3)
    dataset = root / "data" / "eval" / "cases.jsonl"
    # The digest of the file is right and only the count is wrong, so the check cannot pass it by the digest.
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entries = _entries(payload)
    entries[0]["sha256"] = _sha256(dataset)
    entries[0]["records_count"] = 4
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "cases" in output
    assert "3 records" in output
    assert "4 records" in output


def test_a_missing_dataset_fails_and_names_the_dataset_and_the_file(tmp_path: Path) -> None:
    """A dataset the manifest declares but the disk does not have fails."""
    root, _manifest = _build_root(tmp_path)
    (root / "data" / "eval" / "cases.jsonl").unlink()

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "cases" in output
    assert "data/eval/cases.jsonl" in output
    assert "does not exist" in output


def test_a_dataset_that_nobody_declared_fails(tmp_path: Path) -> None:
    """A JSONL file of the folder that no entry declares fails."""
    root, _manifest = _build_root(tmp_path)
    _write_jsonl(root / "data" / "eval" / "stray.jsonl", 2)

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "stray.jsonl" in output
    assert "not declared" in output


def test_the_script_and_the_module_see_the_same_problems(tmp_path: Path) -> None:
    """The rule lives in the module, so the check of the script and the module report the same thing.

    The manifest declares a dataset of another folder and the folder of the datasets holds a file that no entry
    declares: the module refuses it and the script has to refuse it too.
    """
    root = tmp_path / "repo"
    dataset = root / "data" / "other" / "cases.jsonl"
    _write_jsonl(dataset, 2)
    _write_manifest(root, [_entry("cases", "data/other/cases.jsonl", _sha256(dataset), 2)])
    _write_jsonl(root / "data" / "eval" / "stray.jsonl", 1)

    problems = verify_manifests(root)
    done = _run(root)

    assert len(problems) == 1
    assert "stray.jsonl" in problems[0]
    assert done.returncode != 0
    assert "stray.jsonl" in done.stdout + done.stderr


def test_the_verify_writes_nothing(tmp_path: Path) -> None:
    """The verify reads the disk and leaves the manifest exactly as it found it."""
    root, manifest = _build_root(tmp_path)
    _write_jsonl(root / "data" / "eval" / "cases.jsonl", 4)
    before = manifest.read_bytes()

    done = _run(root)

    assert done.returncode != 0
    assert manifest.read_bytes() == before


def test_a_broken_manifest_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    """A manifest that is not JSON is a readable refusal, never a traceback."""
    root = tmp_path / "repo"
    manifest = root / "data" / "eval" / "datasets.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{not json", encoding="utf-8")

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "Traceback" not in output
    assert "manifest" in output


def test_a_dataset_that_is_not_valid_utf8_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    """A dataset whose bytes are not valid UTF-8 is a readable refusal, never a traceback."""
    root, _manifest = _build_root(tmp_path)
    dataset = root / "data" / "eval" / "cases.jsonl"
    dataset.write_bytes(b'{"case_id": "c0"}\n\xff\xfe\n')

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "Traceback" not in output
    assert "UTF-8" in output
    assert "cases" in output


def test_a_manifest_that_is_not_valid_utf8_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    """A manifest file whose bytes are not valid UTF-8 is a readable refusal, never a traceback."""
    root = tmp_path / "repo"
    manifest = root / "data" / "eval" / "datasets.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(b'{"datasets": [\xff]}')

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "Traceback" not in output
    assert "UTF-8" in output


def test_a_dataset_that_cannot_be_opened_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    """A declared dataset that cannot be opened is a readable refusal, never a traceback."""
    root, _manifest = _build_root(tmp_path)
    dataset = root / "data" / "eval" / "cases.jsonl"
    dataset.unlink()
    dataset.mkdir()

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "Traceback" not in output
    assert "could not be read" in output


def test_a_symlink_that_points_outside_the_root_is_refused(tmp_path: Path) -> None:
    """A dataset that is a link to a file outside the root is refused and the file outside is never read.

    The manifest declares the sha256 and the record count of the file outside the root, so a check that read the
    file would find the two of them in agreement and would pass. The refusal is the proof that the file was not
    read as a dataset of the repository.
    """
    root = tmp_path / "repo"
    outside = tmp_path / "outside.jsonl"
    _write_jsonl(outside, 2)
    link = root / "data" / "eval" / "cases.jsonl"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    _write_manifest(root, [_entry("cases", "data/eval/cases.jsonl", _sha256(outside), 2)])

    done = _run(root)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "Traceback" not in output
    assert "outside the root" in output
    assert "cases" in output


def test_write_refuses_a_symlink_that_points_outside_the_root(tmp_path: Path) -> None:
    """The write refuses the entry whose path leaves the root and writes nothing."""
    root = tmp_path / "repo"
    outside = tmp_path / "outside.jsonl"
    _write_jsonl(outside, 2)
    link = root / "data" / "eval" / "cases.jsonl"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    manifest = _write_manifest(root, [_entry("cases", "data/eval/cases.jsonl", _sha256(outside), 2)])
    before = manifest.read_bytes()

    done = _run(root, "--write")

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "outside the root" in output
    assert manifest.read_bytes() == before


def test_write_refuses_to_invent_an_entry(tmp_path: Path) -> None:
    """The write refuses to declare a file of the disk that the manifest does not declare."""
    root, manifest = _build_root(tmp_path)
    _write_jsonl(root / "data" / "eval" / "stray.jsonl", 2)
    before = manifest.read_bytes()

    done = _run(root, "--write")

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "stray.jsonl" in output
    assert "adding an entry is a hand edit of the manifest" in output
    assert manifest.read_bytes() == before


def test_write_refuses_to_remove_an_entry(tmp_path: Path) -> None:
    """The write refuses to drop a dataset the manifest declares but the disk lost."""
    root, manifest = _build_root(tmp_path)
    (root / "data" / "eval" / "cases.jsonl").unlink()
    before = manifest.read_bytes()

    done = _run(root, "--write")

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "cases" in output
    assert "removing an entry is a hand edit of the manifest" in output
    assert manifest.read_bytes() == before


def test_write_updates_the_fingerprint_of_a_dataset_that_moved(tmp_path: Path) -> None:
    """The write recomputes the sha256 and the record count of the dataset that moved."""
    root, manifest = _build_root(tmp_path, records=3)
    dataset = root / "data" / "eval" / "cases.jsonl"
    _write_jsonl(dataset, 5)

    done = _run(root, "--write")

    assert done.returncode == 0, done.stdout + done.stderr
    entries = _entries(json.loads(manifest.read_text(encoding="utf-8")))
    assert entries[0]["sha256"] == _sha256(dataset)
    assert entries[0]["records_count"] == 5
    # The other fields are hand written and the write never touches them.
    assert entries[0]["split_role"] == "tuning"
    assert entries[0]["contamination_policy"] == CONTAMINATION_POLICY


def _entries(payload: object) -> list[dict]:
    """The entries of a manifest file, whatever shape the canonical text of the file has."""
    if isinstance(payload, dict):
        return list(payload["datasets"])
    return list(payload)


def test_write_leaves_a_matching_manifest_alone(tmp_path: Path) -> None:
    """The write of a manifest that already matches says so and does not change what the manifest declares."""
    root, manifest = _build_root(tmp_path)
    before = _entries(json.loads(manifest.read_text(encoding="utf-8")))

    done = _run(root, "--write")

    assert done.returncode == 0, done.stdout + done.stderr
    assert _entries(json.loads(manifest.read_text(encoding="utf-8"))) == before


def test_write_says_that_the_roles_were_not_compared_when_there_is_no_committed_manifest(tmp_path: Path) -> None:
    """Without a committed manifest there is nothing to compare the roles with, and the write says so out loud.

    The write is not blocked, because the creation of the manifest for the first time has to be possible, but the
    truth is printed: nobody can believe the roles were checked when they were not.
    """
    root, _manifest = _build_root(tmp_path)

    done = _run(root, "--write")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "the roles were not compared" in done.stdout
    assert "there is no committed manifest to compare against" in done.stdout
    assert "so the roles were kept as they are" in done.stdout


def test_write_refuses_to_change_the_role_of_an_entry(tmp_path: Path) -> None:
    """The write refuses a role that the committed manifest does not have, and it does not write the manifest.

    The repository of the fixture is a temporary one, with a commit that holds the manifest and the dataset. The
    role of the entry is then changed by hand, in the file of the disk, and the file stops being the canonical
    text, so a write would leave a different file behind.
    """
    root = tmp_path / "repo"
    dataset = root / "data" / "eval" / "cases.jsonl"
    _write_jsonl(dataset, 3)
    manifest = _write_manifest(root, [_entry("cases", "data/eval/cases.jsonl", _sha256(dataset), 3)])
    _git(root, "init")
    _git(root, "add", "data/eval/datasets.json", "data/eval/cases.jsonl")
    _git(
        root,
        "-c",
        "user.email=worker@example.com",
        "-c",
        "user.name=worker",
        "commit",
        "-m",
        "test: the manifest and the dataset",
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["datasets"][0]["split_role"] = "validation"
    manifest.write_text(json.dumps(payload, indent=4, sort_keys=True) + "\n", encoding="utf-8")
    before = manifest.read_bytes()

    done = _run(root, "--write")

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "changing the role is a hand edit of the manifest" in output
    assert "validation" in output
    assert "tuning" in output
    # The write did not happen: the file of the disk still carries the role it had before the run.
    assert manifest.read_bytes() == before
    assert _entries(json.loads(manifest.read_text(encoding="utf-8")))[0]["split_role"] == "validation"
    committed = _git(root, "show", "HEAD:data/eval/datasets.json")
    assert _entries(json.loads(committed.stdout))[0]["split_role"] == "tuning"


def test_the_manifest_follows_the_root_when_it_is_not_named(tmp_path: Path) -> None:
    """Without `--manifest` the check reads and writes the manifest of the root, and the repository is untouched."""
    root, _manifest = _build_root(tmp_path)
    dataset = root / "data" / "eval" / "cases.jsonl"
    _write_jsonl(dataset, 5)
    repository_manifest = REPOSITORY / "data" / "eval" / "datasets.json"
    before = repository_manifest.read_bytes() if repository_manifest.is_file() else b""

    done = _run(root, "--write", with_manifest=False)

    assert done.returncode == 0, done.stdout + done.stderr
    written = root / "data" / "eval" / "datasets.json"
    entries = _entries(json.loads(written.read_text(encoding="utf-8")))
    assert entries[0]["sha256"] == _sha256(dataset)
    assert entries[0]["records_count"] == 5
    after = repository_manifest.read_bytes() if repository_manifest.is_file() else b""
    assert after == before


def test_a_manifest_outside_the_root_is_refused(tmp_path: Path) -> None:
    """A manifest that is not inside the root is refused, because the write would pin the wrong files."""
    root, _manifest = _build_root(tmp_path)
    outside = tmp_path / "outside" / "datasets.json"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text(json.dumps({"datasets": []}, indent=2) + "\n", encoding="utf-8")
    before = outside.read_bytes()

    done = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--manifest",
            str(outside),
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert "outside the root" in output
    assert "Traceback" not in output
    assert outside.read_bytes() == before
