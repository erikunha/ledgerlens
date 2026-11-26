#!/usr/bin/env python3
"""Measure compressed replay artifacts and verify their declared event counts offline.

Pass --paint to measure a running Streamlit replay in Chromium using Python Playwright.
Start the app with uvicorn app.server:portal --host 127.0.0.1 --port 8501. Use --app-url for another origin.
The optional measurement applies CPU and network throttling and reports FCP and LCP.
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
    "DEFAULT_APP_URL",
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

DEFAULT_APP_URL = "http://127.0.0.1:8501"
PAINT_ROUTE = "/?view=Replay"

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
    fcp: float | None
    lcp: float | None


def measure_the_paint(app_url: str = DEFAULT_APP_URL) -> PaintMeasurement:
    """Sample paint after Streamlit renders the recorded investigation and its trace selector."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as exc:
        raise PaintRefusal(
            "Install Python Playwright and Chromium (python -m playwright install chromium) to measure paint."
        ) from exc

    url = app_url.rstrip("/") + PAINT_ROUTE
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(PAINT_TIMEOUT_SECONDS * 1000)
            client = page.context.new_cdp_session(page)
            client.send("Network.enable")
            client.send("Network.emulateNetworkConditions", {
                "offline": False,
                "downloadThroughput": PAINT_DOWNLOAD_BYTES_PER_SECOND,
                "uploadThroughput": PAINT_UPLOAD_BYTES_PER_SECOND,
                "latency": PAINT_LATENCY_MS,
            })
            client.send("Emulation.setCPUThrottlingRate", {"rate": PAINT_CPU_THROTTLING_RATE})
            page.add_init_script("""
                new PerformanceObserver(list => {
                    window.replayLcp = list.getEntries().at(-1).startTime;
                }).observe({type: 'largest-contentful-paint', buffered: true});
            """)
            page.goto(url)
            page.get_by_role("heading", name="Recorded investigations", exact=True).wait_for()
            page.get_by_role("combobox", name="Trace event").wait_for()
            page.evaluate("document.fonts.ready")
            page.wait_for_load_state("networkidle")
            numbers = page.evaluate("""() => ({
                fcp: performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? null,
                lcp: window.replayLcp ?? null
            })""")
            browser.close()
    except Error as exc:
        raise PaintRefusal(f"Chromium could not measure the Streamlit replay at {url}: {exc}") from exc
    return PaintMeasurement(url=url, **numbers)


def report_the_paint(measurement: PaintMeasurement) -> None:
    """Prints the paint of the page and the conditions under which it was measured."""
    print(f"paint of the replay page: {measurement.url}")
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
        "--app-url",
        default=DEFAULT_APP_URL,
        help="base URL of the running Streamlit app",
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
            paint = measure_the_paint(args.app_url)
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
