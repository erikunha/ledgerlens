#!/usr/bin/env python3
"""Summarize full-credit repeatability from a local report without replaying the evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

METRICS = ("correctness", "groundedness")
FIRST_TRIAL = 1
MINIMUM_SCORE = 0
FULL_CREDIT = 1


def _count_cases(trials_by_case: dict[str, dict[int, dict]], metric: str, declared: int, repeats: int) -> dict:
    eligible = passed_all = passed_any = 0
    for trials in trials_by_case.values():
        scores = [trial_scores.get(metric) for trial_scores in trials.values()]
        if len(scores) != repeats or not all(
            type(score) in (int, float) and MINIMUM_SCORE <= score <= FULL_CREDIT for score in scores
        ):
            continue

        eligible += 1
        passed = [score == FULL_CREDIT for score in scores]
        passed_all += all(passed)
        passed_any += any(passed)

    return {
        "declared": declared,
        "eligible": eligible,
        "excluded": declared - eligible,
        "all": passed_all,
        "any": passed_any,
    }


def summarize_repeatability(report: object) -> dict:
    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    declared = report.get("cases")
    repeats = report.get("repeats")
    variants = report.get("variants")
    rows = report.get("per_case")
    if type(declared) is not int or declared < 0:
        raise ValueError("cases must be a nonnegative integer")
    if type(repeats) is not int or repeats < FIRST_TRIAL:
        raise ValueError("repeats must be a positive integer")
    if not isinstance(variants, dict):
        raise ValueError("variants must be a mapping")
    if not isinstance(rows, list):
        raise ValueError("per_case must be a list")

    trials_by_variant: dict[str, dict[str, dict[int, dict]]] = {variant: {} for variant in variants}
    observed_cases: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("trial must be an object")
        variant = row.get("variant")
        case = row.get("case")
        trial = row.get("run")
        if not isinstance(variant, str) or variant not in trials_by_variant:
            raise ValueError("trial uses an undeclared variant")
        if not isinstance(case, str) or not case.strip():
            raise ValueError("trial case must be a nonempty string")
        if type(trial) is not int or not FIRST_TRIAL <= trial <= repeats:
            raise ValueError(f"trial number must be an integer from {FIRST_TRIAL} to {repeats}")

        observed_cases.add(case)
        if len(observed_cases) > declared:
            raise ValueError("report has more distinct cases than declared")
        trials = trials_by_variant[variant].setdefault(case, {})
        if trial in trials:
            raise ValueError("duplicate trial identity")
        scores = row.get("scores")
        trials[trial] = scores if isinstance(scores, dict) else {}

    return {
        "repeats": repeats,
        "variants": {
            variant: {metric: _count_cases(trials_by_case, metric, declared, repeats) for metric in METRICS}
            for variant, trials_by_case in trials_by_variant.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Path to the online evaluation report JSON.")
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except OSError:
        parser.error("cannot read report")
    except (UnicodeError, json.JSONDecodeError):
        parser.error("report is not valid JSON")

    try:
        summary = summarize_repeatability(report)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
