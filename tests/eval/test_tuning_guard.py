"""The guard that says which dataset a tuning script may read.

Why it exists: the thresholds, the prompts and the hyperparameters of the repository were chosen against some
datasets and not against others. A script that reads a set nobody decided anything on silently turns the number of
that set into a measure of the fit. The guard is the one door every tuning script goes through, and these tests
prove that the door says no, in a sentence, for every role that may not be tuned against.

The entries of the manifest are built here by hand and the files they name do not exist: the rule is a rule about
the roles and not about the disk, so the guard has to answer without touching the disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.eval.manifest import (
    TUNING_ROLE,
    EvalDatasetManifest,
    ManifestError,
    TuningRefusal,
    may_be_tuned_against,
    require_tuning_dataset,
)

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
