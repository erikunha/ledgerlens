"""The cancellation of a run: no tool starts after the barrier, and the incomplete claims are marked.

What they guarantee, and why: (a) a cancelled run starts no tool after the barrier of the cancellation,
because a tool that starts after the cancellation spends the money of a visitor who already said stop; (b) the
spans of the run are closed and the claims that were not verified are marked as incomplete, because a run that
was cancelled in the middle did part of the work, and a reader has to see which claims were verified.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.durability.cancellation import CancellationBarrier, CancelledRun, incomplete_claims


def test_no_tool_starts_after_the_cancellation() -> None:
    """The barrier stops the tool that tries to start after the cancellation."""
    barrier = CancellationBarrier()
    barrier.start_tool("query_ledger")
    barrier.cancel()

    with pytest.raises(CancelledRun, match="does not start after the barrier"):
        barrier.start_tool("calculate")

    assert barrier.started_tools == ["query_ledger"]


def test_the_spans_are_closed_and_the_incomplete_claims_are_marked() -> None:
    """The run closes its spans, and the claims that were not verified are marked as incomplete."""
    barrier = CancellationBarrier()
    barrier.start_tool("query_ledger")
    barrier.cancel()
    barrier.close_span("span-of-the-run")

    marked = incomplete_claims(
        claims=["the status of the refund", "the rate of the refund"],
        verified=["the status of the refund"],
    )

    assert barrier.closed_spans == ["span-of-the-run"]
    assert marked == ["the rate of the refund (incomplete: the run was cancelled before the verification)"]
