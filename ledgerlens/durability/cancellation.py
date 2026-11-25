"""The cancellation of a run: a cancelled run starts no tool after the barrier, and its incomplete claims are marked.

Why the barrier exists: a run that is cancelled is a run that the visitor stopped, and a tool that starts after
the cancellation is a tool that spends the money of a visitor who already said stop. The barrier is the point
after which no tool starts, and the run closes its spans and marks the claims that were not verified as
incomplete, because a claim that was not verified is not a claim the run may publish as verified.

Why the incomplete claims are marked and not dropped: a run that was cancelled in the middle did part of the
work, and a reader of the run has to see which claims were verified and which were not, and not a run that
looks whole.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["CancelledRun", "CancellationBarrier"]


class CancelledRun(Exception):
    """A tool tried to start after the cancellation, and the barrier stopped it."""


@dataclass
class CancellationBarrier:
    """The barrier of a run: after the cancellation, no tool starts.

    Why the barrier is an object and not a flag of the run: the barrier is the one place the run asks before a
    tool starts, and a flag that every tool read for itself would be a flag that one tool could forget to read.
    """

    cancelled: bool = False
    started_tools: list[str] = field(default_factory=list)
    closed_spans: list[str] = field(default_factory=list)

    def cancel(self) -> None:
        """Marks the run as cancelled: after this, no tool starts."""
        self.cancelled = True

    def start_tool(self, tool: str) -> None:
        """The start of a tool, and the refusal of it when the run was cancelled.

        Why the refusal is an exception and not a skip: a tool that does not start because the run was
        cancelled is a fact of the run, and a skip that nobody recorded would be a tool that vanished.
        """
        if self.cancelled:
            raise CancelledRun(f"the run was cancelled, and the tool {tool} does not start after the barrier")
        self.started_tools.append(tool)

    def close_span(self, span_id: str) -> None:
        """The span of the run is closed when the run ends, cancelled or not."""
        self.closed_spans.append(span_id)


def incomplete_claims(claims: list[str], verified: list[str]) -> list[str]:
    """The claims that were not verified when the run was cancelled, marked as incomplete.

    Why the incomplete claims are computed and not written: the claims of the run are the claims of its steps,
    and the verified ones are the ones the verifier answered, and the difference is the set of the claims the
    run may not publish as verified.
    """
    done = set(verified)
    return [
        f"{claim} (incomplete: the run was cancelled before the verification)"
        for claim in claims
        if claim not in done
    ]
