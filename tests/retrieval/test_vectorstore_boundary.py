"""The boundary of the vector library: no module of the project imports the library outside the protocol.

What they guarantee, and why: no module of `ledgerlens/` imports `langchain_community.vectorstores` outside
`ledgerlens/vectorstore.py`, because the project promises the three operations of the protocol and not the
library, and a promise about the shape of the repository becomes a test.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "ledgerlens"
PROTOCOL = PACKAGE / "vectorstore.py"


def test_no_module_of_the_project_imports_the_vector_library_outside_the_protocol() -> None:
    """The library is behind the protocol, and the guard refuses any other site of it."""
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path == PROTOCOL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    if name.startswith("langchain_community.vectorstores"):
                        offenders.append(f"{path.relative_to(ROOT)} imports {name}")
    assert not offenders, "the vector library is imported outside the protocol: " + "; ".join(offenders)


def test_the_protocol_is_the_only_site_of_the_library() -> None:
    """The protocol module is the one place of the project that talks to the library."""
    tree = ast.parse(PROTOCOL.read_text(encoding="utf-8"))
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert any(
        (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("langchain_community.vectorstores"))
        for node in imports
    ), "the protocol module is the place of the library"
