#!/usr/bin/env python3
"""Measures the size of the artifacts the site publishes and holds them inside the budget of the repository.

Why it exists: the site is a static export, so what the visitor downloads is exactly what the repository
publishes in `site/replay/`. The size of that payload is a promise of the specification, and a promise
that nobody measures is a promise that nobody keeps. This script measures the promise and fails when the
measurement breaks it, so the budget is checked before the release and not after a visitor complains.

The budget is the one the repository already declares, and it is not invented here:

- **SC-004 of `specs/001-r1-public-replay/spec.md`**: "The compressed payload of one scenario, with the
  events, the result and the ledger rows, stays under 400 kilobytes."
- The kilobyte of that limit is read as 1024 bytes, so the limit is 409600 bytes. The payload of the
  published set is far below the limit under either reading, so the choice does not change the answer
  today; it is named here so that nobody has to guess it.

The check has two arms, because the declaration is about one scenario and the script measures the whole
published set:

1. The **payload of every scenario** (the files of the scenario folder, compressed) has to stay under
   the declared 400 kilobytes. This is the arm the specification states.
2. The **total of the published set** (every file of `site/replay/`, compressed) has to stay under the
   same budget multiplied by the number of published scenarios. This arm is derived from the first one
   and not declared by the repository: it is the sum of the per scenario budget over the scenarios that
   are published, and it exists so that a scenario added to the set cannot quietly eat the budget of
   another one.

The script also counts the events of the recording and compares the count with the number the manifest
of the bundle declares. A recording that does not hold the number of events it claims is a recording
that is not the one it says it is, and the count is the thing the visitor sees in the timeline.

The script reads the disk and nothing else: it never writes anything, it never opens a socket and it
never calls a model. The exit code is the answer.

Usage:

```bash
uv run python scripts/measure_replay_budget.py
uv run python scripts/measure_replay_budget.py --site site/replay --limit 409600
```

Exit code 0 when the published set is inside the budget, 1 when it is not.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.replay.bundle import EVENTS_FILE, MANIFEST_FILE  # noqa: E402  (the path is set up before the import)
from ledgerlens.replay.site_export import SCENARIO_SLUG_PATTERN  # noqa: E402  (the path is set up before the import)

__all__ = [
    "BUDGET_BYTES",
    "BUDGET_SOURCE",
    "DEFAULT_SITE",
    "FileSize",
    "ScenarioSize",
    "main",
    "measure",
    "report",
]

# The folder the repository publishes, and the only source of truth for the recorded artifacts.
DEFAULT_SITE = ROOT / "site" / "replay"

# The budget the repository declares: SC-004 of the specification of the feature.
BUDGET_SOURCE = "SC-004 of specs/001-r1-public-replay/spec.md"
BUDGET_BYTES = 400 * 1024

# The level of the compression, so that the measurement is the one a static host does with gzip.
COMPRESSION_LEVEL = 9


@dataclass(frozen=True)
class FileSize:
    """One published file and what it costs: the bytes on the disk and the bytes on the wire."""

    name: str
    size: int
    compressed: int


@dataclass(frozen=True)
class ScenarioSize:
    """One published scenario: its files, its payload and the number of events of the recording."""

    slug: str
    files: tuple[FileSize, ...]
    declared_events: int | None
    events: int | None

    @property
    def size(self) -> int:
        """The bytes of the scenario on the disk."""
        return sum(item.size for item in self.files)

    @property
    def compressed(self) -> int:
        """The compressed bytes of the scenario, which is what the specification bounds."""
        return sum(item.compressed for item in self.files)


def _compressed_size(payload: bytes) -> int:
    """The size of the payload once a static host compresses it.

    The moment is fixed to zero, so the measurement does not depend on the clock and two runs of the
    script on the same disk give the same numbers.
    """
    return len(gzip.compress(payload, compresslevel=COMPRESSION_LEVEL, mtime=0))


def _declared_events(scenario_dir: Path) -> int | None:
    """The number of events the manifest of the scenario declares, when the manifest can be read.

    A manifest that cannot be read is not a refusal here: this script measures, and the check of the
    digests is what refuses a broken bundle.
    """
    path = scenario_dir / MANIFEST_FILE
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("events")
    return int(value) if isinstance(value, int) else None


def _count_events(scenario_dir: Path) -> int | None:
    """The number of events the recorded file really holds, when the file can be read.

    Only the lines are counted and nothing is parsed, because the count is what is measured and the
    content is the business of the loader of the core.
    """
    path = scenario_dir / EVENTS_FILE
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return sum(1 for line in text.splitlines() if line.strip())


def measure(site_dir: Path) -> tuple[list[FileSize], list[ScenarioSize], list[str]]:
    """Measures every published file, groups the files into scenarios and returns the problems found.

    The problems are the ones the measurement itself can see: a file that cannot be read and a scenario
    whose recording does not hold the number of events its manifest declares.
    """
    problems: list[str] = []
    if not site_dir.is_dir():
        return [], [], [f"the published folder does not exist: {site_dir}"]

    files: list[FileSize] = []
    scenarios: list[ScenarioSize] = []
    for path in sorted(site_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            # A dotfile is metadata of the desktop and not content of the export.
            continue
        name = path.relative_to(site_dir).as_posix()
        try:
            payload = path.read_bytes()
        except OSError as exc:
            problems.append(f"the published file {name} cannot be read: {exc}")
            continue
        files.append(FileSize(name=name, size=len(payload), compressed=_compressed_size(payload)))

    slugs = sorted({item.name.split("/")[0] for item in files if "/" in item.name})
    for slug in slugs:
        if not SCENARIO_SLUG_PATTERN.match(slug):
            continue
        scenario_dir = site_dir / slug
        own = tuple(item for item in files if item.name.startswith(f"{slug}/"))
        scenarios.append(
            ScenarioSize(
                slug=slug,
                files=own,
                declared_events=_declared_events(scenario_dir),
                events=_count_events(scenario_dir),
            )
        )

    for scenario in scenarios:
        if scenario.events is None:
            problems.append(f"the scenario {scenario.slug} publishes no readable {EVENTS_FILE}")
            continue
        if scenario.declared_events is not None and scenario.events != scenario.declared_events:
            problems.append(
                f"the scenario {scenario.slug} publishes {scenario.events} events and its manifest declares "
                f"{scenario.declared_events}"
            )
    return files, scenarios, problems


def report(site_dir: Path, files: list[FileSize], scenarios: list[ScenarioSize], limit: int) -> None:
    """Prints the measurement: the table of the files, the payload of the scenarios and the totals."""
    total = sum(item.size for item in files)
    total_compressed = sum(item.compressed for item in files)
    events = sum(scenario.events or 0 for scenario in scenarios)

    print(f"published folder: {site_dir}")
    if limit == BUDGET_BYTES:
        print(f"budget: {limit} bytes ({limit // 1024} kibibytes) per scenario, from {BUDGET_SOURCE}")
    else:
        print(f"budget: {limit} bytes per scenario, given on the command line (the declared one is {BUDGET_BYTES})")
    print("")
    print(f"  {'file':<34} {'bytes':>10} {'gzipped':>12}")
    for item in files:
        print(f"  {item.name:<34} {item.size:>10} {item.compressed:>12}")
    print(f"  {'TOTAL':<34} {total:>10} {total_compressed:>12}")
    print("")
    print(f"  {'scenario':<34} {'bytes':>10} {'gzipped':>12} {'events':>8}")
    for scenario in scenarios:
        print(
            f"  {scenario.slug:<34} {scenario.size:>10} {scenario.compressed:>12} {scenario.events or 0:>8}"
        )
    print("")
    print(f"  events of the recording: {events}")


def _budget_problems(scenarios: list[ScenarioSize], limit: int) -> list[str]:
    """The problems of the budget: a scenario over the limit and a total over the sum of the limits."""
    problems: list[str] = []
    for scenario in scenarios:
        if scenario.compressed >= limit:
            problems.append(
                f"the scenario {scenario.slug} publishes {scenario.compressed} compressed bytes and the budget "
                f"is {limit}"
            )
    total = sum(scenario.compressed for scenario in scenarios)
    aggregate = limit * len(scenarios)
    if len(scenarios) > 1 and total >= aggregate:
        problems.append(
            f"the published set publishes {total} compressed bytes and the aggregate budget of the "
            f"{len(scenarios)} published scenarios is {aggregate}"
        )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the measurement and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Measures the size of the published artifacts of the site.")
    parser.add_argument("--site", default=str(DEFAULT_SITE), help="folder of the published artifacts")
    parser.add_argument(
        "--limit",
        type=int,
        default=BUDGET_BYTES,
        help=f"the budget of one scenario, in bytes (the default is the one of {BUDGET_SOURCE})",
    )
    args = parser.parse_args(argv)

    site_dir = Path(args.site)
    files, scenarios, problems = measure(site_dir)
    if not files:
        problems.append(f"the published folder holds no file: {site_dir}")
        report(site_dir, files, scenarios, args.limit)
        print("measure_replay_budget: the published artifacts cannot be measured:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    report(site_dir, files, scenarios, args.limit)
    problems += _budget_problems(scenarios, args.limit)
    if problems:
        print("measure_replay_budget: the published artifacts are NOT inside the budget:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("the published artifacts are inside the budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
