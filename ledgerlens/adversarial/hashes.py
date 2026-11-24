"""The hash of a fixture: what makes an exercise of the laboratory reproducible.

Why it exists: an exercise of the laboratory is the attack it holds, and a fixture that changed under the same
exercise id is a different attack wearing the name of the first one. The hash of the fixture is what makes the
exercise reproducible: the list of the exercises names the fixture, and the record of the hashes says which
bytes of it the exercise ran.

Why the record of the hashes is a file of the repository: the record is data, like the list of the exercises,
and a test recomputes the hash of every fixture and refuses when the record and the bytes disagree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["HASHES_FILE", "check_hashes", "compute_hashes", "fixture_hash", "recorded_hashes", "write_hashes"]

# The file of the record of the hashes, beside the fixtures of the exercises.
HASHES_FILE = "hashes.json"


def fixture_hash(path: Path) -> str:
    """The sha256 of the bytes of a fixture: the hash that makes the exercise reproducible."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compute_hashes(fixtures_dir: Path) -> dict[str, str]:
    """The hash of every fixture of the folder, by the name of the file."""
    fixtures_dir = Path(fixtures_dir)
    return {
        path.name: fixture_hash(path)
        for path in sorted(fixtures_dir.glob("*.json"))
        if path.name != HASHES_FILE
    }


def write_hashes(fixtures_dir: Path) -> dict[str, str]:
    """Writes the record of the hashes of the folder, and returns it."""
    hashes = compute_hashes(fixtures_dir)
    target = Path(fixtures_dir) / HASHES_FILE
    target.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashes


def recorded_hashes(fixtures_dir: Path) -> dict[str, str]:
    """The record of the hashes of the folder, as it was written."""
    target = Path(fixtures_dir) / HASHES_FILE
    if not target.is_file():
        return {}
    return {str(name): str(digest) for name, digest in json.loads(target.read_text(encoding="utf-8")).items()}


def check_hashes(fixtures_dir: Path) -> list[str]:
    """The differences between the record of the hashes and the bytes of the fixtures, one line each.

    Why the check exists: a fixture that changed without the record moving is a fixture whose exercise is not
    reproducible anymore, and the laboratory that ran it would measure an attack that is not the one the list
    names.
    """
    recorded = recorded_hashes(fixtures_dir)
    computed = compute_hashes(fixtures_dir)
    lines: list[str] = []
    for name in sorted(set(recorded) | set(computed)):
        if name not in recorded:
            lines.append(f"the fixture {name} has no recorded hash")
        elif name not in computed:
            lines.append(f"the record names the fixture {name} and the file is not in the folder")
        elif recorded[name] != computed[name]:
            lines.append(f"the fixture {name} changed and the record of the hashes did not move")
    return lines
