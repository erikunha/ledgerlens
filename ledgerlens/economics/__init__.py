"""The economics of a run: the money of a case, the utility of a decision and the assumptions they rest on.

Why it exists: the repository knows what a single live run cost, because the coordinator of the budget counts the
calls of every model and the registry carries the price of each model with the source that publishes it and the day
it was last verified. That is the cost of one run. What the repository had no answer for is the cost of a cohort,
the cost per case that was actually resolved, and the loss a policy carries when it is wrong. This package is that
answer, and it is a leaf of the domain: it reads the results of the runs that already happened and it never calls a
model.

Why the numbers the repository cannot measure live here and not in the code: the minutes a review takes, the rate of
an hour and the price snapshot are assumptions of the reader, not facts of the repository. A number that the code
decided cannot be questioned by the person who reads the result, so every assumption is a field of this package and
every result that uses one carries it.

Why an unknown is never a zero: a price that was never verified leaves a money unmeasured, and a probability that
was never calibrated leaves an expected loss unknown. A zero would say that the call was free and that the error
never happened, and both are lies. The names of the unknowns are published with the results.
"""

from __future__ import annotations

__all__ = ["Assumptions", "PriceSnapshot", "ReviewAssumption", "UNKNOWN_SOURCE"]
