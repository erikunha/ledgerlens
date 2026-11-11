"""Callback handler that writes one event per line as JSON (JSON lines).

What it is for: seeing what the chain or the agent did, after it ran, without depending on an external service.
Each start and end of a call to the model, a tool or a chain becomes a line with a timestamp,
the event type, `run_id`, `parent_run_id` (the caller) and, on end or error events, the duration in ms.
The file is read with `json.loads` line by line, or with `jq`, and each line stands on its own.

Privacy and secrets:
- The full text of a prompt or an answer is never written: only counts and sizes
  (`message_count`, `prompt_chars`, `output_chars`). Prompts carry customer data.
- Chain inputs write only the keys. Tool inputs write a short, already filtered excerpt.
- Everything that is text goes through `redact`, which wipes API keys (`sk-...`, `lsv2_...`, `Bearer ...`,
  `ghp_...`, `AKIA...`, `AIza...`).

Interface: `JsonlCallbackHandler(sink)`, where `sink` is an open text file or a `Path`
(the file is created and lines are appended). Pass the handler in `config={"callbacks": [handler]}`.

Writing: a lock (`Lock`) guards the write, because `batch` and tools running in parallel call the
handler from several threads and two lines cannot get mixed.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

# Key patterns: OpenAI (sk-), LangSmith (lsv2_), the Authorization header (Bearer), GitHub tokens (ghp_),
# AWS access key ids (AKIA) and Google API keys (AIza).
_SECRET = re.compile(
    r"sk-[A-Za-z0-9_\-]{8,}|lsv2_[A-Za-z0-9_\-]+|Bearer\s+[A-Za-z0-9._~+/=\-]+"
    r"|ghp_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{20,}"
)
_MAX_FIELD = 200  # maximum size of a written input or error excerpt


def redact(text: str) -> str:
    """Replaces anything that looks like a key with `[REDACTED]`."""
    return _SECRET.sub("[REDACTED]", text)


def _snippet(value: Any) -> str:
    """Short, filtered text of a value: filter first, then cut, so no half key is left."""
    return redact(str(value))[:_MAX_FIELD]


class JsonlCallbackHandler(BaseCallbackHandler):
    """Writes one JSON object per line for each LLM, tool and chain event."""

    def __init__(self, sink: TextIO | Path) -> None:
        self._path: Path | None = None
        self._stream: TextIO | None = None
        if isinstance(sink, Path):
            self._path = sink
            sink.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._stream = sink
        self._lock = threading.Lock()
        self._started: dict[UUID, float] = {}

    # --- writing ---

    def _emit(self, event: str, run_id: UUID, parent_run_id: UUID | None, **fields: Any) -> None:
        row: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event": event,
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            **fields,
        }
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with self._lock:
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            elif self._stream is not None:
                self._stream.write(line)
                self._stream.flush()

    def _begin(self, run_id: UUID) -> None:
        self._started[run_id] = time.monotonic()

    def _duration_ms(self, run_id: UUID) -> float:
        started = self._started.pop(run_id, None)
        return round((time.monotonic() - started) * 1000, 3) if started is not None else 0.0

    # --- model ---

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin(run_id)
        flat = [m for batch in messages for m in batch]
        chars = sum(len(str(getattr(m, "content", m))) for m in flat)
        self._emit(
            "llm_start",
            run_id,
            parent_run_id,
            name=_name(serialized, kwargs),
            message_count=len(flat),
            prompt_chars=chars,
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin(run_id)
        self._emit(
            "llm_start",
            run_id,
            parent_run_id,
            name=_name(serialized, kwargs),
            message_count=len(prompts),
            prompt_chars=sum(len(p) for p in prompts),
        )

    def on_llm_end(self, response: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        generations = [g for batch in response.generations for g in batch]
        chars = sum(len(g.text) for g in generations)
        self._emit(
            "llm_end", run_id, parent_run_id, status="ok", output_chars=chars, duration_ms=self._duration_ms(run_id)
        )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._error("llm_error", error, run_id, parent_run_id)

    # --- tool ---

    def on_tool_start(
        self,
        serialized: dict[str, Any] | None,
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin(run_id)
        self._emit(
            "tool_start",
            run_id,
            parent_run_id,
            name=_name(serialized, kwargs),
            input=_snippet(input_str),
            input_chars=len(input_str),
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        self._emit(
            "tool_end",
            run_id,
            parent_run_id,
            status="ok",
            output_chars=len(str(getattr(output, "content", output))),
            duration_ms=self._duration_ms(run_id),
        )

    def on_tool_error(
        self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._error("tool_error", error, run_id, parent_run_id)

    # --- chain ---

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._begin(run_id)
        keys = sorted(inputs) if isinstance(inputs, dict) else []
        self._emit("chain_start", run_id, parent_run_id, name=_name(serialized, kwargs), input_keys=keys)

    def on_chain_end(self, outputs: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        keys = sorted(outputs) if isinstance(outputs, dict) else []
        self._emit(
            "chain_end", run_id, parent_run_id, status="ok", output_keys=keys, duration_ms=self._duration_ms(run_id)
        )

    def on_chain_error(
        self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        self._error("chain_error", error, run_id, parent_run_id)

    # --- erro ---

    def _error(self, event: str, error: BaseException, run_id: UUID, parent_run_id: UUID | None) -> None:
        self._emit(
            event,
            run_id,
            parent_run_id,
            status="error",
            error_type=type(error).__name__,
            error=_snippet(error),
            duration_ms=self._duration_ms(run_id),
        )


def _name(serialized: dict[str, Any] | None, kwargs: dict[str, Any]) -> str:
    # `name` comes from the runnable; `serialized` may be None in newer versions.
    if kwargs.get("name"):
        return str(kwargs["name"])
    if serialized:
        return str(serialized.get("name") or (serialized.get("id") or ["?"])[-1])
    return "?"
