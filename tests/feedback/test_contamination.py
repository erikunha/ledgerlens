"""The contamination check: a case of the held out set never enters a training set, not even under an alias.

What they guarantee, and why: a training set that holds a case of the held out set under an alias is refused
with the name of the case and of the alias, because the check compares the content of the case and not only
its identifier; and the guard of the tuning of `ledgerlens/eval/manifest.py` still refuses a tuning against a
dataset whose role is `held_out` and refuses the published report of the measurement.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.eval.manifest import (
    TuningRefusal,
    load_manifests,
    may_be_tuned_against,
    require_tuning_dataset,
    require_tuning_path,
)
from ledgerlens.feedback.contamination import ContaminationError, assert_no_contamination

HELD_OUT_CASE = {
    "id": "HO-01",
    "claim": "the refund of TX-1001 is above the captured amount",
    "evidence": "TX-1001 captured 100.00 and the refund asks 120.00",
    "evidence_ids": ["TX:1001", "R:55"],
    "label": "supported",
}


def test_a_training_set_that_holds_a_case_of_the_held_out_set_under_an_alias_is_refused() -> None:
    """The same case with another name is the same case, and the refusal names the case and the alias."""
    alias = dict(HELD_OUT_CASE, id="TRAIN-77")

    with pytest.raises(ContaminationError) as refusal:
        assert_no_contamination([alias], [HELD_OUT_CASE])

    assert "TRAIN-77" in str(refusal.value)
    assert "HO-01" in str(refusal.value)


def test_a_training_set_without_a_case_of_the_held_out_set_passes() -> None:
    """A case whose content is not the content of a held out case is not contamination."""
    other = {
        "id": "TRAIN-01",
        "claim": "the settlement of the week is the gross minus the fees",
        "evidence": "the settlement S-9 has gross 500.00 and fees 12.00",
        "evidence_ids": ["S:9"],
        "label": "supported",
    }

    assert_no_contamination([other], [HELD_OUT_CASE])


def test_the_guard_of_the_tuning_still_refuses_the_held_out_set() -> None:
    """The manifest of the datasets keeps the held out set reserved for the final scoring."""
    manifests = load_manifests()

    assert not may_be_tuned_against("orchestration_comparison", manifests)
    assert not may_be_tuned_against("verification_heldout", manifests)
    with pytest.raises(TuningRefusal):
        require_tuning_dataset("orchestration_comparison", manifests)


def test_the_guard_of_the_tuning_still_refuses_the_published_report_of_the_measurement() -> None:
    """The published report of the measurement of the held out set is not a tuning path."""
    manifests = load_manifests()

    with pytest.raises(TuningRefusal):
        require_tuning_path("data/eval/report_heldout.json", manifests)
