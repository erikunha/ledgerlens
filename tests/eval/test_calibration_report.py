"""The report of the recomputation of the calibration: the manifest, the model, the table and the thresholds.

What they guarantee, and why: the report of the recomputation names the manifest it was measured over, the
model, the thresholds the rule chooses, and it says whether the committed thresholds are the ones the rule
chooses, because a threshold without the sweep that chose it is a number without a measurement.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "data" / "eval" / "reports"


def _report() -> str:
    reports = sorted(REPORTS_DIR.glob("calibration-*.md"))
    assert reports, "the report of the recomputation of the calibration is not on the disk"
    return reports[-1].read_text(encoding="utf-8")


def test_the_report_names_the_manifest_it_was_measured_over() -> None:
    """The digest of the manifest is in the report, and it is the digest of the manifest on the disk."""
    manifest_digest = hashlib.sha256((ROOT / "data" / "eval" / "datasets.json").read_bytes()).hexdigest()
    report = _report()

    assert manifest_digest in report
    assert "the model" in report.lower()


def test_the_report_says_the_committed_thresholds_are_the_ones_the_rule_chooses() -> None:
    """The recomputation confirms the calibration, or it says out loud that it does not."""
    report = _report()
    committed = json.loads((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"))

    chosen = re.search(r"entailment_min (\d+\.\d+) and contradiction_min (\d+\.\d+)", report)
    assert chosen is not None
    assert float(chosen.group(1)) == float(committed["entailment_min"])
    assert float(chosen.group(2)) == float(committed["contradiction_min"])
    assert "are the ones the rule chooses" in report
