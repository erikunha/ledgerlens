#!/usr/bin/env python3
"""Exports the recorded replay bundles into the static artifacts that the public web site reads.

The offline exporter writes the events, manifest, provenance and index under `site/replay`.
Streamlit reads the published files directly.

The site publishes two catalogs, and the export writes one of them per run. The second one, the recordings of a
real model, lives in `site/replay-real` and comes from `data/eval/replay-real`. The mode of the catalog is named
with `--mode`, so that a recording of a real model cannot land in the folder of the sandbox and the other way
round (ADR-075).

The export is reproducible: every timestamp comes from the bundle and not from the clock, so running the script
twice leaves the same bytes on the disk. The `--check` mode verifies the artifacts that are already there without
writing anything, which is what the gate uses to prove that what is published matches the recording.

Usage:

```bash
uv run python scripts/export_replay_site.py                     # the bundles of data/eval/replay, into site/replay
uv run python scripts/export_replay_site.py data/eval/replay/s01 --out site/replay
uv run python scripts/export_replay_site.py --check             # verifies what is on the disk
uv run python scripts/export_replay_site.py data/eval/replay-real --out site/replay-real --mode live_agent
```

Exit code 0 on success, 1 when the bundle does not hold up or when the check finds a difference.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.replay.site_export import (  # noqa: E402  (the path is set up before the import)
    ExportError,
    build_export,
    check_export,
    discover_bundles,
    write_export,
)

DEFAULT_BUNDLE = ROOT / "data" / "eval" / "replay"
DEFAULT_OUT = ROOT / "site" / "replay"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exports the replay bundles into the static artifacts of the site.")
    parser.add_argument("bundle", nargs="?", default=str(DEFAULT_BUNDLE), help="folder of the bundle to export")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the artifacts go to (site/replay)")
    parser.add_argument(
        "--mode",
        default=None,
        help="the mode of the catalog being written (deterministic_sandbox or live_agent); with it, a bundle of "
        "another mode is refused (ADR-075)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compares what would be written with what is on the disk, and writes nothing",
    )
    args = parser.parse_args(argv)
    out = Path(args.out)

    try:
        bundles = discover_bundles(Path(args.bundle))
        # The folder of the output names the catalog, so a recording of a real model cannot land in the folder of
        # the sandbox and the other way round, even when the command line does not name the mode (ADR-075).
        files = build_export(bundles, expected_mode=args.mode, output=out)
    except ExportError as exc:
        print(f"export_replay_site: {exc}", file=sys.stderr)
        return 1

    if args.check:
        differences = check_export(files, out)
        if differences:
            print(f"export_replay_site: the artifacts in {out} do NOT match the bundle:", file=sys.stderr)
            for difference in differences:
                print(f"  {difference}", file=sys.stderr)
            return 1
        print(f"the artifacts in {out} match the bundle")
        return 0

    outcome = write_export(files, out)
    print(f"artifacts written in {out}")
    for artifact in outcome.written:
        print(f"  {artifact.path.relative_to(out)}: {artifact.sha256} ({artifact.size} bytes)")
    if outcome.foreign:
        # The write never deletes a file of somebody else, so the operator is told which one is in the way.
        print("export_replay_site: these files of the output folder are not artifacts of the export:", file=sys.stderr)
        for path in outcome.foreign:
            print(f"  {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
