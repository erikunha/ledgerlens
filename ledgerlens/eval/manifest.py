"""The manifest of the eval datasets: what each file is, how many records it has and what may be done with it.

Why it exists: the repository has six JSONL datasets under `data/eval/` and, until this module, no file that said
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
  when the evidence is not clean. One dataset of this repository carries the role `held_out` today, the labelled set
  of the blind reading, and the answer key of the generator that wrote it is not published and is not declared here,
  so no result over any other dataset of this repository may be presented as a generalization to unseen data.

The scan for an undeclared JSONL file looks at the files that sit directly in `data/eval/`. The folders below it hold
other artifacts with their own contract: the recording of the scenario `S01` lives in `data/eval/replay/s01/` and
declares its own files in its own manifest (ADR-014), so it is not a dataset of this manifest.

The path of an entry is relative to the root of the check and may not leave it. A path that is absolute or that
climbs out of the root with a `..` part is refused when the manifest is read, before the disk is touched. A path that
names a symlink inside the root and points outside of it is refused later, where the root is known: the path is
resolved and compared with the resolved root before the file is read. The two refusals together are the promise that
the manifest of a repository can never pin a file that lives outside it.

The path of an entry is also normalised once, when the manifest is read, and the same normalised form is used by the
read of the dataset, by the comparison with the manifest and by the scan of the folder. A path with a trailing slash
is therefore the path it names, and the two sides of the comparison can never disagree about the same file.

A file that the process cannot open and a file whose bytes are not valid UTF-8 are data problems and not crashes.
Every read of this module turns one of them into a `ManifestError` that names the file and the reason, so a data
problem is a sentence and never a traceback.

Two more rules keep the check from lying to the person who reads its log:

- **A value that enters a sentence is rendered so that it cannot lie.** A file name may hold a newline and an
  identifier may hold an escape, and a name that holds one prints a sentence of its own in the log of the check,
  where the reader would take it for the verdict of the check. Every value that comes from a file and enters a
  sentence goes through `safe_text`, which shows the characters that can lie as the two characters that name them
  and leaves the readable ones as they are.
- **A file that is not a regular file is refused before a byte of it is read.** A named pipe waits for a writer
  that may never come, and a gate that waits forever is a gate that is not a gate. Every file of this module is
  opened without blocking, and the kind of the file is read from the descriptor, so a named pipe, a device, a
  socket or a directory is refused with a sentence instead of a wait.

The rule that decides what is wrong between the manifest and the disk lives in this module and only here.
`manifest_problems` is that rule, `verify_manifests` gives its sentences and the check of the gate prints them.

The module also holds the guard of the tuning: `may_be_tuned_against` answers whether a dataset may be tuned
against and `require_tuning_dataset` refuses with a sentence when it may not. Only the datasets with the role
`tuning` may be tuned against, so a script that chooses a threshold reads a set nobody decided anything on only
by ignoring the guard. The guard takes the entries of the manifest as an argument and never reads the disk, so the
caller decides which root it is about.

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
import io
import json
import os
import stat
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields, replace
from pathlib import Path, PurePosixPath
from typing import Any

from ledgerlens.config import PROJECT_ROOT

MANIFEST_PATH = PROJECT_ROOT / "data" / "eval" / "datasets.json"

# The roles a dataset can carry. A dataset with the role `tuning` is what the thresholds, the prompts and the
# hyperparameters were chosen against. A dataset with the role `validation` may be scored but never tuned against. A
# dataset with the role `held_out` may be read only by the final scoring step.
SPLIT_ROLES: tuple[str, ...] = ("tuning", "validation", "held_out")

# The role of the datasets a tuning script may read. It is the only role that may: a dataset with the role
# `validation` may be scored but never tuned against, and a dataset with the role `held_out` may be read only by
# the final scoring step.
TUNING_ROLE = "tuning"

# The paths that are reserved for the held out set, relative to the root of the project and with forward slashes.
# Why the reservation lives in the code and not in the manifest: the manifest is data and a hand edit of it is one
# line of JSON away, while this constant is code that a reader reviews. A path that is reserved here stays
# refused whatever role the manifest gives it, so the role of the entry cannot unlock the file it names.
HELD_OUT_RESERVED_PATHS: tuple[str, ...] = ("data/eval/verification_heldout.jsonl",)

# The digests that are reserved for the held out set and for the answer key of the generator that wrote it.
# Why the digests and not only the paths: a path names a file and a copy of the file under another name has
# another path, so a reservation by path alone stops at the name. The bytes of the set and of the key are the
# same under any name, and the digest is what the manifest has to declare for the file to be a dataset at all:
# a copy that the check of the datasets accepts carries the digest of the set, and the digest is reserved here.
HELD_OUT_RESERVED_DIGESTS: tuple[str, ...] = (
    "e8dbcdfbc3f75eafbd3cd3c6d88da5641175cec93b4a48109073c80438924212",
    "39720b7261521b911f1b6fb969afb8a59e97c963dc1933c1539a0b19de55ca30",
)

# The folder of the datasets, relative to the project root, and the manifest file relative to it. They are relative
# so that a check over another root reads that root and not this one.
EVAL_DIR_RELATIVE = Path("data") / "eval"
MANIFEST_RELATIVE = Path("data") / "eval" / "datasets.json"

# A sha256 is 64 lowercase hexadecimal characters. Uppercase and a short digest are refused.
_SHA256_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdef")

# The characters that can lie in a log: a line break ends the sentence that holds them and an escape repaints
# the terminal of the person who reads it. They are shown as the two characters that name them.
_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


class ManifestError(Exception):
    """The manifest file or the disk does not agree with the contract, and the message says why.

    Why it exists: the reader of a manifest wants one sentence that names the file and the problem, not a stack
    trace. Every function of this module that can meet a bad file raises this, with that sentence in the message.
    """


class TuningRefusal(ManifestError):
    """A caller asked for a dataset that may not be tuned against, and the message says why.

    Why it exists: the rule of what a tuning script may read is the one thing that keeps a threshold from being
    chosen against a set that no decision of the repository was taken against. The refusal has its own class, so a
    caller can catch it without catching every error of the module, and the message names the dataset, the role it
    has and the role that is allowed.
    """


def _reason(error: Exception) -> str:
    """The reason of an error in plain words, so a sentence names the reason and not the class."""
    return getattr(error, "strerror", None) or str(error) or type(error).__name__


def safe_text(value: str | Path) -> str:
    """A value rendered so that it can carry neither a line break nor an escape into a sentence.

    Why it exists: the name of a file, the id of a dataset and the values of the manifest come from a file, and a
    name may hold a newline. A name that holds one prints a line of its own in the log of the check, and the
    reader of that log would read a forged sentence in it: a line that says the check passed, in the middle of a
    check that failed. Every value that enters a sentence of this module and of the check goes through this
    function, so no name can end a sentence that is not its own.

    The readable characters stay as they are, so a normal path stays a normal path. Only the characters that can
    lie are changed, and they are shown as the two characters that name them.
    """
    rendered: list[str] = []
    for character in str(value):
        escape = _ESCAPES.get(character)
        if escape is not None:
            rendered.append(escape)
        elif character.isprintable():
            rendered.append(character)
        else:
            code = ord(character)
            rendered.append(f"\\x{code:02x}" if code < 256 else f"\\u{code:04x}")
    return "".join(rendered)


def _what_it_is(mode: int) -> str:
    """The kind of a file in plain words, so a refusal says what the file is and not a mode number."""
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISFIFO(mode):
        return "a named pipe"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISBLK(mode):
        return "a block device"
    if stat.S_ISCHR(mode):
        return "a character device"
    return "a file of another kind"


def _open_regular(path: Path) -> int:
    """The descriptor of a file that can be read without blocking, or a `ManifestError` that says why not.

    Why it exists: a read of a named pipe waits for a writer that may never come, and a gate that waits forever
    is a gate that is not a gate. The descriptor is opened without blocking and the kind of the file is read from
    it, so a file that is not a regular file is refused before a single byte of it is read.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except (OSError, ValueError) as error:
        raise ManifestError(f"The file {safe_text(path)} could not be read: {_reason(error)}.") from error
    try:
        mode = os.fstat(descriptor).st_mode
    except OSError as error:
        os.close(descriptor)
        raise ManifestError(f"The file {safe_text(path)} could not be read: {_reason(error)}.") from error
    if not stat.S_ISREG(mode):
        os.close(descriptor)
        raise ManifestError(
            f"The file {safe_text(path)} could not be read: it is not a regular file but {_what_it_is(mode)}."
        )
    return descriptor


