"""The training set: only the records of the tier gold, and only the ones whose permission is training.

Why the tier and the permission are the two conditions of the door: the tier says how much the repository
trusts a record, and the permission says what the record may be used for. A record of the tier gold whose
permission is an evaluation is a record the reviewer measured and did not release for training, and it never
enters a training set, whatever its tier. A training set that mixed the two conditions would be a set that
trains on what it was only allowed to read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ledgerlens.feedback.record import FeedbackRecord
from ledgerlens.feedback.tiers import GOLD

__all__ = ["TrainingSet", "build_training_set"]


@dataclass(frozen=True)
class TrainingSet:
    """The records of the tier gold whose permission is training, with the digest of the set.

    The digest covers the content of the records, so a set whose records moved is a set whose digest moved,
    and the comparison of two sets is the comparison of two digests.
    """

    records: tuple[FeedbackRecord, ...]
    digest: str


def build_training_set(records: Iterable[FeedbackRecord], *, tiers: Mapping[str, str]) -> TrainingSet:
    """The training set of the records: only the tier gold, and only the permission of training.

    The tier of a record comes from the tiers of the loop, computed with the deterministic verdict and the
    second reader, and never from the record itself, because a record that declared its own tier would be a
    record that promotes itself.
    """
    kept = tuple(
        record
        for record in records
        if tiers.get(record.record_id) == GOLD and record.permission == "training"
    )
    canonical = json.dumps([record.to_dict() for record in kept], sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return TrainingSet(records=kept, digest=digest)
