#!/usr/bin/env python3
"""The per case report of the evaluation of the agent, from the report of the evaluation.

Why it exists: the aggregate of the evaluation hides the cases that failed, and the per case report names the
correctness of the agent case by case. The correctness of the agent and the accuracy of the verifier are two
different measurements over two different sets, and the report publishes the correctness of the agent and
nothing else. The report is written under `data/eval/reports/`, and it says which set it was measured over
and which role that set plays.

The script runs offline, with no key and with no network: it reads the report of the evaluation that is on
the disk and writes the per case report. It calls no model at all.

Usage:

```bash
uv run python scripts/report_agent_cases.py
```

Exit code 0 when the report was written, 1 when the report of the evaluation is not on the disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.case_reports import render_agent_report  # noqa: E402
from ledgerlens.eval.manifest import load_manifests  # noqa: E402

REPORTS_DIR = ROOT / "data" / "eval" / "reports"
REPORT_ONLINE = ROOT / "data" / "eval" / "report_online.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Writes the per case report of the agent.")
    parser.parse_args(argv)
    if not REPORT_ONLINE.is_file():
        print(f"report_agent_cases: the report of the evaluation is not on the disk: {REPORT_ONLINE}")
        return 1

    report_online = json.loads(REPORT_ONLINE.read_text(encoding="utf-8"))
    manifests = {manifest.dataset_id: manifest for manifest in load_manifests()}
    role = manifests["eval_cases"].split_role if "eval_cases" in manifests else "tuning"
    per_case = [case for case in report_online["per_case"] if case["variant"] == "C"]
    report = render_agent_report(per_case, set_name="eval_cases", role=role)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORTS_DIR / "agent-cases-eval_cases.md"
    target.write_text(report, encoding="utf-8")
    print(f"the per case report of the agent was written: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
