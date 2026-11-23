#!/usr/bin/env python3
"""Recomputes the sweep of ADR-007 over the datasets with the role `tuning` and prints the thresholds it chooses.

Why it exists: the thresholds of `ledgerlens/verify/thresholds.json` were chosen over a sweep, and a threshold
without the sweep that chose it is a number without a measurement. This script does the sweep again, with the real
NLI model, and prints the table and the thresholds the rule of ADR-007 chooses: no false `supported` and no false
`contradicted` over the two sets, then the highest accuracy, and on a tie the middle of the plateau.

The script is slow and it is not part of the gate: it needs the real model, about 740 MB of weights, and the gate
runs offline and without a key. It is run by hand, before a threshold is chosen, and it is run again by whoever
wants to know that the thresholds still follow the rule.

Three refusals, and each of them is a sentence with an exit code that is not zero:

- the manifest of the disk is not the one the calibration names, and the sentence names the two hashes that
  disagree: a sweep over a manifest that moved measures something else;
- a dataset whose role is not `tuning` is asked for: the guard of `ledgerlens/eval/manifest.py` refuses it, so a
  held out set can never be read by a script that chooses a threshold;
- a dataset the manifest does not declare is asked for: the same guard refuses it.

The model that cannot be loaded is a sentence and not a pass: an unavailable verification is not a measurement, and
the script exits with a code that is not zero.

The script never writes the calibration. It prints the thresholds the rule chooses and the person who ran it
decides whether they go into `ledgerlens/verify/thresholds.json`.

Usage:

```bash
uv run python scripts/sweep_nli_thresholds.py
uv run python scripts/sweep_nli_thresholds.py --dataset verification_set
```

Exit code 0 when the sweep ran, 1 when the run refused, 2 when the model could not be measured with.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import offline  # noqa: E402  (the path is set up before the import)
from ledgerlens.eval.manifest import (  # noqa: E402  (the path is set up before the import)
    MANIFEST_RELATIVE,
    TUNING_ROLE,
    ManifestError,
    TuningRefusal,
    load_manifests,
    require_tuning_dataset,
    require_tuning_path,
    safe_text,
)
from ledgerlens.verify.checks import THRESHOLDS_PATH  # noqa: E402  (the path is set up before the import)
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli  # noqa: E402  (the path is set up before the import)
from ledgerlens.verify.sweep import (  # noqa: E402  (the path is set up before the import)
    NliCase,
    SweepRow,
    nli_cases,
    pick_thresholds,
    score_cases,
    sweep_rows,
)

__all__ = ["main"]

# The exit code of a run that could not measure anything: the model was not there.
NO_MODEL = 2


def _digest(path: Path) -> str:
    """The sha256 of the bytes of a file.

    Why it exists: the pin of the calibration is the digest of the manifest file, and the sweep compares the digest
    of the manifest of the disk with the one the calibration names. The digest is of the bytes of the file, the same
    way `fingerprint_dataset` digests the bytes of a dataset.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refuse(message: str) -> int:
    """A refusal: one sentence on the error output and an exit code that is not zero."""
    print(f"sweep_nli_thresholds: {message}", file=sys.stderr)
    return 1


def _compress(rows: Sequence[SweepRow], value) -> list[tuple[str, SweepRow]]:
    """The rows of a table, with the range of the thresholds that give the same numbers.

    Why it exists: the table of ADR-007 shows a range where the numbers do not move, because a reader of a sweep
    wants to see the plateau and not seventy lines that repeat it.
    """
    compressed: list[tuple[str, SweepRow]] = []
    for row in rows:
        if compressed and _metrics(compressed[-1][1]) == _metrics(row):
            first = compressed[-1][0].split(" to ")[0]
            compressed[-1] = (f"{first} to {value(row)}", compressed[-1][1])
        else:
            compressed.append((f"{value(row)}", row))
    return compressed


def _metrics(row: SweepRow) -> tuple:
    """The numbers of a row of the sweep, the ones that decide whether the row is the same as the one before."""
    return (row.accuracy, row.false_supported, row.false_contradicted, tuple(sorted(row.by_set.items())))


def _print_table(title: str, rows: Sequence[SweepRow], sets: Sequence[str], value) -> None:
    """The table of the sweep, one line per range of thresholds that gives the same numbers."""
    header = f"| {title} | accuracy | false supported | false contradicted | " + " | ".join(sets) + " |"
    print(header)
    print("|---" * (len(sets) + 4) + "|")
    for label, row in _compress(rows, value):
        numbers = " | ".join(f"{row.by_set[name]:.3f}" for name in sets)
        print(
            f"| {label} | {row.accuracy:.3f} | {row.false_supported} | {row.false_contradicted} | {numbers} |"
        )


def _sets_of(cases: Sequence[NliCase]) -> list[str]:
    """The names of the sets of the cases, in the order they come."""
    names: list[str] = []
    for case in cases:
        if case.set_name not in names:
            names.append(case.set_name)
    return names


