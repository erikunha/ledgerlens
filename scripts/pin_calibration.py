#!/usr/bin/env python3
"""Rewrites the pin of the calibration of `ledgerlens/verify/thresholds.json` from the disk.

Why it exists: the calibration of the verifier is a number over a set of datasets, and without a pin nobody can
tell whether the datasets are still the ones the number came from. The pin says what the calibration was measured
over: the sha256 of the manifest of the datasets, the datasets with the role `tuning` that the sweep ran on, the
model that measured them and the sweep that chose the thresholds.

This script is the command that writes that pin, and the coordinator runs it at the end of the milestone, after the
held out set is declared: the manifest moves when a dataset is added, and the pin has to move with it. A pin that
did not move would be a number over a manifest that is not there anymore.

The file is edited, not rewritten: the pin is written inside the object `calibration` and the rest of the text of
the file stays byte for byte the same, because `ledgerlens/verify/checks.py` reads that file and a file that
changes its shape on every pin is a file that surprises the reader. The text is checked with the JSON parser
before it is written, so a file that would not parse is never written.

The script never decides what a threshold is. It writes what the calibration was measured over and nothing else.

Usage:

```bash
uv run python scripts/pin_calibration.py
```

Exit code 0 when the pin was written, 1 when it could not be written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.eval.manifest import (  # noqa: E402  (the path is set up before the import)
    MANIFEST_RELATIVE,
    TUNING_ROLE,
    ManifestError,
    TuningRefusal,
    load_manifests,
    require_tuning_path,
    safe_text,
    verify_manifests,
)
from ledgerlens.verify.checks import THRESHOLDS_PATH  # noqa: E402  (the path is set up before the import)
from ledgerlens.verify.nli import MODEL_ID  # noqa: E402  (the path is set up before the import)

__all__ = ["main"]

# The commit of the weights of the model on the Hugging Face hub. The model id names the repository and not the
# weights, and a repository moves: the revision is what pins the weights the sweep was measured with. It is the
# commit of the branch `main` of the repository, read on 2026-11-22, and it is the same one the local cache of the
# model holds.
NLI_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"

# The sweep of ADR-007 that chose the thresholds, and the command that recomputes it.
SWEEP_FILE = "docs/decisions/ADR-007-nli-verification.md"
SWEEP_SECTION = "Thresholds calibrated with live sentences"
SWEEP_SCRIPT = "scripts/sweep_nli_thresholds.py"
SWEEP_COMMAND = f"uv run python {SWEEP_SCRIPT}"


# --- the JSON text, edited and not rewritten ---------------------------------------------------------------


def _skip_string(text: str, index: int) -> int:
    """The index right after the string that starts at `index`.

    Why it exists: a brace or a comma inside a string is not a brace and not a comma, and the scan of the file has
    to know the difference or it ends the calibration at the wrong place.
    """
    index += 1
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == '"':
            return index + 1
        index += 1
    raise ValueError("the text holds a string that is not closed")


def _value_end(text: str, start: int) -> int:
    """The index right after the JSON value that starts at `start`.

    Why it exists: the pin is written by replacing the value of a key and by adding a key, and both need to know
    where the value of the file ends.
    """
    character = text[start]
    if character == '"':
        return _skip_string(text, start)
    if character in "{[":
        depth = 0
        index = start
        while index < len(text):
            character = text[index]
            if character == '"':
                index = _skip_string(text, index)
                continue
            if character in "{[":
                depth += 1
            elif character in "}]":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
        raise ValueError("the text holds an object that is not closed")
    index = start
    while index < len(text) and text[index] not in ",}]\n":
        index += 1
    return index


def _calibration_span(text: str) -> tuple[int, int]:
    """The span of the object `calibration`: the index of its brace and the index of the one that closes it.

    Why it exists: the pin is written inside that object and nowhere else, so the editor has to find it in the
    text of the file and not in a parsed copy of it.
    """
    marker = '"calibration"'
    if marker not in text:
        raise ValueError("the file does not hold the key 'calibration'")
    position = text.index(marker)
    brace = text.index("{", position)
    return brace, _value_end(text, brace) - 1


def _items(text: str, brace: int) -> list[tuple[str, int, int, int]]:
    """The items of the object that starts at `brace`: the key, where the key starts, where the value starts and
    where the value ends.

    Why it exists: a key of the calibration that is already there is replaced and a key that is not there is added
    at the end of the object, and both need the span of the item they touch.
    """
    items: list[tuple[str, int, int, int]] = []
    index = brace + 1
    while True:
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text) or text[index] == "}":
            return items
        if text[index] != '"':
            raise ValueError(f"the text holds an unexpected character at the position {index}")
        key_start = index
        key_end = _skip_string(text, index)
        key = str(json.loads(text[key_start:key_end]))
        index = key_end
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        if text[index] != ":":
            raise ValueError(f"the key '{key}' of the object has no value")
        index += 1
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        value_start = index
        index = _value_end(text, index)
        items.append((key, key_start, value_start, index))


def _indent_of(text: str, position: int) -> str:
    """The whitespace that starts the line of the position, so an added line looks like the lines around it."""
    line_start = text.rfind("\n", 0, position) + 1
    line = text[line_start:]
    return line[: len(line) - len(line.lstrip(" \t"))]


def _render(value: Any, indent: str) -> str:
    """The value as JSON, with the lines after the first one at the indentation of the key.

    Why it exists: the file of the thresholds is written by hand and its objects are indented by two spaces. A
    value that arrives with another indentation looks like it came from somewhere else.
    """
    head, *rest = json.dumps(value, indent=2, ensure_ascii=False).split("\n")
    return "\n".join([head, *(indent + line for line in rest)])


def _set_key(text: str, key: str, value: Any) -> str:
    """The text with the key of the object `calibration` set to the value.

    Why it exists: the pin is added to a file that a person reads and that the verifier reads, so the pin goes
    inside the object that is already there and the rest of the file stays the way it was written.
    """
    brace, closing = _calibration_span(text)
    items = _items(text, brace)

    for name, _key_start, value_start, value_end in items:
        if name == key:
            rendered = _render(value, _indent_of(text, value_start))
            return text[:value_start] + rendered + text[value_end:]

    if not items:
        raise ValueError("the object 'calibration' holds no item to copy the shape of")
    indent = _indent_of(text, items[-1][1])
    rendered = _render(value, indent)
    last_end = items[-1][3]
    line_start = text.rfind("\n", 0, closing) + 1
    tail = text[last_end:line_start]
    if "," not in tail:
        # the item before the new one has to end with a comma, or the file does not parse
        text = text[:last_end] + "," + text[last_end:]
        line_start += 1
    line = f'{indent}"{key}": {rendered}'
    return text[:line_start] + line + "\n" + text[line_start:]


# --- the pin ----------------------------------------------------------------------------------------------


def _pin(manifest_path: Path, manifests: Sequence[Any]) -> dict[str, Any]:
    """The pin of the calibration, computed from the disk.

    Why it exists: the pin is what the calibration was measured over, and the only honest source of it is the
    manifest that is on the disk now.

    Why a reserved path may not enter the pin: the pin names the material the calibration was measured over, and a
    dataset that may not be tuned against may not be named as tuning material, whatever role the manifest gives it.
    The pin is the record of the calibration, so a pin that named the held out set would be a record that says the
    thresholds were chosen over it.
    """
    # The same door as the sweep of the thresholds: the path of the file and the digest of the entry. A copy of
    # the set or of the answer key under another name carries the same digest, and the pin refuses to name it.
    for entry in manifests:
        if entry.split_role != TUNING_ROLE:
            continue
        require_tuning_path(entry.path, manifests)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "tuning_manifest_sha256": digest,
        "tuning_datasets": sorted(entry.dataset_id for entry in manifests if entry.split_role == TUNING_ROLE),
        "nli_model": {"model": MODEL_ID, "revision": NLI_REVISION},
        "sweep_log": {
            "file": SWEEP_FILE,
            "section": SWEEP_SECTION,
            "script": SWEEP_SCRIPT,
            "command": SWEEP_COMMAND,
        },
    }


def _write(path: Path, text: str) -> None:
    """The text written over the file, without ever writing through a link.

    Why it exists: the text goes to a temporary file of the same folder and is moved over the file with
    `os.replace`, which renames a file and never writes through a link.
    """
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".thresholds.json.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the script. The exit code is the answer."""
    parser = argparse.ArgumentParser(
        description="Rewrites the pin of the calibration of the thresholds from the manifest of the disk.",
    )
    parser.add_argument("--root", default=str(ROOT), help="the root the relative paths resolve against")
    parser.add_argument(
        "--manifest",
        default=None,
        help="the manifest file to read. The default is the one of the root",
    )
    parser.add_argument("--thresholds", default=str(THRESHOLDS_PATH), help="the file of the thresholds to write")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"pin_calibration: the root {safe_text(args.root)} cannot be resolved: {exc}", file=sys.stderr)
        return 1

    manifest_path = root / MANIFEST_RELATIVE if args.manifest is None else Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    thresholds_path = Path(args.thresholds)
    if not thresholds_path.is_absolute():
        thresholds_path = root / thresholds_path

    try:
        manifests = load_manifests(manifest_path)
    except (ManifestError, OSError, ValueError, TuningRefusal) as exc:
        print(f"pin_calibration: the manifest cannot be read: {safe_text(exc)}", file=sys.stderr)
        return 1

    for problem in verify_manifests(root, manifest_path=manifest_path):
        print(f"pin_calibration: the manifest does not agree with the disk: {problem}", file=sys.stderr)

    try:
        original = thresholds_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"pin_calibration: the thresholds cannot be read: {safe_text(exc)}", file=sys.stderr)
        return 1

    try:
        pin = _pin(manifest_path, manifests)
    except TuningRefusal as exc:
        print(f"pin_calibration: {safe_text(exc)}", file=sys.stderr)
        return 1
    text = original
    for key, value in pin.items():
        try:
            text = _set_key(text, key, value)
        except ValueError as exc:
            print(f"pin_calibration: the key '{key}' could not be written: {exc}", file=sys.stderr)
            return 1

    try:
        written = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"pin_calibration: the file would not be valid JSON: {exc.msg}. It was not written.", file=sys.stderr)
        return 1
    calibration = written.get("calibration") if isinstance(written, dict) else None
    if not isinstance(calibration, dict) or any(calibration.get(key) != value for key, value in pin.items()):
        print("pin_calibration: the pin would not be in the file after the write. It was not written.", file=sys.stderr)
        return 1

    if text == original:
        print(f"pin_calibration: the pin of {safe_text(thresholds_path)} is already the one of the disk")
    else:
        try:
            _write(thresholds_path, text)
        except OSError as exc:
            print(f"pin_calibration: the thresholds cannot be written: {safe_text(exc)}", file=sys.stderr)
            return 1
        print(f"pin_calibration: the pin of {safe_text(thresholds_path)} was written")

    before = json.loads(original).get("calibration", {})
    for key, value in pin.items():
        if key not in before:
            print(f"  {key}: added")
        elif before[key] == value:
            print(f"  {key}: unchanged")
        else:
            print(f"  {key}: changed from {json.dumps(before[key], ensure_ascii=False)} to {json.dumps(value)}")
    print(f"  the manifest measured: {safe_text(manifest_path)} ({pin['tuning_manifest_sha256']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
