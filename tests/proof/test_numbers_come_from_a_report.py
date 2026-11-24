"""The numbers of the artifact: every number is in the report it names, and a number that is not fails the build.

What they guarantee, and why: every number of the artifact is present in the report that the artifact names,
with the path and the digest of that report, and the build fails when a number is not in the report, because
a number typed by a person is a claim and not a measurement.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from ledgerlens.proof.numbers import NumberNotInReport, number_from_report

REPORT = "data/eval/report_heldout.json"


def test_every_number_of_the_artifact_is_present_in_the_report_it_names(root) -> None:
    """The accuracy of the verifier over the held out set, read from the report of the measurement."""
    number = number_from_report("heldout_accuracy", root / REPORT, "accuracy.value", root=root)

    assert number.value == Decimal("0.500")
    assert number.report_path == REPORT
    assert number.report_digest == hashlib.sha256((root / REPORT).read_bytes()).hexdigest()


def test_a_number_that_is_not_in_the_report_fails_the_build(root) -> None:
    """The build refuses a number the report does not carry, with the name of the key."""
    with pytest.raises(NumberNotInReport, match="accuracy.of_nothing"):
        number_from_report("nothing", root / REPORT, "accuracy.of_nothing", root=root)
