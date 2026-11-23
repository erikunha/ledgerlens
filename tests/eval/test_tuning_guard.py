"""The guard that says which dataset a tuning script may read.

Why it exists: the thresholds, the prompts and the hyperparameters of the repository were chosen against some
datasets and not against others. A script that reads a set nobody decided anything on silently turns the number of
that set into a measure of the fit. The guard is the one door every tuning script goes through, and these tests
prove that the door says no, in a sentence, for every role that may not be tuned against.

The entries of the manifest are built here by hand and the files they name do not exist: the rule is a rule about
the roles and not about the disk, so the guard has to answer without touching the disk.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ledgerlens.eval.manifest import (
    HELD_OUT_RESERVED_DIGESTS,
    HELD_OUT_RESERVED_PATHS,
    TUNING_ROLE,
    EvalDatasetManifest,
    ManifestError,
    TuningRefusal,
    load_manifests,
    may_be_tuned_against,
    require_tuning_dataset,
    require_tuning_path,
)
from ledgerlens.verify.sweep import nli_cases

ROOT = Path(__file__).resolve().parents[2]

POLICY = (
    "Thresholds, prompts and hyperparameters are tuned only against the datasets whose split_role is 'tuning'. "
    "A dataset with the role 'validation' may be scored but never tuned against."
)


def _entry(dataset_id: str, role: str) -> EvalDatasetManifest:
    """An entry of the manifest with the role of the case, for a file that is not on the disk."""
    return EvalDatasetManifest(
        dataset_id=dataset_id,
        path=f"data/eval/{dataset_id}.jsonl",
        sha256="a" * 64,
        records_count=2,
        source="The records come from the seeded sample ledger of data/scenarios.json.",
        labeling_version="v1",
        split_role=role,
        scenario_seed=42,
        contamination_policy=POLICY,
    )


def _manifests() -> tuple[EvalDatasetManifest, ...]:
    """The entries of a manifest with one dataset of each role."""
    return (
        _entry("tuning_cases", TUNING_ROLE),
        _entry("validation_cases", "validation"),
        _entry("held_out_cases", "held_out"),
    )


# --- the answer -------------------------------------------------------------------------------------


def test_a_dataset_with_the_role_tuning_may_be_tuned_against() -> None:
    """The dataset that carries the role of the tuning may be tuned against, and the guard gives its entry back."""
    manifests = _manifests()

    assert may_be_tuned_against("tuning_cases", manifests) is True
    assert require_tuning_dataset("tuning_cases", manifests) is manifests[0]


def test_a_dataset_with_the_role_validation_may_not_be_tuned_against() -> None:
    """A validation set may be scored and never tuned against."""
    manifests = _manifests()

    assert may_be_tuned_against("validation_cases", manifests) is False

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("validation_cases", manifests)

    assert "validation_cases" in str(caught.value)
    assert "validation" in str(caught.value)


def test_a_dataset_with_the_role_held_out_may_not_be_tuned_against() -> None:
    """A held out set may be read by the final scoring step and by nothing else."""
    manifests = _manifests()

    assert may_be_tuned_against("held_out_cases", manifests) is False

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("held_out_cases", manifests)

    assert "held_out_cases" in str(caught.value)
    assert "held_out" in str(caught.value)


def test_a_dataset_the_manifest_does_not_declare_may_not_be_tuned_against() -> None:
    """A dataset that no entry declares is refused, and the refusal says that it is not declared."""
    manifests = _manifests()

    assert may_be_tuned_against("ghost_cases", manifests) is False

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("ghost_cases", manifests)

    message = str(caught.value)
    assert "ghost_cases" in message
    assert "not declared" in message


# --- the refusal ------------------------------------------------------------------------------------


def test_the_refusal_is_a_dedicated_exception_and_not_a_bare_one() -> None:
    """The refusal has its own class, so a caller catches it without catching every error of the module."""
    manifests = _manifests()

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("held_out_cases", manifests)

    assert caught.type is not Exception
    assert issubclass(caught.type, ManifestError)
    assert issubclass(TuningRefusal, ManifestError)


def test_the_refusal_names_the_roles_that_are_allowed() -> None:
    """The sentence says which role may be tuned against, so the reader knows what to do next."""
    manifests = _manifests()

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("validation_cases", manifests)

    message = str(caught.value)
    assert TUNING_ROLE in message
    assert "may not be tuned against" in message


def test_the_refusal_is_one_sentence_and_not_a_traceback() -> None:
    """The reason is a sentence: it ends with a point and it does not carry the trace of a call."""
    manifests = _manifests()

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_dataset("validation_cases", manifests)

    message = str(caught.value)
    assert message.endswith(".")
    assert "Traceback" not in message


# --- the rule reads no disk -------------------------------------------------------------------------


def test_the_guard_answers_without_reading_the_disk(tmp_path: Path) -> None:
    """The rule is about the roles and not about the files, so it answers for a root with no file at all.

    The entries name files under a root that does not exist: a guard that had to read them would fail here, and a
    caller that checks a manifest of another root would be stuck on the root of this one.
    """
    manifests = (
        EvalDatasetManifest(
            dataset_id="tuning_cases",
            path="data/eval/tuning_cases.jsonl",
            sha256="a" * 64,
            records_count=0,
            source="The records come from the seeded sample ledger of data/scenarios.json.",
            labeling_version="v1",
            split_role=TUNING_ROLE,
            scenario_seed=42,
            contamination_policy=POLICY,
        ),
    )

    assert may_be_tuned_against("tuning_cases", manifests) is True
    assert require_tuning_dataset("tuning_cases", manifests).dataset_id == "tuning_cases"
    assert not (tmp_path / "data" / "eval" / "tuning_cases.jsonl").exists()


# --- the door the scripts of the repository go through -------------------------------------------------------

# The scripts that may read a dataset whose role is not `tuning`, and why. The instrument of the blind reading
# and the measurement of the programme are the scoring step, and the scoring step is the one thing the role
# `held_out` allows. Every other script of the repository reads the sets of the role `tuning` and nothing else.
# The markers that name a file whose role is not `tuning`, in the source of a script. The paths and the constants
# that resolve to them are both here, because a script may name either one.
MARKERS_OF_A_HELD_OUT_FILE = (
    "verification_heldout.jsonl",
    "heldout/recipes.jsonl",
    "RECIPES_PATH",
    "LABELLED_SET_RELATIVE",
)

ALLOWED_READERS = {
    "label_heldout.py": "the instrument of the blind reading, which writes the labels and compares them",
    "measure_heldout.py": "the measurement of the programme, the scoring step of the held out set",
}


def _scripts_of_the_repository() -> list[Path]:
    """The scripts of the repository, in a stable order."""
    return sorted((ROOT / "scripts").glob("*.py"))


def test_no_tuning_script_of_the_repository_opens_a_dataset_that_may_not_be_tuned_against() -> None:
    """Only the scoring step opens a file whose role is not `tuning`, and the list of those is closed.

    Why the source is read and not only the guard: the guard refuses by the name of the dataset, and a script that
    names the path of a file instead of the name of its dataset does not pass through the door. This test holds the
    promise of the role at the level of the code of the repository: a script that opens the labelled set of the held
    out set, or the key of the generator, has to be the scoring step, and it has to be named here.

    Why the list is closed and not open: a script that is added to the list without a reason is a second door.
    """
    offenders: list[str] = []
    for script in _scripts_of_the_repository():
        text = script.read_text(encoding="utf-8")
        mentions = [marker for marker in MARKERS_OF_A_HELD_OUT_FILE if marker in text]
        if not mentions:
            continue
        if script.name in ALLOWED_READERS:
            continue
        offenders.append(f"{script.name} mentions {', '.join(mentions)}")

    assert offenders == [], (
        "a script that may not read a dataset of the role 'held_out' names one of them: "
        + "; ".join(offenders)
    )


def test_the_scripts_that_may_read_the_held_out_set_are_the_scoring_step() -> None:
    """The two scripts that read the held out files are the instrument of the reading and the measurement.

    Why the list is named here and not only in the test above: a reader of the repository has to be able to find out
    who reads the key of the generator, and the answer has to be the same answer the test holds.
    """
    readers = {
        script.name
        for script in _scripts_of_the_repository()
        if any(marker in script.read_text(encoding="utf-8") for marker in MARKERS_OF_A_HELD_OUT_FILE)
    }

    assert readers == set(ALLOWED_READERS)


# --- the door of the path ------------------------------------------------------------------------------


def _manifest_with_roles() -> tuple[EvalDatasetManifest, ...]:
    """Two datasets, one of the role `tuning` and one of the role `held_out`."""
    return (
        EvalDatasetManifest(
            dataset_id="tuning_cases",
            path="data/eval/tuning_cases.jsonl",
            sha256="a" * 64,
            records_count=2,
            source="The records come from the seeded sample ledger of data/scenarios.json.",
            labeling_version="v1",
            split_role=TUNING_ROLE,
            scenario_seed=42,
            contamination_policy=POLICY,
        ),
        EvalDatasetManifest(
            dataset_id="heldout_cases",
            path="data/eval/verification_heldout.jsonl",
            sha256="b" * 64,
            records_count=48,
            source="The records come from the generator of the held out set, over the seed 7301.",
            labeling_version="v1",
            split_role="held_out",
            scenario_seed=7301,
            contamination_policy=POLICY,
        ),
    )


def test_the_path_of_a_dataset_that_may_not_be_tuned_against_is_refused() -> None:
    """The path of the file of a held out dataset is refused, and the refusal is a sentence.

    Why the path and not only the name: a script that opens a file by its path does not pass through the door of
    the name, and the path is the other way a script reaches the data.
    """
    manifests = _manifest_with_roles()

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/verification_heldout.jsonl", manifests)

    message = str(caught.value)
    assert "heldout_cases" in message
    assert "held_out" in message
    assert message.endswith(".")


def test_the_path_of_a_dataset_that_may_be_tuned_against_is_accepted() -> None:
    """The path of a tuning dataset is accepted, and it gives the entry back."""
    manifests = _manifest_with_roles()

    entry = require_tuning_path("data/eval/tuning_cases.jsonl", manifests)

    assert entry.dataset_id == "tuning_cases"


def test_a_path_that_no_entry_declares_is_refused() -> None:
    """A file that the manifest does not name is a file that nobody may tune on."""
    manifests = _manifest_with_roles()

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/heldout/recipes.jsonl", manifests)

    assert "not declared by the manifest" in str(caught.value)


# --- the reservation that lives in the code ---------------------------------------------------------------


def test_the_reserved_paths_are_the_paths_of_the_datasets_with_the_role_held_out() -> None:
    """The reservation of the code and the manifest say the same thing.

    Why the two have to agree: the reservation lives in the code because the role of an entry is data and a data
    edit is one line away. If the manifest declares a dataset with the role `held_out` that the code does not
    reserve, the door of the path can be opened by editing the role of the entry, and the guard of the name is
    the only door left.
    """
    manifests = load_manifests(ROOT / "data" / "eval" / "datasets.json")
    reserved = {path for path in HELD_OUT_RESERVED_PATHS}
    declared = {entry.path for entry in manifests if entry.split_role == "held_out"}

    assert reserved == declared, (
        "the paths reserved in the code and the datasets with the role 'held_out' of the manifest are not the same: "
        f"reserved {sorted(reserved)}, declared {sorted(declared)}"
    )


def test_the_role_of_an_entry_cannot_unlock_the_path_that_is_reserved() -> None:
    """A hand edit of the role of the entry does not open the reserved path.

    Why the test exists: the role of a dataset is a field of a JSON file, and the bypass that this closes is one
    line of JSON away. The reservation lives in the code, so the refusal survives the edit.
    """
    manifests = list(_manifest_with_roles())
    tampered = [
        replace(entry, split_role=TUNING_ROLE) if entry.dataset_id == "heldout_cases" else entry
        for entry in manifests
    ]

    assert may_be_tuned_against("heldout_cases", tampered) is True, "the tampered manifest is what the bypass needs"

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/verification_heldout.jsonl", tampered)

    message = str(caught.value)
    assert "reserved for the held out set" in message
    assert message.endswith(".")


def test_the_sweep_refuses_a_dataset_that_may_not_be_tuned_against(tmp_path_factory: pytest.TempPathFactory) -> None:
    """The sweep of the thresholds does not read the file of the held out set.

    Why the sweep and not only the guard: the guard is a function and the sweep is the script that a person runs
    when it wants a threshold table. The door has to be on the way of the script, and not only on the way of the
    function that the script happens to call.
    """
    root = tmp_path_factory.mktemp("root")
    datasets = root / "data" / "eval"
    datasets.mkdir(parents=True)
    (datasets / "verification_heldout.jsonl").write_text(
        json.dumps({"id": "ho-001", "premise": "a", "claim": "b", "label": "supported"}) + "\n",
        encoding="utf-8",
    )
    manifest = datasets / "datasets.json"
    manifest.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "dataset_id": "verification_heldout",
                        "path": "data/eval/verification_heldout.jsonl",
                        "sha256": "b" * 64,
                        "records_count": 1,
                        "source": "The labels come from the blind reading.",
                        "labeling_version": "v1",
                        "split_role": "held_out",
                        "scenario_seed": 7301,
                        "contamination_policy": POLICY,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifests = load_manifests(manifest)

    # The role `held_out` is not read at all: the sweep skips the entry and the file is never opened.
    assert nli_cases(root, manifests) == ()

    # The bypass is the role of the entry edited by hand. The reservation of the code has to hold there too.
    tampered = [replace(entry, split_role=TUNING_ROLE) for entry in manifests]
    with pytest.raises(TuningRefusal) as caught:
        nli_cases(root, tampered)

    assert "reserved for the held out set" in str(caught.value)


def test_a_copy_of_the_held_out_set_under_another_name_is_refused() -> None:
    """A file with the bytes of the held out set is refused under any name and with any role.

    Why the digest and not only the path: a path names a file and a copy of the file under another name has
    another path, so the reservation by path alone stops at the name. The bytes are the same under any name, and
    the digest of the entry is what the check of the datasets compares with the file on the disk, so a copy that
    the check accepts carries the digest of the set and is refused here.

    Why the digest of the answer key is in the same list: the key of the generator is the same kind of thing. A
    copy of it under another name and declared as tuning material is the same cheat with a different name.
    """
    manifests = list(_manifest_with_roles())
    copy = EvalDatasetManifest(
        dataset_id="another_name",
        path="data/eval/another_name.jsonl",
        sha256=HELD_OUT_RESERVED_DIGESTS[0],
        records_count=48,
        source="A copy of the labelled set of the blind reading under another name.",
        labeling_version="v1",
        split_role=TUNING_ROLE,
        scenario_seed=7301,
        contamination_policy=POLICY,
    )
    manifests.append(copy)

    assert may_be_tuned_against("another_name", manifests) is True, "the copy is what the cheat needs"

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/another_name.jsonl", manifests)

    message = str(caught.value)
    assert "digest of the held out set" in message
    assert message.endswith(".")


def test_the_reserved_digests_are_the_digests_of_the_set_and_of_the_key() -> None:
    """The reserved digests are the digests of the two files that may never be tuning material.

    Why the test reads the disk and not a constant: the digest of the labelled set is the digest of the file of
    the tree, and the digest of the key is the digest of the file that the generator writes. If either of them
    moves, the reservation has to move with it, and the test is what says so.
    """
    manifest_entries = load_manifests(ROOT / "data" / "eval" / "datasets.json")
    labelled = next(entry for entry in manifest_entries if entry.dataset_id == "verification_heldout")

    assert labelled.sha256 in HELD_OUT_RESERVED_DIGESTS, (
        "the digest of the labelled set of the reading is not reserved: a copy of it under another name would pass"
    )

    key = ROOT / "data" / "eval" / "heldout" / "recipes.jsonl"
    if key.exists():
        digest = hashlib.sha256(key.read_bytes()).hexdigest()
        assert digest in HELD_OUT_RESERVED_DIGESTS, (
            "the digest of the answer key of the generator is not reserved: a copy of it under another name would pass"
        )
