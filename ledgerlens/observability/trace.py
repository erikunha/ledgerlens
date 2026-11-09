"""The trace of an investigation: the run tree (like LangSmith's), emitted span by span while it happens.

Why it exists: the agent takes from a few to tens of seconds between the question and the verified answer, and the
page only showed a spinner. With `investigate(..., on_event=f)`, `f` gets a `Span` when each run starts and again
when it ends, so any screen (Streamlit, a terminal, a log viewer) can draw the tree live. This module knows nothing
about the screen and does not depend on LangSmith: it works offline, with no key.

A `Span` has the fields of a LangSmith run: `run_id`, `parent_run_id`, `name`, `run_type` (`chain`, `llm`, `tool`,
`retriever`, `parser`, `prompt` or `verifier`), `start_time`, `end_time`, `latency_ms`, `inputs`, `outputs`, `error`
and `metadata` (model, `prompt`/`completion`/`total` tokens, tags, the LangSmith URL when there is one), plus
`status` (`running`, `ok`, `error`). The start and the end of the same run share the same `run_id`.

Where the spans come from:

- `TraceCallback`, a LangChain `BaseCallbackHandler` passed in the config of the triage and agent calls, turns each
  run into a span: the triage chains, prompts and parsers, the agent graph's nodes, each model call (with the model
  name and the tokens, when the provider reports them), each tool (arguments and the response envelope, with the
  generated SQL) and the runs inside a tool (the model that writes the SQL). Runs LangGraph marks as internal
  (`langsmith:hidden`) are left out, and their children move up to the visible ancestor.
- The integrator opens explicit spans for what is not a LangChain run: the root `investigate`, the plan's single
  follow-up (`plan_followup`), verification (`verify`, with one child per claim: check, label, NLI scores,
  evidence), escalation (`escalation`) and saving the case. Claims and escalation come out of one verifier call,
  so their spans have no duration of their own (`latency_ms` is empty).

A LangChain run with no known parent (triage, the agent) goes under the explicit span open at that moment.

`inputs` and `outputs` go through `compact`: long texts and long lists are cut with a marker ("…+12 rows",
"…+340 chars") and anything that looks like an API key becomes `[REDACTED]` (`redact`). Model prompts and responses
enter the trace, already cut, because the trace stays in the session of the person who asked.

`create_agent` runs each tool in a thread of its executor, so `on_event` may be called from another thread: whoever
draws should receive the spans on a queue and draw on its own thread. The emitter calls `on_event` under a lock, and
an exception in `on_event` goes to the log without bringing the investigation down.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from ledgerlens.observability.callbacks import redact
from ledgerlens.schemas import ESCALATION_PREFIX, InvestigationResult

log = logging.getLogger(__name__)

RunType = Literal["chain", "llm", "tool", "retriever", "parser", "prompt", "verifier"]
SpanStatus = Literal["running", "ok", "error"]
HIDDEN_TAG = "langsmith:hidden"  # LangGraph's mark for the graph's internal runs
MAX_TEXT = 600  # characters of a text before the cut
MAX_ITEMS = 8  # items of a list before the cut
MAX_DEPTH = 6  # nesting levels before the value becomes text


@dataclass(frozen=True)
class Span:
    """One run of the trace, in the shape of a LangSmith run."""

    run_id: str
    parent_run_id: str | None
    name: str
    run_type: RunType
    start_time: str
    end_time: str | None = None
    latency_ms: int | None = None
    inputs: Any = None
    outputs: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: SpanStatus = "running"


OnEvent = Callable[[Span], None]


# ---- what goes into a span ----------------------------------------------------------------------------


def _message(message: BaseMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"type": message.type, "content": message.content}
    if getattr(message, "tool_calls", None):
        out["tool_calls"] = message.tool_calls
    if getattr(message, "tool_call_id", None):
        out["tool_call_id"] = message.tool_call_id
    return out


def compact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """`value` as short JSON with no secrets: long lists and texts cut with a marker of what was left out."""
    if depth > MAX_DEPTH:
        return redact(str(value))[:MAX_TEXT]
    if isinstance(value, BaseMessage):
        return compact(_message(value), key=key, depth=depth)
    if isinstance(value, BaseModel):
        return compact(value.model_dump(mode="json"), key=key, depth=depth)
    if isinstance(value, dict):
        return {str(k): compact(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [compact(v, key=key, depth=depth + 1) for v in list(value)[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            unit = "rows" if key == "rows" else "items"
            items.append(f"…+{len(value) - MAX_ITEMS} {unit}")
        return items
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = redact(str(value))
    return text if len(text) <= MAX_TEXT else f"{text[:MAX_TEXT]}…+{len(text) - MAX_TEXT} chars"


def envelope_of(output: Any) -> dict[str, Any]:
    """The `{"ok": ...}` envelope of what the tool returned: a dict, a `ToolMessage` or JSON text.

    Text that is not JSON becomes an error, as in the result's trace (the integrator's `_envelope`)."""
    if isinstance(output, dict) and "ok" in output:
        return output
    text = getattr(output, "content", output)
    if isinstance(text, list):
        text = "".join(p if isinstance(p, str) else str(p.get("text", "")) for p in text if isinstance(p, (str, dict)))
    try:
        parsed = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and "ok" in parsed:
        return parsed
    return {"ok": False, "error": {"code": "UNPARSEABLE_TOOL_RESULT", "message": str(text)[:200]}}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _usage(response: Any) -> dict[str, int]:
    """The tokens of a model call (`prompt`, `completion`, `total`), when the provider reports them."""
    for batch in getattr(response, "generations", []) or []:
        for generation in batch:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if usage:
                return {
                    "prompt": int(usage.get("input_tokens", 0)),
                    "completion": int(usage.get("output_tokens", 0)),
                    "total": int(usage.get("total_tokens", 0)),
                }
    usage = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}
    if usage:
        return {
            "prompt": int(usage.get("prompt_tokens", 0)),
            "completion": int(usage.get("completion_tokens", 0)),
            "total": int(usage.get("total_tokens", 0)),
        }
    return {}


def _model_name(serialized: Any, kwargs: dict[str, Any]) -> str:
    metadata = kwargs.get("metadata") or {}
    params = kwargs.get("invocation_params") or {}
    return str(
        metadata.get("ls_model_name")
        or params.get("model")
        or params.get("model_name")
        or kwargs.get("name")
        or (serialized or {}).get("name")
        or "?"
    )


def _llm_outputs(response: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"generations": []}
    for batch in getattr(response, "generations", []) or []:
        for generation in batch:
            message = getattr(generation, "message", None)
            item: dict[str, Any] = {"content": getattr(generation, "text", "")}
            if getattr(message, "tool_calls", None):
                item["tool_calls"] = message.tool_calls
            out["generations"].append(item)
    return out


# ---- the summary ---------------------------------------------------------------------------------------


def seconds(ms: int) -> str:
    """Milliseconds as seconds with one decimal: 6200 becomes "6.2 s"."""
    value = (Decimal(ms) / 1000).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{value} s"


def verdict_counts(result: InvestigationResult) -> str:
    """The verdict counts that are not zero, with the noun only on the first: "3 claims supported, 1 without
    evidence". Empty when there is no verdict."""
    counts = {"supported": 0, "contradicted": 0, "not_enough_evidence": 0}
    for verdict in result.verdicts:
        counts[verdict.label] += 1
    words = (
        ("supported", "supported"),
        ("contradicted", "contradicted"),
        ("not_enough_evidence", "without evidence"),
    )
    parts: list[str] = []
    for key, word in words:
        count = counts[key]
        if count:
            noun = ("claim " if count == 1 else "claims ") if not parts else ""
            parts.append(f"{count} {noun}{word}")
    return ", ".join(parts)


