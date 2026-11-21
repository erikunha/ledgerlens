"""The deployment of the sandbox: the check of the shape of a command needs jsonschema.

Why this file exists: the shape of a payload is checked against the published schema of the contract, and the check
needs the library. A deployment without it cannot serve a mutation, and the refusal has to say that the installation
is missing and that the command of the visitor is not the reason.

Why the refusal is not the one of a bad payload: the command of the visitor may be perfect, and an answer that blames
it sends the visitor to look in the wrong place.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import pytest

from ledgerlens.sandbox.mutation import (
    CODE_CONTRACT_UNAVAILABLE,
    MutationCommand,
    MutationRejected,
    status_for_code,
    validate_command,
)
from ledgerlens.sandbox.projector import ProjectedState


def _a_command() -> MutationCommand:
    """A command of a kind of the catalog, with a payload that the rules of the kind do not refuse."""
    return MutationCommand(kind="record.inject_untrusted_note", payload={})


def test_the_sandbox_refuses_a_deployment_without_jsonschema(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment without jsonschema cannot check the shape of a command, and it says so."""
    monkeypatch.setitem(sys.modules, "jsonschema", None)
    state = ProjectedState(conn=None, canonical_hash="", rows={})

    with pytest.raises(MutationRejected) as refusal:
        validate_command(_a_command(), state, datetime.now(UTC))

    assert refusal.value.code == CODE_CONTRACT_UNAVAILABLE
    assert status_for_code(CODE_CONTRACT_UNAVAILABLE) == 503


def test_the_refusal_of_the_sandbox_names_the_extras_that_install_jsonschema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal names the extras that really install jsonschema, and it does not blame the visitor."""
    monkeypatch.setitem(sys.modules, "jsonschema", None)
    state = ProjectedState(conn=None, canonical_hash="", rows={})

    with pytest.raises(MutationRejected) as refusal:
        validate_command(_a_command(), state, datetime.now(UTC))

    message = refusal.value.message
    assert "jsonschema" in message
    assert "api extra" in message
    assert "dev extra" in message
    assert "development extra" not in message
    assert "deployment" in message
