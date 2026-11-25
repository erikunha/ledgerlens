"""The domain boundary of the pipeline: no SQL in the domain layer, and no import of the API.

What they guarantee, and why: no module of `ledgerlens/documents/` carries a SQL string and no module of it
imports `ledgerlens.api`, because the domain never speaks SQL and never imports the API layer, and the match
against the ledger goes through `ledgerlens/tools/ledger_api.py`, the read-only surface of the domain.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = ROOT / "ledgerlens" / "documents"

_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s+[A-Za-z*]", re.IGNORECASE)


def test_no_module_of_the_pipeline_carries_a_sql_string() -> None:
    """The domain never speaks SQL, and the pipeline is a layer of the domain."""
    for path in sorted(DOCUMENTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not _SQL.search(node.value), f"the module {path.name} carries a SQL string: {node.value[:60]!r}"


def test_no_module_of_the_pipeline_imports_the_api() -> None:
    """The domain never imports the API layer."""
    for path in sorted(DOCUMENTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    assert not name.startswith("ledgerlens.api"), f"the module {path.name} imports {name}"
