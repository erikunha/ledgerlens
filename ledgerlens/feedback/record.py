"""The feedback record: a published failure, named with its bundle, its claim, its evidence and its verdict.

Why a record names the bundle and the digest of the bundle: a record without the digest of its source is a
record whose evidence cannot be found again, and the digest is what lets a reader open the published catalog
and check the record against the bytes of the bundle. The record names the catalog of the bundle, because the
two catalogs are not the same kind of thing: the catalog of the scripted model is reproducible byte for byte,
and the catalog of a real model is not, under ADR-075.

Why a corrected amount is a `Decimal`: a correction that is a money value is compared with the value of the
ledger, and the comparison is exact. A float would make the comparison a comparison of roundings.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

__all__ = ["CATALOGS", "PERMISSIONS", "FeedbackRecord", "RecordError"]

CATALOGS = ("replay", "replay-real")
PERMISSIONS = ("training", "evaluation")

# The labels the verifier of the repository gives, and the only ones an NLI label may carry.
_LABELS = ("supported", "contradicted", "not_enough_evidence")


class RecordError(ValueError):
    """The record is not valid, and the message names the field that is wrong."""


@dataclass(frozen=True)
class FeedbackRecord:
    """One failure of a published bundle, with the correction and the evidence that backs it.

    The verdict of the record is not a field of the record: it is computed by the deterministic gate over the
    published evidence of the bundle, and nothing a model said fills it. The label of the NLI model may travel
    with the record, and it is a proposal that the gate may confirm or refuse.
    """

    record_id: str
    bundle: str
    bundle_digest: str
    catalog: str
    claim_id: str
    failure: str
    corrected_value: Decimal | str
    evidence_refs: tuple[str, ...]
    reviewer: str
    reviewer_role: str
    source: str
    permission: str
    nli_label: str | None = None
    model_suggested: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "bundle",
            "bundle_digest",
            "claim_id",
            "failure",
            "reviewer",
            "reviewer_role",
            "source",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RecordError(f"the field {field_name} is missing or empty")
        if self.catalog not in CATALOGS:
            raise RecordError(f"the field catalog is {self.catalog!r} and the catalogs are {CATALOGS}")
        if self.permission not in PERMISSIONS:
            raise RecordError(f"the field permission is {self.permission!r} and the permissions are {PERMISSIONS}")
        if isinstance(self.corrected_value, str) and not self.corrected_value.strip():
            raise RecordError("the field corrected_value is empty")
        if not isinstance(self.corrected_value, (Decimal, str)):
            raise RecordError("the field corrected_value is neither a Decimal nor a text")
        if not isinstance(self.evidence_refs, tuple):
            raise RecordError("the field evidence_refs is not a tuple")
        if self.nli_label is not None and self.nli_label not in _LABELS:
            raise RecordError(f"the field nli_label is {self.nli_label!r} and the labels are {_LABELS}")

    @property
    def is_visitor_sourced(self) -> bool:
        """A record whose source is a session of a visitor, which the registry of the repository refuses."""
        return self.source.startswith("visitor:")

    @property
    def corrects_amount(self) -> bool:
        """The correction is a money value, and the comparison with the ledger is exact."""
        return isinstance(self.corrected_value, Decimal)

    def matches_ledger(self, ledger_value: Decimal) -> bool:
        """The exact comparison of the corrected amount with the value of the ledger."""
        if not self.corrects_amount:
            return False
        return self.corrected_value == ledger_value

    def reproducibility_statement(self) -> str:
        """What the catalog of the record says about the reproducibility of the recording, under ADR-075."""
        if self.catalog == "replay-real":
            return "the recording of a real model is not reproducible byte for byte"
        return "the recording of the scripted model is reproducible byte for byte"

    def to_dict(self) -> dict[str, Any]:
        """The record as a mapping of plain values, for the JSON file of the registry."""
        return {
            "record_id": self.record_id,
            "bundle": self.bundle,
            "bundle_digest": self.bundle_digest,
            "catalog": self.catalog,
            "claim_id": self.claim_id,
            "failure": self.failure,
            "corrected_value": str(self.corrected_value),
            "corrected_value_kind": "decimal" if self.corrects_amount else "text",
            "evidence_refs": list(self.evidence_refs),
            "reviewer": self.reviewer,
            "reviewer_role": self.reviewer_role,
            "source": self.source,
            "permission": self.permission,
            "nli_label": self.nli_label,
            "model_suggested": self.model_suggested,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackRecord:
        """The record read back from its JSON mapping, with the amount a `Decimal` again."""
        value = data["corrected_value"]
        corrected = Decimal(str(value)) if data.get("corrected_value_kind") == "decimal" else str(value)
        return cls(
            record_id=str(data["record_id"]),
            bundle=str(data["bundle"]),
            bundle_digest=str(data["bundle_digest"]),
            catalog=str(data["catalog"]),
            claim_id=str(data["claim_id"]),
            failure=str(data["failure"]),
            corrected_value=corrected,
            evidence_refs=tuple(str(ref) for ref in data["evidence_refs"]),
            reviewer=str(data["reviewer"]),
            reviewer_role=str(data["reviewer_role"]),
            source=str(data["source"]),
            permission=str(data["permission"]),
            nli_label=data.get("nli_label"),
            model_suggested=bool(data.get("model_suggested", False)),
        )