def _read_bytes(path: Path) -> bytes:
    """The bytes of a file, or a `ManifestError` that names the file and the reason.

    Why it exists: every read of this module goes through this door, so a file that the process cannot open is a
    sentence and never a traceback. The file is opened without blocking and refused when it is not a regular file,
    so a named pipe never makes the check wait for a writer that never comes.
    """
    descriptor = _open_regular(path)
    try:
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read()
    except OSError as error:
        raise ManifestError(f"The file {safe_text(path)} could not be read: {_reason(error)}.") from error
    finally:
        if descriptor != -1:
            os.close(descriptor)


def _decode_utf8(raw: bytes, path: Path) -> str:
    """The text of the bytes of a file, or a `ManifestError` that names the file and the reason.

    Why it exists: a dataset and a manifest are text, and bytes that are not valid UTF-8 are a data problem of the
    file, not a crash of the check.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManifestError(f"The file {safe_text(path)} is not valid UTF-8: {error}.") from error


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


def _count_records(text: Iterable[str], path: Path) -> int:
    """The number of records of a text, one per nonblank line that parses as a JSON object.

    Why it exists: the count of the manifest and the count of the disk are computed by the same rule, so they can
    be compared. A line that does not parse is a failure and not a record, and the failure names the file and the
    line.
    """
    count = 0
    for number, line in enumerate(text, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ManifestError(
                f"The line {number} of the file {safe_text(path)} is not valid JSON: {error.msg}."
            ) from error
        if not isinstance(record, dict):
            raise ManifestError(
                f"The line {number} of the file {safe_text(path)} is not a JSON object, so it is not a record."
            )
        count += 1
    return count


def fingerprint_dataset(path: Path) -> tuple[str, int]:
    """The sha256 of the bytes of the file and the number of records it holds.

    Why it exists: the manifest stores these two values and the check compares them with the disk. A record is a
    nonblank line that parses as a JSON object, and a line that does not parse is a failure and not a record, so a
    file that lost a line or gained a broken one cannot pass as the one the manifest describes.

    The file is opened without blocking and refused when it is not a regular file, so a named pipe inside the
    root is a sentence and not a wait that never ends.

    Raises `ManifestError` when the file does not exist, when the process cannot open it, when it is not a regular
    file, when its bytes are not valid UTF-8 or when a line of it does not parse as a JSON object. Every message
    names the file and the reason.
    """
    if not path.exists():
        raise ManifestError(f"The file {safe_text(path)} does not exist, so it has no fingerprint.")

    digest = hashlib.sha256()
    descriptor = _open_regular(path)
    try:
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        os.lseek(descriptor, 0, os.SEEK_SET)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            with io.TextIOWrapper(handle, encoding="utf-8") as text:
                count = _count_records(text, path)
    except UnicodeDecodeError as error:
        raise ManifestError(f"The file {safe_text(path)} is not valid UTF-8: {error}.") from error
    except OSError as error:
        raise ManifestError(f"The file {safe_text(path)} could not be read: {_reason(error)}.") from error
    finally:
        if descriptor != -1:
            os.close(descriptor)

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
            f"The entry {index} of the manifest {safe_text(path)} has the unknown field(s) "
            f"{', '.join(safe_text(name) for name in unknown)}."
        )
    missing = sorted(expected - {"notes"} - set(entry))
    if missing:
        raise ManifestError(
            f"The entry {index} of the manifest {safe_text(path)} is missing the field(s) "
            f"{', '.join(safe_text(name) for name in missing)}."
        )


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
            raise ManifestError(
                f"The field {name} of the entry {index} of the manifest {safe_text(path)} is not a string."
            )
    notes = entry.get("notes", "")
    if not isinstance(notes, str):
        raise ManifestError(f"The field notes of the entry {index} of the manifest {safe_text(path)} is not a string.")
    count = entry["records_count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ManifestError(
            f"The field records_count of the entry {index} of the manifest {safe_text(path)} is not an integer."
        )
    seed = entry["scenario_seed"]
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ManifestError(
            f"The field scenario_seed of the entry {index} of the manifest {safe_text(path)} is not an integer."
        )


def _check_dataset_id(dataset_id: str, path: Path) -> None:
    """Refuses a dataset id that holds a character that is not printable.

    Why it exists: the id of a dataset is a name, and a name that holds a line break or an escape can end a
    sentence in the log of the check and be read as a verdict of the check. The refusal happens when the manifest
    is read, before any disk access.
    """
    if not dataset_id.isprintable():
        raise ManifestError(
            f"The dataset_id '{safe_text(dataset_id)}' of the manifest {safe_text(path)} holds a character that is "
            f"not printable, and a dataset id may not hold one."
        )


def _check_path(dataset_id: str, declared: str, path: Path) -> str:
    """The path of an entry in the one normalised form the module uses, or a refusal that names the file.

    Why it exists: the path of an entry is resolved against the root of the check, and a path that is absolute or
    that climbs out of the root would make the check read a file that is not a dataset of the repository. The three
    refusals are lexical: they never touch the disk, so they hold for any root. A path that holds a null byte is
    refused here as well, because the operating system cannot name a file with one and the read of it would raise
    a ValueError that is not a sentence.

    The path comes back normalised, so the read of the dataset, the comparison with the manifest and the scan of
    the folder all speak of the same file and can never disagree about it.
    """
    if "\x00" in declared:
        raise ManifestError(
            f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} declares a path that holds a "
            f"null byte, and a file cannot be named with one."
        )
    if PurePosixPath(declared).is_absolute() or Path(declared).is_absolute():
        raise ManifestError(
            f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} declares the path "
            f"'{safe_text(declared)}', and the path of a dataset is relative to the root."
        )
    if ".." in PurePosixPath(declared).parts:
        raise ManifestError(
            f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} declares the path "
            f"'{safe_text(declared)}', and the path of a dataset may not leave the root with '..'."
        )
    return Path(declared).as_posix()


def _resolved_root(base: Path) -> Path:
    """The root of a check with every symlink of the path resolved, so two paths are compared like for like.

    Why it exists: the refusal of `_outside_the_root` compares a path with the root, and the comparison only means
    something when both of them are resolved.
    """
    resolved = _resolved(base)
    return base.absolute() if resolved is None else resolved


def _resolved(path: Path) -> Path | None:
    """The path with every symlink resolved, or None when the path cannot be resolved.

    Why it exists: a path that holds a null byte cannot be resolved at all, and the operating system says so with
    a ValueError. A path that cannot be resolved is not refused here: the read that follows fails with its own
    reason, and that reason is the honest one.
    """
    try:
        return path.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _under(base: Path, path: Path) -> bool:
    """Whether the path is inside the base.

    Why it exists: two paths are compared like for like only when both of them are resolved, and the comparison
    of a path with a base is a relative_to that fails when the path is somewhere else.
    """
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _outside_the_root(base: Path, resolved_base: Path, declared: str) -> Path | None:
    """The file a declared path points at when that file is outside the root, and None when it stays inside.

    Why it exists: the refusal of `_check_path` is lexical and never touches the disk, so it cannot see a symlink.
    A path that names a file inside the root may be a link that points outside of it, and the check would then read
    a file that is not a dataset of the repository. The root is known here, so the path is resolved and compared
    with the resolved root before the file is read.

    A path that cannot be resolved is not refused here: the read that follows fails with its own reason, and that
    reason is the honest one.
    """
    resolved = _resolved(base / declared)
    if resolved is None or _under(resolved_base, resolved):
        return None
    return resolved


def load_manifests(path: Path = MANIFEST_PATH) -> tuple[EvalDatasetManifest, ...]:
    """The entries of the manifest file, already validated.

    Why it exists: the manifest file is hand written and reviewed, so it can carry a mistake. This function refuses
    a file that is missing, that the process cannot open, that is not a regular file or whose bytes are not valid
    UTF-8, a file that is not JSON, an entry with a missing or an unknown field, a repeated `dataset_id`, a
    `dataset_id` that holds a character that is not printable, a `split_role` outside `SPLIT_ROLES`, a `sha256` that
    is not 64 lowercase hexadecimal characters, a negative `records_count` and a `path` that is absolute, that
    leaves the root with a `..` part or that holds a null byte. Every message names the file and the problem.

    Every field of the record is required in the file, `notes` apart: that one has a default of an empty string in the
    record, so an entry may leave it out. Without the other fields the entry does not say what the dataset is.

    The path of an entry comes back normalised, so the read of the dataset, the comparison with the manifest and the
    scan of the folder all speak of the same file.

    Raises `ManifestError` for any of those.
    """
    if not path.exists():
        raise ManifestError(f"The manifest {safe_text(path)} does not exist.")

    try:
        payload = json.loads(_decode_utf8(_read_bytes(path), path))
    except json.JSONDecodeError as error:
        raise ManifestError(f"The manifest {safe_text(path)} is not valid JSON: {error.msg}.") from error

    if not isinstance(payload, dict) or "datasets" not in payload:
        raise ManifestError(f"The manifest {safe_text(path)} does not have the key 'datasets'.")
    entries = payload["datasets"]
    if not isinstance(entries, list):
        raise ManifestError(f"The key 'datasets' of the manifest {safe_text(path)} is not a list of entries.")

    manifests: list[EvalDatasetManifest] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ManifestError(f"The entry {index} of the manifest {safe_text(path)} is not an object.")
        _check_fields(entry, path, index)
        _check_types(entry, path, index)

        dataset_id = entry["dataset_id"]
        if dataset_id in seen:
            raise ManifestError(
                f"The dataset_id '{safe_text(dataset_id)}' appears more than once in the manifest {safe_text(path)}."
            )
        seen.add(dataset_id)
        _check_dataset_id(dataset_id, path)

        declared = _check_path(dataset_id, entry["path"], path)

        split_role = entry["split_role"]
        if split_role not in SPLIT_ROLES:
            raise ManifestError(
                f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} has the split_role "
                f"'{safe_text(split_role)}', and the roles are {', '.join(SPLIT_ROLES)}."
            )

        sha256 = entry["sha256"]
        if len(sha256) != _SHA256_LENGTH or not set(sha256) <= _HEX_DIGITS:
            raise ManifestError(
                f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} has the sha256 "
                f"'{safe_text(sha256)}', and a sha256 is {_SHA256_LENGTH} lowercase hexadecimal characters."
            )

        if entry["records_count"] < 0:
            raise ManifestError(
                f"The dataset '{safe_text(dataset_id)}' of the manifest {safe_text(path)} has the records_count "
                f"{entry['records_count']}, and a count is not negative."
            )

        manifests.append(
            EvalDatasetManifest(
                dataset_id=dataset_id,
                path=declared,
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

    A manifest file that is missing, that the process cannot open, that is not valid UTF-8 or that is not valid JSON
    is a problem of its own and comes back as the only problem of the list, so that the caller can print it and fail
    without a stack trace.

    A declared path that resolves outside the root is a declared file that cannot be read: it comes back as the
    problem of the kind `unreadable` and the file it points at is never read.

    A manifest file that is outside the root is a problem of its own, of the kind `error`, and it is not read: the
    manifest follows the root, and a manifest that is a link to a file outside of the root would pin the files of
    one root to a file that is not a dataset of the repository.
    """
    base = PROJECT_ROOT if root is None else Path(root)
    resolved_base = _resolved_root(base)
    manifest_file = base / MANIFEST_RELATIVE if manifest_path is None else Path(manifest_path)
    if manifest_path is not None and not manifest_file.is_absolute():
        # A relative manifest path names a file of the root, the same way the argument of the check names one.
        manifest_file = base / manifest_file

    # The manifest follows the root: a check of another root that read the manifest of the repository would pin
    # the files of one root to the manifest of another, and a manifest that is a link to a file outside of the root
    # would do the same with a file that is not a dataset of the repository at all.
    resolved_manifest = _resolved(manifest_file)
    if resolved_manifest is not None and not _under(resolved_base, resolved_manifest):
        return [
            ManifestProblem(
                kind="error",
                message=(
                    f"The manifest {safe_text(manifest_file)} is outside the root {safe_text(base)}, "
                    f"so it was not read."
                ),
            )
        ]

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
        outside = _outside_the_root(base, resolved_base, manifest.path)
        if outside is not None:
            unreadable.append(
                ManifestProblem(
                    kind="unreadable",
                    message=(
                        f"The dataset '{safe_text(manifest.dataset_id)}' declares the file "
                        f"'{safe_text(manifest.path)}' and the file could not be read: the path "
                        f"'{safe_text(manifest.path)}' resolves to '{safe_text(outside)}', which is outside the root "
                        f"'{safe_text(base)}'."
                    ),
                )
            )
            continue
        if not path.exists():
            missing.append(
                ManifestProblem(
                    kind="missing",
                    message=(
                        f"The dataset '{safe_text(manifest.dataset_id)}' declares the file "
                        f"'{safe_text(manifest.path)}' and the file does not exist."
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
                        f"The dataset '{safe_text(manifest.dataset_id)}' declares the file "
                        f"'{safe_text(manifest.path)}' and the file could not be read: {error}"
                    ),
                )
            )
            continue
        if digest != manifest.sha256:
            wrong_hash.append(
                ManifestProblem(
                    kind="hash",
                    message=(
                        f"The dataset '{safe_text(manifest.dataset_id)}' declares the sha256 "
                        f"'{safe_text(manifest.sha256)}' for the file '{safe_text(manifest.path)}' and the file has "
                        f"'{digest}'."
                    ),
                )
            )
        if count != manifest.records_count:
            wrong_count.append(
                ManifestProblem(
                    kind="count",
                    message=(
                        f"The dataset '{safe_text(manifest.dataset_id)}' declares {manifest.records_count} records for "
                        f"the file '{safe_text(manifest.path)}' and the file has {count} records."
                    ),
                )
            )

    # The path of an entry was normalised when the manifest was read, so the two sides of this comparison speak of
    # the same file and can never disagree about it.
    declared = {manifest.path for manifest in manifests}
    undeclared: list[ManifestProblem] = []
    for path in sorted((base / EVAL_DIR_RELATIVE).glob("*.jsonl")):
        relative = path.relative_to(base).as_posix()
        if relative not in declared:
            undeclared.append(
                ManifestProblem(
                    kind="undeclared",
                    message=(
                        f"The file '{safe_text(relative)}' is a JSONL file of '{EVAL_DIR_RELATIVE.as_posix()}' "
                        f"and it is not declared by any entry of the manifest."
                    ),
                )
            )

    return missing + wrong_hash + wrong_count + unreadable + undeclared


