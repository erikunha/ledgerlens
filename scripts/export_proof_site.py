#!/usr/bin/env python3
"""Exports the proofs of the two published catalogs into the static artifacts under `site/proof/`.

Why it exists: the site is a static export, so the artifacts of the proof of work have to exist as files
before anyone opens the page. This script composes the artifact of every bundle of the two published catalogs,
validates it against the schema of the package, scans it with the redaction of the repository and writes it
under `site/proof/`. It runs offline, with no key and with no network, and it calls no model at all.

The export is reproducible: every byte comes from the bundles and from the reports of the repository, so
running the script twice leaves the same bytes on the disk. The `--check` mode verifies the artifacts that are
already there without writing anything, which is what the gate uses to prove that what is published matches
the bundles.

Usage:

```bash
uv run python scripts/export_proof_site.py            # the bundles of the two catalogs, into site/proof
uv run python scripts/export_proof_site.py --check    # verifies what is on the disk
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

from ledgerlens.proof.export import (  # noqa: E402  (the path is set up before the import)
    build_proof_export,
    check_proof_export,
    write_proof_export,
)

DEFAULT_OUT = ROOT / "site" / "proof"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exports the proofs of the two catalogs into site/proof.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the artifacts go to (site/proof)")
    parser.add_argument("--check", action="store_true", help="verifies what is on the disk, writes nothing")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    try:
        files = build_proof_export(ROOT)
    except ValueError as error:
        print(f"the export of the proofs cannot be built: {error}")
        return 1
    if args.check:
        problems = check_proof_export(files, out_dir)
        for problem in problems:
            print(problem)
        if problems:
            print(f"the published proofs have {len(problems)} difference(s) against the bundles")
            return 1
        print(f"the published proofs match the bundles: {len(files)} file(s) checked")
        return 0
    write_proof_export(files, out_dir)
    print(f"the proofs were written to {out_dir}: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
