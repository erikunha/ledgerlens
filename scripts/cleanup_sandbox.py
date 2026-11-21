#!/usr/bin/env python3
"""Runs one sweep of the cleanup of the expired branches of the sandbox.

Why it exists: ADR-029 keeps the cleanup in the process of the facade and offers it as a command as well, so a
deployment that runs the facade with many workers, or that restarts it often, can schedule the cleanup from the
outside. The command runs the same function the thread of the facade runs, so the two cannot disagree.

Where the store comes from: the setting `LEDGERLENS_SANDBOX_DATABASE_URL` and the file backed store otherwise, the
same rule the facade uses. The command needs no key and no network beyond the local container.

What it prints: how many branches were deleted and the identifiers of them. The exit code is 0 when the sweep ran
and 1 when it could not run.

Usage:

    uv run python scripts/cleanup_sandbox.py
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ledgerlens.config import get_settings
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.ttl import cleanup_expired_branches


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deletes the expired branches of the sandbox.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="prints only how many branches were deleted",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    store = build_branch_store(settings)
    try:
        deleted = cleanup_expired_branches(store)
    except Exception as exc:
        print(f"cleanup_sandbox: the sweep did not run: {exc}", file=sys.stderr)
        return 1
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()

    print(f"cleanup_sandbox: {len(deleted)} expired branch(es) deleted")
    if not args.quiet:
        for branch_id in deleted:
            print(f"deleted {branch_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
