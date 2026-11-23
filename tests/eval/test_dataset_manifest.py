"""The manifest of the eval datasets: what it pins and what it refuses.

Why it exists: the six JSONL files under `data/eval/` are the source of every number the repository publishes,
and the manifest is what says which file each number comes from, how many records it has and what a tuning script
may read. These tests cover the fingerprint of a file, the reading of the manifest file and the comparison of the
manifest with the disk, with temporary folders for the fixtures and the real repository only for the manifest that
ships.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.eval.manifest import (
    MANIFEST_PATH,
    SPLIT_ROLES,
    EvalDatasetManifest,
    ManifestError,
    fingerprint_dataset,
    load_manifests,
    render_manifests,
    safe_text,
    update_fingerprints,
    verify_manifests,
)

POLICY = (
    "Thresholds, prompts and hyperparameters are tuned only against the datasets whose split_role is 'tuning'. "
    "A dataset with the role 'validation' may be scored but never tuned against."
)
SHA = "a" * 64


def _entry(
    dataset_id: str = "eval_cases",
    path: str = "data/eval/eval_cases.jsonl",
    **overrides: Any,
) -> dict[str, Any]:
    """A manifest entry with every field of the record, so a test can change one of them."""
    entry: dict[str, Any] = {
        "dataset_id": dataset_id,
        "path": path,
        "sha256": SHA,
        "records_count": 2,
        "source": "The records come from the seeded sample ledger of data/scenarios.json.",
        "labeling_version": "v1",
        "split_role": "tuning",
        "scenario_seed": 42,
        "contamination_policy": POLICY,
        "notes": "The caveat of the dataset.",
    }
    entry.update(overrides)
    return entry


def _write_manifest(root: Path, entries: list[dict[str, Any]]) -> Path:
    """Writes a manifest file in the layout the repository uses and returns its path."""
    path = root / "data" / "eval" / "datasets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"datasets": entries}, indent=2), encoding="utf-8")
    return path


def _dataset(root: Path, name: str, lines: list[str]) -> Path:
    """Writes a JSONL dataset under the data/eval folder of a temporary root."""
    path = root / "data" / "eval" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- the fingerprint of a file ---------------------------------------------------------------------------


def test_the_fingerprint_of_a_file_is_its_hash_and_its_count(tmp_path: Path) -> None:
    """A file gives back the sha256 of its bytes and the number of records it holds."""
    path = tmp_path / "dataset.jsonl"
    content = '{"id": "a"}\n{"id": "b"}\n'
    path.write_text(content, encoding="utf-8")

    digest, count = fingerprint_dataset(path)

    assert count == 2
    assert digest == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_a_blank_line_is_not_a_record(tmp_path: Path) -> None:
    """A blank line carries no record, so the count ignores it and the hash still covers the bytes."""
    path = tmp_path / "dataset.jsonl"
    path.write_text('{"id": "a"}\n\n   \n{"id": "b"}\n', encoding="utf-8")

    _digest, count = fingerprint_dataset(path)

    assert count == 2


def test_a_line_that_is_not_json_is_a_failure(tmp_path: Path) -> None:
    """A line that does not parse is a failure and not a record, and the error names the file and the line."""
    path = tmp_path / "dataset.jsonl"
    path.write_text('{"id": "a"}\nnot json at all\n', encoding="utf-8")

    with pytest.raises(ManifestError) as caught:
        fingerprint_dataset(path)

    message = str(caught.value)
    assert "dataset.jsonl" in message
    assert "2" in message


def test_a_line_that_is_not_a_json_object_is_a_failure(tmp_path: Path) -> None:
    """A line that parses but is not an object carries no record either."""
    path = tmp_path / "dataset.jsonl"
    path.write_text('{"id": "a"}\n[1, 2]\n', encoding="utf-8")

    with pytest.raises(ManifestError) as caught:
        fingerprint_dataset(path)

    assert "dataset.jsonl" in str(caught.value)


# --- the files that cannot be read ------------------------------------------------------------------------


def test_a_dataset_that_is_not_valid_utf8_is_an_error(tmp_path: Path) -> None:
    """A dataset whose bytes are not valid UTF-8 is a data problem and not a crash of the check."""
    path = tmp_path / "dataset.jsonl"
    path.write_bytes(b'{"id": "a"}\n\xff\xfe\n')

    with pytest.raises(ManifestError) as caught:
        fingerprint_dataset(path)

    message = str(caught.value)
    assert "dataset.jsonl" in message
    assert "UTF-8" in message


def test_a_manifest_that_is_not_valid_utf8_is_an_error(tmp_path: Path) -> None:
    """A manifest file whose bytes are not valid UTF-8 is refused with a sentence and not with a crash."""
    path = tmp_path / "datasets.json"
    path.write_bytes(b'{"datasets": [\xff]}')

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "datasets.json" in message
    assert "UTF-8" in message


def test_a_file_that_cannot_be_opened_is_an_error(tmp_path: Path) -> None:
    """A file that the process cannot open is a data problem and not a crash of the check.

    A directory in the place of the file is the portable way to make the open fail: the permission of a file does
    not stop the process that owns it on some machines.
    """
    path = tmp_path / "dataset.jsonl"
    path.mkdir()

    with pytest.raises(ManifestError) as caught:
        fingerprint_dataset(path)

    message = str(caught.value)
    assert "dataset.jsonl" in message
    assert "could not be read" in message


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="a process that is root opens a file whatever the permission of the file is",
)
def test_a_file_without_the_permission_to_be_read_is_an_error(tmp_path: Path) -> None:
    """A file the process may not open is a data problem and not a crash of the check."""
    path = tmp_path / "dataset.jsonl"
    path.write_text('{"id": "a"}\n', encoding="utf-8")
    path.chmod(0o000)
    try:
        with pytest.raises(ManifestError) as caught:
            fingerprint_dataset(path)
    finally:
        path.chmod(0o644)

    message = str(caught.value)
    assert "dataset.jsonl" in message
    assert "could not be read" in message


# --- the reading of the manifest file ---------------------------------------------------------------------


def test_a_manifest_file_that_is_missing_is_an_error(tmp_path: Path) -> None:
    """A manifest file that is not there cannot be read and the error says so."""
    missing = tmp_path / "datasets.json"

    with pytest.raises(ManifestError) as caught:
        load_manifests(missing)

    assert "datasets.json" in str(caught.value)


def test_a_manifest_file_that_is_not_json_is_an_error(tmp_path: Path) -> None:
    """A manifest file that is not JSON cannot be read and the error says so."""
    path = tmp_path / "datasets.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    assert "datasets.json" in str(caught.value)


def test_an_entry_with_an_unknown_field_is_an_error(tmp_path: Path) -> None:
    """An entry with a field the record does not have is refused and the error names the field."""
    path = _write_manifest(tmp_path, [_entry(role="supervisor")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "role" in message
    assert "datasets.json" in message


def test_an_entry_with_a_missing_field_is_an_error(tmp_path: Path) -> None:
    """An entry without one of the fields of the record is refused and the error names the field."""
    entry = _entry()
    del entry["source"]
    path = _write_manifest(tmp_path, [entry])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    assert "source" in str(caught.value)


def test_a_duplicate_dataset_id_is_an_error(tmp_path: Path) -> None:
    """The same dataset_id twice is refused and the error names it."""
    path = _write_manifest(tmp_path, [_entry(), _entry(path="data/eval/other.jsonl")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    assert "eval_cases" in str(caught.value)


def test_a_split_role_outside_the_roles_is_an_error(tmp_path: Path) -> None:
    """A split_role that is not one of SPLIT_ROLES is refused and the error names the roles."""
    path = _write_manifest(tmp_path, [_entry(split_role="golden")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "golden" in message
    assert "tuning" in message


def test_a_sha256_that_is_not_hexadecimal_is_an_error(tmp_path: Path) -> None:
    """A sha256 that is not 64 lowercase hexadecimal characters is refused."""
    path = _write_manifest(tmp_path, [_entry(sha256="not-a-hash")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    assert "sha256" in str(caught.value)


def test_a_negative_records_count_is_an_error(tmp_path: Path) -> None:
    """A records_count below zero is refused."""
    path = _write_manifest(tmp_path, [_entry(records_count=-1)])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    assert "records_count" in str(caught.value)


def test_a_path_that_is_absolute_is_an_error(tmp_path: Path) -> None:
    """A dataset whose path is absolute is refused, because the path of a dataset is relative to the root."""
    path = _write_manifest(tmp_path, [_entry(path="/tmp/outside.jsonl")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "eval_cases" in message
    assert "/tmp/outside.jsonl" in message
    assert "datasets.json" in message


def test_a_path_that_leaves_the_root_is_an_error(tmp_path: Path) -> None:
    """A dataset whose path climbs out of the root with '..' is refused, before the disk is touched."""
    path = _write_manifest(tmp_path, [_entry(path="../outside.jsonl")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "eval_cases" in message
    assert "../outside.jsonl" in message
    assert "datasets.json" in message


def test_a_relative_path_still_loads(tmp_path: Path) -> None:
    """A path that stays inside the root is accepted, so the rule does not refuse a manifest that is fine."""
    path = _write_manifest(tmp_path, [_entry(path="data/eval/eval_cases.jsonl")])

    manifests = load_manifests(path)

    assert manifests[0].path == "data/eval/eval_cases.jsonl"


def test_a_manifest_with_the_five_fields_of_a_record_loads(tmp_path: Path) -> None:
    """A manifest that respects the contract loads and gives back the entries it declares."""
    path = _write_manifest(tmp_path, [_entry(dataset_id="one"), _entry(dataset_id="two", path="data/eval/two.jsonl")])

    manifests = load_manifests(path)

    assert [m.dataset_id for m in manifests] == ["one", "two"]
    assert manifests[0].split_role in SPLIT_ROLES
    assert manifests[0].contamination_policy == POLICY
    assert isinstance(manifests[0], EvalDatasetManifest)


# --- the comparison of the manifest with the disk ------------------------------------------------------------


def test_a_declared_file_that_is_missing_on_the_disk_is_a_problem(tmp_path: Path) -> None:
    """A dataset the manifest declares and the disk does not have is a problem."""
    _write_manifest(tmp_path, [_entry(path="data/eval/gone.jsonl")])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "gone.jsonl" in problems[0]


def test_a_file_whose_sha256_does_not_match_is_a_problem(tmp_path: Path) -> None:
    """A dataset whose bytes moved without the manifest moving is a problem that names both values."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}', '{"id": "b"}'])
    _write_manifest(tmp_path, [_entry(sha256="b" * 64)])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "b" * 64 in problems[0]


