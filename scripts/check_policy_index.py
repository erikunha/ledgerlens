#!/usr/bin/env python3
"""Verify the delivered policy index against its corpus and artifact digests without loading a model or pickle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.retrieval import INDEX_ARTIFACTS, META_FILE, corpus_digest

__all__ = ["check", "main"]

DEFAULT_POLICIES = PROJECT_ROOT / "data" / "policies"
INDEX_ROOT = PROJECT_ROOT / "data" / "index"
DEFAULT_INDEXES = (INDEX_ROOT / "policies_openai", INDEX_ROOT / "policies_offline")
BUILD_HINT = "rebuild the index with the matching embedding provider"


def check(policies_dir: Path | str, index_dir: Path | str) -> list[str]:
    """The problems between the index and the corpus, one sentence per problem. Empty when they agree.

    Why it exists: the check has to say what is wrong and not only that something is wrong, because the
    reader of the failure is a person editing a policy. The problems are read, never written.
    """
    policies = Path(policies_dir)
    index = Path(index_dir)
    meta_file = index / META_FILE
    if not meta_file.is_file():
        return [f"the index of the policies has no {META_FILE} in {index}; {BUILD_HINT}"]
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"the {META_FILE} of {index} cannot be read; {BUILD_HINT}"]
    if not isinstance(meta, dict):
        return [f"the {META_FILE} of {index} is not a set of fields; {BUILD_HINT}"]

    declared = meta.get("corpus_sha256")
    if not isinstance(declared, str) or not declared:
        return [f"the {META_FILE} of {index} does not carry the digest of the corpus it was built from; {BUILD_HINT}"]

    current = corpus_digest(policies)
    if declared != current:
        return [
            f"the index in {index} was built from another corpus: the index says '{declared}' and the policies "
            f"in {policies} hash to '{current}'; {BUILD_HINT}"
        ]
    digests = meta.get("artifact_sha256")
    if not isinstance(digests, dict):
        return [f"{meta_file} has no artifact digests; {BUILD_HINT}"]

    problems = []
    for filename in INDEX_ARTIFACTS:
        artifact = index / filename
        try:
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        except OSError:
            problems.append(f"{artifact} cannot be read; {BUILD_HINT}")
            continue
        if digests.get(filename) != actual:
            problems.append(f"{artifact} does not match its SHA-256 digest; {BUILD_HINT}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the check. The exit code is the answer."""
    parser = argparse.ArgumentParser(description="Checks the committed policy index against the policies on the disk.")
    parser.add_argument("--policies", default=str(DEFAULT_POLICIES), help="the folder with the policy .md files")
    parser.add_argument("--index", type=Path, help="check only this folder (default: both shipped indexes)")
    args = parser.parse_args(argv)

    indexes = (args.index,) if args.index else DEFAULT_INDEXES
    problems = [problem for index in indexes for problem in check(args.policies, index)]
    if problems:
        for problem in problems:
            print(f"check_policy_index: {problem}", file=sys.stderr)
        print(f"check_policy_index: {len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print(f"verified {len(indexes)} policy index(es) against {args.policies}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
