#!/usr/bin/env python3
"""Plan a blinded family holdout and compare independently adjudicated trial results offline."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, quantiles

from ledgerlens.eval.json_input import read_experiment_json

ARMS = ("A", "B")
RESOLVED = "resolved"
CLARIFIED = "clarified"
FAILED = "failed"
ERROR = "error"
TIMEOUT = "timeout"
MISSING = "missing"
REVIEWABLE_OUTCOMES = (RESOLVED, CLARIFIED)
OUTCOMES = (*REVIEWABLE_OUTCOMES, FAILED, ERROR, TIMEOUT)
FIRST_TRIAL = 1
MINIMUM_INTERVAL_FAMILIES = 2
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
BOOTSTRAP_QUANTILES = 40
PLAN_COMMAND = "plan"
REPORT_COMMAND = "report"


@dataclass(frozen=True)
class Judgment:
    outcome: str
    success: bool
    cost: Decimal | None


MISSING_JUDGMENT = Judgment(MISSING, False, None)


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _token(seed: str, value: object) -> str:
    return hmac.new(seed.encode("utf-8"), _encoded(value), hashlib.sha256).hexdigest()


def _is_label(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_plan(manifest: object, blind_seed: str) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    variants = manifest.get("variants")
    cases = manifest.get("cases")
    split_seed = manifest.get("split_seed")
    count = manifest.get("holdout_families")
    repeats = manifest.get("repeats")
    if (
        not isinstance(variants, list)
        or len(variants) != len(ARMS)
        or not all(_is_label(variant) for variant in variants)
        or len(set(variants)) != len(ARMS)
    ):
        raise ValueError("variants must contain two distinct names")
    if (
        not isinstance(cases, dict)
        or not cases
        or not all(_is_label(case) and _is_label(family) for case, family in cases.items())
    ):
        raise ValueError("cases must map nonempty case IDs to nonempty family IDs")
    if not _is_label(split_seed) or not _is_label(blind_seed):
        raise ValueError("split and blind seeds must be nonempty")
    if type(repeats) is not int or repeats < FIRST_TRIAL:
        raise ValueError("repeats must be a positive integer")

    families = set(cases.values())
    if type(count) is not int or not FIRST_TRIAL <= count <= len(families):
        raise ValueError("holdout_families must be between one and the number of declared families")
    ranked = sorted(families, key=lambda family: (_token(split_seed, family), family))
    holdout_families = set(ranked[:count])
    split = {
        "holdout": {case: family for case, family in cases.items() if family in holdout_families},
        "development": {case: family for case, family in cases.items() if family not in holdout_families},
    }
    split_hash = hashlib.sha256(_encoded(split)).hexdigest()
    design_id = hashlib.sha256(_encoded(manifest)).hexdigest()
    masked_variants = sorted(variants, key=lambda variant: (_token(blind_seed, [design_id, variant]), variant))
    variants_by_arm = dict(zip(ARMS, masked_variants, strict=True))
    assignments = []
    for case in sorted(split["holdout"]):
        first_order = sorted(ARMS, key=lambda arm: (_token(blind_seed, [design_id, case, arm]), arm))
        for run in range(FIRST_TRIAL, repeats + FIRST_TRIAL):
            order = first_order if run % len(ARMS) == FIRST_TRIAL else reversed(first_order)
            slots = [
                {
                    "id": _token(blind_seed, [design_id, case, run, arm]),
                    "arm": arm,
                    "variant": variants_by_arm[arm],
                }
                for arm in order
            ]
            assignments.append({"case": case, "run": run, "slots": slots})

    return {
        **split,
        "split_sha256": split_hash,
        "manifest_sha256": design_id,
        "repeats": repeats,
        "assignments": assignments,
    }


def _read_judgments(rows: object, trial_ids: set[str]) -> dict[str, Judgment]:
    if not isinstance(rows, list):
        raise ValueError("results must be a list")
    judgments = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("result must be an object")
        trial_id = row.get("id")
        if not isinstance(trial_id, str) or trial_id not in trial_ids:
            raise ValueError("unknown trial ID")
        if trial_id in judgments:
            raise ValueError("duplicate trial ID")
        outcome = row.get("outcome")
        if outcome not in OUTCOMES:
            raise ValueError("invalid trial outcome")
        success = row.get("success", outcome == RESOLVED)
        if type(success) is not bool or (success and outcome not in REVIEWABLE_OUTCOMES):
            raise ValueError("invalid trial success")
        cost = row.get("cost_usd")
        if cost is not None:
            try:
                if not isinstance(cost, str):
                    raise InvalidOperation
                cost = Decimal(cost)
                if not cost.is_finite() or cost < 0:
                    raise InvalidOperation
            except InvalidOperation:
                raise ValueError("cost_usd must be a nonnegative decimal string") from None
        judgments[trial_id] = Judgment(outcome, success, cost)
    return judgments


def _comparison(family_differences: list[list[float]], observed_families: int) -> dict:
    differences = [mean(values) for values in family_differences]
    interval = None
    if observed_families >= MINIMUM_INTERVAL_FAMILIES:
        sampler = random.Random(BOOTSTRAP_SEED)
        estimates = [mean(sampler.choices(differences, k=len(differences))) for _ in range(BOOTSTRAP_RESAMPLES)]
        # The outer of 40 equal quantiles are the 2.5th and 97.5th percentiles.
        bounds = quantiles(estimates, n=BOOTSTRAP_QUANTILES, method="inclusive")
        interval = [bounds[0], bounds[-1]]
    return {"difference_b_minus_a": mean(differences), "interval_95": interval}


def summarize(plan: dict, results: object) -> dict:
    trial_ids = {slot["id"] for assignment in plan["assignments"] for slot in assignment["slots"]}
    judgments = _read_judgments(results, trial_ids)
    by_arm: dict[str, dict[str, list[Judgment]]] = {arm: defaultdict(list) for arm in ARMS}
    for assignment in plan["assignments"]:
        for slot in assignment["slots"]:
            by_arm[slot["arm"]][assignment["case"]].append(judgments.get(slot["id"], MISSING_JUDGMENT))

    arms = {}
    passed_cases = {}
    trial_counts = {}
    for arm, cases in by_arm.items():
        trial_counts[arm] = {case: sum(trial.success for trial in trials) for case, trials in cases.items()}
        passed_cases[arm] = {case for case, count in trial_counts[arm].items() if count == plan["repeats"]}
        judgments_for_arm = [trial for trials in cases.values() for trial in trials]
        costs = [trial.cost for trial in judgments_for_arm if trial.cost is not None]
        outcomes = Counter(trial.outcome for trial in judgments_for_arm)
        successes = sum(trial_counts[arm].values())
        arms[arm] = {
            "trials": len(judgments_for_arm),
            **{outcome: outcomes[outcome] for outcome in (*OUTCOMES, MISSING)},
            "successful_trials": successes,
            "per_trial_success_rate": successes / len(judgments_for_arm),
            "cases": len(cases),
            "all_trials_success": len(passed_cases[arm]),
            "all_trial_success_rate": len(passed_cases[arm]) / len(cases),
            "cost_usd": str(sum(costs)) if costs else None,
            "trials_with_cost": len(costs),
        }

    arm_a, arm_b = ARMS
    all_trial_differences = defaultdict(list)
    per_trial_differences = defaultdict(list)
    for case, family in sorted(plan["holdout"].items()):
        all_trial_differences[family].append(int(case in passed_cases[arm_b]) - int(case in passed_cases[arm_a]))
        per_trial_differences[family].append((trial_counts[arm_b][case] - trial_counts[arm_a][case]) / plan["repeats"])
    observed_families = {
        family
        for case, family in plan["holdout"].items()
        if any(
            left.outcome != MISSING and right.outcome != MISSING
            for left, right in zip(by_arm[arm_a][case], by_arm[arm_b][case], strict=True)
        )
    }
    return {
        "split_sha256": plan["split_sha256"],
        "manifest_sha256": plan["manifest_sha256"],
        "repeats": plan["repeats"],
        "arms": arms,
        "missing_trial_ids": sorted(trial_ids - judgments.keys()),
        "shared_failure_cases": sorted(plan["holdout"].keys() - (passed_cases[arm_a] | passed_cases[arm_b])),
        "disagreement_cases": sorted(passed_cases[arm_a] ^ passed_cases[arm_b]),
        "paired": {
            "families": len(all_trial_differences),
            "families_with_observed_pairs": len(observed_families),
            "method": "paired percentile bootstrap with equal family weights",
            "resamples": BOOTSTRAP_RESAMPLES,
            "all_trial_success": _comparison(list(all_trial_differences.values()), len(observed_families)),
            "per_trial_success": _comparison(list(per_trial_differences.values()), len(observed_families)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser(PLAN_COMMAND, help="Emit the private assignment plan in execution order.")
    report_parser = commands.add_parser(REPORT_COMMAND, help="Summarize adjudicated trial results by blinded arm.")
    for command in (plan_parser, report_parser):
        command.add_argument("--manifest", type=Path, required=True, help="Frozen experiment manifest JSON.")
        command.add_argument("--blind-seed", required=True, help="Coordinator-only seed, kept outside reviewer data.")
    report_parser.add_argument("--results", type=Path, required=True, help="JSON array of judgments with opaque IDs.")
    args = parser.parse_args()

    try:
        manifest = read_experiment_json(args.manifest)
        plan = build_plan(manifest, args.blind_seed)
        result = plan
        if args.command == REPORT_COMMAND:
            rows = read_experiment_json(args.results)
            result = summarize(plan, rows)
    except OSError:
        parser.error("cannot read input")
    except (UnicodeError, json.JSONDecodeError):
        parser.error("input is not valid JSON")
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
