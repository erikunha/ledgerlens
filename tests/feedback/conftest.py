"""The shared factory of the feedback records of the tests.

Why a factory: every test of the loop starts from a record that is valid, over a bundle of the published
catalog, and the variants of the record (the tier, the permission, the source) are one argument away. The
bundle of the factory is a bundle of the published catalog, so the deterministic gate of the tests runs over
the real evidence of the repository.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.feedback.record import FeedbackRecord
from ledgerlens.replay.bundle import bundle_digest


def make_record(**overrides) -> FeedbackRecord:
    """A valid record over the bundle s02 of the published catalog, with the fields a test may override."""
    fields = {
        "record_id": "FR-0001",
        "bundle": "data/eval/replay/s02",
        "bundle_digest": bundle_digest(Path("data/eval/replay/s02")),
        "catalog": "replay",
        "claim_id": "CL3",
        "failure": "the answer states the deadline of the dispute and the evidence does not carry it",
        "corrected_value": Decimal("12.50"),
        "evidence_refs": ("TX:1001",),
        "reviewer": "erik",
        "reviewer_role": "maintainer",
        "source": "catalog",
        "permission": "training",
    }
    fields.update(overrides)
    return FeedbackRecord(**fields)


@pytest.fixture
def record_factory():
    """The factory of the feedback records, for the tests that need a variant of the valid record."""
    return make_record


@pytest.fixture
def record() -> FeedbackRecord:
    """The valid record of the tests, over the bundle s02 of the published catalog."""
    return make_record()
