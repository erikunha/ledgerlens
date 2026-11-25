#!/usr/bin/env python3
"""Publishes the experiment of the orchestration comparison: the single agent against the studio, over the same
cohort of cases.

Why it exists: the measurement of the orchestration studio over the corrected corpus happened
(`data/runtime/orchestration/result.json`), and the paired arena publishes the measurements of the repository as
experiments. The script reads the published result of the measurement and the cohort of the cases, builds the
manifest and the runs of the experiment, and publishes them through the same door as every experiment
(`scripts/run_paired_experiment.py`), so the refusal to overwrite is the same everywhere.

The script computes nothing about the cases and it never calls a model: it reads the results of the runs that
already happened, under ADR-037.

Usage:

```bash
uv run python scripts/publish_orchestration_experiment.py
```

Exit code 0 when the experiment was published, 1 when it could not be.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.experiment import ExperimentManifest, Variant  # noqa: E402
from ledgerlens.eval.paired import DEFAULT_METHOD  # noqa: E402
from scripts.run_paired_experiment import publish  # noqa: E402

RESULT = ROOT / "data" / "runtime" / "orchestration" / "result.json"
CASES = ROOT / "data" / "eval" / "eval_cases.jsonl"

# The citation of an answer, as the answers of the runs write it: `[sql:1]`, `[calc:1]`, `[fx:...]`.
CITATION = re.compile(r"\[([^\]]+)\]")


def _citations_of(answer: str) -> tuple[str, ...]:
    """The citations of an answer, in the order the answer wrote them."""
    citations: list[str] = []
    for match in CITATION.finditer(answer):
        for part in match.group(1).split(","):
            named = part.strip()
            if named:
                citations.append(named)
    return tuple(citations)


def runs_of(result: dict, cases: dict) -> list[dict[str, object]]:
    """The runs of the experiment, built from the published result of the measurement and the cohort of the
    cases.

    Why the function is apart from the command line: the runs of the experiment are the input of the
    comparison, and a test reads them to check that the experiment says what the measurement said. The
    function reads the results of the runs that already happened and never calls a model (ADR-037).
    """
    cohort = result["cohort"]["digest"]
    runs: list[dict[str, object]] = []
    for arm in ("single_agent", "orchestration_studio"):
        for case in result["arms"][arm]["cases"]:
            case_id = case["case"]
            runs.append(
                {
                    "case_id": case_id,
                    "variant": arm,
                    "cohort_sha256": cohort,
                    "ran": True,
                    "score": case["correctness"],
                    "failure": None,
                    "expected_facts": list(cases.get(case_id, {}).get("expected_facts", [])),
                    "evidence_cited": list(_citations_of(case.get("answer", ""))),
                    # The intent of the triage of the run is not recorded in the published result of the
                    # measurement, and the experiment says so instead of inventing it.
                    "intent": "",
                    "complexity": "",
                }
            )
    return runs


def main() -> int:
    """Runs the command and returns the exit code of the answer."""
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    cases = {
        json.loads(line)["id"]: json.loads(line)
        for line in CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    cohort = result["cohort"]["digest"]
    runs = runs_of(result, cases)

    manifest = ExperimentManifest(
        cohort_path="data/eval/eval_cases.jsonl",
        cohort_sha256=cohort,
        cohort_cases=int(result["cohort"]["cases"]),
        variants=(
            Variant(name="single_agent", description="the path that the repository ships", model="gpt-4.1-mini"),
            Variant(
                name="orchestration_studio",
                description="the experimental variant of the studio",
                model="gpt-4.1-mini",
            ),
        ),
        judge="the deterministic judge of the repository, with the stub of the NLI",
        seed=0,
        commit=str(result["commit"]),
        command="uv run python scripts/run_paired_experiment.py --manifest <manifest> --runs <runs>",
        registered_on="2026-11-25",
        goal=0.80,
        method=DEFAULT_METHOD,
    )

    with tempfile.TemporaryDirectory() as work:
        manifest_path = Path(work) / "manifest.json"
        runs_path = Path(work) / "runs.json"
        manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False) + "\n", encoding="utf-8")
        runs_path.write_text(
            json.dumps({"cohort_sha256": cohort, "runs": runs}, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        try:
            out_dir = publish(manifest_path, runs_path, "tuning")
        except Exception as exc:  # noqa: BLE001 - the refusal of the publication is the answer of the command
            print(f"publish_orchestration_experiment: {exc}", file=sys.stderr)
            return 1
    print(f"the experiment was published: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
