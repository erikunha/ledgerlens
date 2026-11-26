"""The paired comparison of two variants over a cohort: the difference, case by case.

Why the comparison is paired: two variants over the same cohort are compared case by case, because a mean over
one cohort and a mean over another is a comparison over two questions. The comparison reads the results of the
runs that already happened and never calls a model (ADR-037): the runs are the input, and the comparison is a
function of them.

Why a missing run is excluded and never a zero: a case that one variant did not run, or whose run failed, says
nothing about the variant that ran it. The case is excluded from the pairing and named with the reason, so the
mean of a variant is never lowered by a run that did not happen.

Why the interval names its method: an interval without the method that computed it is a number without a
measurement. The method of the uncertainty is declared in the result, and the goal of the experiment is checked
against the measured score, so a score of 0.73 never meets a goal of 0.80.

The result declares the minimum number of measured pairs needed for a stratum mean. Each stratum counts all
its cases, including excluded ones, so the totals of the strata add up to the cohort.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class ComparisonError(Exception):
    """The comparison cannot be made, and the message says why."""


# The method of the uncertainty that the repository declares: the paired difference, with the standard error of
# the differences and the normal approximation of 95 percent. It is closed form and deterministic, and it is the
# method the orchestration comparison already declares (ADR-102).
DEFAULT_METHOD = (
    "the paired difference, with the standard error of the differences and the normal approximation of 95 percent"
)


@dataclass(frozen=True)
class CaseRun:
    """The run of one case in one variant, as the measurement recorded it."""

    case_id: str
    variant: str
    cohort_sha256: str
    ran: bool
    score: float | None
    failure: str | None = None
    expected_facts: tuple[str, ...] = ()
    evidence_cited: tuple[str, ...] = ()
    intent: str = ""
    complexity: str = ""


@dataclass(frozen=True)
class ExcludedCase:
    """A case that is out of the pairing, and the reason it is out."""

    case_id: str
    reason: str


@dataclass(frozen=True)
class CaseDifference:
    """The difference of one paired case: the score of the first variant minus the score of the second."""

    case_id: str
    first: float
    second: float
    difference: float


@dataclass(frozen=True)
class Interval:
    """The interval of the mean difference, with the method that computed it."""

    low: float
    high: float
    method: str


@dataclass(frozen=True)
class Stratum:
    """One stratum of the cohort: the dimension, the name, the count and the mean when it is earned."""

    dimension: str
    name: str
    count: int
    mean: float | None
    marked: str | None


@dataclass(frozen=True)
class PairedComparison:
    """The result of a paired comparison: the pairing, the excluded, the differences, the interval and the goal."""

    cohort_sha256: str
    variants: tuple[str, str]
    paired_cases: int
    excluded: tuple[ExcludedCase, ...]
    differences: tuple[CaseDifference, ...]
    means: dict[str, float]
    mean_difference: float
    interval: Interval
    goal: float
    goal_variant: str
    goal_met: bool
    strata: tuple[Stratum, ...]
    minimum_stratum: int

    def mean_of(self, variant: str) -> float:
        """The mean of one variant over the paired cases."""
        return self.means[variant]


def read_runs(path: Path) -> tuple[CaseRun, ...]:
    """Reads the runs of a measurement, as the fixture or the result of an experiment holds them."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        CaseRun(
            case_id=str(run["case_id"]),
            variant=str(run["variant"]),
            cohort_sha256=str(run["cohort_sha256"]),
            ran=bool(run["ran"]),
            score=run["score"],
            failure=run.get("failure"),
            expected_facts=tuple(run.get("expected_facts", ())),
            evidence_cited=tuple(run.get("evidence_cited", ())),
            intent=str(run.get("intent", "")),
            complexity=str(run.get("complexity", "")),
        )
        for run in data["runs"]
    )


def _by_case(runs: Sequence[CaseRun]) -> dict[str, dict[str, CaseRun]]:
    """Group runs by case and variant, rejecting repeated observations."""
    grouped: dict[str, dict[str, CaseRun]] = {}
    for run in runs:
        by_variant = grouped.setdefault(run.case_id, {})
        if run.variant in by_variant:
            raise ComparisonError(f"duplicate observation for case {run.case_id} and variant {run.variant}")
        by_variant[run.variant] = run
    return grouped


