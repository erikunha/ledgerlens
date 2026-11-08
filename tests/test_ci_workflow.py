"""CI installs the same extras the README tells you to install.

Why: the gate calls ruff and pytest, which come from the dev extra. A `uv sync` without the extras
removes those tools and the gate fails with "Failed to spawn: ruff".
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _extras(text: str) -> set[str]:
    return set(re.findall(r"--extra (\w+)", text))


def test_ci_sync_installs_readme_extras():
    workflow = (ROOT / ".github/workflows/gate.yml").read_text(encoding="utf-8")
    sync = [line for line in workflow.splitlines() if "uv sync" in line]
    assert sync, "gate.yml has no uv sync step"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_sync = next(line for line in readme.splitlines() if "uv sync" in line)
    assert "dev" in _extras(sync[0])
    assert _extras(readme_sync) <= _extras(sync[0])
