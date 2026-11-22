#!/usr/bin/env python3
"""Produces the frozen artifact of the ledger of a recorded scenario.

Why it exists: the site publishes the ledger of the account of the recording, next to the recording itself, and the
file it publishes has to be the same file every time. The artifact therefore lives beside the bundle, in
`data/eval/replay/ledger/<slug>.json`, and it is written by this command and never by hand.

Why the command is not the capture: the recording is frozen and it names the commit it was made from, so a command
that rewrites one half of the milestone would put the other half in doubt. The capture writes the bundle and this
command writes the artifact of the bundle, after it.

What the command does, in this order: it opens the bundle with the loader of the core, so that the hashes, the secret
and the order of the events are checked before anything is written; it rebuilds the ledger of the account, the same
way the capture built it; it proves that the ledger it rebuilt is the ledger the recording read, by comparing the
sha256 of the file with the digest the manifest declares; and it writes the artifact.

The bytes of a file of SQLite carry the version of the library that wrote it, so the proof of the identity of the
ledger belongs to this command, once, and not to the export, which runs on every machine.

Usage:

```bash
uv run python scripts/build_ledger_artifact.py
uv run python scripts/build_ledger_artifact.py --bundle data/eval/replay/s01 --out data/eval/replay/ledger
```

Exit code 0 when the artifact was written and 1 when it was refused.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The command runs offline: it reads the repository and writes a file, and it calls nobody.
os.environ.setdefault("LEDGERLENS_OFFLINE", "1")

sys.path.insert(0, str(ROOT))

from ledgerlens.api.accounts import scoped_ledger  # noqa: E402  (the path is set up before the import)
from ledgerlens.replay.bundle import BundleError, load_bundle  # noqa: E402  (the path is set up before the import)
from ledgerlens.replay.ledger_artifact import (  # noqa: E402  (the path is set up before the import)
    LedgerArtifactError,
    account_of_manifest,
    build_ledger_artifact,
    write_ledger_artifact,
)
from ledgerlens.sim.config import SimConfig  # noqa: E402  (the path is set up before the import)
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402  (the path is set up before the import)

# The canonical bundle of the repository and the folder of the frozen artifacts, beside the folder of the bundle.
DEFAULT_BUNDLE = ROOT / "data" / "eval" / "replay" / "s01"
DEFAULT_OUT = ROOT / "data" / "eval" / "replay" / "ledger"


__all__ = [
    "DEFAULT_BUNDLE",
    "DEFAULT_OUT",
    "build",
    "main",
]


def _sha256(path: Path) -> str:
    """The hash of a file, to identify the ledger the recording read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(bundle_dir: Path, out_dir: Path) -> Path:
    """The artifact of the scenario of the bundle, written in the output folder, and the path of the file.

    The order of the steps is the order of the promises: the bundle is checked first, the ledger is rebuilt and proved
    to be the ledger of the recording, and only then is anything written. A refusal writes nothing at all.
    """
    try:
        manifest, _events = load_bundle(bundle_dir)
    except BundleError as exc:
        raise LedgerArtifactError(f"the bundle in {bundle_dir.name} does not hold up: {exc}") from exc

    account_id = account_of_manifest(manifest)
    if account_id is None:
        raise LedgerArtifactError(
            f"the note of the manifest of {bundle_dir.name} names no account, so the recording owes no ledger"
        )
    if not manifest.snapshot_sha256:
        raise LedgerArtifactError(
            f"the manifest of {bundle_dir.name} declares no digest of the ledger, so the artifact could not prove "
            "which ledger it is"
        )

    with tempfile.TemporaryDirectory(prefix="ledgerlens_ledger_") as work:
        root = Path(work)
        base = root / "ledger.db"
        result = build_ledger(SimConfig(source="sample"), base)
        result.conn.close()
        account_db = scoped_ledger(base, account_id, root / "account.db")

        # The proof of the identity of the ledger: the digest of the file the recording read.
        observed = _sha256(account_db)
        if observed != manifest.snapshot_sha256:
            raise LedgerArtifactError(
                f"the ledger of the account {account_id} that was rebuilt has the digest {observed} and the recording "
                f"declares {manifest.snapshot_sha256}, so it is not the ledger the recording read"
            )

        artifact = build_ledger_artifact(bundle_dir, account_db)
        path = out_dir / f"{str(manifest.scenario).lower()}.json"
        write_ledger_artifact(path, artifact)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the command and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Produces the frozen artifact of the ledger of a recorded scenario.")
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE), help="folder of the bundle of the recording")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder the frozen artifacts go to")
    args = parser.parse_args(argv)

    try:
        path = build(Path(args.bundle), Path(args.out))
    except LedgerArtifactError as exc:
        print(f"build_ledger_artifact: {exc}", file=sys.stderr)
        return 1

    print(f"artifact written in {path}")
    print(f"sha256 of the artifact: {_sha256(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
