"""The gallery of the failures of an experiment: what a variant lost, published without the key of the set.

Why the gallery exists: a comparison that publishes only the means hides the cases that made them. The gallery
of an experiment holds the cases a variant lost and the runs that failed, so a reader can check what the means
are made of.

Why the gallery never holds the key of the held out set: the lost cases of a held out set would carry the
expected facts, and the expected facts of a held out case are the key of the set, which is never published, in
any form (ADR-069). The gallery is built over a cohort whose role is not the held out one, and it refuses a
held out cohort instead of redacting it, because a redaction that one day forgets a field is a leak.

Why a failed run is never a zero: a zero is a measurement, and a failure is the absence of one. The gallery
publishes the failed runs with the reason, and it never writes a score of zero for a run that did not answer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ledgerlens.eval.paired import CaseRun, PairedComparison


class GalleryError(Exception):
    """The gallery cannot be built, and the message says why."""


def build_gallery(
    comparison: PairedComparison,
    runs: Sequence[CaseRun],
    *,
    cohort_role: str,
) -> dict[str, Any]:
    """The gallery of an experiment: the cases a variant lost and the runs that failed.

    The lost cases are the paired cases where the two variants disagreed, published with the expected facts and
    the evidence the answer cited. The failed runs are the runs that did not answer, published with the reason
    and never with a score of zero.
    """
    if cohort_role == "held_out":
        raise GalleryError(
            "the gallery of a held out cohort is refused: the lost cases would carry the expected facts, and "
            "the key of the held out set is never published (ADR-069)"
        )

    run_of = {(run.case_id, run.variant): run for run in runs}
    lost_cases: list[dict[str, Any]] = []
    for difference in comparison.differences:
        if difference.difference == 0:
            continue
        first_run = run_of.get((difference.case_id, comparison.variants[0]))
        second_run = run_of.get((difference.case_id, comparison.variants[1]))
        lost_cases.append(
            {
                "case_id": difference.case_id,
                "winner": comparison.variants[0] if difference.difference > 0 else comparison.variants[1],
                "loser": comparison.variants[1] if difference.difference > 0 else comparison.variants[0],
                "scores": {
                    comparison.variants[0]: difference.first,
                    comparison.variants[1]: difference.second,
                },
                "expected_facts": list(first_run.expected_facts) if first_run else [],
                "evidence_cited": sorted(
                    {
                        *(first_run.evidence_cited if first_run else ()),
                        *(second_run.evidence_cited if second_run else ()),
                    }
                ),
            }
        )

    failed_runs = [
        {
            "case_id": run.case_id,
            "variant": run.variant,
            "failure": run.failure or "no reason recorded",
            "score": None,
        }
        for run in runs
        if run.ran and run.score is None
    ]

    return {
        "artifact": "failure_gallery",
        "cohort_sha256": comparison.cohort_sha256,
        "variants": list(comparison.variants),
        "lost_cases": lost_cases,
        "failed_runs": failed_runs,
    }