def verify_manifests(root: Path | None = None, manifest_path: Path | None = None) -> list[str]:
    """The problems the disk has against the manifest, one sentence per problem.

    Why it exists: the check in the gate calls this and refuses the build when the list is not empty. The order is
    the one of the contract: a declared file that does not exist, a declared file whose sha256 does not match, a
    declared file whose record count does not match, a declared file that exists and cannot be read, and a JSONL file
    of `data/eval/` that no entry declares. An empty list means the manifest agrees with the disk.

    The sentences come from `manifest_problems`, which is the one implementation of the rule, so the check of the
    gate and any other caller see the same problems in the same order.

    A manifest file that is missing, that the process cannot open, that is not valid UTF-8 or that is not valid JSON
    is a problem of its own and comes back as the only sentence of the list, so that the caller can print it and
    fail without a stack trace.
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

    An entry whose file does not exist keeps its values and is reported in the messages. An entry whose path resolves
    outside the root keeps its values as well and is reported in the messages: the file it points at is not a dataset
    of the repository and is never read.
    """
    base = PROJECT_ROOT if root is None else Path(root)
    messages: list[str] = []
    entries: list[EvalDatasetManifest] = []
    resolved_base = _resolved_root(base)

    for manifest in manifests:
        path = base / manifest.path
        outside = _outside_the_root(base, resolved_base, manifest.path)
        if outside is not None:
            messages.append(
                f"The dataset '{safe_text(manifest.dataset_id)}' was not updated because its file could not be read: "
                f"the path '{safe_text(manifest.path)}' resolves to '{safe_text(outside)}', which is outside the root "
                f"'{safe_text(base)}'."
            )
            entries.append(manifest)
            continue
        if not path.exists():
            messages.append(
                f"The dataset '{safe_text(manifest.dataset_id)}' declares the file '{safe_text(manifest.path)}' and "
                f"the file does not exist, so its sha256 and its record count were not recomputed."
            )
            entries.append(manifest)
            continue
        try:
            digest, count = fingerprint_dataset(path)
        except ManifestError as error:
            messages.append(
                f"The dataset '{safe_text(manifest.dataset_id)}' was not updated because its file could not be read: "
                f"{error}"
            )
            entries.append(manifest)
            continue

        moved: list[str] = []
        if digest != manifest.sha256:
            moved.append(f"the sha256 changed from '{safe_text(manifest.sha256)}' to '{digest}'")
        if count != manifest.records_count:
            moved.append(f"the record count changed from {manifest.records_count} to {count}")
        if moved:
            messages.append(f"The dataset '{safe_text(manifest.dataset_id)}' moved: " + " and ".join(moved) + ".")

        entries.append(replace(manifest, sha256=digest, records_count=count))

    return FingerprintUpdate(entries=tuple(entries), messages=tuple(messages))


