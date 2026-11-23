#!/usr/bin/env python3
"""Checks the committed policy index against the policies of the repository.

Why it exists: the index of the policies is a build artifact that lives in git, next to the policies it was
made of. Nothing in the repository said when it went out of date, so an edited policy kept being answered
from the old index, silently: every test was green, the manifest of the datasets was green and the answer
was the text of a version of the policy that was not on the disk anymore. This script is the side of the
triangle that closes that gap: it reads the meta of the committed index, recomputes the digest of the
corpus of the disk and refuses with a readable reason and a non zero exit code when the two disagree.

What it does, and what it does not do:
- it reads the disk, prints one line per problem and writes nothing;
- it never opens the vectors of the index and never downloads the embedding model: the digest of the corpus
  needs no vector, which is what makes the check possible in the offline gate (`scripts/gate.sh`);
- it never rebuilds the index: the rebuild is a step of a person (`uv run python scripts/build_index.py`),
  because it needs the embedding model.

The rule that decides what is wrong between the index and the corpus lives in `ledgerlens/retrieval.py`
(`corpus_digest`) and only there. This script asks the module, prints the sentences it returns and keeps its
own job: the modes, the exit code, the readable refusal and the write it never does.

Usage:

```bash
uv run python scripts/check_policy_index.py           # checks the committed index, writes nothing
```

Exit code 0 when the committed index describes the policies of the disk, 1 when there is a problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.retrieval import META_FILE, corpus_digest

__all__ = ["check", "main"]

DEFAULT_POLICIES = PROJECT_ROOT / "data" / "policies"
DEFAULT_INDEX = PROJECT_ROOT / "data" / "index" / "policies_fastembed"
BUILD_HINT = "run `uv run python scripts/build_index.py` to build it"


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
    return []


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the check. The exit code is the answer."""
    parser = argparse.ArgumentParser(description="Checks the committed policy index against the policies on the disk.")
    parser.add_argument("--policies", default=str(DEFAULT_POLICIES), help="the folder with the policy .md files")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="the folder of the index to check")
    args = parser.parse_args(argv)

    problems = check(args.policies, args.index)
    if problems:
        for problem in problems:
            print(f"check_policy_index: {problem}", file=sys.stderr)
        print(f"check_policy_index: {len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print(f"the index describes the policies of {args.policies}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
