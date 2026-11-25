"""The review of a case by a person: the task, the evidence it carries and the state machine that moves it.

Why it exists: the repository decides that a case goes to a person and stops there. The decision is the part that a
person takes, and it is the part that a case cannot close without. This package holds the typed task, the table of
the transitions and the checks that run before a decision moves it.

Why the agent prepares the evidence and never decides: the evidence of a case is read by a person, and a decision
that came out of the text of a tool would be a decision that anybody could write into a tool.

Why the package imports no API and no payment client: the red line of the repository is that no real money moves. An
approval of a review applies to a branch of the sandbox and never to a live payment.
"""

from __future__ import annotations

__all__ = ["ReviewEvent", "ReviewTask", "evidence_hash", "new_task"]