# --- the guard of the tuning --------------------------------------------------------------------------


def may_be_tuned_against(dataset_id: str, manifests: Sequence[EvalDatasetManifest]) -> bool:
    """Whether the dataset may be tuned against, given the entries of the manifest.

    Why it exists: the thresholds, the prompts and the hyperparameters of the repository were chosen against the
    datasets with the role `tuning` and against nothing else. A dataset with the role `validation` may be scored
    but never tuned against, and a dataset with the role `held_out` may be read only by the final scoring step. A
    dataset that no entry declares may not be tuned against either: the manifest is what says which file is which,
    so a file nobody declared is a file nobody may tune on.

    The entries are an argument and the disk is never read, so the caller decides which root it is about and the
    rule can be checked without a disk at all.
    """
    entry = next((manifest for manifest in manifests if manifest.dataset_id == dataset_id), None)
    return entry is not None and entry.split_role == TUNING_ROLE


def require_tuning_dataset(dataset_id: str, manifests: Sequence[EvalDatasetManifest]) -> EvalDatasetManifest:
    """The entry of the dataset when it may be tuned against, and a refusal when it may not.

    Why it exists: a script that tunes reads a dataset by name, and that door has to say no. The refusal names the
    dataset, the role it has and the rule it breaks, and it names the role that is allowed, so the reader of the
    log knows what to do next and does not have to read the source to find out.

    Raises `TuningRefusal` when the manifest does not declare the dataset or when its role is not `tuning`.
    """
    entry = next((manifest for manifest in manifests if manifest.dataset_id == dataset_id), None)
    if entry is None:
        raise TuningRefusal(
            f"The dataset '{safe_text(dataset_id)}' is not declared by the manifest, so it may not be tuned "
            f"against: only the datasets with the role '{TUNING_ROLE}' may be tuned against."
        )
    if entry.split_role != TUNING_ROLE:
        raise TuningRefusal(
            f"The dataset '{safe_text(dataset_id)}' has the role '{safe_text(entry.split_role)}' and may not be "
            f"tuned against: only the datasets with the role '{TUNING_ROLE}' may be tuned against."
        )
    return entry