def _calibration(path: Path) -> dict:
    """The calibration of the thresholds file, or an empty object when the file does not hold one.

    Why it exists: the pin of the calibration is what says which manifest the sweep may read, and the file is read
    here so a run over another calibration can be told apart from a run over the one of the repository.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    calibration = payload.get("calibration")
    return calibration if isinstance(calibration, dict) else {}


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the sweep. The exit code is the answer."""
    parser = argparse.ArgumentParser(
        description="Recomputes the sweep of ADR-007 over the datasets with the role `tuning`.",
    )
    parser.add_argument("--root", default=str(ROOT), help="the root the relative paths resolve against")
    parser.add_argument(
        "--manifest",
        default=None,
        help="the manifest file to read. The default is the manifest of the root",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="the dataset to sweep over. It may be repeated. The default is every dataset of the role `tuning`",
    )
    parser.add_argument(
        "--thresholds",
        default=str(THRESHOLDS_PATH),
        help="the file of the thresholds that holds the calibration. The default is the one of the repository",
    )
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return _refuse(f"the root {safe_text(args.root)} cannot be resolved: {exc}")

    thresholds_path = Path(args.thresholds)
    if not thresholds_path.is_absolute():
        thresholds_path = root / thresholds_path

    manifest_path = root / MANIFEST_RELATIVE if args.manifest is None else Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    try:
        manifests = load_manifests(manifest_path)
    except (ManifestError, OSError, ValueError) as exc:
        return _refuse(f"the manifest cannot be read: {exc}")

    # The first refusal: the manifest of the disk is not the one the calibration was measured over.
    calibration = _calibration(thresholds_path)
    pinned = calibration.get("tuning_manifest_sha256")
    if not isinstance(pinned, str) or not pinned:
        return _refuse(
            "the calibration does not name the sha256 of the manifest it was measured over, so the sweep cannot "
            "know whether it reads the same datasets. Write the pin with `python scripts/pin_calibration.py`."
        )
    digest = _digest(manifest_path)
    if digest != pinned:
        return _refuse(
            f"the manifest of the disk has the sha256 '{digest}' and the calibration names the manifest '{pinned}': "
            "the sweep would measure something else. Write the pin with `python scripts/pin_calibration.py`."
        )

    # The second and the third refusals: the guard of the manifest, for the datasets the caller names.
    chosen = list(args.dataset)
    if not chosen:
        chosen = sorted(entry.dataset_id for entry in manifests if entry.split_role == TUNING_ROLE)
    for dataset_id in chosen:
        try:
            entry = require_tuning_dataset(dataset_id, manifests)
            # The door of the path: the role of an entry is a field of a JSON file, and the reservation of the
            # held out set lives in the code, so the path is asked as well.
            require_tuning_path(entry.path, manifests, root)
        except TuningRefusal as exc:
            return _refuse(str(exc))

    # The model has to be the real one: offline mode replaces it with the stand-in, which measures word rules.
    if offline():
        return _refuse(
            "the sweep needs the real NLI model and offline mode replaces it with the stand-in. Run it without "
            "LEDGERLENS_OFFLINE=1."
        )
    missing = [name for name in ("transformers", "torch") if importlib.util.find_spec(name) is None]
    if missing:
        return _refuse(
            f"the real NLI model needs {', '.join(missing)}: install the `verify` extra (uv sync --extra verify)."
        )

    try:
        cases = nli_cases(root, tuple(entry for entry in manifests if entry.dataset_id in chosen))
    except TuningRefusal as exc:
        return _refuse(str(exc))
    if not cases:
        return _refuse("the datasets with the role `tuning` hold no case that goes to the NLI model.")
    sets = _sets_of(cases)
    print(f"the sweep over {len(cases)} case(s) of {len(sets)} set(s) with the role `{TUNING_ROLE}`")
    for name in sets:
        count = sum(1 for case in cases if case.set_name == name)
        print(f"  {name}: {count} case(s)")
    print(f"the model: {MODEL_ID}")
    print(f"the manifest: {safe_text(manifest_path)} ({digest})")

    nli = HuggingFaceNli(MODEL_ID)
    try:
        scores = score_cases(cases, nli)
    except Exception as exc:  # the model may be missing, unreachable or broken: it is a sentence and not a pass
        print(f"sweep_nli_thresholds: the NLI model could not be measured with: {safe_text(exc)}", file=sys.stderr)
        return NO_MODEL

    scored = [(case.label, score) for case, score in zip(cases, scores, strict=True)]
    rows = sweep_rows(cases, scores)
    try:
        entailment, contradiction = pick_thresholds(scored)
    except ValueError as exc:
        return _refuse(str(exc))

    print()
    _print_table(
        f"entailment_min (contradiction_min {contradiction})",
        [row for row in rows if row.contradiction_min == contradiction],
        sets,
        lambda row: row.entailment_min,
    )
    print()
    _print_table(
        f"contradiction_min (entailment_min {entailment})",
        [row for row in rows if row.entailment_min == entailment],
        sets,
        lambda row: row.contradiction_min,
    )
    print()
    print(f"the thresholds the rule chooses: entailment_min {entailment} and contradiction_min {contradiction}")
    print("the script writes nothing: the person who ran it decides whether the thresholds change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
