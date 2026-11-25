#!/usr/bin/env python3
"""The per case report of the verifier over the verification sets, with the real NLI model.

Why it exists: the aggregate of the calibration hides the cases that failed, and the per case report names
the claim, the evidence, the expected verdict and the verdict that came out for every case, with the false
supported, the false contradicted and the case without a verdict. The report is written under
`data/eval/reports/`, and it says which set it was measured over and which role that set plays.

The script is slow and it is not part of the gate: it needs the real NLI model, and the gate runs offline and
without a key. The builder of the report is `ledgerlens/eval/case_reports.py`, and the gate tests the builder
offline.

Usage:

```bash
uv run python scripts/report_verifier_cases.py
```

Exit code 0 when the report was written, 1 when the run refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import offline  # noqa: E402  (the path is set up before the import)
from ledgerlens.eval.case_reports import render_verifier_report, verifier_cases  # noqa: E402
from ledgerlens.eval.manifest import load_manifests  # noqa: E402
from ledgerlens.verify.nli import get_nli, verification_status  # noqa: E402

REPORTS_DIR = ROOT / "data" / "eval" / "reports"
THRESHOLDS_PATH = ROOT / "ledgerlens" / "verify" / "thresholds.json"
SETS = ("verification_set", "verification_live")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Writes the per case report of the verifier.")
    parser.parse_args(argv)
    if offline():
        print(
            "report_verifier_cases: the report needs the real NLI model, "
            "and offline mode replaces it with the stand-in."
        )
        return 1

    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    manifests = {manifest.dataset_id: manifest for manifest in load_manifests()}
    nli = get_nli(offline=False, require_real=True)
    status = verification_status(nli)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for set_name in SETS:
        path = ROOT / "data" / "eval" / f"{set_name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        role = manifests[set_name].split_role if set_name in manifests else "tuning"
        cases = verifier_cases(rows, nli, thresholds)
        report = render_verifier_report(cases, set_name=set_name, role=role, status=status)
        target = REPORTS_DIR / f"verifier-cases-{set_name}.md"
        target.write_text(report, encoding="utf-8")
        sidecar = REPORTS_DIR / f"verifier-cases-{set_name}.json"
        sidecar.write_text(
            json.dumps(
                {
                    "set_name": set_name,
                    "role": role,
                    "status": status,
                    "cases": [
                        {
                            "case_id": case.case_id,
                            "claim": case.claim,
                            "evidence": case.evidence,
                            "expected": case.expected,
                            "got": case.got,
                            "outcome": case.outcome,
                        }
                        for case in cases
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"the per case report of the verifier was written: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