def require_tuning_path(path: str | Path, manifests: Sequence[EvalDatasetManifest]) -> EvalDatasetManifest:
    """The entry of the dataset a path names, when it may be tuned against, and a refusal when it may not.

    Why it exists next to the guard of the name: a tuning script that opens a file by its path does not pass
    through the door of the name, and the door of the name was the only one. The path of the file of the dataset is
    the other way a script reaches the data, so it is the other way the rule has to hold.

    Why a path nobody declared is refused: the manifest is what says which file is which, so a file that no entry
    names is a file that nobody may tune on.

    Why a reserved path is refused before the manifest is even asked: the role of a dataset is a field of a JSON
    file, and a hand edit of that field is one line away, so a guard that reads the role of the entry alone can be
    unlocked by editing the data. The reservation lives in the code, where a reader reviews it, and it holds
    whatever role the manifest gives the path.

    Why a reserved digest is refused: a path names a file and a copy of the file under another name has another
    path, so the reservation by path alone stops at the name. The bytes are the same under any name, and the
    digest of the entry is what the check of the datasets compares with the file on the disk, so a copy that the
    check accepts carries the digest of the set and is refused here.

    Raises `TuningRefusal` when the path is reserved, when the digest of the entry is reserved, when no entry
    names the path, or when the entry that names it may not be tuned against.
    """
    wanted = Path(path).as_posix()
    entry = next((manifest for manifest in manifests if manifest.path == wanted), None)
    if entry is None:
        raise TuningRefusal(
            f"The path '{safe_text(wanted)}' is not declared by the manifest, so it may not be tuned against: only "
            f"the datasets with the role '{TUNING_ROLE}' may be tuned against."
        )
    if entry.split_role != TUNING_ROLE:
        raise TuningRefusal(
            f"The dataset '{safe_text(entry.dataset_id)}' has the role '{safe_text(entry.split_role)}' and may not be "
            f"tuned against: only the datasets with the role '{TUNING_ROLE}' may be tuned against."
        )
    if wanted in HELD_OUT_RESERVED_PATHS:
        raise TuningRefusal(
            f"The path '{safe_text(wanted)}' is reserved for the held out set, so it may not be tuned against "
            f"whatever role the manifest gives it: only the datasets with the role '{TUNING_ROLE}' may be tuned "
            f"against."
        )
    if entry.sha256 in HELD_OUT_RESERVED_DIGESTS:
        raise TuningRefusal(
            f"The dataset '{safe_text(entry.dataset_id)}' has the digest of the held out set or of the answer key "
            f"of the generator that wrote it, so it may not be tuned against under any name and with any role: "
            f"only the datasets with the role '{TUNING_ROLE}' may be tuned against."
        )
    return entry


__all__ = [
    "EVAL_DIR_RELATIVE",
    "HELD_OUT_RESERVED_PATHS",
    "MANIFEST_PATH",
    "MANIFEST_RELATIVE",
    "SPLIT_ROLES",
    "TUNING_ROLE",
    "EvalDatasetManifest",
    "FingerprintUpdate",
    "ManifestError",
    "ManifestProblem",
    "TuningRefusal",
    "fingerprint_dataset",
    "load_manifests",
    "manifest_problems",
    "may_be_tuned_against",
    "render_manifests",
    "require_tuning_dataset",
    "require_tuning_path",
    "safe_text",
    "update_fingerprints",
    "verify_manifests",
]
