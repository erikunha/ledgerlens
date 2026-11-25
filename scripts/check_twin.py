#!/usr/bin/env python3
"""Checks that the twin stays honest: a run of the seed 42 is deterministic, and the catalogs are untouched.

Why the check exists: the twin is a research instrument, and the gate checks that it stays honest. A run of
the seed 42 over a short horizon produces the expected bytes of the manifest (the bytes of the first run of
the same configuration, because the run is deterministic), and the two published catalogs of the recordings
of the agent are untouched by the run, because a run of the twin is a simulation and not a recording of the
agent.

The check writes nothing and fails the gate with a readable reason, so the gate stops on the reason and not
on a traceback.

Usage:

```bash
uv run python scripts/check_twin.py
```

Exit code 0 when the twin is honest, 1 when it is not.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.sim.twin.config import TwinConfig  # noqa: E402  (the path is set up before the import)
from ledgerlens.sim.twin.manifest import canonical_bytes  # noqa: E402
from ledgerlens.sim.twin.run import run_twin  # noqa: E402

REPLAY = ROOT / "data" / "eval" / "replay"
REPLAY_REAL = ROOT / "data" / "eval" / "replay-real"

# The configuration of the check: the seed 42 over a short horizon, with a fixed commit, so the expected
# bytes of the manifest are the bytes of the first run of the same configuration.
CONFIG = TwinConfig(seed=42, horizon_minutes=60, arrival_rate_per_hour=Decimal("6"), slots=2)
FIXED_COMMIT = "0" * 40


def _catalogs() -> set[str]:
    """The directories of the two published catalogs, for the check that they are untouched."""
    return {str(path) for root in (REPLAY, REPLAY_REAL) for path in root.glob("*") if path.is_dir()}


def main() -> int:
    """Runs the check and returns the exit code of the answer."""
    before = _catalogs()
    first = run_twin(CONFIG, truth_path=ROOT / "data" / "scenarios.json", commit=FIXED_COMMIT)
    second = run_twin(CONFIG, truth_path=ROOT / "data" / "scenarios.json", commit=FIXED_COMMIT)
    if canonical_bytes(first.manifest) != canonical_bytes(second.manifest):
        print("check_twin: the run of the seed 42 is not deterministic: two runs gave two manifests", file=sys.stderr)
        return 1
    if _catalogs() != before:
        print("check_twin: a run of the twin wrote into the published catalogs of the recordings", file=sys.stderr)
        return 1
    print("the twin is honest: the run of the seed 42 is deterministic and the catalogs are untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
