"""The case memory of a sandbox session: the folder of the session that owns the branch, and nothing else.

Why it exists: the branch layer knows the owner of a branch, and the run context already scopes the case memory of
the product to a session (ADR-015), but nothing joined the two. Without the join, a sandbox execution has no context,
so it writes in the global runtime folder of the configuration and the memory of one visitor shows up in the answer of
another one (FR-027).

The rule is in one place and it is the rule of the run context: the memory folder of a branch is the folder of the
session that owns it, `<runtime_dir>/sessions/<canonical session id>`, and the global runtime folder is never the
memory of a sandbox session. This module asks the run context for the folder instead of recomputing it, so the rule of
the sandbox and the rule of the context cannot drift.

The module holds the scope and nothing else. The module itself imports neither the FAISS stack of the case memory nor
the branch module at runtime, so the rule can be read, and tested, without the stack of the memory. The package of
the sandbox does import the branch module, and that is a property of the package and not of this module.

What is allowed and what is not: the memory of a branch goes in the folder of the session of the branch, and the
global runtime folder of the configuration is never that folder. The memory of a session dies with the session, so
the purge removes the folder of the session and never anything that is not exactly that folder inside the folder of
the sessions.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from ledgerlens.run_context import RunContext, canonical_session_id

if TYPE_CHECKING:  # pragma: no cover - the type is only needed to read the module.
    from ledgerlens.sandbox.branch import SandboxBranch

log = logging.getLogger(__name__)

# The run identifier of the context that only asks for a folder. The folder does not depend on the run, and a name
# that says what the context is for is better than one that says nothing.
SCOPE_RUN_ID = "session-memory-scope"


def session_memory_dir(session_id: str, runtime_dir: Path | str | None = None) -> Path:
    """The folder of the case memory of a session: the session one, inside the runtime folder.

    Why the question is asked to the run context and not answered here: the context owns the rule of the folder, and
    the sandbox asks for it. Two rules would drift, and the drift would show up as the memory of one visitor in the
    answer of another one.

    The session id is accepted in the declared form and in the canonical form, because the owner of a branch is
    stored in the canonical form (ADR-030).
    """
    context = RunContext(run_id=SCOPE_RUN_ID, session_id=session_id)
    return context.resolve_memory_dir(Path(runtime_dir) if runtime_dir is not None else None)


def branch_run_context(
    branch: SandboxBranch,
    *,
    run_id: str | None = None,
    runtime_dir: Path | str | None = None,
) -> RunContext:
    """The context of an execution that runs inside a branch.

    The session of the context is the owner of the branch, in the canonical form, because that is the form the branch
    stores and the form that names the folder of the memory. The branch id, the revision and the canonical hash of
    the base travel with it, so every trace and every answer says which branch it was (FR-042).

    The run identifier is the one of the branch when the caller gives none, because the branch is the scope of the
    execution. A caller that runs several executions inside the same branch gives its own identifier.
    """
    owner = branch.owner_session
    return RunContext(
        run_id=run_id or f"run-{branch.branch_id}",
        session_id=owner,
        branch_id=branch.branch_id,
        branch_revision=branch.revision,
        snapshot_sha256=branch.base_canonical_hash,
        memory_dir=session_memory_dir(owner, runtime_dir),
    )


def purge_session_memory(session_id: str, runtime_dir: Path | str | None = None) -> bool:
    """Removes the folder of the case memory of a session, and says whether it removed something.

    The removal is bounded: the folder is computed, resolved, and compared with the folder of the sessions before
    anything is deleted, so the purge never removes a folder that is not exactly the one of that session.

    The purge is tolerant on purpose. A session that never wrote anything has no folder, and that is not an error. A
    folder that cannot be removed is logged and reported as not removed, because the end of a session must never fail
    over a folder of the disk (ADR-030).
    """
    try:
        folder = session_memory_dir(session_id, runtime_dir)
    except ValueError as error:
        log.warning("the memory of the session was not purged: %s", error)
        return False

    owner = canonical_session_id(session_id)
    sessions = folder.parent
    try:
        resolved = folder.resolve()
        parent = sessions.resolve()
    except OSError as error:  # pragma: no cover - the path of a folder that cannot even be resolved.
        log.warning("the memory folder of the session %s could not be read: %s", owner, error)
        return False

    if resolved.parent != parent or resolved.name != owner:
        log.warning("the memory folder of the session %s is not the folder of the session; nothing was removed", owner)
        return False

    if not resolved.exists():
        return False

    try:
        shutil.rmtree(resolved)
    except OSError as error:
        log.warning("the memory folder of the session %s could not be removed: %s", owner, error)
        return False
    return True


__all__ = [
    "SCOPE_RUN_ID",
    "branch_run_context",
    "purge_session_memory",
    "session_memory_dir",
]
