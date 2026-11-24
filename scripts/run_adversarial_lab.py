#!/usr/bin/env python3
"""Runs the list of the exercises of the adversarial laboratory, offline, and writes the result of each one.

Why it exists: the laboratory measures the boundaries of the repository with canned exercises, and the results
of the exercises are the evidence of the measurement. This script runs the whole list in the offline mode,
with the scripted model and the fake provider, and writes the result of each exercise under
`data/adversarial/results/`, so the page of the laboratory and the reader of the repository can check what
each attack did and which layer answered.

The script refuses to run with a key in the environment: the exercises run in the offline mode with the fake
provider, so an attack never spends the money of anybody, and a run with a key in the environment is a run
that could spend it. The refusal names the variable, never the value.

Usage:

```bash
uv run python scripts/run_adversarial_lab.py
```

Exit code 0 when every exercise ran and the results were written, 1 when the script refused to run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.adversarial.exercises import EXERCISES  # noqa: E402  (the path is set up before the import)
from ledgerlens.adversarial.runner import run_exercise  # noqa: E402

__all__ = ["DEFAULT_OUT", "main", "run_lab"]

# Where the results of the exercises go. The results are the evidence of the measurement of the laboratory.
DEFAULT_OUT = ROOT / "data" / "adversarial" / "results"

# The variables that mean a run could spend the money of somebody. The laboratory runs offline, with no key.
KEY_VARIABLES = ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")


def run_lab(out_dir: Path) -> list[Path]:
    """Runs the whole list of the exercises and writes the result of each one. Returns the paths written."""
    for variable in KEY_VARIABLES:
        if os.environ.get(variable):
            raise RuntimeError(
                f"the laboratory runs offline and with no key, and the variable {variable} is set: unset it "
                "before you run the exercises"
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="ledgerlens_adversarial_") as work:
        for exercise in EXERCISES:
            result = run_exercise(exercise, work_dir=Path(work) / exercise.exercise_id)
            target = out_dir / f"{exercise.exercise_id}.json"
            target.write_text(
                json.dumps(
                    {
                        "exercise_id": result.exercise_id,
                        "surface": result.surface,
                        "expected_boundary": result.expected_boundary,
                        "trace_ref": result.trace_ref,
                        "blocked_actions": [
                            {"action": blocked.action, "layer": blocked.layer, "reason": blocked.reason}
                            for blocked in result.blocked_actions
                        ],
                        "open_risk": result.open_risk,
                        "unauthorized_actions": result.unauthorized_actions,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            written.append(target)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the laboratory and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Runs the exercises of the adversarial laboratory, offline.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the results of the exercises go to")
    args = parser.parse_args(argv)

    try:
        written = run_lab(Path(args.out))
    except RuntimeError as exc:
        print(f"run_adversarial_lab: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"the result of the exercise is in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
