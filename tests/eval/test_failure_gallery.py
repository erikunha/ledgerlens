"""The gallery of the failures of an experiment: what a variant lost, published without the key of the set.

What they guarantee, and why: (a) the gallery of a held out cohort is refused, because the lost cases of a held
out set would carry the expected facts, and the expected facts of a held out case are the key of the set, which
is never published (ADR-069); (b) a run that failed is published as a failed run and never as a score of zero,
because a zero is a measurement and a failure is the absence of one; (c) a lost case is published with the
expected facts and with the evidence its answer cited, because a lost case without them is a case a reader
cannot check.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.eval.failures import GalleryError, build_gallery
from ledgerlens.eval.paired import compare, read_runs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "paired_runs.json"
METHOD = "the paired difference, with the standard error of the differences and the normal approximation of 95 percent"


def _gallery(cohort_role: str = "tuning"):
    runs = read_runs(FIXTURE)
    comparison = compare(runs, goal=0.80, method=METHOD)
    return build_gallery(comparison, runs, cohort_role=cohort_role)


def test_the_gallery_of_a_held_out_cohort_is_refused() -> None:
    """The key of the held out set is never published, in any form (ADR-069)."""
    with pytest.raises(GalleryError):
        _gallery(cohort_role="held_out")


def test_a_run_that_failed_is_published_as_a_failed_run_and_never_as_a_zero() -> None:
    """A zero is a measurement and a failure is the absence of one."""
    gallery = _gallery()

    failed = gallery["failed_runs"]
    assert len(failed) == 1
    assert failed[0]["case_id"] == "EC-04"
    assert failed[0]["variant"] == "single_agent"
    assert failed[0]["failure"]
    assert "score" not in failed[0] or failed[0]["score"] is None
    assert failed[0]["score"] != 0


def test_a_lost_case_is_published_with_the_expected_facts_and_the_evidence_it_cited() -> None:
    """A lost case without the expected facts and the evidence is a case a reader cannot check."""
    gallery = _gallery()

    lost = gallery["lost_cases"]
    assert lost, "the gallery holds no lost case"
    for case in lost:
        assert case["expected_facts"]
        assert "evidence_cited" in case
    # EC-01 is the case the second variant lost: it is in the gallery with its facts and its evidence.
    lost_ids = {case["case_id"] for case in lost}
    assert "EC-01" in lost_ids
    ec01 = next(case for case in lost if case["case_id"] == "EC-01")
    assert ec01["expected_facts"] == ["14.08"]
    assert ec01["evidence_cited"]
