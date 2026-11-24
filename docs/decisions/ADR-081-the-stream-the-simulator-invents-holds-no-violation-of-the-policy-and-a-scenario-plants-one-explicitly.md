---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-081: The stream the simulator invents holds no violation of the policy, and a scenario plants one explicitly

Status: accepted. Date: 2026-11-24.

## Context

The policy of the cross-currency refunds says how much a merchant may apply over the reference rate of the day of the
refund: a merchant on the markup plan may apply up to 3.0 percent, and a merchant on the standard plan applies none
(`ledgerlens/policy_limits.py`). The rule that sends a case like that to a person lives in the code
(`ledgerlens/verify/escalation.py`), and ADR-074 says the decision belongs to the code and not to the answer of the
model.

The stream of the simulator, the one that invents the rows that no public source has, never went over that limit:
`ledgerlens/sim/gaps.py` refused a markup over the ceiling, and the refund of the natural stream carried the rate of
the reference of the day times one minus a markup that was inside the limit. That refusal was right: a ledger the
simulator invents holds no violation of the policy, and the rows of the natural stream are not the case of anybody.

The consequence was that no ledger could carry a violation, and the case that catches one could not be built. The
scenario S01 proves the opposite side of the same rule: a markup of 2.50 percent on a merchant of the markup plan is
the contracted one, the difference is the markup of the plan and not an error, and the case ends with an explanation.
The product had no case where the same markup is over the limit, and the rule of the escalation had no ledger to fire
on. The scenario S13 is that case: the refund of the merchant M-19, on the markup plan, applies 4.50 percent over the
reference rate of the day of the refund, the plan allows 3.0, and the case goes to a person.

Three ways were open to the repository, and the one that was refused is the one that would have changed what the
natural rows mean:

- **To let the natural stream go over the ceiling from time to time.** Refused. Then the rows the simulator invents
  would carry violations that no scenario planted, and the reader of the manifest could not tell which refund is the
  case and which is the noise. The manifest is the list of the cases, and the list has to be complete.
- **To write the rate of the scenario by hand, as a literal in the builder.** Refused. The rate of a scenario comes from
  the same formula as every other rate of the repository, with the reference of the day of the series, and a literal
  would be a number that no other code can reproduce.
- **To lift the ceiling for the one call that plants the violation.** Accepted.

## Decision

**The stream the simulator invents holds no violation of the policy. A scenario that needs one plants it, and it says
so by lifting the ceiling of the one call that builds it.**

1. **The natural stream keeps the ceiling.** `refund_applied_rate` refuses a markup over the limit, as it did before,
   and the refund of the natural stream carries a rate inside the limit.
2. **The scenario lifts it explicitly.** `refund_applied_rate` and `cross_currency_refund` take a `policy_ceiling`, and
   the scenario S13 passes `policy_ceiling=None` at the call that builds its refund. The opt-out is a name at the call
   site, not a flag on the simulator and not a value in the manifest.
3. **The ceiling is not written by the simulator.** The number comes from `ledgerlens/sim/gaps.py`, the same limit the
   simulator uses everywhere else, and the simulator does not import the policy of the product. The limit of the product
   is in `ledgerlens/policy_limits.py`, and it is the one the calculator states and the one the escalation rule
   compares against.
4. **The truth of the scenario says it.** The manifest of the scenario S13 declares `within_limit: no`, the markup of
   4.5003 percent, the limit of 3.0 and the escalation of the case, so a reader of the manifest sees the violation
   before the ledger does.

Why the merchant is not a new one: a merchant that goes over the limit on one refund is a fact of the ledger, and not
a new kind of merchant. The plan of M-19 was already in the catalogue, and the case of the scenario S12, which finds a
markup of about 2.5 percent on M-17, would contradict a claim about M-17 that the case does not make.

## Alternatives considered

- **To change the limit of the policy so that a natural refund goes over it.** Refused. The limit is the policy, and
  the policy is not a parameter of the simulator.
- **To plant the violation in the builder of the scenario without the formula.** Refused, and the refusal is the whole
  of this decision: a rate written by hand is a rate nobody can reproduce from the series of the reference source.
- **To add a merchant to the catalogue for the scenario.** Refused. The merchants are fixed, and the plan of a
  merchant is a fact of the ledger, not a kind of merchant.
- **To let any caller of the gap filler lift the ceiling.** Refused. The opt-out is named at the call site of the
  scenario, so the places that may plant a violation are the places that say they plant one.

## Consequences

- **The ledger of the scenario S13 carries a violation of the policy**, the refund of 431.54 BRL against a payment of
  453.06 BRL, with a markup of 4.5003 percent against the 3.0 percent of the plan, and the rule of the escalation of
  the product fires on it and names the policy of the limit.
- **The natural stream is unchanged**, and the tests that ask for a markup over the ceiling still refuse it.
- **A scenario that plants a violation says so in its truth**, and the evaluation answers the question of the case with
  the numbers of the truth and not with a guess.
- **The recordings of the catalogue carry the case**, in the sandbox catalogue and in the catalogue of a real model,
  and the reader of the bundle finds the reason of the escalation in the published evidence.

## Links

- [ADR-009, public data first, simulation only for the gaps](ADR-009-public-data-first-simulation-for-gaps.md)
- [ADR-074, a case ends in a decision, and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [the gap filler of the simulator](../../ledgerlens/sim/gaps.py)
- [the rule of the markup of the escalation](../../ledgerlens/verify/escalation.py)
