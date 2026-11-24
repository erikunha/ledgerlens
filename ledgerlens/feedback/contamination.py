"""The contamination check: a case of another split never enters a training set, not even under an alias.

Why an identifier is not enough: a case of the held out set that enters a training set under another
identifier would pass a check that compares identifiers, and the holdout would stop being a holdout without
anyone seeing it. The check compares the content of the case, with the digest of the case of the manifest of
the datasets, so a case that is the same case with another name is refused with the name of the case and the
name of the alias.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ledgerlens.eval.manifest import case_digest

__all__ = ["ContaminationError", "assert_no_contamination"]


class ContaminationError(ValueError):
    """The training set holds a case of another split, and the message names the case and the alias."""


def assert_no_contamination(
    cases: Iterable[Mapping[str, Any]], held_out_cases: Iterable[Mapping[str, Any]]
) -> None:
    """The refusal of a training set that holds a case of the held out set, under any identifier.

    The comparison is the comparison of the content of the cases, and a match is a refusal whether the
    identifier is the same or an alias.
    """
    held = {case_digest(case): str(case.get("id", "")) for case in held_out_cases}
    for case in cases:
        digest = case_digest(case)
        if digest in held:
            case_id = str(case.get("id", ""))
            raise ContaminationError(
                f"the case {case_id} is the case {held[digest]} of the held out set under an alias"
            )
