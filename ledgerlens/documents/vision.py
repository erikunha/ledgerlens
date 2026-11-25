"""The vision path of the pipeline: the model proposes and the deterministic parser decides.

Why the vision path exists and is bounded: a document whose text layer cannot be read (an image, a blur) may
be read by a vision model, and the call of the model is a call of the run, bounded by the ceiling of the run
of ADR-054. The vision path exists, and it is bounded, and it never publishes a value on its own.

Why no field that only the model read becomes a value: the model proposes a value, and the deterministic
parser of the repository decides whether the value is confirmed. A value that only the model read carries the
kind of confidence that names the doubt, and it never becomes a value of the extraction. The model proposes
and the deterministic parser decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

__all__ = ["VisionRefused", "propose_with_vision"]


class VisionRefused(Exception):
    """The vision path is refused, and the message says why."""


@dataclass(frozen=True)
class VisionProposal:
    """The proposal of the vision model: the value it read and whether the deterministic parser confirmed it."""

    name: str
    value: Decimal | None
    confirmed: bool
    confidence: str


def propose_with_vision(
    image_path: object,
    *,
    model: object,
    field_name: str,
    deterministic_value: Decimal | None,
) -> VisionProposal:
    """The proposal of the vision model for a field, with the confirmation of the deterministic parser.

    Why the model is an argument and not a default: the caller of the run holds the provider, and a vision
    path that built its own model would be a path that spends the money of a caller that did not consent to
    it. With no model reachable, the vision path is refused with the reason.

    Why the value of the model is never a value of the extraction: the model proposes, and the deterministic
    parser decides. A value that only the model read carries the kind of confidence that names the doubt.
    """
    if model is None:
        raise VisionRefused(
            "the vision path needs a model, and no model is reachable: the deterministic path of the pipeline "
            "reads the text layer, and the vision path is refused with the reason"
        )
    proposal = model.invoke([("human", f"read the {field_name} of the document")])  # type: ignore[attr-defined]
    proposed = _value_of(proposal)
    confirmed = proposed is not None and proposed == deterministic_value
    return VisionProposal(
        name=field_name,
        value=proposed if confirmed else None,
        confirmed=confirmed,
        confidence="read" if confirmed else "uncertain",
    )


def _value_of(proposal: object) -> Decimal | None:
    """The value the model proposed, as a `Decimal`, and None when the proposal is not an amount."""
    content = getattr(proposal, "content", str(proposal))
    try:
        return Decimal(str(content).strip())
    except Exception:
        return None
