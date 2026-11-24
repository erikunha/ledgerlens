#!/usr/bin/env python3
"""Measures the multi-agent orchestration studio against the single agent, over the same cases and snapshot.

Why it exists: ADR-P007 keeps the studio behind a flag until a paired comparison measures a gain, and this
script is the measurement. It runs the two arms over the set of the registered experiment
(`data/runtime/orchestration/comparison.json`), over the same ledger built from the versioned sample, with the
same model, and it writes the measures with their denominator, the uncertainty of the difference and the
decision that follows the result, whether the result is a gain or a loss.

The comparison needs a key and a network: it calls a real model. It refuses offline, and it says why, because
the single agent replays the script of the case when the model is scripted, and a comparison over scripted
answers measures the plumbing and not the runtime.

The script refuses to run when the manifest of the experiment was written after the first run: the first run
pins the digest of the manifest in `data/runtime/orchestration/runs.jsonl`, and a registration that may be
rewritten after the run is not a registration.

The script writes three files and nothing else: `data/runtime/orchestration/result.json`, the numbers with
their denominator; `docs/orchestration/comparison.md`, the page of the result with the decision; and one line
of `data/runtime/orchestration/runs.jsonl`, the record of the run. It never rewrites the manifest of the
experiment, the cases or the recordings of the catalogue.

Usage:

```bash
LEDGERLENS_OFFLINE=0 LEDGERLENS_ORCHESTRATION_STUDIO=1 uv run python scripts/measure_orchestration.py
```

Exit code 0 when the comparison was measured and written, 1 when it could not be.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import get_chat_model, get_embeddings, get_settings  # noqa: E402  (the path comes first)
from ledgerlens.eval.dataset import CASES_PATH, load_cases  # noqa: E402
from ledgerlens.eval.routing_comparison import build_world  # noqa: E402
from ledgerlens.orchestration.comparison import (  # noqa: E402
    PAGE_RELATIVE,
    RESULT_RELATIVE,
    RUNS_RELATIVE,
    ComparisonRefused,
    build_report,
    ensure_preregistered,
    record_run,
    render_markdown,
    run_single_arm,
    run_studio_arm,
)
from ledgerlens.orchestration.studio import COMPARISON_RELATIVE, StudioRefused, studio_manifest  # noqa: E402

__all__ = ["DEFAULT_OUT", "main", "measure"]

# Where the numbers of the comparison go. The files are the evidence of the measurement, and they are read by
# the page of the orchestration.
DEFAULT_OUT = ROOT / "data" / "runtime" / "orchestration"

# The note that travels with the numbers. It says what was measured and what the numbers are not.
NOTE = (
    "Real run of the two arms over the same set of cases, over the same ledger, with the same model and with "
    "the deterministic judge of the repository. One run per case: the numbers are a trend and not a statistical "
    "significance. The answer of the studio is composed and not written by a model: it renders the evidence the "
    "verifier supported, and a case the studio did not resolve counts in the denominator like any other. The "
    "dollars of a model whose price nobody verified are unknown, and unknown is never zero."
)


def _commit() -> str:
    """The commit of the code that ran the comparison, for the report."""
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def measure(out_dir: Path, *, cases_path: Path = CASES_PATH) -> tuple[Path, Path]:
    """Runs the comparison and writes the result, the page and the record of the run."""
    settings = get_settings()
    if settings.offline:
        raise RuntimeError(
            "the comparison calls a real model, so it cannot run offline: set LEDGERLENS_OFFLINE=0 and a key"
        )
    model_name = settings.model
    if not model_name:
        raise RuntimeError("the deployment declares no model: set LEDGERLENS_MODEL")

    manifest_path = ROOT / COMPARISON_RELATIVE
    runs_path = out_dir / RUNS_RELATIVE.name
    ensure_preregistered(manifest_path, runs_path)
    records = studio_manifest(manifest_path)["records"]
    rule = next((record for record in records if record.get("section") == "rule"), {})
    uncertainty = next((record for record in records if record.get("section") == "uncertainty"), {})

    cases = load_cases(cases_path)
    embeddings = get_embeddings(settings)
    with tempfile.TemporaryDirectory(prefix="ledgerlens_orchestration_") as work:
        world = build_world(Path(work))
        single = run_single_arm(
            cases,
            world,
            model_name=model_name,
            index_root=settings.index_dir,
            embeddings=embeddings,
        )
        studio = run_studio_arm(
            cases,
            world,
            settings=settings,
            model=get_chat_model(model=model_name, temperature=0),
            model_name=model_name,
            index_root=settings.index_dir,
            embeddings=embeddings,
        )
        report = build_report(
            single,
            studio,
            cohort=cases,
            world=world,
            cases_path=cases_path,
            manifest_path=manifest_path,
            model_name=model_name,
            commit=_commit(),
            threshold_cases=int(rule.get("threshold_cases", 2)),
            rule_text=str(rule.get("decision", "")),
            uncertainty_text=str(uncertainty.get("statement", "")),
            note=NOTE,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / RESULT_RELATIVE.name
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_run(runs_path, manifest_path=manifest_path, commit=report["commit"], result_name=result_path.name)
    page_path = ROOT / PAGE_RELATIVE
    page_path.write_text(render_markdown(report), encoding="utf-8")
    return result_path, page_path


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the measurement and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Measures the studio against the single agent over the same cases.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the numbers of the comparison go to")
    args = parser.parse_args(argv)

    try:
        result_path, page_path = measure(Path(args.out))
    except (RuntimeError, ComparisonRefused, StudioRefused) as exc:
        print(f"measure_orchestration: {exc}", file=sys.stderr)
        return 1
    print(f"the result of the comparison is in {result_path}")
    print(f"the page of the comparison is in {page_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
