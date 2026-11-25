#!/usr/bin/env python3
"""Exports the diff of a branch of the sandbox as data, with a hash and with the command that reproduces it.

Why it exists: the diff of a branch is a read of the branch under ADR-028, and the package of the sandbox asks
for the diff published as data and not as a picture. The export reads the branch from the store of the runtime,
builds the artifact of the diff and writes it, and it never writes into the branch: the revision and the
canonical hash of the branch are the same before and after the export.

Usage:

```bash
uv run python scripts/export_sandbox_diff.py --branch <branch_id> --session <session_id> [--out <folder>]
```

Exit code 0 when the artifact was written, 1 when the branch could not be read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerlens.config import get_settings  # noqa: E402
from ledgerlens.sandbox.branch import BranchLayer  # noqa: E402
from ledgerlens.sandbox.diff_artifact import read_diff_artifact, render_diff_artifact  # noqa: E402
from ledgerlens.sandbox.factory import build_branch_store  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402


def main() -> int:
    """Runs the command and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Exports the diff of a branch of the sandbox as data.")
    parser.add_argument("--branch", required=True, help="the identifier of the branch")
    parser.add_argument("--session", required=True, help="the identifier of the session that owns the branch")
    parser.add_argument("--out", default=None, help="the folder of the artifact (by default the runtime folder)")
    args = parser.parse_args()

    settings = get_settings()
    store = build_branch_store(settings)
    layer = BranchLayer(store, BaseResolver(settings.runtime_dir / "sandbox-bases"))
    try:
        artifact = read_diff_artifact(layer, args.session, args.branch)
    except Exception as exc:  # noqa: BLE001 - the refusal of the layer is the answer of the command
        print(f"export_sandbox_diff: the branch could not be read: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else settings.runtime_dir / "sandbox-diffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.branch}.json"
    path.write_bytes(render_diff_artifact(artifact))
    print(f"the diff of the branch was written: {path}")
    print(f"sha256 of the artifact: {__import__('hashlib').sha256(path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
