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
configuration when the context does not declare another one. The label does not depend on who calls, and a declaration
is trusted in one direction only: a live machine may declare the deterministic sandbox, because the sandbox is the safe
label, but a machine that is offline runs the scripted model and the recorded exchange rate, so a `live_agent`
declaration cannot be true there and it is held down to the deterministic sandbox.

The `session_id` lands in a path, and a filesystem may ignore the case of a name. The folder is therefore named after
the canonical form of the identifier, which keeps `Visitor-A` and `visitor-a` apart on every filesystem: two visitors
never share the folder of the case memory, and one visitor never reads what another wrote.

ADR-015 declared that the pattern of an identifier refuses the escape marker of the canonical form. ADR-030 amends
that: the context accepts the canonical form of an identifier as well, because the owner of a branch is stored in
that form and the context of a branch is built from it. The invariant is about the session and not about the string:
two identifiers that are different as declared identifiers never name the same folder, because the canonical form is
injective over the declared alphabet, and the canonical form of an identifier names the folder of that same
identifier and not the folder of another one. A string that is the canonical form of an identifier is the same
session as that identifier, and that is why the two of them name the same folder.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ledgerlens.config import get_settings, offline
from ledgerlens.observability.trace_event import TraceEventStream, TraceMode, TraceSink, default_mode

log = logging.getLogger(__name__)

# The prompt and policy versions go into the trace, so it is possible to say which version produced an answer.
PROMPT_VERSION = "integrator-v1"
POLICY_VERSION = "policies-v1"
TRACE_SCHEMA_VERSION = "1"

# The session id lands in a path, so it has to look like an identifier and nothing else. Anything with a separator or a
# dot segment is refused, because the id may come from a visitor in the phase R2.
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# The canonical form of an identifier is written with this marker, and the marker is not part of the identifier
# pattern, so it cannot be confused with a character of the identifier itself.
CANONICAL_ESCAPE = "%"

# The canonical form of an identifier is accepted as well, because the owner of a branch is stored in that form
# (ADR-030). The pattern is the exact image of the canonical function over the declared alphabet: a lowercase
# letter, a digit, `_` and `-` stay as they are, an uppercase letter becomes the marker and the two hexadecimal
# digits of its lowercase letter (`%61` to `%7a`), and a dot becomes `%2e`. Nothing else is ever escaped, so nothing
# else may appear in a canonical form, and an escape that the function never produces is refused.
#
# The declared identifier begins with a letter or a digit, so the canonical form begins with one too, and the declared
# identifier holds at most 64 characters while an escaped character takes three of them. The canonical form therefore
# holds at most 64 units and 192 characters, and the pattern refuses everything longer: a name of more than 255
# bytes cannot be created on the disk, and a folder of a session has to exist.
CANONICAL_SESSION_ID_PATTERN = re.compile(
    r"^(?:[a-z0-9]|%6[1-9a-f]|%7[0-9a])(?:[a-z0-9_-]|%6[1-9a-f]|%7[0-9a]|%2e){0,63}$"
)


def canonical_session_id(session_id: str) -> str:
    """The canonical form of a session id: the name of the folder that holds its case memory.

    Why it exists: the identifier lands in a path, and a filesystem may ignore the case of a name. On such a
    filesystem `Visitor-A` and `visitor-a` are one folder, and one visitor reads what another wrote. The canonical
    form keeps them apart: every uppercase letter becomes the marker followed by the code of its lowercase letter,
    and the marker is not allowed in an identifier, so the form is unique and can be read back. The result holds
    only lowercase letters, digits, `_`, `-` and the marker, so two different canonical forms are two different
    folders on a filesystem that ignores the case as well.

    The same identifier always gives the same canonical form, and two different identifiers never give the same one.
    """
    parts = []
    for char in session_id:
        if char.isupper():
            parts.append(f"{CANONICAL_ESCAPE}{ord(char.lower()):02x}")
        elif char == ".":
            # A dot is written too, because a filesystem may read a name that ends with a dot as the name without it.
            parts.append(f"{CANONICAL_ESCAPE}2e")
        else:
            parts.append(char)
    return "".join(parts)


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
    inside the runtime folder of the configuration, which already separates one visitor from the other. The session
    folder is named after the canonical form of the session id, so two identifiers that differ only in the case do not
    land in the same folder.

    `mode` is what the caller declared; `resolved_mode()` is the mode of the execution, and it is the one that
    travels with the trace.
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

        The session id is accepted in the declared form and in the canonical form, because the owner of a branch is
        stored in the canonical form and the context of a branch has to be built from it (ADR-030).
        """
        if self.mode is not None and self.mode not in {"recorded_replay", "deterministic_sandbox", "live_agent"}:
            raise ValueError(f"invalid mode: {self.mode!r}")
        if not (SESSION_ID_PATTERN.match(self.session_id) or CANONICAL_SESSION_ID_PATTERN.match(self.session_id)):
            raise ValueError(f"invalid session_id: {self.session_id!r}")

    @property
    def canonical_session_id(self) -> str:
        """The canonical form of the session id, the one that names the memory folder.

        The declared id stays in `session_id`, because that is what the caller and the visitor know. The canonical
        form is the storage detail, and it is what keeps two identifiers apart on a filesystem that ignores the case.
        """
        return canonical_session_id(self.session_id)

    def resolved_mode(self) -> TraceMode:
        """The mode of the execution: the declared one, held down by what the process configuration is doing.

        A declaration is trusted in one direction only. A live machine may declare the deterministic sandbox, because
        the sandbox is the safe label. An offline machine runs the scripted model and the recorded exchange rate, so
        a `live_agent` declaration cannot be true there: it is held down to `deterministic_sandbox` and the log says
        so. The resolved mode is never `live_agent` while the configuration is offline. A declared `recorded_replay`
        keeps its label in both directions, because a replay is a replay.
        """
        declared = self.mode
        if declared is None:
            return default_mode()
        if declared == "live_agent" and offline():
            log.warning(
                "run %s declared the live mode while the product is offline; "
                "the mode is held down to the deterministic sandbox",
                self.run_id,
            )
            return "deterministic_sandbox"
        return declared

    def resolve_memory_dir(self, runtime_dir: Path | None = None) -> Path:
        """The memory folder of this execution: the one of the context, or the session one inside the runtime folder.

        The folder is named after the canonical form of the session id, so two identifiers that differ only in the
        case never share it, on a filesystem that ignores the case as well.
        """
        if self.memory_dir is not None:
            return Path(self.memory_dir)
        base = Path(runtime_dir) if runtime_dir is not None else get_settings().runtime_dir
        return base / "sessions" / self.canonical_session_id

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

        The session id is reported as it was declared, not as its canonical form: the declared id is what the caller
        and the visitor know, and the canonical form is an internal detail of the folder that holds the memory.

        The revision of the branch travels with the identity as the decimal text of the integer, because the identity
        is a map of texts and the interface never reads a number (FR-042).
        """
        identity = {"run_id": self.run_id, "session_id": self.session_id}
        for name in ("account_id", "branch_id", "branch_revision", "snapshot_sha256", "model_profile_id"):
            value = getattr(self, name)
            if value is not None:
                identity[name] = str(value)
        return identity
