"""The command of the twin: it runs the twin over a configuration and prints the manifest of the run.

Why the command exists: the twin is run by one command, and the command prints the manifest of the run, so a
reader of the manifest knows which world the run measured and under which assumptions. The command writes
nothing into the catalogs of the recordings: a run of the twin is a simulation and not a recording of the
agent.

What the command refuses: a configuration that cannot be simulated is refused before anything is written, and
the refusal names the field that is wrong.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.twin.config import TwinConfig, TwinConfigRefused
from ledgerlens.sim.twin.manifest import canonical_bytes
from ledgerlens.sim.twin.run import run_twin

__all__ = ["main"]

ROOT = Path(__file__).resolve().parents[3]
TRUTH = ROOT / "data" / "scenarios.json"


def _commit() -> str:
    """The commit of the code that ran the twin, for the manifest."""
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the twin and prints the manifest of the run."""
    parser = argparse.ArgumentParser(description="Runs the operations digital twin over a configuration.")
    parser.add_argument("--seed", type=int, default=42, help="the seed of the run")
    parser.add_argument("--horizon", type=int, default=480, help="the horizon of the run, in minutes")
    parser.add_argument("--arrival-rate", default="6", help="the arrival rate of the run, in cases per hour")
    parser.add_argument("--slots", type=int, default=2, help="the capacity of the run, in slots")
    parser.add_argument("--service-time", default="15", help="the service time of a case, in minutes")
    parser.add_argument("--review-policy", default="shipped", help="the review policy of the run")
    args = parser.parse_args(argv)

    config = TwinConfig(
        seed=args.seed,
        horizon_minutes=args.horizon,
        arrival_rate_per_hour=Decimal(args.arrival_rate),
        slots=args.slots,
        service_time_minutes=Decimal(args.service_time),
        review_policy=args.review_policy,
    )
    try:
        run = run_twin(config, truth_path=TRUTH, commit=_commit())
    except TwinConfigRefused as exc:
        print(f"ledgerlens-twin: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(json.loads(canonical_bytes(run.manifest)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
