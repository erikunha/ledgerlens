"""The join of the results of the steps: on a matching snapshot and on evidence that resolves to a record of the run.

Why the arithmetic decides and never the vote: two specialists that disagree over an amount are two readings of the
same row, and the calculator recomputes it. Money is never decided by a model (FR-006).

Why the join refuses an evidence identifier that resolves to no record of the run: an identifier that a result
invented is a claim about a row that nobody read, and a join that accepted it would publish a number about a row
that does not exist.

Why the join refuses a result of another snapshot: two results of two snapshots are two results of two questions,
and the join of them is a join of nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.schemas import StepResult

__all__ = ["JoinOutcome", "JoinRefused", "join_results"]

# The recomputation of an amount: the deterministic calculator of the repository receives the row and returns the
# amount, or None when it cannot decide. It is a callable and not the tool itself, because the join must not call a
# tool on its own and because the test needs a calculator it can trust.
Recompute = Callable[[str], Decimal | None]


class JoinRefused(Exception):
    """The join of the results is refused, and the message says why."""


@dataclass(frozen=True)
class JoinOutcome:
    """The joined results: the amount of every row, the rows that were contested and the reason of the refusal.

    Why the contested rows are named and not dropped: a row that two specialists read differently and that the
    calculator could not settle is a row the reader has to see, because it is a row the run does not know.
    """

    amounts: Mapping[str, Decimal]
    contested: tuple[str, ...]
    results: tuple[StepResult, ...]
    error: str | None = None

    @property
    def abstained(self) -> bool:
        """Whether the join abstained over at least one row."""
        return bool(self.contested)


def join_results(
    results: Sequence[StepResult],
    *,
    snapshot: str,
    records: Sequence[str],
    recompute: Recompute,
    result_snapshots: Mapping[str, str] | None = None,
) -> JoinOutcome:
    """The join of the results of the steps, and a refusal when the results may not be joined.

    Why the records of the run are an argument and not a read of the disk: the join knows the records that the run
    produced, and a join that read the disk would accept a record of another case.
    """
    known = set(records)
    for result in results:
        for reference in result.evidence_refs:
            if reference not in known:
                raise JoinRefused(
                    f"the step {result.step_id} cites the evidence {reference!r} and it resolves to no record "
                    "of the run"
                )
        if result_snapshots is not None:
            step_snapshot = result_snapshots.get(result.step_id)
            if step_snapshot is not None and step_snapshot != snapshot:
                raise JoinRefused(
                    f"the step {result.step_id} read the snapshot {step_snapshot} and the run reads {snapshot}"
                )

    amounts: dict[str, Decimal] = {}
    contested: list[str] = []
    for result in results:
        if result.row is None or result.amount is None:
            continue
        seen = amounts.get(result.row)
        if seen is None:
            amounts[result.row] = result.amount
            continue
        if seen == result.amount:
            continue
        # The two readings disagree, so the calculator decides. When it cannot, the row stays contested and the
        # join abstains over it: a majority of the readings is not an amount (FR-006).
        recomputed = recompute(result.row)
        if recomputed is None:
            contested.append(result.row)
            continue
        amounts[result.row] = recomputed

    return JoinOutcome(
        amounts=dict(amounts),
        contested=tuple(sorted(contested)),
        results=tuple(results),
        error=None,
    )