def compare(
    runs: Sequence[CaseRun],
    *,
    goal: float,
    method: str,
    goal_variant: str | None = None,
    minimum_stratum: int = 5,
) -> PairedComparison:
    """Compares two variants over a cohort, case by case.

    The runs of the two variants must name the same cohort, or the comparison is refused. A case is paired when
    both variants ran it and both runs carry a score. Every other case is excluded with the reason. A repeated
    case and variant observation is refused. The mean of a variant is over the paired cases only.

    The goal is checked against the mean of the `goal_variant`, and the result names that variant, because a
    check of the goal that does not say which variant it checked is a check a reader cannot read. The
    `goal_variant` is the first variant when the caller names none.
    """
    cohorts = {run.cohort_sha256 for run in runs}
    if len(cohorts) != 1:
        raise ComparisonError(
            f"the runs name {len(cohorts)} cohorts, and a comparison over two cohorts is a comparison over two "
            "questions"
        )
    cohort = cohorts.pop()

    variants = sorted({run.variant for run in runs})
    if len(variants) != 2:
        raise ComparisonError(f"the comparison is over two variants, and the runs name {len(variants)}")
    first_name, second_name = variants

    grouped = _by_case(runs)
    differences: list[CaseDifference] = []
    excluded: list[ExcludedCase] = []
    paired_runs: dict[str, list[CaseRun]] = {first_name: [], second_name: []}
    case_strata: dict[str, tuple[str, str]] = {}

    for case_id, by_variant in grouped.items():
        first = by_variant.get(first_name)
        second = by_variant.get(second_name)
        any_run = first or second
        if any_run is not None:
            case_strata[case_id] = (any_run.intent, any_run.complexity)
        if first is None or second is None:
            missing = first_name if first is None else second_name
            excluded.append(ExcludedCase(case_id=case_id, reason=f"the variant {missing} did not run the case"))
            continue
        if not first.ran or not second.ran:
            missing = first_name if not first.ran else second_name
            excluded.append(ExcludedCase(case_id=case_id, reason=f"the variant {missing} did not run the case"))
            continue
        if first.score is None or second.score is None:
            failed = first_name if first.score is None else second_name
            reason = first.failure if first.score is None else second.failure
            excluded.append(
                ExcludedCase(case_id=case_id, reason=f"the run of {failed} failed: {reason or 'no reason recorded'}")
            )
            continue
        differences.append(
            CaseDifference(
                case_id=case_id,
                first=first.score,
                second=second.score,
                difference=first.score - second.score,
            )
        )
        paired_runs[first_name].append(first)
        paired_runs[second_name].append(second)

    if not differences:
        raise ComparisonError("no case was paired, and a comparison with no paired case is no comparison")

    means = {
        name: sum(run.score for run in case_runs if run.score is not None) / len(case_runs)
        for name, case_runs in paired_runs.items()
    }
    mean_difference = sum(item.difference for item in differences) / len(differences)
    variance = sum((item.difference - mean_difference) ** 2 for item in differences) / max(len(differences) - 1, 1)
    standard_error = math.sqrt(variance) / math.sqrt(len(differences))
    interval = Interval(
        low=mean_difference - 1.96 * standard_error,
        high=mean_difference + 1.96 * standard_error,
        method=method,
    )

    strata = _stratify(grouped, differences, case_strata, minimum_stratum)

    checked = goal_variant if goal_variant is not None else first_name
    if checked not in means:
        raise ComparisonError(f"the goal is checked against the variant {checked}, and the runs name no such variant")

    return PairedComparison(
        cohort_sha256=cohort,
        variants=(first_name, second_name),
        paired_cases=len(differences),
        excluded=tuple(excluded),
        differences=tuple(differences),
        means=means,
        mean_difference=mean_difference,
        interval=interval,
        goal=goal,
        goal_variant=checked,
        goal_met=means[checked] >= goal,
        strata=strata,
        minimum_stratum=minimum_stratum,
    )


def _stratify(
    grouped: dict[str, dict[str, CaseRun]],
    differences: list[CaseDifference],
    case_strata: dict[str, tuple[str, str]],
    minimum_stratum: int,
) -> tuple[Stratum, ...]:
    """The stratification of the cohort by intent and by complexity.

    The count of a stratum is the count of the cases of the stratum, paired or excluded, so the totals of the
    strata of one dimension add up to the cohort. The mean of a stratum is the mean of the differences of the
    paired cases of the stratum. A stratum below the declared minimum of measured pairs carries no mean.
    """
    difference_of = {item.case_id: item.difference for item in differences}
    strata: list[Stratum] = []
    for dimension, index in (("intent", 0), ("complexity", 1)):
        by_name: dict[str, list[str]] = {}
        for case_id, values in case_strata.items():
            by_name.setdefault(values[index] or "unknown", []).append(case_id)
        for name in sorted(by_name):
            case_ids = by_name[name]
            paired = [difference_of[case_id] for case_id in case_ids if case_id in difference_of]
            count = len(case_ids)
            pair_count = len(paired)
            if pair_count < minimum_stratum:
                observations = f"{count} case(s)" if pair_count == count else f"{pair_count} measured pair(s)"
                strata.append(
                    Stratum(
                        dimension=dimension,
                        name=name,
                        count=count,
                        mean=None,
                        marked=f"the stratum holds {observations}, below the declared minimum of {minimum_stratum}",
                    )
                )
            else:
                mean = sum(paired) / len(paired) if paired else None
                strata.append(Stratum(dimension=dimension, name=name, count=count, mean=mean, marked=None))
    return tuple(strata)