def test_a_file_whose_record_count_does_not_match_is_a_problem(tmp_path: Path) -> None:
    """A dataset that gained or lost a record without the manifest moving is a problem."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}', '{"id": "b"}'])
    digest, _count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    _write_manifest(tmp_path, [_entry(sha256=digest, records_count=3)])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "3" in problems[0]


def test_a_jsonl_of_data_eval_that_no_entry_declares_is_a_problem(tmp_path: Path) -> None:
    """A JSONL file of data/eval that no entry declares is a problem, so a new dataset cannot arrive quietly."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}'])
    _dataset(tmp_path, "hidden.jsonl", ['{"id": "b"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    _write_manifest(tmp_path, [_entry(sha256=digest, records_count=count)])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "hidden.jsonl" in problems[0]


def test_a_root_that_matches_gives_no_problem(tmp_path: Path) -> None:
    """A manifest that agrees with the disk gives no problem at all."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}', '{"id": "b"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    _write_manifest(tmp_path, [_entry(sha256=digest, records_count=count)])

    assert verify_manifests(tmp_path) == []


def test_the_problems_come_in_the_order_of_the_contract(tmp_path: Path) -> None:
    """The order is the one of the contract: the missing file, the hash, the count and the file nobody declares."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}', '{"id": "b"}'])
    _dataset(tmp_path, "hidden.jsonl", ['{"id": "b"}'])
    digest, _count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    _write_manifest(
        tmp_path,
        [
            _entry(path="data/eval/gone.jsonl", sha256="c" * 64, records_count=7),
            _entry(dataset_id="other", path="data/eval/eval_cases.jsonl", sha256="d" * 64, records_count=9),
        ],
    )

    problems = verify_manifests(tmp_path)

    assert len(problems) == 4
    assert "gone.jsonl" in problems[0]
    assert "d" * 64 in problems[1]
    assert "9" in problems[2]
    assert "hidden.jsonl" in problems[3]


# --- the files that cannot be read, seen through the check ----------------------------------------------------


def test_a_dataset_that_is_not_valid_utf8_is_a_problem_and_not_a_crash(tmp_path: Path) -> None:
    """The comparison of the manifest with the disk turns a dataset that is not valid UTF-8 into a sentence."""
    dataset = tmp_path / "data" / "eval" / "eval_cases.jsonl"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_bytes(b'{"id": "a"}\n\xff\xfe\n')
    _write_manifest(tmp_path, [_entry()])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "UTF-8" in problems[0]
    assert "eval_cases" in problems[0]


def test_a_manifest_that_is_not_valid_utf8_is_a_problem_and_not_a_crash(tmp_path: Path) -> None:
    """A manifest file that is not valid UTF-8 is one sentence and not a crash of the check."""
    manifest = tmp_path / "data" / "eval" / "datasets.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(b'{"datasets": [\xff]}')

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "UTF-8" in problems[0]
    assert "datasets.json" in problems[0]


def test_a_manifest_that_cannot_be_opened_is_a_problem_and_not_a_crash(tmp_path: Path) -> None:
    """A manifest file that cannot be opened is one sentence and not a crash of the check."""
    manifest = tmp_path / "data" / "eval" / "datasets.json"
    manifest.mkdir(parents=True)

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "could not be read" in problems[0]


def test_a_dataset_that_cannot_be_opened_is_a_problem_and_not_a_crash(tmp_path: Path) -> None:
    """A declared dataset that cannot be opened is one sentence and not a crash of the check."""
    dataset = tmp_path / "data" / "eval" / "eval_cases.jsonl"
    dataset.mkdir(parents=True)
    _write_manifest(tmp_path, [_entry()])

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    assert "could not be read" in problems[0]


# --- the paths that leave the root ---------------------------------------------------------------------------


def test_a_symlink_that_points_outside_the_root_is_refused(tmp_path: Path) -> None:
    """A path that names a link inside the root and points outside of it is refused before the file is read.

    The file outside the root holds bytes that are not valid UTF-8: a check that had read the file would say that
    the file is not valid UTF-8, and the sentence of the refusal has to be the one about the root instead. The
    check therefore refused the path and never opened the file.
    """
    root = tmp_path / "repo"
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(b"\xff\xfe")
    link = root / "data" / "eval" / "eval_cases.jsonl"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    _write_manifest(root, [_entry(path="data/eval/eval_cases.jsonl")])

    problems = verify_manifests(root)

    assert len(problems) == 1
    assert "outside the root" in problems[0]
    assert "UTF-8" not in problems[0]


def test_a_symlink_that_points_inside_the_root_is_accepted(tmp_path: Path) -> None:
    """A link that points at a file inside the root is a dataset of the repository and is checked as one."""
    root = tmp_path / "repo"
    target = root / "data" / "target.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"id": "a"}\n', encoding="utf-8")
    digest, count = fingerprint_dataset(target)
    link = root / "data" / "eval" / "link.jsonl"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    _write_manifest(root, [_entry(path="data/eval/link.jsonl", sha256=digest, records_count=count)])

    problems = verify_manifests(root)

    assert problems == []


def test_the_update_does_not_read_a_file_outside_the_root(tmp_path: Path) -> None:
    """The update keeps the values of an entry whose path leaves the root and says so in its messages."""
    root = tmp_path / "repo"
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(b"\xff\xfe")
    link = root / "data" / "eval" / "eval_cases.jsonl"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    manifest = _write_manifest(root, [_entry(path="data/eval/eval_cases.jsonl")])
    manifests = load_manifests(manifest)

    result = update_fingerprints(manifests, root)

    assert result.entries[0].sha256 == SHA
    assert result.entries[0].records_count == 2
    assert len(result.messages) == 1
    assert "outside the root" in result.messages[0]


# --- the canonical text and the update ----------------------------------------------------------------------


def test_the_canonical_text_is_sorted_and_ends_with_a_newline(tmp_path: Path) -> None:
    """The canonical text sorts the entries by dataset_id, sorts the keys and ends with a newline."""
    manifests = (
        EvalDatasetManifest(
            dataset_id="second",
            path="data/eval/second.jsonl",
            sha256="b" * 64,
            records_count=1,
            source="The records come from the second dataset.",
            labeling_version="v1",
            split_role="tuning",
            scenario_seed=42,
            contamination_policy=POLICY,
        ),
        EvalDatasetManifest(
            dataset_id="first",
            path="data/eval/first.jsonl",
            sha256="a" * 64,
            records_count=2,
            source="The records come from the first dataset.",
            labeling_version="v1",
            split_role="tuning",
            scenario_seed=42,
            contamination_policy=POLICY,
        ),
    )

    text = render_manifests(manifests)

    assert text.endswith("\n")
    assert text.index("first") < text.index("second")
    payload = json.loads(text)
    assert [entry["dataset_id"] for entry in payload["datasets"]] == ["first", "second"]
    assert list(payload["datasets"][0]) == sorted(payload["datasets"][0])


def test_update_fingerprints_says_what_moved_and_leaves_the_hand_written_fields_alone(tmp_path: Path) -> None:
    """The update recomputes the hash and the count and never touches the fields a person wrote."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}', '{"id": "b"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    manifests = [
        EvalDatasetManifest(
            dataset_id="eval_cases",
            path="data/eval/eval_cases.jsonl",
            sha256="f" * 64,
            records_count=1,
            source="The records come from the seeded sample ledger.",
            labeling_version="v1",
            split_role="tuning",
            scenario_seed=42,
            contamination_policy=POLICY,
            notes="The caveat of the dataset.",
        )
    ]

    result = update_fingerprints(manifests, tmp_path)

    assert len(result.messages) == 1
    assert "eval_cases" in result.messages[0]
    updated = result.entries[0]
    assert updated.sha256 == digest
    assert updated.records_count == count
    assert updated.split_role == "tuning"
    assert updated.source == "The records come from the seeded sample ledger."
    assert updated.notes == "The caveat of the dataset."


def test_update_fingerprints_gives_the_caller_the_new_values_and_changes_nothing_it_passed(tmp_path: Path) -> None:
    """The caller receives the new fingerprints and the sequence it passed stays exactly as it was."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    manifests = (
        EvalDatasetManifest(
            dataset_id="eval_cases",
            path="data/eval/eval_cases.jsonl",
            sha256="0" * 64,
            records_count=99,
            source="The records come from the seeded sample ledger.",
            labeling_version="v1",
            split_role="tuning",
            scenario_seed=42,
            contamination_policy=POLICY,
        ),
    )

    result = update_fingerprints(manifests, tmp_path)

    assert len(result.entries) == 1
    assert result.entries[0].sha256 == digest
    assert result.entries[0].records_count == count
    # The text the caller writes carries the pin of the disk, not the pin the manifest had.
    text = render_manifests(result.entries)
    entry = json.loads(text)["datasets"][0]
    assert entry["sha256"] == digest
    assert entry["records_count"] == count
    # The tuple the caller passed is not modified, so a caller that renders it writes the old pin.
    assert manifests[0].sha256 == "0" * 64
    assert manifests[0].records_count == 99


def test_update_fingerprints_says_nothing_when_nothing_moved(tmp_path: Path) -> None:
    """A manifest that already agrees with the disk gives no sentence at all."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    manifests = [
        EvalDatasetManifest(
            dataset_id="eval_cases",
            path="data/eval/eval_cases.jsonl",
            sha256=digest,
            records_count=count,
            source="The records come from the seeded sample ledger.",
            labeling_version="v1",
            split_role="tuning",
            scenario_seed=42,
            contamination_policy=POLICY,
        )
    ]

    result = update_fingerprints(manifests, tmp_path)

    assert result.messages == ()
    assert result.entries[0].sha256 == digest


# --- the files that are not regular files ---------------------------------------------------------------------


def test_a_named_pipe_is_refused_and_the_read_does_not_wait(tmp_path: Path) -> None:
    """A named pipe is refused with a sentence, and the refusal does not wait for a writer that never comes.

    The read of a named pipe waits for a writer, and a gate that waits forever is a gate that is not a gate. The
    read happens in a thread that is given a deadline, so a regression that waits fails the test instead of
    hanging the suite.
    """
    path = tmp_path / "pipe.jsonl"
    os.mkfifo(path)
    sentences: list[str] = []

    def read_it() -> None:
        try:
            fingerprint_dataset(path)
        except ManifestError as error:
            sentences.append(str(error))

    worker = threading.Thread(target=read_it, daemon=True)
    worker.start()
    worker.join(timeout=10)

    assert not worker.is_alive(), "the read of a named pipe waited for a writer"
    assert len(sentences) == 1
    assert "named pipe" in sentences[0]
    assert "pipe.jsonl" in sentences[0]


def test_a_dataset_that_is_not_a_regular_file_is_a_problem_and_not_a_crash(tmp_path: Path) -> None:
    """A declared dataset that is a named pipe is one sentence and not a crash of the check."""
    root = tmp_path / "repo"
    (root / "data" / "eval").mkdir(parents=True)
    os.mkfifo(root / "data" / "eval" / "pipe.jsonl")
    _write_manifest(root, [_entry(path="data/eval/pipe.jsonl")])

    problems = verify_manifests(root)

    assert len(problems) == 1
    assert "named pipe" in problems[0]
    assert "pipe.jsonl" in problems[0]


# --- the paths that the operating system cannot name ------------------------------------------------------------


def test_a_null_byte_in_a_declared_path_is_refused_by_the_loader(tmp_path: Path) -> None:
    """A path that holds a null byte is refused when the manifest is read, and never reaches the disk."""
    path = _write_manifest(tmp_path, [_entry(path="data/eval/ds\x00.jsonl")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "null byte" in message
    assert "eval_cases" in message
    assert "datasets.json" in message


def test_a_dataset_id_that_holds_a_line_break_is_refused(tmp_path: Path) -> None:
    """A dataset id that holds a line break is refused, because such a name can forge a line of the log."""
    path = _write_manifest(tmp_path, [_entry(dataset_id="eval\ncases")])

    with pytest.raises(ManifestError) as caught:
        load_manifests(path)

    message = str(caught.value)
    assert "not printable" in message
    assert "eval\\ncases" in message


# --- the path of an entry, normalised once ---------------------------------------------------------------------


def test_the_path_of_an_entry_is_normalised_when_the_manifest_is_read(tmp_path: Path) -> None:
    """A path with a trailing slash is the path it names, and it comes back in the normalised form."""
    path = _write_manifest(tmp_path, [_entry(path="data/eval/eval_cases.jsonl/")])

    manifests = load_manifests(path)

    assert manifests[0].path == "data/eval/eval_cases.jsonl"


def test_a_declared_path_with_a_trailing_slash_is_not_reported_as_undeclared(tmp_path: Path) -> None:
    """The read of a dataset and the scan of the folder speak of the same file and cannot disagree about it."""
    _dataset(tmp_path, "ds.jsonl", ['{"id": "a"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "ds.jsonl")
    _write_manifest(tmp_path, [_entry(dataset_id="ds", path="data/eval/ds.jsonl/", sha256=digest, records_count=count)])

    assert verify_manifests(tmp_path) == []


# --- the values that enter a sentence ---------------------------------------------------------------------------


def test_safe_text_leaves_a_normal_path_alone_and_escapes_what_can_lie() -> None:
    """A readable value stays as it is and a character that can lie is shown as the two characters that name it."""
    assert safe_text("data/eval/cases.jsonl") == "data/eval/cases.jsonl"
    assert safe_text("a\nb") == "a\\nb"
    assert safe_text("a\tb") == "a\\tb"
    assert safe_text("a\x1b[31mb") == "a\\x1b[31mb"
    assert safe_text("a\x00b") == "a\\x00b"
    assert "\n" not in safe_text("a\nb")


def test_the_name_of_a_file_that_holds_a_line_break_cannot_forge_a_line(tmp_path: Path) -> None:
    """A file name that holds a line break is printed on one line, with the break shown as the two characters."""
    _dataset(tmp_path, "eval_cases.jsonl", ['{"id": "a"}'])
    digest, count = fingerprint_dataset(tmp_path / "data" / "eval" / "eval_cases.jsonl")
    _write_manifest(tmp_path, [_entry(sha256=digest, records_count=count)])
    forged = "a\nis not declared\nevery dataset matches the manifest: 5 dataset(s) checked\n#b.jsonl"
    (tmp_path / "data" / "eval" / forged).write_text("", encoding="utf-8")

    problems = verify_manifests(tmp_path)

    assert len(problems) == 1
    # the name is printed on one line: the line breaks it holds are shown as the two characters that name them
    assert "\n" not in problems[0]
    assert "\\n" in problems[0]
    assert "every dataset matches the manifest: 5 dataset(s) checked" not in problems[0].splitlines()


# --- the manifest that is not inside the root -------------------------------------------------------------------


def test_a_manifest_that_is_a_link_outside_the_root_is_refused_and_not_read(tmp_path: Path) -> None:
    """A manifest that is a link to a file outside of the root is refused, and that file is never read.

    The file outside the root holds bytes that are not valid JSON: a check that had read it would say that the
    manifest is not valid JSON, and the sentence of the refusal has to be the one about the root instead.
    """
    root = tmp_path / "repo"
    outside = tmp_path / "outside.json"
    outside.write_text("{not json", encoding="utf-8")
    manifest = root / "data" / "eval" / "datasets.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.symlink_to(outside)

    problems = verify_manifests(root)

    assert len(problems) == 1
    assert "outside the root" in problems[0]
    assert "not valid JSON" not in problems[0]


# --- the manifest that ships --------------------------------------------------------------------------------


def test_the_manifest_of_the_repository_declares_the_six_datasets() -> None:
    """The manifest of the repository declares the six datasets with the roles the archaeology decided.

    Why the list has six entries and not seven: the held out set of the verification came with the blind reading
    of ADR-059, and the answer key of the generator came with it too, and the key is not published and is not
    declared here. A key that is public is not a key, so the tree keeps the cases and the labels and leaves the key
    out, and the guard refuses the path of the key because no entry of the manifest names it (ADR-062).
    """
    manifests = load_manifests(MANIFEST_PATH)

    assert [m.dataset_id for m in manifests] == [
        "eval_cases",
        "policy_questions",
        "triage_cases",
        "verification_heldout",
        "verification_live",
        "verification_set",
    ]
    assert {m.dataset_id: m.split_role for m in manifests} == {
        "eval_cases": "tuning",
        "policy_questions": "tuning",
        "triage_cases": "tuning",
        "verification_heldout": "held_out",
        "verification_live": "tuning",
        "verification_set": "tuning",
    }
    assert all(m.split_role in SPLIT_ROLES for m in manifests)
    assert all(m.labeling_version == "v1" for m in manifests)
    assert len({m.contamination_policy for m in manifests}) == 1


def test_the_manifest_of_the_repository_matches_the_disk() -> None:
    """Every entry of the manifest of the repository matches the file it names, and no file is left out."""
    assert verify_manifests() == []


def test_the_manifest_file_of_the_repository_is_the_canonical_text() -> None:
    """The file of the repository is the canonical text, so writing it again does not change it."""
    manifests = load_manifests(MANIFEST_PATH)

    assert render_manifests(manifests) == MANIFEST_PATH.read_text(encoding="utf-8")
