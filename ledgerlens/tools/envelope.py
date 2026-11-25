"""The common response format of the agent's tools.

Why it exists: every tool returns a dictionary and never raises an exception to the model. Success
carries the evidence ids and the data; an error carries a code, a message and whether retrying is worth it.
That way the agent can reason about the failure ("the FX source is down, I will not make up the
rate") instead of getting stuck. The format is in `docs/contracts/tools.md` (section "Common result envelope").

The two shapes::

    {"ok": True,  "evidence_ids": ["sql:1"], "data": {...}}
    {"ok": False, "error": {"code": "SQL_TIMEOUT", "message": "...", "retryable": False}}
"""

from __future__ import annotations

import json
import re
from typing import Any

# Each evidence id starts with its source: sql, api, policy, fx, calc, case, doc or world.
EVIDENCE_ID = re.compile(r"^(sql|api|policy|fx|calc|case|doc|world):.+$")


def ok(evidence_ids: list[str], data: dict[str, Any]) -> dict[str, Any]:
    """Success response. An id outside the scheme is a programming error and fails right away."""
    for evidence_id in evidence_ids:
        if not EVIDENCE_ID.match(evidence_id):
            raise ValueError(f"evidence id outside the scheme <source>:<id>: {evidence_id!r}")
    return {"ok": True, "evidence_ids": list(evidence_ids), "data": data}


def world_evidence(slug: str, *, url: str, read_on: str, content: str) -> dict[str, Any]:
    """The way to cite a rule of the world: the id, the URL of the source and the date it was read.

    Why a rule of the world is a kind of evidence: an answer that is right about the real world can be
    cited, and the verifier can name the conflict between the cited rule of the world and a cited policy
    instead of scoring a plain contradiction (gap 11 of the audit of the truth of the policies and the
    money). The source and the date are required, because a rule of the world without them is a rule of the
    fiction enforced as if it were a rule of the world.
    """
    if not slug.strip():
        raise ValueError("the slug of a rule of the world is not empty")
    if not url.strip():
        raise ValueError("a rule of the world names the URL of its source")
    if not read_on.strip():
        raise ValueError("a rule of the world names the date it was read")
    return {
        "id": f"world:{slug}",
        "source_type": "world",
        "url": url,
        "read_on": read_on,
        "content": content,
    }


def error(code: str, message: str, retryable: bool) -> dict[str, Any]:
    """Error response. `retryable` says whether the agent should try again with another input."""
    return {"ok": False, "error": {"code": code, "message": message, "retryable": retryable}}


def invalid_input(exc: Exception) -> str:
    """For LangChain's `handle_validation_error`: the input failed the schema before any work.

    LangChain requires this handler to return text, so the error envelope goes out as JSON.
    """
    errors = getattr(exc, "errors", None)
    detail = (
        "; ".join(f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in errors())
        if callable(errors)
        else str(exc)
    )
    return json.dumps(error("INVALID_INPUT", detail, True), ensure_ascii=False)
