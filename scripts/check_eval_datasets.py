#!/usr/bin/env python3
"""Checks the manifest of the eval datasets against the datasets that are on the disk.

Why it exists: the repository holds six JSONL datasets under `data/eval/` and the numbers the reports publish
depend on them. When a dataset moves and the manifest does not move with it, the report keeps the number of the
old file and the reader of the report has no way to tell that the data changed under the number. This script is
the side of the triangle that closes that gap: it reads the disk, recomputes the sha256 and the record count of
every dataset the manifest declares, and refuses with a readable reason and a non zero exit code when the two
disagree, when a declared dataset is missing or when a dataset of the folder is not declared.

The rule that decides what is wrong between the manifest and the disk lives in `ledgerlens/eval/manifest.py` and
only there. This script asks the module, prints the sentences the module returns and keeps its own job: the two
modes, the exit code, the readable refusal and the write. There is one definition of the order of the problems
and not two.

Two modes, and the difference matters:

- without arguments it VERIFIES. It reads the disk, prints one line per problem and writes nothing.
- `--write` UPDATES the sha256 and the record count of the entries whose file moved, prints what moved and
  writes the canonical text of the manifest. It never changes the role, the source, the labeling version, the seed,
  the policy or the notes of an entry, because those are hand edits of the manifest file: the role of a dataset is a
  decision that a person reviews, not something a script decides. When the committed manifest exists and the role on
  the disk differs from the role of the commit, the write refuses. When there is no committed manifest to compare
  against, the write says so out loud instead of pretending the roles were checked.

The manifest that is checked is the one of the root, `<root>/data/eval/datasets.json`, unless `--manifest` names
another one. A manifest outside the root is refused, because a check of another root that wrote the manifest of
the repository would pin the files of one root to the manifest of another. The path is resolved before it is
compared with the root, so the default path is checked exactly like a named one, and a relative `--manifest` is
resolved against the root and not against the current directory.

The write of the manifest never writes through a link: the canonical text goes to a temporary file of the same
folder and is moved over the manifest with `os.replace`, which renames a file. A manifest that is a link to a file
outside of the root is refused before the write, so the write cannot reach outside of the root.

A dataset whose path resolves outside the root is refused as well, and the file it points at is never read: a check
that read it would be reading a file that is not a dataset of the repository. A dataset that is not a regular file,
a named pipe for example, is refused with a sentence and not with a wait that never ends.

A data problem is never a traceback. Every problem is a line of plain English that names the dataset, the file
and the two values that disagree, because the reader of the failure is a person and not a stack trace. Every value
of a file that enters one of those lines is rendered so that it cannot carry a line break or an escape into the
log, so no file name can forge the line that says the check passed.

Usage:

```bash
uv run python scripts/check_eval_datasets.py           # verifies, writes nothing
uv run python scripts/check_eval_datasets.py --write   # updates the fingerprints that moved
```

Exit code 0 when every dataset matches the manifest, 1 when there is a problem.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.manifest import (  # noqa: E402  (the path is set up before the import)
    MANIFEST_RELATIVE,
    EvalDatasetManifest,
    ManifestError,
    load_manifests,
    manifest_problems,
    render_manifests,
    safe_text,
    update_fingerprints,
    verify_manifests,
)

__all__ = ["main"]

# The sentence that opens a refusal, so the reason of a failure is the same shape everywhere.
REFUSAL = "refused"


def _git_toplevel(root: Path) -> Path | None:
    """The root of the git repository that holds the root, or None when there is no git or no repository.

    Why it exists: the write compares the role of the file on the disk with the role of the committed manifest,
    and the path of that commit is relative to the root of the repository, not to the root of the check.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    toplevel = done.stdout.strip()
    if not toplevel:
        return None
    return Path(toplevel).resolve()


