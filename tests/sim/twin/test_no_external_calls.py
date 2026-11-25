"""The twin runs with the network disabled, and no module of the twin imports the API.

What they guarantee, and why: (a) the twin finishes with the network disabled, because the twin runs no model
and calls no provider, and a twin that called the network would be a twin that spends the money of somebody;
(b) no module of `ledgerlens/sim/twin/` imports `ledgerlens.api`, because the domain never imports the API
layer, and the twin is a layer of the domain.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import socket
from pathlib import Path

from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.run import run_twin

ROOT = Path(__file__).resolve().parents[3]


def test_the_twin_finishes_with_the_network_disabled(monkeypatch) -> None:
    """The twin runs no model and calls no provider: it finishes with the network disabled."""

    def no_network(*args, **kwargs):
        raise OSError("the network is disabled for the test of the twin")

    monkeypatch.setattr(socket, "socket", no_network)
    run = run_twin(
        TwinConfig(seed=42, horizon_minutes=60),
        truth_path=ROOT / "data" / "scenarios.json",
        commit="abc123",
    )

    assert run.manifest.label


def test_no_module_of_the_twin_imports_the_api() -> None:
    """The domain never imports the API layer, and the twin is a layer of the domain."""
    import ast

    twin_dir = ROOT / "ledgerlens" / "sim" / "twin"
    for path in sorted(twin_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    assert not name.startswith("ledgerlens.api"), f"the module {path.name} imports {name}"
