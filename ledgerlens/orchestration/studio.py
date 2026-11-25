"""The door of the studio: the flag of the deployment and the experiment that was registered before it ran.

Why the flag is off in the shipped configuration: ADR-P007 is a red line. The runtime stays a single agent with a
deterministic verifier until a paired comparison measures a gain, and a flag that is on by default would make every
number of the repository a number of a multi-agent system.

Why the flag alone does not open the studio: a flag that opens a variant that was never registered is a variant whose
set, denominator and rule nobody wrote down. The studio opens only for an experiment that is registered before it
runs, and the refusal names the experiment that is missing (SC-002).

Why the manifest of the comparison is read and not trusted: the file is the registration, and a registration that a
caller may rewrite after the run is not a registration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledgerlens.config import PROJECT_ROOT, Settings

__all__ = [
    "COMPARISON_RELATIVE",
    "StudioRefused",
    "open_studio",
    "studio_manifest",
]

# The manifest of the comparison of the studio, relative to the root of the project. It is the file that was
# registered before the comparison ran, and it is registered in the manifest of the datasets with the role
# `held_out`.
COMPARISON_RELATIVE = Path("data") / "runtime" / "orchestration" / "comparison.json"


class StudioRefused(Exception):
    """The studio may not run, and the message says why."""


def studio_manifest(path: Path | None = None) -> dict[str, Any]:
    """The manifest of the registered experiment, and a refusal when there is no registered experiment.

    Why the manifest is read as the records it is: the file holds one record per line, so that the manifest of the
    datasets can count its records and pin its digest like the records of every other dataset.
    """
    target = path if path is not None else PROJECT_ROOT / COMPARISON_RELATIVE
    if not target.is_file():
        raise StudioRefused(
            f"no experiment of the studio is registered: the file {COMPARISON_RELATIVE} does not exist, and a studio "
            "that was not registered before it ran is not an experiment"
        )
    records: list[dict[str, Any]] = []
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise StudioRefused(
                f"the line {number} of the manifest of the comparison is not a record: {error}"
            ) from error
        if not isinstance(record, dict):
            raise StudioRefused(f"the line {number} of the manifest of the comparison is not a record")
        records.append(record)
    return {"records": records, "path": str(target)}


def open_studio(settings: Settings, *, path: Path | None = None) -> dict[str, Any]:
    """The manifest of the experiment the studio may run, and a refusal when it may not.

    Why the flag is checked before the manifest is read: a deployment that did not open the flag has no experiment
    to run, and reading the file of the comparison for nothing is a read that can only leak.
    """
    if not settings.orchestration_studio:
        raise StudioRefused(
            "the flag of the studio is off in the shipped configuration, so the runtime stays a single agent with "
            "the deterministic verifier (ADR-P007)"
        )
    manifest = studio_manifest(path)
    experiments = [record for record in manifest["records"] if record.get("section") == "experiment"]
    if not experiments:
        raise StudioRefused(
            "the manifest of the comparison declares no experiment, so there is nothing for the studio to run"
        )
    return manifest
