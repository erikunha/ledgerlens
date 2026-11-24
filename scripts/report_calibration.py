#!/usr/bin/env python3
"""The report of the recomputation of the calibration over the sets of the role `tuning`.

Why it exists: the thresholds of `ledgerlens/verify/thresholds.json` were chosen over a sweep, and the
recomputation of the calibration is the proof that the thresholds still follow the rule of ADR-007 over the
manifest of the day. The report names the manifest it was measured over, the model, the table of the sweep and
the thresholds the rule chooses, and it says whether the committed thresholds are the ones the rule chooses.

The script is slow and it is not part of the gate: it needs the real NLI model, and the gate runs offline and
without a key. It writes the report under `data/eval/reports/`, with the digest of the manifest in the name,
so the report is found by the manifest it was measured over.

Usage:

```bash
uv run python scripts/report_calibration.py
```

Exit code 0 when the report was written, 1 when the run refused, 2 when the model could not be measured with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import offline  # noqa: E402  (the path is set up before the import)
from ledgerlens.eval.manifest import load_manifests  # noqa: E402
from ledgerlens.verify.nli import get_nli  # noqa: E402
from ledgerlens.verify.sweep import nli_cases, pick_thresholds, score_cases, sweep_rows  # noqa: E402

REPORTS_DIR = ROOT / "data" / "eval" / "reports"
THRESHOLDS_PATH = ROOT / "ledgerlens" / "verify" / "thresholds.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Writes the report of the recomputation of the calibration.")
    parser.parse_args(argv)
    if offline():
        print(
            "report_calibration: the recomputation needs the real NLI model, "
            "and offline mode replaces it with the stand-in."
        )
        return 1

    manifests = load_manifests()
    manifest_path = ROOT / "data" / "eval" / "datasets.json"
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    cases = nli_cases(ROOT, manifests)
    nli = get_nli(offline=False, require_real=True)
    scores = score_cases(cases, nli)
    rows = sweep_rows(cases, scores)
    scored = [(case.label, score) for case, score in zip(cases, scores, strict=True)]
    entailment, contradiction = pick_thresholds(scored)
    committed = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    matches = (
        float(committed["entailment_min"]) == entailment and float(committed["contradiction_min"]) == contradiction
    )

    lines = [
        "# The recomputation of the calibration over the sets of the role tuning",
        "",
        f"The manifest of the datasets: `data/eval/datasets.json`, digest `{manifest_digest}`.",
        f"The model: {getattr(nli, 'model_id', 'the real NLI model')}.",
        f"The cases of the sweep: {len(cases)} over the datasets of the role tuning.",
        "",
        "| entailment_min | contradiction_min | accuracy | false supported | false contradicted |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.entailment_min} | {row.contradiction_min} | {row.accuracy} | "
            f"{row.false_supported} | {row.false_contradicted} |"
        )
    lines += [
        "",
        f"The thresholds the rule chooses: entailment_min {entailment} and contradiction_min {contradiction}.",
        (
            "The committed thresholds of `ledgerlens/verify/thresholds.json` are the ones the rule chooses."
            if matches
            else "The committed thresholds of `ledgerlens/verify/thresholds.json` are NOT the ones the rule chooses."
        ),
        "",
    ]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORTS_DIR / f"calibration-{manifest_digest[:12]}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"the report of the calibration was written: {report.relative_to(ROOT)}")
    print(f"the thresholds the rule chooses: entailment_min {entailment} and contradiction_min {contradiction}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
