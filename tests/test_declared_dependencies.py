"""Every third-party package imported in ledgerlens/ must be declared in pyproject.toml.

Why: a dependency that only arrives transitively (such as langchain-text-splitters through
langchain) can disappear in an update and break a fresh clone without warning.
"""

import ast
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _declared() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = list(data["project"]["dependencies"])
    for extra in data["project"].get("optional-dependencies", {}).values():
        reqs += extra
    names = set()
    for req in reqs:
        name = req.split(";")[0]
        for sep in "=<>![ ~":
            name = name.split(sep)[0]
        names.add(name.strip().lower().replace("_", "-"))
    return names


def _imported_roots() -> set[str]:
    roots = set()
    for path in (ROOT / "ledgerlens").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots - set(sys.stdlib_module_names) - {"ledgerlens", "__future__"}


def test_every_third_party_import_is_declared():
    dists = packages_distributions()
    declared = _declared()
    missing = []
    for root in sorted(_imported_roots()):
        owners = {d.lower().replace("_", "-") for d in dists.get(root, [root])}
        if not owners & declared:
            missing.append(f"{root} ({', '.join(sorted(owners))})")
    assert not missing, f"imported but not declared in pyproject.toml: {missing}"
