#!/usr/bin/env python3
"""Publishes the economics of the measured cohort: the cost per correctly resolved case, with its denominator.

Why it exists: the economics module computes, and the numbers it computes have to reach a reader as an artifact
that can be checked. This script takes the published measurement of the comparison of the routes, builds the cohort
of each of its two arms out of the per-case money and the per-case label that the measurement recorded, and writes
the economics with the hash of its content and the digest of the cohort it was computed over.

What it publishes: the cost of each case, the total of the cohort, the number of cases the code resolved, the cost
of a resolved case and the comparison of the two arms over the same cohort.

What it refuses: a cohort whose digest moved, because a result computed over one cohort and published over another
describes nothing. It also refuses to invent a money for a model whose price nobody verified: the artifact names the
price that is missing and prints no amount for it, because unknown is never zero (FR-011).

What it never does: it never calls a model and it never chooses one. It reads the results of the runs that already
happened, under ADR-037 and the FR-013 it carries.

Usage:

```bash
uv run python scripts/export_economics.py
```

Exit code 0 when the artifacts were written, 1 when they could not be.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.economics.assumptions import Assumptions, PriceSnapshot, ReviewAssumption  # noqa: E402
from ledgerlens.economics.cost import (  # noqa: E402
    CATEGORY_MODEL,
    CaseCost,
    CohortComparison,
    CohortCost,
    CostCategory,
    compare_cohorts,
)
from ledgerlens.economics.publish import export_comparison, export_economics  # noqa: E402

__all__ = ["DEFAULT_OUT", "DEFAULT_REPORT", "build_cohorts", "main"]

# Where the artifacts of the economics go. The files are the evidence of the computation, and they are read by the
# page of the routing.
DEFAULT_OUT = ROOT / "data" / "eval"

# The measurement of the comparison of the routes: the per-case money and the per-case label of every arm.
DEFAULT_REPORT = ROOT / "data" / "eval" / "routing_comparison.json"

# The minutes of a review and the rate of an hour, which are assumptions of the reader and not facts of the
# repository. The cohort of the comparison holds no case that went to a person, so no review money enters the
# total, and the assumptions travel with the artifact anyway.
REVIEW_MINUTES = Decimal("15")
REVIEW_HOURLY_RATE_USD = Decimal("60.00")


def _price_of(model: str) -> PriceSnapshot:
    """The price of a model, as the registry of the repository carries it.

    Why the registry and not a number of the script: the price has a source and a day, and a price that the script
    wrote would have neither.
    """
    from ledgerlens.byok.registry import ALLOWLIST

    for profile in ALLOWLIST:
        if profile.model_id == model:
            pricing = profile.pricing
            return PriceSnapshot(
                source=pricing.source,
                last_verified=pricing.last_verified,
                input_per_1m_usd=pricing.input_per_1m_usd,
                output_per_1m_usd=pricing.output_per_1m_usd,
            )
    return PriceSnapshot()


def _assumptions_of(report: dict[str, object]) -> Assumptions:
    """The assumptions of the cohort: the review and the price of every model the cohort called."""
    models: set[str] = set()
    for arm in report.get("arms", {}).values():  # type: ignore[union-attr]
        for case in arm.get("cases", []):  # type: ignore[union-attr]
            models.update(str(model) for model in case.get("calls_by_model", {}))
    return Assumptions(
        review=ReviewAssumption(
            minutes=REVIEW_MINUTES,
            hourly_rate_usd=REVIEW_HOURLY_RATE_USD,
            source="manual",
        ),
        prices=tuple((model, _price_of(model)) for model in sorted(models)),
    )


def build_cohorts(report_path: Path = DEFAULT_REPORT) -> tuple[list[CohortCost], CohortComparison | None]:
    """The cohort of each arm of the measurement, and the comparison of the two when there are two.

    Why a case is resolved when the label of the measurement is a full score: the oracle of a resolved case comes
    from the code that resolved it, and the label of the measurement is the score of the evaluator of the
    repository. A case with a partial score was not settled, and it is not in the denominator.

    Why a case with no money is unknown and not zero: the price of the model was never verified, and a zero would
    say that the call was free (FR-011).
    """
    report = json.loads(report_path.read_text(encoding="utf-8"))
    digest = str(report.get("cohort", {}).get("digest", ""))
    assumptions = _assumptions_of(report)

    cohorts: list[CohortCost] = []
    for name, arm in report.get("arms", {}).items():
        cases = tuple(
            CaseCost(
                case_id=str(case.get("case", "")),
                categories=(
                    CostCategory(
                        name=CATEGORY_MODEL,
                        usd=None if case.get("cost_usd") is None else Decimal(str(case["cost_usd"])),
                        known=case.get("cost_usd") is not None,
                        reason=(
                            ""
                            if case.get("cost_usd") is not None
                            else str(case.get("money_reason", "the money of the case is unknown"))
                        ),
                    ),
                ),
                resolved=float(case.get("correctness", 0.0)) >= 1.0,
                went_to_person=False,
            )
            for case in arm.get("cases", [])
        )
        cohorts.append(
            CohortCost(
                cohort_id=str(name),
                cases=cases,
                assumptions=assumptions,
                cohort_digest=digest,
            )
        )

    comparison = compare_cohorts(cohorts[0], cohorts[1]) if len(cohorts) == 2 else None
    return cohorts, comparison


def main(argv: Sequence[str] | None = None) -> int:
    """Publishes the economics of the measured cohort and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Publishes the economics of the measured cohort.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the artifacts of the economics go to")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="the published measurement of the cohort")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    out_dir = Path(args.out)
    try:
        cohorts, comparison = build_cohorts(report_path)
        written = []
        for cohort in cohorts:
            written.append(
                export_economics(
                    cohort,
                    expected_digest=cohort.cohort_digest,
                    out_dir=out_dir / cohort.cohort_id,
                )
            )
        if comparison is not None:
            path = export_comparison(comparison, out_dir=out_dir)
            written.append(path)
    except (OSError, ValueError) as exc:
        print(f"export_economics: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"the economics are in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
