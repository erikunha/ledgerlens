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

The script has two arms, and the difference between them is the difference between a gate and a measurement:

1. **The default arm is the payload.** It reads the disk and nothing else: it never writes anything, it never opens
   a socket, it never starts a browser and it never calls a model. This is the arm that `scripts/gate.sh` calls and
   the arm that the first job of the continuous integration runs, and that job installs no Node and no browser. A
   gate that fails because a tool is missing is not a gate, so the arm of the gate never needs a tool that the
   machine of the gate does not have.
2. **The arm of the paint is opt in.** It measures the paint of the replay page with a browser, it prints the numbers
   with the conditions under which they were taken, and it refuses with a readable reason when the tool it needs is
   not on the machine. It is asked for with `--paint`, and it never runs by accident.

The paint of the arm is the paint of the promise of the specification:

- **SC-003 of `specs/001-r1-public-replay/spec.md`**: "The replay page reaches a largest contentful paint under 2.5
  seconds and a first contentful paint under 1.8 seconds on a throttled mid-range connection, measured on the
  deployed static site."

A number without the conditions under which it was taken is not a measurement, so the arm prints the throttling it
applied, the export it measured and the route it opened, and it compares the numbers with the promise of SC-003 and
with the generous bound that the suite of the frontend asserts. The arm fails on the bound and not on the promise: the
promise is a number of a deployed site on a given connection, and the wall clock of a shared machine is not that
clock. ADR-051 says which layer is which.

Usage:

```bash
uv run python scripts/measure_replay_budget.py
uv run python scripts/measure_replay_budget.py --site site/replay --limit 409600
uv run python scripts/measure_replay_budget.py --paint
```

Exit code 0 when the published set is inside the budget, 1 when it is not. With `--paint`, the exit code is 1 when
the paint is outside the bound of the suite or when the measurement could not be taken.
"""

from __future__ import annotations

import argparse
import functools
import gzip
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
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
    "DEFAULT_EXPORT",
    "DEFAULT_SITE",
    "FileSize",
    "PAINT_CPU_THROTTLING_RATE",
    "PAINT_DOWNLOAD_BYTES_PER_SECOND",
    "PAINT_FCP_BOUND_MS",
    "PAINT_FCP_PROMISE_MS",
    "PAINT_LATENCY_MS",
    "PAINT_LCP_BOUND_MS",
    "PAINT_LCP_PROMISE_MS",
    "PAINT_ROUTE",
    "PAINT_UPLOAD_BYTES_PER_SECOND",
    "PaintMeasurement",
    "ScenarioSize",
    "main",
    "measure",
    "measure_the_paint",
    "report",
    "report_the_paint",
]

# The folder the repository publishes, and the only source of truth for the recorded artifacts.
DEFAULT_SITE = ROOT / "site" / "replay"

# The budget the repository declares: SC-004 of the specification of the feature.
BUDGET_SOURCE = "SC-004 of specs/001-r1-public-replay/spec.md"
BUDGET_BYTES = 400 * 1024

# The level of the compression, so that the measurement is the one a static host does with gzip.
COMPRESSION_LEVEL = 9

# The folder of the static export of the frontend: the files a visitor of the site receives.
DEFAULT_EXPORT = ROOT / "apps" / "web" / "out"

# The route of the recording of the scenario `S01` inside the export.
#
# Why this route and not another: the recording of `S01` is the heaviest page of the site, and the paint of the
# heaviest page is the one the promise of the specification is about.
PAINT_ROUTE = "/replay/scenario/S01"

# The throttling of the measurement of the paint.
#
# Why these numbers: a connection of four megabits per second with one hundred milliseconds of latency is a phone on
# a shared mobile network, which is the middle of the range and the machine most of the visitors are on, and a
# processor four times slower is the same idea applied to the machine. The suite of the frontend applies the same
# numbers, so the two measurements can be compared with each other.
PAINT_CPU_THROTTLING_RATE = 4
PAINT_DOWNLOAD_BYTES_PER_SECOND = 500_000
PAINT_UPLOAD_BYTES_PER_SECOND = 125_000
PAINT_LATENCY_MS = 100

# The promise of SC-003, the number that the deployment of the site has to keep.
PAINT_LCP_PROMISE_MS = 2500
PAINT_FCP_PROMISE_MS = 1800

# The bound that the suite of the frontend asserts, the one that catches a catastrophic regression.
#
# Why the bound is far above the promise: a machine that is shared, a container and a processor four times slower make
# the wall clock noisy, and a bound that goes red for the noise of the machine is not a bound.
PAINT_LCP_BOUND_MS = 8000
PAINT_FCP_BOUND_MS = 5000

# The seconds the measurement of the paint may take before it is given up on.
PAINT_TIMEOUT_SECONDS = 300


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


class PaintRefusal(RuntimeError):
    """A refusal of the measurement of the paint, with the reason a reader can act on."""


@dataclass(frozen=True)
class PaintMeasurement:
    """The paint of the replay page, with the conditions under which it was taken.

    Why the conditions live in the measurement and not in the report: a number without the conditions under which it
    was taken is not a measurement, and the conditions are the same for every reader of the number.
    """

    url: str
    export: str
    fcp: float | None
    lcp: float | None


class _ExportHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the static export the way a host of static files serves it.

    Why the class exists: the export writes one file per page and the routes of the site carry no extension, so the
    server has to answer the route of a page with the file of the page, the way the server of the end to end suite
    answers it.
    """

    def translate_path(self, path: str) -> str:
        """Gives back the file of the route, adding the extension of the page when the route has none."""
        resolved = super().translate_path(path)
        if not resolved.endswith((".html", ".htm")) and not os.path.exists(resolved):
            with_extension = f"{resolved}.html"
            if os.path.exists(with_extension):
                return with_extension
        return resolved

    def log_message(self, format: str, *args: object) -> None:
        """Keeps the log of the server out of the output of the measurement."""


