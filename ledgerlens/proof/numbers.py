"""The numbers of the artifact: every number comes from a report of the repository, with its digest.

Why a number typed by a person is a claim and not a measurement: the build reads the report, takes the number
and writes the path and the digest of the report next to it, and a number that is not in the report fails the
build. That is the same rule the repository follows for the reports of the evaluation, and it is what keeps an
artifact from drifting away from the code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

__all__ = ["Number", "NumberNotInReport", "number_from_report"]


class NumberNotInReport(ValueError):
    """The number the artifact asks for is not in the report it names, and the build fails."""


@dataclass(frozen=True)
class Number:
    """One number of the artifact: the value, the report it came from and the digest of that report."""

    name: str
    value: Decimal
    report_path: str
    report_digest: str


def _read(path: Path, key: str) -> Any:
    """The value of one key of the report, read from the disk, or the failure of the build."""
    data = json.loads(path.read_text(encoding="utf-8"))
    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise NumberNotInReport(f"the number {key!r} is not in the report {path}")
        value = value[part]
    return value


def number_from_report(name: str, report_path: Path, key: str, *, root: Path) -> Number:
    """The number of the artifact, read from the report it names, with the path and the digest of the report.

    The value of the number is the value of the key of the report, read at the moment of the build, and the
    digest is the digest of the bytes of the report on the disk. A number that is not in the report fails the
    build with the name of the key and the path of the report.
    """
    value = _read(report_path, key)
    return Number(
        name=name,
        value=Decimal(str(value)),
        report_path=str(report_path.relative_to(root)),
        report_digest=hashlib.sha256(report_path.read_bytes()).hexdigest(),
    )
