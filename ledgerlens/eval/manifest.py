"""The manifest of the eval datasets: what each file is, how many records it has and what may be done with it.

Why it exists: the repository has five JSONL datasets under `data/eval/` and, until this module, no file that said
what they were, how many records each one held, which one the thresholds had been tuned on or which one a tuning
script was allowed to read. The numbers that the verifier and the evaluation publish come from these files, and the
43 against 30 discrepancy of the calibration is exactly the symptom of that missing file: nobody had pinned what was
tuned on.

The manifest is that pin. Every dataset carries its sha256, its record count, where its records come from, the
version of the labeling pass, the role it plays in the split, the seed of the scenarios it comes from and the rule
that says what may be done with it. The check in `scripts/check_eval_datasets.py` reads the disk and refuses when a
dataset moved without the manifest moving with it, so a number that was produced over one file cannot be presented as
a number over another.

Two decisions of this module:

- **A record is a nonblank line that parses as a JSON object.** A line that does not parse is a failure, not a
  record: `fingerprint_dataset` raises `ManifestError` naming the file and the line. The count of the manifest and the
  count of the disk are then computed by the same rule, so they can be compared.
- **The role of a dataset is decided by what the repository can prove it was used for.** The conservative role wins
  when the evidence is not clean. No dataset of this repository carries the role `held_out` today, so no result of
  this repository may be presented as a generalization to unseen data.

The scan for an undeclared JSONL file looks at the files that sit directly in `data/eval/`. The folders below it hold
other artifacts with their own contract: the recording of the scenario `S01` lives in `data/eval/replay/s01/` and
declares its own files in its own manifest (ADR-014), so it is not a dataset of this manifest.

The path of an entry is relative to the root of the check and may not leave it. A path that is absolute or that
climbs out of the root with a `..` part is refused when the manifest is read, before the disk is touched, so the
manifest of a repository can never pin a file that lives outside it.

The rule that decides what is wrong between the manifest and the disk lives in this module and only here.
`manifest_problems` is that rule, `verify_manifests` gives its sentences and the check of the gate prints them.

Usage:

```python
from ledgerlens.eval.manifest import load_manifests, update_fingerprints, verify_manifests

problems = verify_manifests()              # an empty list means the manifest agrees with the disk
manifests = load_manifests()               # the entries, already validated
result = update_fingerprints(manifests)    # result.entries and result.messages
```
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, fields, replace
from pathlib import Path, PurePosixPath
from typing import Any

from ledgerlens.config import PROJECT_ROOT

MANIFEST_PATH = PROJECT_ROOT / "data" / "eval" / "datasets.json"

# The roles a dataset can carry. A dataset with the role `tuning` is what the thresholds, the prompts and the
# hyperparameters were chosen against. A dataset with the role `validation` may be scored but never tuned against. A
# dataset with the role `held_out` may be read only by the final scoring step.
SPLIT_ROLES: tuple[str, ...] = ("tuning", "validation", "held_out")

# The folder of the datasets, relative to the project root, and the manifest file relative to it. They are relative
# so that a check over another root reads that root and not this one.
EVAL_DIR_RELATIVE = Path("data") / "eval"
MANIFEST_RELATIVE = Path("data") / "eval" / "datasets.json"

# A sha256 is 64 lowercase hexadecimal characters. Uppercase and a short digest are refused.
_SHA256_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdef")


class ManifestError(Exception):
    """The manifest file or the disk does not agree with the contract, and the message says why.

    Why it exists: the reader of a manifest wants one sentence that names the file and the problem, not a stack
    trace. Every function of this module that can meet a bad file raises this, with that sentence in the message.
    """


@dataclass(frozen=True)
class EvalDatasetManifest:
    """One dataset of `data/eval/`, pinned by the file it names and the role it plays.

    Why it exists: the record is the unit of the manifest. It is frozen because it is a fact about a file that was
    measured once: nothing may change it in place, and the only way to change it is to write a new manifest file that
    a person reviewed.
    """

    dataset_id: str
    path: str  # relative to the project root, with forward slashes
    sha256: str  # the sha256 of the file, 64 lowercase hexadecimal characters
    records_count: int  # the number of records of the file, counted as nonblank JSONL lines
    source: str  # where the records come from
    labeling_version: str  # the version of the labeling pass
    split_role: str  # one of SPLIT_ROLES
    scenario_seed: int | None  # the seed of the scenarios the records come from, None when there is none
    contamination_policy: str  # the rule that says what may be done with this dataset
    notes: str = ""  # the honest caveat, empty when there is none


@dataclass(frozen=True)
class ManifestProblem:
    """One problem the disk has against the manifest, with the kind of the problem and the sentence that says it.

    Why it exists: the rule that decides what is wrong between the manifest and the disk lives in this module, and
    the caller that writes the manifest has to know the kind of a problem to know whether it may fix it or has to
    refuse. The kind is one of `missing`, `hash`, `count`, `unreadable`, `undeclared` and `error`.
    """

    kind: str
    message: str


def fingerprint_dataset(path: Path) -> tuple[str, int]:
    """The sha256 of the bytes of the file and the number of records it holds.

    Why it exists: the manifest stores these two values and the check compares them with the disk. A record is a
    nonblank line that parses as a JSON object, and a line that does not parse is a failure and not a record, so a
    file that lost a line or gained a broken one cannot pass as the one the manifest describes.

    Raises `ManifestError` when the file is missing or when a line of it does not parse as a JSON object.
    """
    if not path.is_file():
        raise ManifestError(f"The file {path} does not exist, so it has no fingerprint.")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    count = 0
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ManifestError(f"The line {number} of the file {path} is not valid JSON: {error.msg}.") from error
            if not isinstance(record, dict):
                raise ManifestError(
                    f"The line {number} of the file {path} is not a JSON object, so it is not a record."
                )
            count += 1

    return digest.hexdigest(), count


def _check_fields(entry: dict[str, Any], path: Path, index: int) -> None:
    """Refuses an entry with a missing or an unknown field, naming the file and the field.

    The field `notes` may be left out, because the record gives it a default of an empty string. Every other field
    of the record is required: without it the entry does not say what the dataset is.
    """
    expected = {field.name for field in fields(EvalDatasetManifest)}
    unknown = sorted(set(entry) - expected)
    if unknown:
        raise ManifestError(
            f"The entry {index} of the manifest {path} has the unknown field(s) {', '.join(unknown)}."
        )
    missing = sorted(expected - {"notes"} - set(entry))
    if missing:
        raise ManifestError(f"The entry {index} of the manifest {path} is missing the field(s) {', '.join(missing)}.")


def _check_types(entry: dict[str, Any], path: Path, index: int) -> None:
    """Refuses an entry whose fields do not have the type of the record."""
    for name in (
        "dataset_id",
        "path",
        "sha256",
        "source",
        "labeling_version",
        "split_role",
        "contamination_policy",
    ):
        if not isinstance(entry[name], str):
            raise ManifestError(f"The field {name} of the entry {index} of the manifest {path} is not a string.")
    notes = entry.get("notes", "")
    if not isinstance(notes, str):
        raise ManifestError(f"The field notes of the entry {index} of the manifest {path} is not a string.")
    count = entry["records_count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ManifestError(f"The field records_count of the entry {index} of the manifest {path} is not an integer.")
    seed = entry["scenario_seed"]
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ManifestError(f"The field scenario_seed of the entry {index} of the manifest {path} is not an integer.")


def _check_path(dataset_id: str, declared: str, path: Path) -> None:
    """Refuses a path that is absolute or that leaves the root with a `..` part.

    Why it exists: the path of an entry is resolved against the root of the check, and a path that is absolute or
    that climbs out of the root would make the check read a file that is not a dataset of the repository. The two
    refusals are lexical: they never touch the disk, so they hold for any root.
    """
    if PurePosixPath(declared).is_absolute() or Path(declared).is_absolute():
        raise ManifestError(
            f"The dataset '{dataset_id}' of the manifest {path} declares the path '{declared}', "
            f"and the path of a dataset is relative to the root."
        )
    if ".." in PurePosixPath(declared).parts:
        raise ManifestError(
            f"The dataset '{dataset_id}' of the manifest {path} declares the path '{declared}', "
            f"and the path of a dataset may not leave the root with '..'."
        )


def load_manifests(path: Path = MANIFEST_PATH) -> tuple[EvalDatasetManifest, ...]:
    """The entries of the manifest file, already validated.

    Why it exists: the manifest file is hand written and reviewed, so it can carry a mistake. This function refuses
    a file that is missing or is not JSON, an entry with a missing or an unknown field, a repeated `dataset_id`, a
    `split_role` outside `SPLIT_ROLES`, a `sha256` that is not 64 lowercase hexadecimal characters, a negative
    `records_count` and a `path` that is absolute or that leaves the root with a `..` part. Every message names the
    file and the problem.

    Every field of the record is required in the file, `notes` apart: that one has a default of an empty string in the
    record, so an entry may leave it out. Without the other fields the entry does not say what the dataset is.

    Raises `ManifestError` for any of those.
    """
    if not path.is_file():
        raise ManifestError(f"The manifest {path} does not exist.")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ManifestError(f"The manifest {path} is not valid JSON: {error.msg}.") from error

    if not isinstance(payload, dict) or "datasets" not in payload:
        raise ManifestError(f"The manifest {path} does not have the key 'datasets'.")
    entries = payload["datasets"]
    if not isinstance(entries, list):
        raise ManifestError(f"The key 'datasets' of the manifest {path} is not a list of entries.")

    manifests: list[EvalDatasetManifest] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ManifestError(f"The entry {index} of the manifest {path} is not an object.")
        _check_fields(entry, path, index)
        _check_types(entry, path, index)

        dataset_id = entry["dataset_id"]
        if dataset_id in seen:
            raise ManifestError(f"The dataset_id '{dataset_id}' appears more than once in the manifest {path}.")
        seen.add(dataset_id)

        _check_path(dataset_id, entry["path"], path)

        split_role = entry["split_role"]
        if split_role not in SPLIT_ROLES:
            raise ManifestError(
                f"The dataset '{dataset_id}' of the manifest {path} has the split_role '{split_role}', "
                f"and the roles are {', '.join(SPLIT_ROLES)}."
            )

        sha256 = entry["sha256"]
        if len(sha256) != _SHA256_LENGTH or not set(sha256) <= _HEX_DIGITS:
            raise ManifestError(
                f"The dataset '{dataset_id}' of the manifest {path} has the sha256 '{sha256}', "
                f"and a sha256 is {_SHA256_LENGTH} lowercase hexadecimal characters."
            )

        if entry["records_count"] < 0:
            raise ManifestError(
                f"The dataset '{dataset_id}' of the manifest {path} has the records_count "
                f"{entry['records_count']}, and a count is not negative."
            )

        manifests.append(
            EvalDatasetManifest(
                dataset_id=dataset_id,
                path=entry["path"],
                sha256=sha256,
                records_count=entry["records_count"],
                source=entry["source"],
                labeling_version=entry["labeling_version"],
                split_role=split_role,
                scenario_seed=entry["scenario_seed"],
                contamination_policy=entry["contamination_policy"],
                notes=entry.get("notes", ""),
            )
        )

    return tuple(manifests)


def manifest_problems(
    root: Path | None = None,
    manifest_path: Path | None = None,
) -> list[ManifestProblem]:
    """The problems the disk has against the manifest, each one with its kind and its sentence.

    Why it exists: this is the one implementation of the rule that decides what is wrong between the manifest and
    the disk. `verify_manifests` gives the sentences of these problems and the check of the gate prints them, so
    there is one definition of the order of the problems and not two.

    The order is the one of the contract: a declared file that does not exist, a declared file whose sha256 does
    not match, a declared file whose record count does not match, a declared file that cannot be read, and a JSONL
    file of `data/eval/` that no entry declares.

    The manifest that is checked is the one of the root, `<root>/data/eval/datasets.json`, unless `manifest_path`
    names another one. An empty list means the manifest agrees with the disk.

    A manifest file that is missing or that is not valid JSON is a problem of its own and comes back as the only
    problem of the list, so that the caller can print it and fail without a stack trace.
    """
    base = PROJECT_ROOT if root is None else Path(root)
    manifest_file = base / MANIFEST_RELATIVE if manifest_path is None else Path(manifest_path)
    try:
        manifests = load_manifests(manifest_file)
    except ManifestError as error:
        return [ManifestProblem(kind="error", message=str(error))]

    missing: list[ManifestProblem] = []
    wrong_hash: list[ManifestProblem] = []
    wrong_count: list[ManifestProblem] = []
    unreadable: list[ManifestProblem] = []

    for manifest in sorted(manifests, key=lambda item: item.dataset_id):
        path = base / manifest.path
        if not path.is_file():
            missing.append(
                ManifestProblem(
                    kind="missing",
                    message=(
                        f"The dataset '{manifest.dataset_id}' declares the file '{manifest.path}' and the file does "
                        f"not exist."
                    ),
                )
            )
            continue
        try:
            digest, count = fingerprint_dataset(path)
        except ManifestError as error:
            unreadable.append(
                ManifestProblem(
                    kind="unreadable",
                    message=(
                        f"The dataset '{manifest.dataset_id}' declares the file '{manifest.path}' and the file could "
                        f"not be read: {error}"
                    ),
                )
            )
            continue
        if digest != manifest.sha256:
            wrong_hash.append(
                ManifestProblem(
                    kind="hash",
                    message=(
                        f"The dataset '{manifest.dataset_id}' declares the sha256 '{manifest.sha256}' for the file "
                        f"'{manifest.path}' and the file has '{digest}'."
                    ),
                )
            )
        if count != manifest.records_count:
            wrong_count.append(
                ManifestProblem(
                    kind="count",
                    message=(
                        f"The dataset '{manifest.dataset_id}' declares {manifest.records_count} records for the file "
                        f"'{manifest.path}' and the file has {count} records."
                    ),
                )
            )

    declared = {manifest.path.replace("\\", "/") for manifest in manifests}
    undeclared: list[ManifestProblem] = []
    for path in sorted((base / EVAL_DIR_RELATIVE).glob("*.jsonl")):
        relative = path.relative_to(base).as_posix()
        if relative not in declared:
            undeclared.append(
                ManifestProblem(
                    kind="undeclared",
                    message=(
                        f"The file '{relative}' is a JSONL file of '{EVAL_DIR_RELATIVE.as_posix()}' "
                        f"and it is not declared by any entry of the manifest."
                    ),
                )
            )

    return missing + wrong_hash + wrong_count + unreadable + undeclared


def verify_manifests(root: Path | None = None, manifest_path: Path | None = None) -> list[str]:
    """The problems the disk has against the manifest, one sentence per problem.

    Why it exists: the check in the gate calls this and refuses the build when the list is not empty. The order is
    the one of the contract: a declared file that does not exist, a declared file whose sha256 does not match, a
    declared file whose record count does not match and a JSONL file of `data/eval/` that no entry declares. An empty
    list means the manifest agrees with the disk.

    The sentences come from `manifest_problems`, which is the one implementation of the rule, so the check of the
    gate and any other caller see the same problems in the same order.

    A manifest file that is missing or that is not valid JSON is a problem of its own and comes back as the only
    sentence of the list, so that the caller can print it and fail without a stack trace.
    """
    return [problem.message for problem in manifest_problems(root=root, manifest_path=manifest_path)]


def render_manifests(manifests: Sequence[EvalDatasetManifest]) -> str:
    """The canonical text of the manifest file.

    Why it exists: the file that ships is written by this function, so it has one shape and writing it again does not
    change it. The text is JSON with two space indentation, the keys sorted, one entry per dataset sorted by
    `dataset_id` and a trailing newline.

    The shape of the file is the one the contract fixes: one object with the key `datasets` and one entry per
    dataset.
    """
    payload = {
        "datasets": [
            {
                "dataset_id": manifest.dataset_id,
                "path": manifest.path,
                "sha256": manifest.sha256,
                "records_count": manifest.records_count,
                "source": manifest.source,
                "labeling_version": manifest.labeling_version,
                "split_role": manifest.split_role,
                "scenario_seed": manifest.scenario_seed,
                "contamination_policy": manifest.contamination_policy,
                "notes": manifest.notes,
            }
            for manifest in sorted(manifests, key=lambda item: item.dataset_id)
        ]
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class FingerprintUpdate:
    """The entries with the fingerprints of the disk, and the sentences that say what moved.

    Why it exists: `update_fingerprints` gives back the sentences, and the caller also needs the entries with the
    new sha256 and the new record count to write the file. This record carries both, and it is frozen because the
    two of them are facts about a disk that was measured once. The caller reads `entries` to render the manifest
    and `messages` to say what moved.
    """

    entries: tuple[EvalDatasetManifest, ...]
    messages: tuple[str, ...]


def update_fingerprints(manifests: Sequence[EvalDatasetManifest], root: Path | None = None) -> FingerprintUpdate:
    """The sha256 and the record count of every entry recomputed from the disk, and what moved.

    Why it exists: when a dataset changes on purpose, the two measured values of its entry change with it, and the
    hand written fields must not. This function recomputes only `sha256` and `records_count` and never touches
    `split_role`, `source`, `labeling_version`, `scenario_seed`, `contamination_policy` or `notes`, because those are
    written by a person and reviewed.

    The caller receives a `FingerprintUpdate`. Its `entries` are the entries with the fingerprints of the disk and
    its `messages` are the sentences that say what moved; an empty tuple of messages means nothing moved. The
    sequence the caller passed is never changed, so a caller that keeps the tuple it read from the manifest and
    renders it writes the old values, and the caller that wants the new ones reads `entries`.

    An entry whose file does not exist keeps its values and is reported in the messages.
    """
    base = PROJECT_ROOT if root is None else Path(root)
    messages: list[str] = []
    entries: list[EvalDatasetManifest] = []

    for manifest in manifests:
        path = base / manifest.path
        if not path.is_file():
            messages.append(
                f"The dataset '{manifest.dataset_id}' declares the file '{manifest.path}' and the file does not "
                f"exist, so its sha256 and its record count were not recomputed."
            )
            entries.append(manifest)
            continue
        try:
            digest, count = fingerprint_dataset(path)
        except ManifestError as error:
            messages.append(
                f"The dataset '{manifest.dataset_id}' was not updated because its file could not be read: {error}"
            )
            entries.append(manifest)
            continue

        moved: list[str] = []
        if digest != manifest.sha256:
            moved.append(f"the sha256 changed from '{manifest.sha256}' to '{digest}'")
        if count != manifest.records_count:
            moved.append(f"the record count changed from {manifest.records_count} to {count}")
        if moved:
            messages.append(f"The dataset '{manifest.dataset_id}' moved: " + " and ".join(moved) + ".")

        entries.append(replace(manifest, sha256=digest, records_count=count))

    return FingerprintUpdate(entries=tuple(entries), messages=tuple(messages))


__all__ = [
    "EVAL_DIR_RELATIVE",
    "MANIFEST_PATH",
    "MANIFEST_RELATIVE",
    "SPLIT_ROLES",
    "EvalDatasetManifest",
    "FingerprintUpdate",
    "ManifestError",
    "ManifestProblem",
    "fingerprint_dataset",
    "load_manifests",
    "manifest_problems",
    "render_manifests",
    "update_fingerprints",
    "verify_manifests",
]
