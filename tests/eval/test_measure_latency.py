"""The report of the latency: the denominator, the hardware, the set and the role of the set.

What they guarantee, and why: the report of the latency names the denominator of the cases that produced a
measurement, the hardware of the machine, the set it was measured over and the role of that set in the
manifest, because a latency without the hardware and the denominator is a number a reader cannot check.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data" / "eval" / "report_latency.md"


def test_the_report_names_the_denominator_and_the_hardware() -> None:
    """The denominator of the cases measured and the hardware of the machine are in the report."""
    report = REPORT.read_text(encoding="utf-8")

    assert "The denominator:" in report
    assert "The hardware:" in report
    assert "Python" in report
    assert "| end to end |" in report


def test_the_report_names_the_set_the_digest_and_the_role_of_the_set() -> None:
    """The set of the measurement, the digest of the file and the role of the set in the manifest."""
    report = REPORT.read_text(encoding="utf-8")
    digest = hashlib.sha256((ROOT / "data" / "eval" / "eval_cases.jsonl").read_bytes()).hexdigest()
    manifests = json.loads((ROOT / "data" / "eval" / "datasets.json").read_text(encoding="utf-8"))
    role = next(entry["split_role"] for entry in manifests["datasets"] if entry["dataset_id"] == "eval_cases")

    assert "eval_cases" in report
    assert digest in report
    assert f"role `{role}`" in report
    assert "a tendency and not a generalization" in report
