#!/usr/bin/env python3
"""Measures what the cascade of the deployment costs against one model for the whole run.

Why it exists: the router of ADR-078 chooses the model of each slot of a run by the task the slot does, and the
repository has no number that says what that choice costs. The published evaluation used one model for every
slot, so the numbers of the report on the disk are the numbers of the behaviour before the router existed. This
script runs the same cohort of cases twice, over the same ledger, once with one model in the four slots and once
with the cascade, and writes the accuracy by intent, the cost per correct case, the p95 of the latency, the rate
of fallback and the mix of models, each one with the denominator and the set it was measured over.

The comparison needs a key and a network: it calls a real model. It refuses offline, and it says why, because a
comparison over scripted answers measures the plumbing and not the routing.

The script writes two files and nothing else: `data/eval/routing_comparison.json`, the numbers with their
denominator, and `data/eval/routing_comparison.md`, the same numbers as prose. It never rewrites the cases, the
reports of the evaluation or the recordings of the catalogue.

Usage:

```bash
LEDGERLENS_MODEL=gpt-4.1-mini LEDGERLENS_MODEL_CASCADE="gpt-4.1-mini,gpt-4.1" \
  uv run python scripts/measure_routing.py
```

Exit code 0 when the comparison was measured and written, 1 when it could not be.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import get_settings, model_cascade  # noqa: E402  (the path is set up before the import)
from ledgerlens.eval.dataset import CASES_PATH, load_cases  # noqa: E402
from ledgerlens.eval.routing_comparison import (  # noqa: E402
    arms_of,
    build_report,
    build_world,
    render_markdown,
    run_arm,
)

__all__ = ["DEFAULT_OUT", "main", "measure"]

# Where the numbers of the comparison go. The files are the evidence of the measurement, and they are read by
# the page of the routing.
DEFAULT_OUT = ROOT / "data" / "eval"

# The note that travels with the numbers. It says what was measured and what the numbers are not.
NOTE = (
    "Real run of the two arms over the same cohort of cases, over the same ledger, with the deterministic judge "
    "of the repository. One run per case and one arm per model: the numbers are a trend and not a statistical "
    "significance. The dollars of a model whose price nobody verified are unknown, and unknown is never zero. "
    "The judge of the arms is the deterministic one with the stub of the NLI of the repository, and the client "
    "of the exchange runs on the fixtures of the repository: the absolute numbers are not the numbers of the "
    "published online report, and the two arms are the ones that are comparable with each other."
)


def measure(out_dir: Path, *, cases_path: Path = CASES_PATH) -> tuple[Path, Path]:
    """Runs the comparison and writes the two files of the measurement.

    Why the two arms are run in the order they are: the arm of one model is the behaviour the product had
    before the router, and it is the one the published report of the evaluation measured.
    """
    settings = get_settings()
    if settings.offline:
        raise RuntimeError(
            "the comparison calls a real model, so it cannot run offline: set LEDGERLENS_OFFLINE=0 and a key"
        )
    cascade = model_cascade(settings)
    if not cascade:
        raise RuntimeError("the deployment declares no model: set LEDGERLENS_MODEL and LEDGERLENS_MODEL_CASCADE")
    one_model = settings.model or cascade[0]
    arms = arms_of(cascade, one_model=one_model)
    cases = load_cases(cases_path)

    with tempfile.TemporaryDirectory(prefix="ledgerlens_routing_") as work:
        world = build_world(Path(work))
        results = [run_arm(arm, cases, world) for arm in arms]
        report = build_report(results, cohort=cases, world=world, cases_path=cases_path, note=NOTE)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "routing_comparison.json"
    md_path = out_dir / "routing_comparison.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the measurement and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Measures the cascade against one model over the same cases.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the numbers of the comparison go to")
    args = parser.parse_args(argv)

    try:
        json_path, md_path = measure(Path(args.out))
    except RuntimeError as exc:
        print(f"measure_routing: {exc}", file=sys.stderr)
        return 1
    print(f"the comparison is in {json_path}")
    print(f"the prose of the comparison is in {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
