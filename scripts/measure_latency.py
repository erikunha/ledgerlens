#!/usr/bin/env python3
"""The measurement of the latency of a turn: the p50 and the p95 over the cases of the evaluation set.

Why it exists: the repository publishes the latency of a turn, and a latency without the hardware, the
denominator and the role of the set is a number a reader cannot check. This script runs the cases of
`data/eval/eval_cases.jsonl` through the full agent offline, measures the latency of each case end to end and
per stage, and writes `data/eval/report_latency.md` with the p50 and the p95, the hardware of the machine,
the version of Python, the model and its temperature, the digest of the set and the role of the set in the
manifest.

The script runs offline, with no key and with no network: the model of the measurement is the scripted model
of the offline evaluation, and the latency it measures is the latency of the plumbing of the turn on this
machine. A latency over a tuning set is a tendency and not a generalization, and the report says so.

Usage:

```bash
uv run python scripts/measure_latency.py
```

Exit code 0 when the report was written.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.dataset import build_cases  # noqa: E402
from ledgerlens.eval.latency import METHOD, LatencyCollector, percentile  # noqa: E402
from ledgerlens.eval.manifest import load_manifests  # noqa: E402
from ledgerlens.eval.run import _no_tracing, build_offline_world, evaluate_variant  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402

REPORT = ROOT / "data" / "eval" / "report_latency.md"
DATASET = ROOT / "data" / "eval" / "eval_cases.jsonl"


def _hardware() -> dict[str, str]:
    """The hardware of the machine of the measurement: the processor, the memory and the system."""
    memory = "unknown"
    try:
        memory = f"{(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) // (1024**3)} GiB"
    except (ValueError, OSError, AttributeError):
        memory = "unknown"
    return {
        "processor": platform.processor() or "unknown",
        "cores": str(os.cpu_count() or "unknown"),
        "memory": memory,
        "system": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measures the latency of a turn over the evaluation set.")
    parser.parse_args(argv)

    work = ROOT / "data" / "runtime" / "measure-latency"
    work.mkdir(parents=True, exist_ok=True)
    ledger = build_ledger(SimConfig(source="sample"), work / "ledger.db")
    ledger.conn.close()
    cases = build_cases(work / "ledger.db")
    manifests = {manifest.dataset_id: manifest for manifest in load_manifests()}
    role = manifests["eval_cases"].split_role
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()

    collector = LatencyCollector()
    with _no_tracing():
        world = build_offline_world(work / "world")
        rows = evaluate_variant("C", cases, world, [])
    for row in rows:
        latency = row.get("latency") or {}
        if latency.get("end_to_end_ms") is not None:
            collector.end_to_end.append(float(latency["end_to_end_ms"]))
            for stage, ms in latency.get("per_stage_ms", {}).items():
                collector.per_stage.setdefault(stage, []).append(float(ms))

    hardware = _hardware()
    lines = [
        "# The latency of a turn over the evaluation set",
        "",
        f"The set: `eval_cases` (`data/eval/eval_cases.jsonl`, digest `{digest}`), role `{role}` in the "
        "manifest of the datasets. A latency over a tuning set is a tendency and not a generalization.",
        "",
        "The model: the scripted model of the offline evaluation, temperature 0. The latency measured is the "
        "latency of the plumbing of the turn on this machine.",
        "",
        f"The hardware: {hardware['processor']}, {hardware['cores']} cores, {hardware['memory']}, "
        f"{hardware['system']}, Python {hardware['python']}.",
        "",
        f"The method of the percentile: {METHOD}. The denominator: {collector.denominator} cases that "
        "produced a measurement.",
        "",
        "| stage | p50 (ms) | p95 (ms) |",
        "|---|---|---|",
        f"| end to end | {percentile(collector.end_to_end, 50)} | {percentile(collector.end_to_end, 95)} |",
    ]
    for stage, values in collector.per_stage.items():
        lines.append(f"| {stage} | {percentile(values, 50)} | {percentile(values, 95)} |")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"the report of the latency was written: {REPORT.relative_to(ROOT)}")
    print(f"the denominator: {collector.denominator} cases, the p95 of the end to end: "
          f"{percentile(collector.end_to_end, 95)} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