def summary_line(result: InvestigationResult, ms: int, tokens: int = 0) -> str:
    """The one-line summary: sources, total time, tokens (when reported) and what verification found."""
    took = seconds(ms) + (f", {tokens} tokens" if tokens else "")
    if result.recommended_action == "ask_for_clarification" and not result.tool_trace:
        return f"Asked for a clarification in {took}"
    if not result.tool_trace:
        return f"Answered without checking any source in {took}"
    sources = f"{len(result.tool_trace)} {'source' if len(result.tool_trace) == 1 else 'sources'}"
    found = verdict_counts(result) or "no claim to verify"
    line = f"Checked {sources} in {took}: {found}"
    return line + ("; goes to human review" if result.requires_human_review else "")


def review_reasons(result: InvestigationResult) -> list[str]:
    """Why a person must review: the escalation reasons, without the prefix, or what was missing."""
    reasons = [m.removeprefix(ESCALATION_PREFIX) for m in result.missing_information if m.startswith(ESCALATION_PREFIX)]
    if result.requires_human_review and not reasons:
        return list(result.missing_information)
    return reasons


def langsmith_url(run_id: str) -> str | None:
    """The run's URL in LangSmith, when LangChain tracing is on in this process; otherwise `None`.

    Without tracing the run was never sent, so there is no URL. A network failure also gives `None`."""
    try:
        from langsmith import Client
        from langsmith.utils import tracing_is_enabled

        if not tracing_is_enabled():
            return None
        return Client(timeout_ms=3000).get_run_url(run=_RunRef(id=UUID(run_id)))
    except Exception as exc:  # the URL is an extra: the local trace goes on
        log.info("no LangSmith URL for %s: %s: %s", run_id, type(exc).__name__, exc)
        return None


