"""Audit first-investigation A/A records offline and estimate visitors for a fixed-horizon A/B."""

import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist

from ledgerlens.eval.json_input import read_experiment_json

ARMS = ("A", "B")
FIELDS = {"visitor", "arm", "exposed", "resolved"}
ALLOCATION_ALPHA = 0.01
SIGNIFICANCE = 0.05
POWER = 0.80
EXACT_ALLOCATION_LIMIT = 100


def plan(baseline: float, improvement: float) -> int:
    """Approximate visitors per arm for independent binary outcomes with equal allocation."""
    target = baseline + improvement
    if not 0 < baseline < target < 1:
        raise ValueError("Baseline and target probabilities must be strictly between zero and one.")
    pooled = (baseline + target) / 2
    normal = NormalDist()
    null_sd = math.sqrt(2 * pooled * (1 - pooled))
    alt_sd = math.sqrt(baseline * (1 - baseline) + target * (1 - target))
    distance = normal.inv_cdf(1 - SIGNIFICANCE / 2) * null_sd + normal.inv_cdf(POWER) * alt_sd
    return math.ceil((distance / improvement) ** 2)


def _outcome_check(first: dict, second: dict) -> tuple[float | None, str | None]:
    """Compare binary first-investigation outcomes in a completed A/A run."""
    if any(not arm["assigned"] or arm["missing_outcomes"] for arm in (first, second)):
        return None, None
    a, b = first["assigned"], second["assigned"]
    successes = first["resolved"] + second["resolved"]
    total = a + b
    if successes in (0, total):
        return 1.0, "identical constant outcomes"
    if total <= EXACT_ALLOCATION_LIMIT:

        def weight(k):
            return math.comb(a, k) * math.comb(b, successes - k)

        observed = weight(first["resolved"])
        possible = range(max(0, successes - b), min(a, successes) + 1)
        return sum(w for k in possible if (w := weight(k)) <= observed) / math.comb(total, successes), "Fisher exact"
    rate = successes / total
    if min(a, b) * min(rate, 1 - rate) < 5:
        return None, "insufficient expected counts for normal approximation"
    error = math.sqrt(rate * (1 - rate) * (1 / a + 1 / b))
    difference = abs(first["resolved"] / a - second["resolved"] / b)
    return math.erfc(difference / error / math.sqrt(2)), "pooled two-proportion z-test"


def audit(rows: list[dict]) -> dict:
    """Each input is one eligible assigned visitor, including those without observed outcomes."""
    if not isinstance(rows, list):
        raise ValueError("Expected a JSON array of visitor records.")
    seen = set()
    arms = {arm: dict(assigned=0, resolved=0, missing_exposures=0, missing_outcomes=0) for arm in ARMS}
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("Expected only visitor, arm, exposed and resolved.")
        visitor, arm, exposed, resolved = (row[key] for key in ("visitor", "arm", "exposed", "resolved"))
        if not isinstance(visitor, str) or not visitor.strip() or visitor in seen or arm not in ARMS:
            raise ValueError("Expected one record per distinct visitor and a known arm.")
        if type(exposed) is not bool or (resolved is not None and (type(resolved) is not bool or not exposed)):
            raise ValueError("Exposure must be boolean. An observed outcome requires exposure.")
        seen.add(visitor)
        counts = arms[arm]
        counts["assigned"] += 1
        counts["resolved"] += resolved is True
        counts["missing_exposures"] += not exposed
        counts["missing_outcomes"] += resolved is None
    findings = []
    total = len(seen)
    for arm, counts in arms.items():
        assigned = counts["assigned"]
        counts["resolution_per_assigned"] = counts["resolved"] / assigned if assigned else None
        if not assigned or counts["missing_exposures"] or counts["missing_outcomes"]:
            findings.append(f"Check enrollment, exposure and outcome coverage in arm {arm}.")
    p = None
    method = None
    if total:
        smaller = min(counts["assigned"] for counts in arms.values())
        if total <= EXACT_ALLOCATION_LIMIT:
            method = "exact binomial"
            tail = sum(math.comb(total, i) for i in range(smaller + 1))
            p = min(1.0, 2 * tail / 2**total)
        else:
            method = "normal approximation with continuity correction"
            distance = max(0, total - 2 * smaller - 1) / math.sqrt(total)
            p = math.erfc(distance / math.sqrt(2))
    if p is not None and p < ALLOCATION_ALPHA:
        findings.append("Assignment counts are inconsistent with equal allocation.")
    outcome_p, outcome_method = _outcome_check(*arms.values())
    if outcome_p is not None and outcome_p < ALLOCATION_ALPHA:
        findings.append("Check the A/A outcome rates and adjudication pipeline.")
    if outcome_p is None and outcome_method:
        findings.append(outcome_method)
    return {
        "outcome_p_value": outcome_p,
        "outcome_method": outcome_method,
        "arms": arms,
        "allocation_p_value": p,
        "allocation_method": method,
        "instrumentation_findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSON array of eligible first-investigation records")
    parser.add_argument("--baseline", required=True, type=float)
    parser.add_argument("--improvement", required=True, type=float)
    args = parser.parse_args()
    try:
        result = audit(read_experiment_json(args.records))
        result["planned_visitors_per_arm"] = plan(args.baseline, args.improvement)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
