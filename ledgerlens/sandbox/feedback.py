"""The feedback of a visitor: it stays in the session of the visitor, and the shared set never sees it.

Why the feedback of a visitor is sandbox only: ADR-P009 is a safety invariant and not a preference, and a
visitor that could write into the shared set of the repository could poison the records the maintainers
review. The comment of a visitor is written under the runtime of the sandbox, keyed by the session of the
visitor, and nothing of it is written under `data/eval/feedback/`, which is the door of the shared set.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["FEEDBACK_DIR", "record_visitor_feedback"]

# The runtime of the sandbox of the visitors, never the shared set of the repository.
FEEDBACK_DIR = Path("data/runtime/sandbox/feedback")


def record_visitor_feedback(session_id: str, comment: str, *, root: Path | None = None) -> Path:
    """The comment of a visitor, appended to the feedback of the session of the visitor.

    The session identifier names the file, so the feedback of one visitor is never mixed with the feedback of
    another, and the root of the runtime is an argument so that the test can point it at a temporary disk.
    """
    if not session_id.strip() or "/" in session_id or "\\" in session_id:
        raise ValueError(f"the session id {session_id!r} is not a session id")
    if not comment.strip():
        raise ValueError("the comment is empty")
    base = (root if root is not None else Path.cwd()) / FEEDBACK_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{session_id}.jsonl"
    line = json.dumps({"at": datetime.now(UTC).isoformat(), "comment": comment}, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return path