def _committed_roles(manifest_path: Path, root: Path) -> dict[str, str] | None:
    """The role of every dataset of the committed manifest, or None when there is no committed manifest.

    The role of a dataset is a decision that a person reviews, so the script never changes it. This only reads
    the committed manifest to notice when the file on the disk carries a role that the commit does not have, and
    then the write refuses. When there is no committed manifest, or no git, there is nothing to compare with, and
    the caller says so out loud instead of pretending the roles were checked.
    """
    toplevel = _git_toplevel(root)
    if toplevel is None:
        return None
    try:
        relative = manifest_path.resolve().relative_to(toplevel)
    except ValueError:
        return None
    try:
        done = subprocess.run(
            ["git", "-C", str(toplevel), "show", f"HEAD:{relative.as_posix()}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        return None
    entries = payload.get("datasets") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    roles: dict[str, str] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("dataset_id"), str):
            roles[entry["dataset_id"]] = str(entry.get("split_role"))
    return roles


def _role_comparison(
    manifests: tuple[EvalDatasetManifest, ...],
    root: Path,
    manifest_path: Path,
) -> tuple[list[str], list[str]]:
    """The refusals of the roles, and the notices that say what was not compared.

    Adding, removing and re-roling an entry are hand edits of the manifest file. A script that made them would
    decide, without a reader, which dataset is a tuning set and which one is not.
    """
    refusals: list[str] = []
    notices: list[str] = []
    roles = _committed_roles(manifest_path, root)
    if roles is None:
        notices.append(
            "the roles were not compared: there is no committed manifest to compare against, "
            "so the roles were kept as they are"
        )
        return refusals, notices

    for manifest in manifests:
        expected = roles.get(manifest.dataset_id)
        if expected is None:
            notices.append(
                f"the role of the dataset '{safe_text(manifest.dataset_id)}' was not compared: the committed "
                f"manifest does not declare it, so the role was kept as it is"
            )
        elif expected != manifest.split_role:
            refusals.append(
                f"{REFUSAL}: the dataset {safe_text(manifest.dataset_id)} has the role "
                f"{safe_text(manifest.split_role)} and the committed manifest has the role {safe_text(expected)}; "
                f"changing the role is a hand edit of the manifest"
            )
    return refusals, notices


def _refusals(
    manifests: tuple[EvalDatasetManifest, ...],
    root: Path,
    manifest_path: Path,
) -> tuple[list[str], list[str]]:
    """The changes of the manifest that the write refuses, and the notices that say what was not compared.

    The problems come from the module, which owns the rule. A file that the manifest declares and the disk lost
    is a removal of an entry, a file of the folder that no entry declares is an addition of one, and both are
    hand edits of the manifest file.
    """
    refusals: list[str] = []
    for problem in manifest_problems(root, manifest_path=manifest_path):
        if problem.kind == "missing":
            refusals.append(
                f"{REFUSAL}: {problem.message}; removing an entry is a hand edit of the manifest"
            )
        elif problem.kind == "undeclared":
            refusals.append(
                f"{REFUSAL}: {problem.message}; adding an entry is a hand edit of the manifest"
            )
        elif problem.kind in {"unreadable", "error"}:
            refusals.append(f"{REFUSAL}: {problem.message}")

    role_refusals, notices = _role_comparison(manifests, root, manifest_path)
    return refusals + role_refusals, notices


def _manifest_path(root: Path, declared: str | None) -> Path | None:
    """The manifest file of the run, resolved, or None when the check refuses to run.

    Why it exists: the manifest follows the root, because a check of another root that wrote the manifest of the
    repository would pin the files of one root to the manifest of another. A manifest outside the root is
    refused with a readable reason and no exit code of zero.

    The path is resolved before it is compared with the root, so the default path of the root is checked exactly
    like a named one: a `data/eval/datasets.json` that is a link to a file outside of the root is refused and
    never written. A relative path is resolved against the root and not against the current directory, so the same
    argument names the same file from anywhere.
    """
    candidate = root / MANIFEST_RELATIVE if declared is None else Path(declared)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        print(
            f"check_eval_datasets: the manifest {safe_text(candidate)} cannot be resolved: {error}",
            file=sys.stderr,
        )
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        print(
            f"check_eval_datasets: the manifest {safe_text(resolved)} is outside the root {safe_text(root)}, "
            f"so the check refused to run.",
            file=sys.stderr,
        )
        return None
    return resolved


def _mode_of(path: Path) -> int:
    """The mode of the file that is written, so the write does not change the permissions of the manifest."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return 0o644


def _write_manifest(manifest_path: Path, text: str) -> None:
    """The canonical text written over the manifest, without ever writing through a link.

    Why it exists: the write must not be able to reach a file outside of the root. The text is written to a
    temporary file of the same folder and moved over the manifest with `os.replace`, which renames a file and
    never writes through a link. `os.replace` is atomic and behaves the same on macOS and on Linux.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(manifest_path.parent), prefix=".datasets.json.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temporary, _mode_of(manifest_path))
        os.replace(temporary, manifest_path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temporary)


def _verify(manifests: tuple[EvalDatasetManifest, ...], root: Path, manifest_path: Path) -> int:
    """The verify mode: read the disk, print one line per problem, write nothing."""
    problems = verify_manifests(root, manifest_path=manifest_path)

    for problem in problems:
        print(problem)
    if problems:
        print(f"check_eval_datasets: {len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print(f"every dataset matches the manifest: {len(manifests)} dataset(s) checked")
    return 0


def _write(manifests: tuple[EvalDatasetManifest, ...], root: Path, manifest_path: Path) -> int:
    """The write mode: update the fingerprints that moved and write the canonical text of the manifest."""
    refusals, notices = _refusals(manifests, root, manifest_path)
    for notice in notices:
        print(notice)
    if refusals:
        for refusal in refusals:
            print(refusal, file=sys.stderr)
        print("check_eval_datasets: the manifest was not written", file=sys.stderr)
        return 1

    result = update_fingerprints(manifests, root=root)
    text = render_manifests(result.entries)
    previous = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
    if previous == text:
        print(f"the manifest is already canonical: {safe_text(manifest_path)}")
    else:
        try:
            _write_manifest(manifest_path, text)
        except OSError as exc:
            print(f"check_eval_datasets: the manifest cannot be written: {safe_text(exc)}", file=sys.stderr)
            return 1
        print(f"the manifest was written: {safe_text(manifest_path)}")
    for sentence in result.messages:
        print(f"  {sentence}")
    if not result.messages:
        print("  nothing moved")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the check. The exit code is the answer."""
    parser = argparse.ArgumentParser(
        description="Checks the manifest of the eval datasets against the datasets that are on the disk.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="the manifest file to read, inside the root. The default is the manifest of the root",
    )
    parser.add_argument("--root", default=str(ROOT), help="the root the relative paths of the datasets resolve against")
    parser.add_argument(
        "--write",
        action="store_true",
        help="updates the sha256 and the record count of the entries whose file moved, and writes the manifest",
    )
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"check_eval_datasets: the root {safe_text(args.root)} cannot be resolved: {exc}", file=sys.stderr)
        return 1
    manifest_path = _manifest_path(root, args.manifest)
    if manifest_path is None:
        return 1

    try:
        manifests = load_manifests(manifest_path)
    except (ManifestError, OSError, ValueError) as exc:
        print(f"check_eval_datasets: the manifest cannot be read: {safe_text(exc)}", file=sys.stderr)
        return 1

    if args.write:
        return _write(manifests, root, manifest_path)
    return _verify(manifests, root, manifest_path)


if __name__ == "__main__":
    sys.exit(main())
