"""`recall_cases`: the agent asks long-term memory what was already investigated before.

Why it exists: a customer who comes back and asks again about the same merchant should not get the
same explanation from scratch. The tool returns what past investigations concluded, with the case id
(`case:CASE-0001`) and the date, for the agent to cite. It is a lead, not a proof: the result is a finding from
another day, and the agent must confirm it in the ledger before claiming anything about today.

Rules the code makes visible:

- The merchant and customer filter is applied before the cut to `k` results, so a case from another
  merchant does not get in just for being semantically closer.
- A semantic fact past its validity (`valid_until` in the past) is not returned.
- Memory is optional: if the case index does not exist, the tool returns an empty list with a note
  instead of breaking the agent. A search with no result is a success with an empty list.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from langchain_core.embeddings import Embeddings
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.config import get_embeddings, get_settings
from ledgerlens.memory.long_term import CaseIndexMismatch, CaseIndexUnavailable, CaseMemory
from ledgerlens.tools.envelope import error, invalid_input, ok

log = logging.getLogger(__name__)

DEFAULT_K = 3

DESCRIPTION = (
    "Look up what earlier investigations found, from long-term case memory. Use it at the start of an "
    "investigation about a merchant or customer you may have seen before, and to check whether a pattern was "
    "seen. Results are past findings with their case id and date, not facts about today's data: confirm with "
    "the ledger before relying on them, and cite the case id when you use one."
)


class RecallCasesInput(BaseModel):
    """Tool input, validated before any search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=300)
    merchant_id: str | None = Field(default=None, pattern=r"^M-[0-9]{2}$")
    customer_id: str | None = Field(default=None, pattern=r"^C-[0-9]{4}$")
    kind: Literal["any", "episodic", "semantic"] = "any"
    k: int = Field(default=DEFAULT_K, ge=1, le=5)


def _handle_validation_error(exc: Exception) -> str:
    """A wrong entity id is `INVALID_ID`; the rest of the input is `INVALID_INPUT`."""
    errors = getattr(exc, "errors", None)
    items = list(errors()) if callable(errors) else []
    for item in items:
        field = ".".join(str(part) for part in item.get("loc", ()))
        if field in {"merchant_id", "customer_id"}:
            detail = "; ".join(
                f"{'.'.join(str(part) for part in entry.get('loc', ()))}: {entry.get('msg', '')}" for entry in items
            )
            return json.dumps(error("INVALID_ID", detail, False), ensure_ascii=False)
    return invalid_input(exc)


def _recall_with(
    memory: CaseMemory,
    query: str,
    merchant_id: str | None = None,
    customer_id: str | None = None,
    kind: str = "any",
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    """The search itself, with the common response envelope."""
    entity_ids: dict[str, list[str]] = {}
    if merchant_id:
        entity_ids["merchant_ids"] = [merchant_id]
    if customer_id:
        entity_ids["customer_ids"] = [customer_id]
    try:
        hits = memory.recall(query, entity_ids=entity_ids or None, k=k, kind=kind)
    except (CaseIndexUnavailable, CaseIndexMismatch) as exc:
        log.info("case memory unavailable: %s", exc)
        return ok([], {"results": [], "note": f"CASE_INDEX_UNAVAILABLE: {exc}"})

    return ok([f"case:{hit['case_id']}" for hit in hits], {"results": hits})


def _default_memory() -> CaseMemory:
    """The configured memory: runtime folder and embeddings of the current mode."""
    settings = get_settings()
    return CaseMemory(settings.runtime_dir, embeddings=get_embeddings())


def build_recall_cases_tool(
    *,
    memory: CaseMemory | None = None,
    runtime_dir: Path | str | None = None,
    embeddings: Embeddings | None = None,
) -> StructuredTool:
    """Builds the tool bound to a memory. Without one, it uses the configured memory (loaded on the first call)."""
    bound = memory
    if bound is None:
        settings = get_settings()
        bound = CaseMemory(runtime_dir or settings.runtime_dir, embeddings=embeddings)

    def recall_cases(
        query: str,
        merchant_id: str | None = None,
        customer_id: str | None = None,
        kind: str = "any",
        k: int = DEFAULT_K,
    ) -> dict[str, Any]:
        return _recall_with(bound, query, merchant_id, customer_id, kind, k)

    return StructuredTool.from_function(
        func=recall_cases,
        name="recall_cases",
        description=DESCRIPTION,
        args_schema=RecallCasesInput,
        handle_validation_error=_handle_validation_error,
    )


# The agent's tool, with the configured memory. The memory is loaded on the first call, so that
# creating the object costs nothing (and the import does not download the embedding model).
_STATE: dict[str, Any] = {}


def _configured_memory() -> CaseMemory:
    if "memory" not in _STATE:
        _STATE["memory"] = _default_memory()
    return _STATE["memory"]


def _recall_cases(
    query: str,
    merchant_id: str | None = None,
    customer_id: str | None = None,
    kind: str = "any",
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    return _recall_with(_configured_memory(), query, merchant_id, customer_id, kind, k)


recall_cases = StructuredTool.from_function(
    func=_recall_cases,
    name="recall_cases",
    description=DESCRIPTION,
    args_schema=RecallCasesInput,
    handle_validation_error=_handle_validation_error,
)
