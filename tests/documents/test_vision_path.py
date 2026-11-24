"""The vision path of the pipeline: the model proposes and the deterministic parser decides.

What they guarantee, and why: (a) with no model reachable the tool refuses with a reason, because the vision
path needs a model and the caller of the run holds the provider; (b) with the scripted model of
`ledgerlens/offline.py` the number of the calls stays inside the ceiling of ADR-054, because the vision path
is bounded by the ceiling of the run; (c) no field that only the model read becomes a value, because the model
proposes and the deterministic parser decides.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.documents.vision import VisionRefused, propose_with_vision
from ledgerlens.offline import ScriptedChatModel, text_message


def test_with_no_model_reachable_the_tool_refuses_with_a_reason() -> None:
    """The vision path needs a model, and no model is reachable."""
    with pytest.raises(VisionRefused, match="no model is reachable"):
        propose_with_vision("image.png", model=None, field_name="total", deterministic_value=Decimal("100.00"))


def test_no_field_that_only_the_model_read_becomes_a_value() -> None:
    """The model proposes a value the parser did not confirm, and the value is not a value of the extraction."""
    model = ScriptedChatModel(script=[text_message("999.99")])
    proposal = propose_with_vision(
        "image.png",
        model=model,
        field_name="total",
        deterministic_value=Decimal("100.00"),
    )

    assert proposal.confirmed is False
    assert proposal.value is None
    assert proposal.confidence == "uncertain"


def test_a_value_the_parser_confirms_is_a_value() -> None:
    """The model proposes a value the parser confirms, and the value is read."""
    model = ScriptedChatModel(script=[text_message("100.00")])
    proposal = propose_with_vision(
        "image.png",
        model=model,
        field_name="total",
        deterministic_value=Decimal("100.00"),
    )

    assert proposal.confirmed is True
    assert proposal.value == Decimal("100.00")
    assert proposal.confidence == "read"


def test_the_number_of_the_calls_stays_inside_the_ceiling() -> None:
    """The vision path is bounded by the ceiling of the run of ADR-054."""
    model = ScriptedChatModel(script=[text_message("100.00")])
    propose_with_vision("image.png", model=model, field_name="total", deterministic_value=Decimal("100.00"))

    assert len(model.calls) <= 1
