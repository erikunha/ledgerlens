"""The tool catalog: what the agent registers matches `docs/tools.md` and `docs/contracts/tools.md`.

For each registered tool, both documents must carry the same name, the same description (exactly the
text the model reads), the same type (hardcoded or semantic) and the same kind of integration. A new
tool with no documentation, or a description edited only in the code, breaks here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from langchain_core.tools import BaseTool

from ledgerlens.offline import ScriptedChatModel
from ledgerlens.tools.calculator import build_calculate_tool
from ledgerlens.tools.cases import build_recall_cases_tool
from ledgerlens.tools.fx import build_get_reference_fx_tool
from ledgerlens.tools.ledger_api import build_get_ledger_record_tool
from ledgerlens.tools.policies import build_search_policies_tool
from ledgerlens.tools.sql import build_query_ledger_tool

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
CONTRACT = (ROOT / "docs" / "contracts" / "tools.md").read_text(encoding="utf-8")

# expected type and kind of integration, in contract order; the rest comes from the documents
EXPECTED = {
    "query_ledger": ("semantic", "database"),
    "get_ledger_record": ("hardcoded", "internal service"),
    "search_policies": ("semantic", "vector store"),
    "get_reference_fx": ("hardcoded", "external web API"),
    "calculate": ("hardcoded", "serverless-style function"),
    "recall_cases": ("semantic", "vector store"),
}
# how each kind of integration shows up in the contract table
INTEGRATION_CONTRACT = {
    "database": "database",
    "internal service": "internal service",
    "vector store": "vector store",
    "external web API": "external web API",
    "serverless-style function": "serverless-style",
}


def registered_tools() -> dict[str, BaseTool]:
    tools = [
        build_query_ledger_tool(ScriptedChatModel(script=[])),
        build_get_ledger_record_tool(),
        build_search_policies_tool(),
        build_get_reference_fx_tool(),
        build_calculate_tool(),
        build_recall_cases_tool(runtime_dir="unused"),
    ]
    return {tool.name: tool for tool in tools}


TOOLS = registered_tools()


def table_rows(text: str, header_start: str) -> list[list[str]]:
    """The data rows of the Markdown table whose header starts with `header_start`."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header_start))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def first_quote_after(text: str, marker: str) -> str:
    """The first quote block (`> ...`) after `marker`, on a single line."""
    after = text.split(marker, 1)[1] if marker else text
    quote = re.search(r"^> (.+)$", after, re.MULTILINE)
    assert quote, f"no quoted description after {marker!r}"
    return quote.group(1).strip()


def contract_section(name: str) -> str:
    match = re.search(rf"^## \d+\. `{name}`$(.*?)(?=^## |\Z)", CONTRACT, re.MULTILINE | re.DOTALL)
    assert match, f"{name} has no section in docs/contracts/tools.md"
    return match.group(1)


def test_the_expected_set_is_what_is_registered() -> None:
    assert set(TOOLS) == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_catalog_description_is_what_the_model_reads(name: str) -> None:
    assert first_quote_after(CATALOG, f"**`{name}`**") == TOOLS[name].description


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_contract_description_is_what_the_model_reads(name: str) -> None:
    assert first_quote_after(contract_section(name), "") == TOOLS[name].description


def test_catalog_table_lists_every_tool_with_type_and_integration() -> None:
    rows = {row[0].strip("`"): row for row in table_rows(CATALOG, "| Tool | Type |")}
    assert set(rows) == set(EXPECTED)
    for name, (kind, integration) in EXPECTED.items():
        assert rows[name][1].startswith(kind), (name, rows[name][1])
        assert rows[name][3].startswith(integration), (name, rows[name][3])


def test_catalog_usage_table_places_every_tool_in_one_kind_of_integration() -> None:
    placed: dict[str, str] = {}
    for row in table_rows(CATALOG, "| Kind of use |"):
        for name in re.findall(r"`(\w+)`", row[1]):
            placed[name] = row[0]
    assert set(placed) == set(EXPECTED)
    for name, (_, integration) in EXPECTED.items():
        assert placed[name].lower().startswith(integration.lower()), (name, placed[name])


def test_contract_table_lists_every_tool_with_type_and_integration() -> None:
    rows = {row[0].strip("`"): row for row in table_rows(CONTRACT, "| Tool | Type |")}
    assert set(rows) == set(EXPECTED)
    for name, (kind, integration) in EXPECTED.items():
        assert rows[name][1].startswith(kind), (name, rows[name][1])
        assert INTEGRATION_CONTRACT[integration] in rows[name][2], (name, rows[name][2])


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_contract_section_states_the_type(name: str) -> None:
    kind = EXPECTED[name][0]
    assert re.search(rf"^Type: {kind}\b", contract_section(name), re.MULTILINE)


def test_the_catalog_has_a_diagram_of_which_tool_talks_to_which_system() -> None:
    diagram = re.search(r"```mermaid\n(.*?)```", CATALOG, re.DOTALL)
    assert diagram, "docs/tools.md needs a Mermaid diagram"
    for name in EXPECTED:
        assert name in diagram.group(1)