# The program of the browser that measures the paint.
#
# Why the program lives here and not in the repository: the arm of the paint is opt in and the gate of the Python
# side must never need a browser, so the program is a constant of the script and not a file of the tree that the
# build of the frontend has to know about.
#
# Why the program is the same measurement as the one of the suite of the frontend: the two numbers have to be
# comparable, and they are comparable when the two apply the same throttling and read the same entries of the
# timeline of the performance of the browser.
_PAINT_SCRIPT = r"""
import { chromium } from "playwright";

const [url, cpu, download, upload, latency] = process.argv.slice(1);

const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const client = await context.newCDPSession(page);

  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: false,
    downloadThroughput: Number(download),
    uploadThroughput: Number(upload),
    latency: Number(latency),
  });
  await client.send("Emulation.setCPUThrottlingRate", { rate: Number(cpu) });

  // The observer is installed before the navigation, because the entries of the paint that were already
  // recorded are the ones that an observer that comes later misses.
  await page.addInitScript(() => {
    const store = { lcp: 0 };
    window.__ledgerlensPaint = store;
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          store.lcp = entry.startTime;
        }
      }).observe({ type: "largest-contentful-paint", buffered: true });
    } catch {
      // a browser that does not know the entry reports no number, and the arm says so
    }
  });

  await page.goto(url, { waitUntil: "load" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => undefined);

  const readThePaint = () =>
    page.evaluate(() => {
      const first = performance.getEntriesByName("first-contentful-paint")[0];
      const store = window.__ledgerlensPaint;
      return {
        fcp: first === undefined ? null : first.startTime,
        lcp: store === undefined || store.lcp <= 0 ? null : store.lcp,
      };
    });

  // The largest contentful paint keeps changing while the page loads, so the measurement waits for it to settle
  // instead of reading the number of a moment.
  let paint = { fcp: null, lcp: null };
  let previous = null;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    paint = await readThePaint();
    if (paint.lcp !== null && paint.lcp === previous) {
      break;
    }
    previous = paint.lcp;
    await page.waitForTimeout(250);
  }

  console.log(JSON.stringify(paint));
} finally {
  await browser.close();
}
"""


