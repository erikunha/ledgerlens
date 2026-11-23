---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-074: A case ends in a decision, and the decision belongs to the code

Status: accepted. Date: 2026-11-24.

## Context

The published scenario S01 is the first case a visitor meets, and it read like an arithmetic exercise. The trace of
the recording holds 57 events, four calls of tools and three claims, and the answer was this: the payment came to
BRL 566.79, the refund to BRL 549.31, the difference of BRL 17.48 is BRL 3.40 of movement of the reference rate and
BRL 14.08 of markup, and the reference rate on 2026-10-20 was 5.6339. Every number of it was right and every number
of it was already in the evidence.

What the answer did not say is the thing a complaint is about. It never named the merchant, never named the plan of
the merchant, never named the limit that the policy gives to that plan (3.0% over the reference rate), never said
what the customer would have received at the reference rate of the refund day, and never said whether the refund was
correct. The escalation of the run was empty and the recommended action was `explain_to_customer`: the case was
explained and not decided. A reader could not tell whether the customer was owed money, and the case of the flagship
of the catalogue was a description of a difference.

The policy already says how the case ends. `data/policies/cross-currency-refunds.md` says that the difference has
two parts and that the calculation is done with the calculation tool, that a merchant on the `markup` plan may
apply up to 3.0% over the reference rate, that a markup above the limit goes to human review, and that a merchant on
the `standard` plan applies no markup at all. The policy had the rule and the code had no rule: nothing in the
product compared the markup a merchant applied with the limit of its plan, and the escalation of a breach would
have been empty.

## Decision

**A case ends in a decision, and the numbers of the decision come from the code.**

Three parts, each in the layer that owns it:

1. **The calculator states the decision it has.** The new operation `fx_markup_check` is the decomposition of the
   difference of a cross-currency refund with the limit that the plan of the merchant allows, whether the markup
   applied is within that limit and the amount the refund would have been at the reference rate of the refund day.
   The plan of the merchant is not a number and does not go into `values`: it is the argument `plan`, which the
   model reads from the ledger and states, and the operation refuses to run without it (`MISSING_PLAN`).
2. **The limits are numbers of the policy, not values the model sends.** They live in `ledgerlens/policy_limits.py`,
   a leaf module that both the calculator and the escalation rule read, and each of them names the section of the
   policy it comes from.
3. **The escalation rule decides the breach on its own.** `ledgerlens/verify/escalation.py` reads the applied rate
   and the plan of the merchant from the ledger, not from the rows the model chose, reads the reference rate from
   the trace, and sends the case to a person when the markup is above the limit of the plan or when a merchant on
   the standard plan applies a markup at all. The reason names the policy section that decided.

The flagship case was rewritten to the decision: it reads the plan of the merchant from the ledger, states the
markup, the limit and the amount at the reference rate, and ends with the conclusion that the difference is the
markup of the plan and not an error.

## Alternatives considered

- **To leave the decision to the prose of the model.** Refused. A model that writes "the markup is within the limit"
  without naming the limit is a claim nobody can check, and the case that ends in a decision has to be one that the
  code can redo.
- **To put the limits of the plans in the thresholds of the verifier.** Refused. The thresholds of
  `ledgerlens/verify/thresholds.json` are the calibration of the verifier; these numbers are the policy, and the
  calculator needs them too. A leaf module serves both without a layer that depends on another.
- **To take the plan of the merchant as one of the values of the calculation.** Refused. The values of `calculate`
  are decimal strings by contract, and the plan is a fact of the ledger and not a number: it has its own argument,
  and the tool states where it comes from.
- **To read the ledger twice, once for the rates and once for the merchant, and to move the ground truth of the
  tools of the scenario.** Refused for this change. One read brings the rates and the plan of the merchant, and the
  declared tools of the scenario do not move; a change of the dataset moves the digest of the published dataset and
  belongs to a change of the scenario and not to a change of the answer.
- **To publish a new scenario in which the markup is above the limit.** Deferred, and it is not a debt. The rule is
  proven by the tests of the escalation, and a new scenario needs the ledger and the dataset rebuilt, which is a
  change of its own. The limitation it would have to solve is written down here: the rule reads the ledger, so a
  bundle re-verified without the ledger reproduces the labels of the claims and not the reasons of the escalation.

## Consequences

- **The published S01 changes**: the answer names the merchant, the plan, the limit and the amount at the reference
  rate, and it ends with the conclusion. The bundle is recaptured and the site is reexported.
- **The verdict of the claims of the S01 stays `supported`**, and now every claim of the answer carries the numbers
  that the calculation produced, so the decision of the case is as checkable as the arithmetic of it was.
- **A merchant on the standard plan that applies a markup goes to a person**, whatever the model writes, and the
  reason names the rule that decided it.
- **The tool has a new operation and a new argument**, so the contract of the tools (`docs/contracts/tools.md`) and
  the catalogue of the tools (`docs/tools.md`) were updated with it.
- **The plan the model states is not trusted by the rule**: the escalation rule reads the plan of the merchant from
  the ledger, so a model that states the wrong plan cannot hide a breach.

## Links

- [ADR-068, the published catalogue holds the failures and not only the cases the agent resolves](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
- [ADR-072, a currency the reference source does not publish is missing data and the case goes to a person](ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md)
- [the rules of the escalation](../../ledgerlens/verify/escalation.py)
- [the numbers of the policy](../../ledgerlens/policy_limits.py)
- [the calculator](../../ledgerlens/tools/calculator.py)
- [the policy of the refunds in another currency](../../data/policies/cross-currency-refunds.md)
