#!/usr/bin/env python3
"""Exports the Eval Lab into the static artifact that the public web site reads.

Why it exists: the site is a static export, so the numbers of the Eval Lab have to exist as a file before
anyone opens the page. This script reads the reports of the repository and writes `site/eval/index.json`,
with the numbers of the verification and of the evaluation, each one with the dataset it comes from and the
restriction that applies to it, the list of the cases that failed and the confusion matrix of the verifier
with its denominator. It runs offline, with no key and with no network, and it calls no model at all.

The export is reproducible: every byte comes from the reports of the repository, so running the script twice
leaves the same bytes on the disk. The `--check` mode verifies the artifact that is already there without
writing anything, which is what the gate uses to prove that what is published matches the reports.

Usage:

```bash
uv run python scripts/export_eval_lab.py            # the reports of data/eval, into site/eval
uv run python scripts/export_eval_lab.py --check    # verifies what is on the disk
```

Exit code 0 on success, 1 when the export cannot be built or when the check finds a difference.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.lab_export import (  # noqa: E402  (the path is set up before the import)
    build_eval_lab_export,
    check_eval_lab_export,
    write_eval_lab_export,
)

DEFAULT_OUT = ROOT / "site" / "eval"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exports the Eval Lab into site/eval.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the artifact goes to (site/eval)")
    parser.add_argument("--check", action="store_true", help="verifies what is on the disk, writes nothing")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    try:
        files = build_eval_lab_export(ROOT)
    except (ValueError, KeyError, FileNotFoundError) as error:
        print(f"the export of the eval lab cannot be built: {error}")
        return 1
    if args.check:
        problems = check_eval_lab_export(files, out_dir)
        for problem in problems:
            print(problem)
        if problems:
            print(f"the published eval lab has {len(problems)} difference(s) against the reports")
            return 1
        print(f"the published eval lab matches the reports: {len(files)} file(s) checked")
        return 0
    write_eval_lab_export(files, out_dir)
    print(f"the eval lab was written to {out_dir}: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
