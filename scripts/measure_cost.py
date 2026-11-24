#!/usr/bin/env python3
"""The report of the cost of a turn: the cost of an investigation, the cost of a resolved case and the review.

Why it exists: the repository publishes the cost of a turn, and a cost without the provenance of every price
is a number a reader cannot check. This script reads the report of the offline evaluation and writes
`data/eval/report_cost.md` with the cost of an investigation, the cost per correctly resolved case, the cost
of the human review, the total of the run, the provenance of every price, the missing pricing and the
sensitivity of the review to the rate.

The script runs offline, with no key and with no network: it reads the report of the evaluation that is on
the disk and the assumptions of the review, and it calls no model at all. The price of the model of the
offline run is unknown, and the report says so: an unknown price is unknown and never zero, and the total of
the run is not published.

Usage:

```bash
uv run python scripts/measure_cost.py
```

Exit code 0 when the report was written, 1 when the report of the evaluation is not on the disk.
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

from ledgerlens.economics.assumptions import ReviewAssumption  # noqa: E402

REPORT_ONLINE = ROOT / "data" / "eval" / "report_offline.json"
REPORT = ROOT / "data" / "eval" / "report_cost.md"

# The assumption of the review of this report: the minutes of a review and the rate of an hour, with the
# source. The assumption is a field of the report and never a constant of the code, so the reader can
# recompute the cost with another rate.
ASSUMPTION = ReviewAssumption(
    minutes=Decimal("10"),
    hourly_rate_usd=Decimal("30"),
    source="the assumption of the maintainer of the repository",
)
SENSITIVITY_RATE = Decimal("60")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Writes the report of the cost of a turn.")
    parser.parse_args(argv)
    if not REPORT_ONLINE.is_file():
        print(f"measure_cost: the report of the evaluation is not on the disk: {REPORT_ONLINE}")
        return 1

    report = json.loads(REPORT_ONLINE.read_text(encoding="utf-8"))
    variant_c = report["variants"]["C"]
    reviews = int(variant_c["human_review"])
    cases = [row for row in report["per_case"] if row["variant"] == "C"]
    resolved = sum(
        1
        for row in cases
        if float(row["scores"]["correctness"]) >= 1.0 and not row["requires_human_review"]
    )
    cut = (report.get("cost") or {}).get("cut_by_cap", [])

    review_total = (ASSUMPTION.cost_usd or Decimal("0")) * reviews
    sensitive = ReviewAssumption(minutes=ASSUMPTION.minutes, hourly_rate_usd=SENSITIVITY_RATE, source=ASSUMPTION.source)
    review_total_sensitive = (sensitive.cost_usd or Decimal("0")) * reviews
    lines = [
        "# The cost of a turn over the evaluation set",
        "",
        "The set: `eval_cases`, role `tuning` in the manifest of the datasets. A cost over a tuning set is a "
        "tendency and not a generalization.",
        "",
        "## The cost of an investigation",
        "",
        "The price of the model of the offline run is unknown, and an unknown price is unknown and never "
        "zero: the cost of an investigation is not published, and the total of the run is not published.",
        "",
        "## The cost per correctly resolved case",
        "",
        f"The cases the agent resolved: {resolved} of {len(cases)}. The cost per correctly resolved case is "
        "not published, because the price of the model is unknown and the total of the run is not published.",
        "",
        "## The cost of the human review",
        "",
        f"The cases that went to a human review: {reviews}. The assumption of the review: "
        f"{ASSUMPTION.minutes} minutes of a review and {ASSUMPTION.hourly_rate_usd} USD of an hour, "
        f"from {ASSUMPTION.source}.",
        "",
        f"The cost of the review of the run: {review_total} USD.",
        "",
        "## The sensitivity to the rate of the review",
        "",
        f"With the rate of {SENSITIVITY_RATE} USD of an hour, the cost of the review of the run is "
        f"{review_total_sensitive} USD. The sensitivity is a measurement of the assumption and not an "
        "interval of confidence.",
        "",
        "## The cases a cap cut",
        "",
        f"The cases a cap cut, named as cut and not as wrong answers: {', '.join(cut) if cut else 'none'}.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"the report of the cost was written: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
