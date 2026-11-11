"""The context of an execution: what it is, where it comes from and what it may spend.

Why it exists: today the product keeps the state of an execution in places that hold for the whole machine: the runtime
folder of the configuration, the Streamlit session dictionary, the global ledger. With one execution that does not
show. With several visitors at the same time, the same place becomes shared state: the case memory of one visitor
shows up in the answer of another, and the trace does not say whose execution it was.

The `RunContext` is the identity and the scope of an execution, in a frozen object that is passed along: who runs,
who writes the trace, who decides the memory path. It replaces the global state without breaking what exists: the case
memory becomes the session one when there is a context, and stays the global folder when there is none.

What it carries today is what the repository can genuinely fill: the execution and session identifiers, the account,
the mode, the snapshot hash and the memory folder. The fields the design package asks for in later phases have a place,
but they are optional: `branch_id` and `branch_revision` only exist when the phase R2 sandbox exists, and the `budget`
only becomes a ceiling when the provider price is known.

The `mode` is what separates a real execution, the deterministic sandbox and a replay, and it comes from the process
configuration when the context does not declare another one. The label does not depend on who calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ledgerlens.config import get_settings
from ledgerlens.observability.trace_event import TraceEventStream, TraceMode, TraceSink, default_mode

# The prompt and policy versions go into the trace, so it is possible to say which version produced an answer.
PROMPT_VERSION = "integrator-v1"
POLICY_VERSION = "policies-v1"
TRACE_SCHEMA_VERSION = "1"

# The session id lands in a path, so it has to look like an identifier and nothing else. Anything with a separator or a
# dot segment is refused, because the id may come from a visitor in the phase R2.
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class RunBudget:
    """The ceiling of an execution. What is not given is not a limit.

    The model price is not always known. When it is not, the money limit stays off and the call, token and time limits
    hold the execution. That is declared, not hidden.
    """

    max_model_calls: int | None = None
    max_tool_calls: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_estimated_usd: Decimal | None = None
    max_wall_seconds: float | None = None
    max_sql_rows: int | None = None
    max_sql_seconds: float | None = None
    max_memory_items: int | None = None


@dataclass(frozen=True)
class RunContext:
    """The identity and the scope of an execution, without global state.

    `memory_dir` is the folder where the case memory of this execution writes. Without it, the folder is the session one
    inside the runtime folder of the configuration, which already separates one visitor from the other.
    """

    run_id: str
    session_id: str
    mode: TraceMode | None = None
    account_id: str | None = None
    branch_id: str | None = None
    branch_revision: int | None = None
    snapshot_sha256: str | None = None
    model_profile_id: str | None = None
    prompt_version: str = PROMPT_VERSION
    policy_version: str = POLICY_VERSION
    trace_schema_version: str = TRACE_SCHEMA_VERSION
    budget: RunBudget = field(default_factory=RunBudget)
    deadline_at: datetime | None = None
    memory_dir: Path | None = None

    def __post_init__(self) -> None:
        """Refuses what the contract refuses, so the identity cannot be wrong by accident.

        The mode is part of the public contract, and the session id becomes a path segment. Both are checked here
        because a frozen dataclass does not validate types by itself.
        """
        if self.mode is not None and self.mode not in {"recorded_replay", "deterministic_sandbox", "live_agent"}:
            raise ValueError(f"invalid mode: {self.mode!r}")
        if not SESSION_ID_PATTERN.match(self.session_id):
            raise ValueError(f"invalid session_id: {self.session_id!r}")

    def resolved_mode(self) -> TraceMode:
        """The mode of the execution: the one declared in the context or the one the process configuration is doing."""
        return self.mode or default_mode()

    def resolve_memory_dir(self, runtime_dir: Path | None = None) -> Path:
        """The memory folder of this execution: the one of the context, or the session one inside the runtime folder."""
        if self.memory_dir is not None:
            return Path(self.memory_dir)
        base = Path(runtime_dir) if runtime_dir is not None else get_settings().runtime_dir
        return base / "sessions" / self.session_id

    def trace_stream(self, sink: TraceSink) -> TraceEventStream:
        """The trace coordinator of this execution, with the mode and the snapshot of the context."""
        return TraceEventStream(
            self.run_id,
            sink,
            mode=self.resolved_mode(),
            snapshot_sha256=self.snapshot_sha256,
        )

    def identity(self) -> dict[str, str]:
        """The identity of the execution, the part that travels with the trace and the result.

        It is here so that the core can carry the identity without holding the whole context, and so that a caller can
        read what the execution was without reaching into private fields.
        """
        identity = {"run_id": self.run_id, "session_id": self.session_id}
        for name in ("account_id", "branch_id", "snapshot_sha256", "model_profile_id"):
            value = getattr(self, name)
            if value is not None:
                identity[name] = str(value)
        return identity
