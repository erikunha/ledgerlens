"""The deployment of the export of the site: the check of the shape of an event needs jsonschema.

Why this file exists: every recorded event is checked against the versioned public schema, and the check needs the
library. A deployment without it cannot export, and the refusal has to say that the installation is missing and that
the bundle is not the reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ledgerlens.replay.site_export import ExportError, build_export

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "eval" / "replay" / "s01"


def test_the_export_refuses_a_deployment_without_jsonschema(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment without jsonschema cannot check the shape of an event, and it says so."""
    monkeypatch.setitem(sys.modules, "jsonschema", None)

    with pytest.raises(ExportError) as refusal:
        build_export([CANONICAL])

    message = str(refusal.value)
    assert "jsonschema" in message
    assert "api extra" in message
    assert "dev extra" in message
    assert "development extra" not in message
    assert "deployment" in message