@dataclass
class _RunRef:
    id: UUID
    session_id: UUID | None = None
    trace_id: UUID | None = None


# ---- the emitter ---------------------------------------------------------------------------------------


class Tracer:
    """Keeps the spans of one investigation and hands them to `on_event`. Without `on_event` it adds no callbacks.

    `begin` and `finish` open and close an explicit span; while it is open, LangChain runs with no known parent go
    under it. `point` records a span that is already finished (a verified claim)."""

    def __init__(self, on_event: OnEvent | None = None) -> None:
        self._on_event = on_event
        self._lock = threading.Lock()
        self._emit_lock = threading.Lock()
        self.spans: dict[str, Span] = {}
        self._started: dict[str, float] = {}
        self._hidden: dict[str, str | None] = {}  # internal run -> its visible ancestor
        self._stack: list[str] = []
        self.roots: list[str] = []  # LangChain runs with no parent: the ones LangSmith shows as traces

    @property
    def enabled(self) -> bool:
        return self._on_event is not None

    def handlers(self) -> list[BaseCallbackHandler]:
        """The callbacks to put in the config of a LangChain call (none, without `on_event`)."""
        return [TraceCallback(self)] if self.enabled else []

    def emit(self, span: Span) -> None:
        if self._on_event is None:
            return
        with self._emit_lock:
            try:
                self._on_event(span)
            except Exception as exc:  # the drawer failed; the investigation goes on
                log.warning("trace listener failed on %s: %s: %s", span.name, type(exc).__name__, exc)

    def parent_for(self, parent_run_id: Any) -> str | None:
        """The visible parent: the known span, the visible ancestor of an internal run or the open explicit span."""
        with self._lock:
            parent = str(parent_run_id) if parent_run_id is not None else None
            if parent is not None and parent in self._hidden:
                return self._hidden[parent]
            if parent is not None and parent in self.spans:
                return parent
            return self._stack[-1] if self._stack else None

    def hide(self, run_id: Any, parent_run_id: Any) -> None:
        resolved = self.parent_for(parent_run_id)
        with self._lock:
            self._hidden[str(run_id)] = resolved

    def start(
        self,
        name: str,
        run_type: RunType,
        inputs: Any,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        metadata: dict[str, Any] | None = None,
        explicit: bool = False,
    ) -> str:
        run = str(run_id or uuid.uuid4())
        parent = self._stack[-1] if explicit and self._stack else self.parent_for(parent_run_id)
        span = Span(run, parent, name, run_type, _now(), inputs=compact(inputs), metadata=dict(metadata or {}))
        with self._lock:
            self.spans[run] = span
            self._started[run] = time.perf_counter()
            if not explicit and parent_run_id is None:
                self.roots.append(run)
        self.emit(span)
        return run

    def end(
        self,
        run_id: Any,
        *,
        outputs: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Span | None:
        run = str(run_id)
        with self._lock:
            span = self.spans.get(run)
            started = self._started.pop(run, None)
            if span is None or started is None:
                return None
            span = replace(
                span,
                end_time=_now(),
                latency_ms=_ms(started),
                outputs=compact(outputs) if outputs is not None else None,
                error=redact(error)[:MAX_TEXT] if error else None,
                metadata={**span.metadata, **(metadata or {})},
                status="error" if error else "ok",
            )
            self.spans[run] = span
        self.emit(span)
        return span

    def begin(self, name: str, run_type: RunType, inputs: Any) -> str:
        run = self.start(name, run_type, inputs, explicit=True)
        self._stack.append(run)
        return run

    def finish(self, run_id: str, *, outputs: Any = None, error: str | None = None, **metadata: Any) -> None:
        if self._stack and self._stack[-1] == run_id:
            self._stack.pop()
        self.end(run_id, outputs=outputs, error=error, metadata=metadata)

    def point(self, name: str, run_type: RunType, inputs: Any, outputs: Any, **metadata: Any) -> None:
        """A span that starts and ends at once, with no duration of its own."""
        run = str(uuid.uuid4())
        parent = self._stack[-1] if self._stack else None
        now = _now()
        span = Span(
            run, parent, name, run_type, now, now, None, compact(inputs), compact(outputs), None, metadata, "ok"
        )
        with self._lock:
            self.spans[run] = span
        self.emit(span)

    def elapsed_ms(self, run_id: str) -> int:
        """How long the open span `run_id` has been running."""
        with self._lock:
            started = self._started.get(run_id)
        return _ms(started) if started is not None else 0

    def tokens(self) -> int:
        with self._lock:
            return sum(int(s.metadata.get("tokens", {}).get("total", 0)) for s in self.spans.values())


class TraceCallback(BaseCallbackHandler):
    """Turns LangChain callbacks into `Tracer` spans."""

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    def _visible(self, run_id: UUID, parent_run_id: UUID | None, tags: list[str] | None) -> bool:
        if tags and HIDDEN_TAG in tags:
            self._tracer.hide(run_id, parent_run_id)
            return False
        return True

    # --- chains, prompts and parsers ---

    def on_chain_start(
        self,
        serialized: Any,
        inputs: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._visible(run_id, parent_run_id, tags):
            return
        name = str(kwargs.get("name") or (serialized or {}).get("name") or "chain")
        run_type = kwargs.get("run_type") if kwargs.get("run_type") in ("parser", "prompt") else "chain"
        if run_type == "chain" and "pars" in name.lower():  # a parser written as a function (`parse_with_repair`)
            run_type = "parser"
        self._tracer.start(
            name, run_type, inputs, run_id=run_id, parent_run_id=parent_run_id, metadata={"tags": tags or []}
        )

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end(run_id, outputs=outputs)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end(run_id, error=f"{type(error).__name__}: {error}")

    # --- models ---

    def on_chat_model_start(
        self,
        serialized: Any,
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._visible(run_id, parent_run_id, tags):
            return
        model = _model_name(serialized, kwargs)
        inputs = {"messages": [m for batch in messages for m in batch]}
        self._tracer.start(
            model,
            "llm",
            inputs,
            run_id=run_id,
            parent_run_id=parent_run_id,
            metadata={"model": model, "tags": tags or []},
        )

    def on_llm_start(
        self,
        serialized: Any,
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._visible(run_id, parent_run_id, tags):
            return
        model = _model_name(serialized, kwargs)
        self._tracer.start(
            model, "llm", {"prompts": prompts}, run_id=run_id, parent_run_id=parent_run_id, metadata={"model": model}
        )

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        usage = _usage(response)
        self._tracer.end(run_id, outputs=_llm_outputs(response), metadata={"tokens": usage} if usage else None)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end(run_id, error=f"{type(error).__name__}: {error}")

    # --- tools ---

    def on_tool_start(
        self,
        serialized: Any,
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        inputs: Any = None,
        **kwargs: Any,
    ) -> None:
        if not self._visible(run_id, parent_run_id, tags):
            return
        name = str(kwargs.get("name") or (serialized or {}).get("name") or "tool")
        args = inputs if isinstance(inputs, dict) else {"input": input_str}
        self._tracer.start(name, "tool", args, run_id=run_id, parent_run_id=parent_run_id)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        envelope = envelope_of(output)
        failure = None if envelope.get("ok") else str((envelope.get("error") or {}).get("code", "UNKNOWN"))
        self._tracer.end(run_id, outputs=envelope, error=failure)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end(run_id, error=f"{type(error).__name__}: {error}")

    # --- retrieval ---

    def on_retriever_start(
        self,
        serialized: Any,
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._visible(run_id, parent_run_id, tags):
            return
        name = str(kwargs.get("name") or (serialized or {}).get("name") or "retriever")
        self._tracer.start(name, "retriever", {"query": query}, run_id=run_id, parent_run_id=parent_run_id)

    def on_retriever_end(self, documents: Any, *, run_id: UUID, **kwargs: Any) -> None:
        docs = [{"page_content": d.page_content, "metadata": d.metadata} for d in documents]
        self._tracer.end(run_id, outputs={"documents": docs})

    def on_retriever_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tracer.end(run_id, error=f"{type(error).__name__}: {error}")
