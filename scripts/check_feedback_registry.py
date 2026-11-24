#!/usr/bin/env python3
"""The check of the registry of the feedback records: it reads the disk, it writes nothing, and it fails loudly.

The registry of the feedback is the door of the shared set of the repository: every record of the loop lives
under `data/eval/feedback/` with its digest, its permission and its tier. This script reads the registry and
checks every entry against the disk: the digest of the file, the vocabulary of the permission and of the tier,
and the refusal of a record whose source is a session of a visitor. A problem is a non zero exit with a
readable reason, because a registry that cannot be checked is a registry that cannot be trusted.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledgerlens.feedback.registry import REGISTRY_PATH, check_registry, load_registry  # noqa: E402


def main() -> int:
    """The check of the registry of the repository, against the disk of the repository."""
    registry_path = ROOT / REGISTRY_PATH
    if not registry_path.is_file():
        print(f"the registry of the feedback is not on the disk: {REGISTRY_PATH}")
        return 1
    entries = load_registry(registry_path)
    if not entries:
        print("the registry of the feedback holds no record")
        return 1
    problems = check_registry(entries, ROOT)
    for problem in problems:
        print(problem)
    if problems:
        print(f"the registry of the feedback has {len(problems)} problem(s)")
        return 1
    print(f"the registry of the feedback is clean: {len(entries)} record(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
