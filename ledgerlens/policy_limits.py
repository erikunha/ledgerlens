"""The numbers the policies write down, in code, so that no model decides them.

Why they live here and not in `ledgerlens/verify/thresholds.json`: the thresholds of the verifier are a property of
the verifier (the calibration of the NLI model, the deadline of a dispute, the amount above which a case goes to a
person). These are the numbers of the policies, and two layers need them: the calculator, which states the limit of
a plan next to the markup it computes, and the escalation rule, which compares the markup a merchant applied with
the limit of its plan. A leaf module with no import of the project is the one place both can read.

Every limit names the section of the policy it comes from, so that a reason which fires can point at the rule that
decided it, and not only at the number.

The policy in prose is `data/policies/cross-currency-refunds.md`: a merchant on the `markup` plan may apply up to
3.0% over the reference rate, a markup above the limit goes to human review, a merchant on the `standard` plan
applies no markup at all, and the applied rate is rounded to four decimal places.
"""

from __future__ import annotations

from decimal import Decimal

__all__ = [
    "FX_MARKUP_LIMIT_PCT",
    "FX_MARKUP_LIMIT_POLICY",
    "FX_MARKUP_TOLERANCE_PCT",
    "FX_STANDARD_PLAN_POLICY",
]

# The limit of the markup plan: the highest markup a merchant may apply over the reference rate of the refund day.
FX_MARKUP_LIMIT_PCT = Decimal("3.0")
FX_MARKUP_LIMIT_POLICY = "cross-currency-refunds#merchant-fx-markup"

# The difference under which nothing is a markup: the applied rate is rounded to four decimal places, so a rate that
# is the reference rate can differ from it by the rounding and nothing else.
FX_MARKUP_TOLERANCE_PCT = Decimal("0.01")
FX_STANDARD_PLAN_POLICY = "cross-currency-refunds#standard-plan"