def _serve_the_export(export_dir: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    """Serves the export on a port of the loopback and gives back the server and the origin it answers on.

    Why the loopback: the measurement is of a static site, and the site of a visitor is served by a host of static
    files. Nothing of the measurement leaves the machine.
    """
    handler = functools.partial(_ExportHandler, directory=str(export_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def _run_the_browser(node: str, url: str) -> dict[str, float | None]:
    """Runs the browser and gives back the numbers of the paint, or refuses with the reason of the browser."""
    arguments = [
        node,
        "--input-type=module",
        "-e",
        _PAINT_SCRIPT,
        url,
        str(PAINT_CPU_THROTTLING_RATE),
        str(PAINT_DOWNLOAD_BYTES_PER_SECOND),
        str(PAINT_UPLOAD_BYTES_PER_SECOND),
        str(PAINT_LATENCY_MS),
    ]
    try:
        completed = subprocess.run(
            arguments,
            cwd=str(ROOT / "apps" / "web"),
            capture_output=True,
            text=True,
            timeout=PAINT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise PaintRefusal(
            f"the browser did not answer in {PAINT_TIMEOUT_SECONDS} seconds, and the measurement was given up on."
        ) from None

    if completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip() or "the browser gave no reason"
        raise PaintRefusal(f"the browser could not measure the paint of the page. Its reason is:\n{reason}")

    for line in reversed(completed.stdout.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            return dict(json.loads(stripped))
        except json.JSONDecodeError:
            continue

    raise PaintRefusal("the browser reported no measurement of the paint.")


def measure_the_paint(export_dir: Path = DEFAULT_EXPORT) -> PaintMeasurement:
    """Measures the paint of the replay page with a browser and gives back the numbers and the conditions.

    Why the refusal is a sentence and not a traceback: a missing tool is a fact of the machine and not a fault of
    the code, and the reader of the refusal has to know what to install and where.
    """
    page_file = export_dir / "replay" / "scenario" / "S01.html"
    if not page_file.is_file():
        raise PaintRefusal(
            f"the static export of the site is not on the disk: {page_file} does not exist. "
            "Build it with `cd apps/web && npm run build` and run the measurement again."
        )

    node = shutil.which("node")
    if node is None:
        raise PaintRefusal(
            "Node is not installed on this machine, and the measurement of the paint needs it. "
            "The arm of the payload does not need it."
        )

    if not (ROOT / "apps" / "web" / "node_modules" / "playwright").is_dir():
        raise PaintRefusal(
            "the frontend of the repository is not installed, so the browser of the measurement is not there. "
            "Install it with `cd apps/web && npm ci` and run the measurement again."
        )

    server, origin = _serve_the_export(export_dir)
    try:
        numbers = _run_the_browser(node, f"{origin}{PAINT_ROUTE}")
    finally:
        server.shutdown()
        server.server_close()

    return PaintMeasurement(
        url=f"{origin}{PAINT_ROUTE}",
        export=str(export_dir),
        fcp=numbers.get("fcp"),
        lcp=numbers.get("lcp"),
    )


def report_the_paint(measurement: PaintMeasurement) -> None:
    """Prints the paint of the page and the conditions under which it was measured."""
    print(f"paint of the replay page: {measurement.url}")
    print(f"export measured: {measurement.export}")
    print(
        "throttling: the processor "
        f"{PAINT_CPU_THROTTLING_RATE} times slower, {PAINT_DOWNLOAD_BYTES_PER_SECOND} bytes per second down, "
        f"{PAINT_UPLOAD_BYTES_PER_SECOND} bytes per second up, {PAINT_LATENCY_MS} ms of latency"
    )
    print("")
    print(f"  first contentful paint: {measurement.fcp} ms")
    print(f"  largest contentful paint: {measurement.lcp} ms")
    print("")
    print(
        "  promise of SC-003: the first contentful paint under "
        f"{PAINT_FCP_PROMISE_MS} ms and the largest contentful paint under {PAINT_LCP_PROMISE_MS} ms"
    )
    print(
        "  bound of the suite: the first contentful paint under "
        f"{PAINT_FCP_BOUND_MS} ms and the largest contentful paint under {PAINT_LCP_BOUND_MS} ms"
    )


def _paint_problems(measurement: PaintMeasurement) -> list[str]:
    """The problems of the paint: a number that is missing and a number that is outside the bound of the suite.

    Why the promise of SC-003 is not a problem here: the promise is a number of a deployed site on a given connection,
    and the wall clock of a shared machine is not that clock. The arm says whether the measurement is inside the
    promise, and it fails on the bound of the suite.
    """
    problems: list[str] = []
    if measurement.fcp is None:
        problems.append("the browser reported no first contentful paint")
    elif measurement.fcp > PAINT_FCP_BOUND_MS:
        problems.append(
            f"the first contentful paint is {measurement.fcp} ms and the bound of the suite is {PAINT_FCP_BOUND_MS} ms"
        )
    if measurement.lcp is None:
        problems.append("the browser reported no largest contentful paint")
    elif measurement.lcp > PAINT_LCP_BOUND_MS:
        problems.append(
            f"the largest contentful paint is {measurement.lcp} ms and the bound of the suite "
            f"is {PAINT_LCP_BOUND_MS} ms"
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
    parser.add_argument(
        "--paint",
        action="store_true",
        help="measures the paint of the replay page with a browser (the arm of the gate never does it)",
    )
    parser.add_argument(
        "--export",
        default=str(DEFAULT_EXPORT),
        help="folder of the static export of the frontend, the files the measurement of the paint serves",
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

    paint_problems: list[str] = []
    if args.paint:
        try:
            paint = measure_the_paint(Path(args.export))
        except PaintRefusal as refusal:
            print("measure_replay_budget: the paint could not be measured:", file=sys.stderr)
            print(f"  {refusal}", file=sys.stderr)
            return 1

        report_the_paint(paint)
        paint_problems = _paint_problems(paint)
        if paint.fcp is not None and paint.lcp is not None:
            inside = paint.fcp <= PAINT_FCP_PROMISE_MS and paint.lcp <= PAINT_LCP_PROMISE_MS
            print(
                f"  the measurement is {'inside' if inside else 'outside'} the promise of SC-003, "
                "and the promise is a number of the deployed site on the connection named above"
            )

    if problems or paint_problems:
        if paint_problems and not problems:
            print("measure_replay_budget: the paint is NOT inside the bound of the suite:", file=sys.stderr)
        else:
            print("measure_replay_budget: the published artifacts are NOT inside the budget:", file=sys.stderr)
        for problem in [*problems, *paint_problems]:
            print(f"  {problem}", file=sys.stderr)
        return 1
    if args.paint:
        print("the published artifacts are inside the budget and the paint is inside the bound of the suite")
        return 0
    print("the published artifacts are inside the budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
